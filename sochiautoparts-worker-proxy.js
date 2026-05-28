/**
 * SochiAutoParts Cloudflare Worker v13.0
 *
 * Proxies sochiautoparts.ru → GitHub Pages static site.
 * Handles regional filtering for Admitad partner programs.
 * Provides /api/shop/products and /api/ads endpoints for client-side dynamic content.
 *
 * Architecture:
 *   1. /api/go/{platform}/{id} → Product affiliate redirect (lookup by platform + product ID)
 *   2. /api/{id}               → Admitad affiliate redirect (direct lookup by program ID, no region filter)
 *   3. /api/shop/products      → Products API for shop page pagination/filtering
 *   4. /api/ads                → Region-filtered ad blocks HTML (for static pages), supports ?cat= filter
 *   5. /shop/{id}              → Proxy to GitHub Pages /shop/{id}/index.html
 *   6. /rss.xml                → serve from GitHub Pages /rss.xml
 *   7. /feed.xml               → serve from GitHub Pages /rss.xml (compat alias)
 *   8. All other requests      → proxy from GitHub Pages
 *   9. 404 from GH Pages       → try .html, then /index.html, then custom 404
 *  10. Server-Side Ads Injection → <!-- REGIONAL_ADS_PLACEHOLDER --> in HTML replaced
 *      with region-filtered ads (supports _RU / _EN suffixes for lang-specific slots)
 *
 * GitHub Pages URL: https://creastudioai-beep.github.io/sapapp/
 * Route: sochiautoparts.ru/* → creastudioai-beep.github.io/sapapp/*
 */

const GITHUB_PAGES_BASE = 'https://creastudioai-beep.github.io/sapapp';
const SITE_URL = 'https://sochiautoparts.ru';
const CHANNEL_USERNAME = 'sochiautoparts';

// Cache settings
const CACHE_TTL_BROWSER = 300;    // 5 minutes browser cache
const CACHE_TTL_EDGE = 3600;      // 1 hour edge cache

// Admitad program data — fetched from pipeline and cached
const ADMITAD_DATA_URL = 'https://raw.githubusercontent.com/creastudioai-beep/pr/main/data/admitad_ads.json';
let admitadCache = null;
let admitadCacheTime = 0;
const ADMITAD_CACHE_TTL = 3600000; // 1 hour in ms

// Admitad category names (bilingual)
const ADMITAD_CATEGORIES = {
  autoparts: { ru: 'Автозапчасти', en: 'Auto Parts' },
  autoinsurance: { ru: 'Автострахование', en: 'Car Insurance' },
  tires: { ru: 'Шины и диски', en: 'Tires & Wheels' },
  checkauto: { ru: 'Проверка авто', en: 'Car Check' },
  autorent: { ru: 'Прокат авто', en: 'Car Rental' },
  tools: { ru: 'Инструменты', en: 'Tools' },
  coupons: { ru: 'Купоны и скидки', en: 'Coupons & Deals' },
  other: { ru: 'Другое', en: 'Other' },
};

// Platform name normalisation for /api/go/{platform}/{id}
// Maps common aliases to canonical feed_name substrings
const PLATFORM_ALIASES = {
  ozon: ['ozon', 'озон'],
  wb: ['wb', 'wildberries', 'вайлдберриз'],
  lukoil: ['lukoil', 'лукойл'],
  yandex: ['yandex', 'яндекс', 'market', 'ямаркет'],
  exist: ['exist', 'экзист'],
  autodoc: ['autodoc', 'автодок'],
  zzap: ['zzap', 'ззап'],
  emex: ['emex', 'эмекс'],
  pasker: ['pasker', 'паскер'],
};

// Products data (for shop) — loaded directly from zap.online repo (always fresh)
const PRODUCTS_JSON_URL = 'https://raw.githubusercontent.com/creastudioai-beep/zap.online/main/products.json';
const PRODUCTS_FALLBACK_URL = GITHUB_PAGES_BASE + '/data/products/page_1.json';
let productsCache = null;           // full products array (mapped to readable keys)
let productsCacheTime = 0;
const PRODUCTS_CACHE_TTL = 3600000; // 1 hour in ms

// Product lookup index: id -> product (lazy-built from all pages)
let productIndexCache = null;
let productIndexCacheTime = 0;

const USER_AGENT = 'SochiAutoParts-Worker/14.0';

const ALLOWED_ORIGINS = [
  'https://sochiautoparts.ru',
  'https://www.sochiautoparts.ru',
];

const MAX_RETRIES = 2;
const RETRY_DELAY_MS = 500;

// Path aliases — redirect old/alternative URLs to correct static files
const PATH_ALIASES = {
  '/ads': '/ads/index.html',
  '/ads/': '/ads/index.html',
  '/shop': '/shop/index.html',
  '/shop/': '/shop/index.html',
  '/articles': '/articles/index.html',
  '/articles/': '/articles/index.html',
  '/article': '/articles/index.html',
  '/article/': '/articles/index.html',
  '/contacts': '/contacts/index.html',
  '/contacts/': '/contacts/index.html',
  '/privacy': '/privacy/index.html',
  '/privacy/': '/privacy/index.html',
  '/rss.xml': '/rss.xml',
  '/feed.xml': '/rss.xml',
  '/sitemap.xml': '/sitemap.xml',
  '/robots.txt': '/robots.txt',
  '/manifest.json': '/manifest.json',
};

// SVG icons
const TELEGRAM_SVG = '<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.479.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/></svg>';
const SUN_ICON = '☀️';
const MOON_ICON = '🌙';

// ============================================================
// Main request handler
// ============================================================

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    let path = url.pathname;
    const country = request.cf?.country || 'RU';

    // --- Product affiliate redirect: /api/go/{platform}/{id} ---
    // e.g. /api/go/ozon/12345 → redirect to affiliate URL for product 12345 on Ozon
    // Platform name may contain any URL-encoded characters (Cyrillic, spaces, etc.)
    const goMatch = path.match(/^\/api\/go\/([^/]+)\/([^/]+)$/);
    if (goMatch) {
      return handleProductAffiliateRedirect(decodeURIComponent(goMatch[1]), decodeURIComponent(goMatch[2]), country, request, ctx);
    }

    // --- Admitad affiliate redirect: /api/{programId} ---
    // Matches ONLY numeric IDs — /api/12345 (no conflict with /api/go/* or /api/shop/*)
    const apiMatch = path.match(/^\/api\/(\d+)$/);
    if (apiMatch) {
      return handleAffiliateRedirect(apiMatch[1], country, request, ctx);
    }

    // --- Shop Products API: /api/shop/products ---
    // Supports: ?page=N&per_page=N&q=search&cat=category&sort=field&feed=supplier&random=N
    if (path === '/api/shop/products') {
      // Check for ?random=N parameter (for shop widget)
      if (url.searchParams.has('random')) {
        return handleShopRandomProductsAPI(url, request, ctx);
      }
      return handleShopProductsAPI(url, request, ctx);
    }

    // --- Region-filtered Ads API: /api/ads ---
    if (path === '/api/ads') {
      return handleAdsAPI(url, country, request, ctx);
    }

    // --- Shop product page: /shop/{id} → proxy /shop/{id}/index.html ---
    const shopProductMatch = path.match(/^\/shop\/([a-zA-Z0-9_-]+)$/);
    if (shopProductMatch) {
      path = `/shop/${shopProductMatch[1]}/index.html`;
    }

    // --- Shop product page with trailing slash: /shop/{id}/ → proxy /shop/{id}/index.html ---
    const shopProductSlashMatch = path.match(/^\/shop\/([a-zA-Z0-9_-]+)\/$/);
    if (shopProductSlashMatch) {
      path = `/shop/${shopProductSlashMatch[1]}/index.html`;
    }

    // --- Post page: /post/{slug} → proxy to GitHub Pages /post/{slug}.html ---
    // Slug-based URLs (e.g. /post/toyota-corolla-2024-87923) are served
    // from /post/{slug}.html on GitHub Pages. The static site generator
    // also creates redirect files at /post/{id}.html for backward compat.
    const postMatch = path.match(/^\/post\/([a-zA-Z0-9_-]+)$/);
    if (postMatch) {
      path = `/post/${postMatch[1]}.html`;
    }

    // --- Article page: /article/{slug} → proxy to GitHub Pages /article/{slug}.html ---
    // Article slugs may contain Latin, Cyrillic, digits, hyphens, underscores
    const articleMatch = path.match(/^\/article\/([^/]+)$/);
    if (articleMatch) {
      path = `/article/${articleMatch[1]}.html`;
    }

    // --- Tag page: /tag/{name} → proxy to GitHub Pages /tag/{name}.html ---
    // Tag names may contain Unicode characters (Cyrillic, Arabic, etc.)
    const tagMatch = path.match(/^\/tag\/([^/]+)$/);
    if (tagMatch && !path.endsWith('.html') && !path.endsWith('.xml')) {
      path = `/tag/${tagMatch[1]}.html`;
    }

    // --- RSS compatibility: /feed.xml → serve /rss.xml ---
    if (path === '/feed.xml') {
      path = '/rss.xml';
    }

    // --- Handle root path ---
    if (path === '/') {
      path = '/index.html';
    }

    // --- Apply path aliases for directory-style URLs ---
    if (PATH_ALIASES[path]) {
      path = PATH_ALIASES[path];
    }

    // --- Handle directory paths with trailing slash (add /index.html) ---
    if (path.endsWith('/') && path !== '/') {
      path = path + 'index.html';
    }

    // --- Proxy to GitHub Pages ---
    return proxyToGitHubPages(path, request, ctx, country);
  },
};


// =============================================================================
// Product affiliate redirect: /api/go/{platform}/{id}
// Finds product by ID, matches platform, and redirects to affiliate URL
// =============================================================================

async function handleProductAffiliateRedirect(platform, productId, country, request, ctx) {
  try {
    // Build product index if needed
    const productIndex = await getProductIndex(ctx);

    // Try exact ID match first
    let product = productIndex[productId];

    // If not found by exact ID, try searching all products for a matching feed + ID
    if (!product) {
      const allProducts = await getProducts(ctx);
      // Try matching by id, feedId, or any other identifier
      product = allProducts.find(p =>
        String(p.id) === String(productId) ||
        String(p.feedId) === String(productId)
      );
    }

    if (product) {
      // If the product has a direct affiliate URL (goto_link), use it
      const gotoLink = product.goto_link || product.gotoLink || '';
      if (gotoLink) {
        return Response.redirect(gotoLink, 302);
      }

      // If the product's URL is already an affiliate link (most are from Admitad feeds)
      const productUrl = product.url || '';
      if (productUrl && productUrl !== '#') {
        // Check if it's already an affiliate/tracking URL
        if (productUrl.includes('hvjjg.com') || productUrl.includes('admitad') ||
            productUrl.includes('goto_link') || productUrl.includes('/g/') ||
            productUrl.includes('ad_network') || productUrl.includes('utm_')) {
          return Response.redirect(productUrl, 302);
        }
      }

      // Try to find an Admitad program matching the product's feed_name
      const feedName = (product.feedName || '').toLowerCase();
      const platformLower = platform.toLowerCase();

      if (feedName || platformLower) {
        const programs = await getAdmitadPrograms(ctx);

        // Build a list of candidate programs by matching platform/feed_name
        let candidatePrograms = [];

        // 1. Match by feed_name
        if (feedName) {
          const feedMatches = programs.filter(p => {
            const progName = (p.name || '').toLowerCase();
            const progFeedName = (p.feed_name || p.feedName || '').toLowerCase();
            return progFeedName.includes(feedName) || feedName.includes(progFeedName) ||
                   progName.includes(feedName) || feedName.includes(progName);
          });
          candidatePrograms.push(...feedMatches);
        }

        // 2. Match by platform alias
        const aliases = PLATFORM_ALIASES[platformLower] || [platformLower];
        for (const alias of aliases) {
          const aliasMatches = programs.filter(p => {
            const progName = (p.name || '').toLowerCase();
            const progFeedName = (p.feed_name || p.feedName || '').toLowerCase();
            const progSite = (p.site_url || p.siteUrl || '').toLowerCase();
            return progName.includes(alias) || progFeedName.includes(alias) || progSite.includes(alias);
          });
          candidatePrograms.push(...aliasMatches);
        }

        // Deduplicate and find one with a goto_link
        const seen = new Set();
        candidatePrograms = candidatePrograms.filter(p => {
          if (seen.has(p.id)) return false;
          seen.add(p.id);
          return true;
        });

        // Prefer programs with goto_link that match the platform
        const withLink = candidatePrograms.filter(p => p.goto_link || p.gotoLink);
        if (withLink.length > 0) {
          return Response.redirect(withLink[0].goto_link || withLink[0].gotoLink, 302);
        }
      }

      // Fallback: redirect to the product's original URL
      if (productUrl && productUrl !== '#') {
        return Response.redirect(productUrl, 302);
      }
    }

    // No product found or no URL — redirect to /ads/ as final fallback
    return Response.redirect(SITE_URL + '/ads/', 302);
  } catch (e) {
    console.error('Product affiliate redirect error:', e);
    return Response.redirect(SITE_URL + '/ads/', 302);
  }
}


// Build a lookup index: productId → product object
async function getProductIndex(ctx) {
  const now = Date.now();
  if (productIndexCache && (now - productIndexCacheTime) < PRODUCTS_CACHE_TTL) {
    return productIndexCache;
  }

  const allProducts = await getProducts(ctx);
  const index = {};
  for (const p of allProducts) {
    // Index by both id and feedId
    if (p.id) index[String(p.id)] = p;
    if (p.feedId && !index[String(p.feedId)]) index[String(p.feedId)] = p;
  }
  productIndexCache = index;
  productIndexCacheTime = now;
  return index;
}


// =============================================================================
// Affiliate redirect handler (with regional filtering)
// =============================================================================

async function handleAffiliateRedirect(programId, country, request, ctx) {
  try {
    const programs = await getAdmitadPrograms(ctx);
    // Try exact ID match first, then string comparison, then admitad_id field
    let prog = programs.find(p => p.id === Number(programId));
    if (!prog) prog = programs.find(p => String(p.id) === String(programId));
    if (!prog) prog = programs.find(p => String(p.admitad_id) === String(programId));

    if (prog) {
      const affiliateUrl = prog.goto_link || prog.gotoLink || prog.affiliateUrl || prog.affiliate_url || '';
      if (affiliateUrl) {
        // IMPORTANT: Always redirect to the SPECIFIC program the user clicked.
        // Region filtering is done at the ad DISPLAY level (renderAdBlocks),
        // not at the redirect level. If a user has a link to program X,
        // they should be redirected to program X regardless of their current region.
        // The affiliate network handles region-based validation internally.
        return Response.redirect(affiliateUrl, 302);
      }
    }

    // Program not found by ID — try to find a similar program in the same category
    const referer = request.headers.get('Referer') || '';
    const categoryMatch = referer.match(/\/ads\/([a-z]+)/);
    if (categoryMatch) {
      const category = categoryMatch[1];
      // Shuffle category programs to avoid always picking the same fallback
      const categoryProgs = programs.filter(p => {
        const pCat = p.jsonCategory || p.category || '';
        return pCat === category && (p.goto_link || p.gotoLink);
      });
      if (categoryProgs.length > 0) {
        const randomIdx = Math.floor(Math.random() * categoryProgs.length);
        const fallbackUrl = categoryProgs[randomIdx].goto_link || categoryProgs[randomIdx].gotoLink || '';
        if (fallbackUrl) return Response.redirect(fallbackUrl, 302);
      }
    }

    // Last resort: redirect to a random program (shuffled to avoid same result)
    const progsWithLinks = programs.filter(p => p.goto_link || p.gotoLink);
    if (progsWithLinks.length > 0) {
      const randomIdx = Math.floor(Math.random() * progsWithLinks.length);
      const fallbackUrl = progsWithLinks[randomIdx].goto_link || progsWithLinks[randomIdx].gotoLink || '';
      if (fallbackUrl) return Response.redirect(fallbackUrl, 302);
    }

    return Response.redirect(SITE_URL + '/ads/', 302);
  } catch (e) {
    console.error('Affiliate redirect error:', e);
    return Response.redirect(SITE_URL + '/ads/', 302);
  }
}


async function getAdmitadPrograms(ctx) {
  const now = Date.now();
  if (admitadCache && (now - admitadCacheTime) < ADMITAD_CACHE_TTL) {
    return admitadCache;
  }

  try {
    const response = await fetchWithRetry(ADMITAD_DATA_URL, {
      headers: { 'User-Agent': USER_AGENT },
      cf: { cacheTtl: 3600, cacheEverything: true },
    });

    if (!response.ok) throw new Error(`Admitad fetch failed: ${response.status}`);

    const data = await response.json();
    const programs = data.programs || data.results || (Array.isArray(data) ? data : []);
    admitadCache = programs;
    admitadCacheTime = now;
    return programs;
  } catch (e) {
    console.error('Failed to fetch Admitad data:', e);
    return admitadCache || [];
  }
}


// =============================================================================
// Products data (for shop page)
// =============================================================================

// Get ALL products — loads products.json from zap.online, maps to readable keys.
// Cached for 1 hour. Falls back to GitHub Pages paginated data.
async function getProducts(ctx) {
  const now = Date.now();
  if (productsCache && (now - productsCacheTime) < PRODUCTS_CACHE_TTL) {
    return productsCache;
  }

  // Primary: load full products.json from zap.online
  try {
    const resp = await fetchWithRetry(PRODUCTS_JSON_URL, {
      headers: { 'User-Agent': USER_AGENT },
      cf: { cacheTtl: 1800, cacheEverything: true },
    });
    if (resp.ok) {
      const raw = await resp.json();
      const items = Array.isArray(raw) ? raw : (raw.products || raw.items || []);
      const mapped = items.map((p, idx) => ({
        id: p.id || (p.f ? p.f + '-' + idx : String(idx)),
        name: p.n || p.name || '',
        price: p.p || p.price || 0,
        oldPrice: p.o || p.oldPrice || p.old_price || 0,
        currency: p.c || p.currency || 'RUB',
        url: p.u || p.url || p.productUrl || '#',
        image: p.i || p.image || p.imageUrl || '',
        vendor: p.v || p.vendor || p.brand || '',
        description: p.d || p.description || '',
        feedId: p.f || p.feedId || p.feed_id || '',
        feedName: p.fn || p.feedName || p.feed_name || '',
        feedColor: p.fc || p.feedColor || '',
        feedIcon: p.fi || p.feedIcon || '',
        categoryId: p.cat || p.categoryId || p.category_id || '',
        available: p.a !== undefined ? p.a : (p.available !== undefined ? p.available : true),
        shortNote: p.sn || p.shortNote || '',
        model: p.m || p.model || '',
        type: p.tp || p.type || '',
        goto_link: p.goto_link || p.gotoLink || '',
        product_page: p.product_page || '',
      }));
      productsCache = mapped;
      productsCacheTime = now;
      // Invalidate product index since data changed
      productIndexCache = null;
      return mapped;
    }
  } catch (e) {
    console.error('Failed to fetch products.json from zap.online:', e);
  }

  // Fallback: try GitHub Pages paginated data
  try {
    const metaResp = await fetchWithRetry(GITHUB_PAGES_BASE + '/data/products/meta.json', {
      headers: { 'User-Agent': USER_AGENT },
      cf: { cacheTtl: 3600, cacheEverything: true },
    });
    if (metaResp.ok) {
      const meta = await metaResp.json();
      const totalPages = meta.pages_count || 1;
      const allProducts = [];
      for (let pageNum = 1; pageNum <= totalPages; pageNum++) {
        const pageResp = await fetchWithRetry(`${GITHUB_PAGES_BASE}/data/products/page_${pageNum}.json`, {
          headers: { 'User-Agent': USER_AGENT },
          cf: { cacheTtl: 3600, cacheEverything: true },
        });
        if (pageResp.ok) {
          const pageData = await pageResp.json();
          const items = Array.isArray(pageData) ? pageData : [];
          items.forEach((p, idx) => {
            allProducts.push({
              id: p.id || (p.f ? p.f + '-' + (allProducts.length) : String(allProducts.length)),
              name: p.n || p.name || '',
              price: p.p || p.price || 0,
              oldPrice: p.o || p.oldPrice || p.old_price || 0,
              currency: p.c || p.currency || 'RUB',
              url: p.u || p.url || p.productUrl || '#',
              image: p.i || p.image || p.imageUrl || '',
              vendor: p.v || p.vendor || p.brand || '',
              description: p.d || p.description || '',
              feedId: p.f || p.feedId || p.feed_id || '',
              feedName: p.fn || p.feedName || p.feed_name || '',
              feedColor: p.fc || p.feedColor || '',
              feedIcon: p.fi || p.feedIcon || '',
              categoryId: p.cat || p.categoryId || p.category_id || '',
              available: p.a !== undefined ? p.a : (p.available !== undefined ? p.available : true),
              shortNote: p.sn || p.shortNote || '',
              model: p.m || p.model || '',
              type: p.tp || p.type || '',
              goto_link: p.goto_link || p.gotoLink || '',
              product_page: p.product_page || '',
            });
          });
        }
      }
      productsCache = allProducts;
      productsCacheTime = now;
      productIndexCache = null;
      return allProducts;
    }
  } catch (e) {
    console.error('Failed to fetch products from GitHub Pages fallback:', e);
  }

  return productsCache || [];
}


// =============================================================================
// Shop Random Products API: /api/shop/products?random=N
// Returns N random products as JSON (for the shop widget on post pages)
// =============================================================================

async function handleShopRandomProductsAPI(url, request, ctx) {
  try {
    const count = Math.min(20, Math.max(1, parseInt(url.searchParams.get('random') || '6', 10)));
    const products = await getProducts(ctx);
    if (!products || products.length === 0) {
      return new Response(JSON.stringify([]), {
        headers: { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'public, max-age=300', 'Access-Control-Allow-Origin': getAllowedOrigin(request) },
      });
    }
    // Fisher-Yates shuffle and pick first N
    const shuffled = [...products];
    for (let i = shuffled.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
    }
    const randomProducts = shuffled.slice(0, count).map(p => ({
      id: p.id || '',
      name: p.n || p.name || '',
      price: p.p || p.price || 0,
      image: p.i || p.image || '',
      url: p.u || p.url || '#',
      vendor: p.v || p.vendor || '',
      feedName: p.fn || p.feedName || p.feed_name || '',
      product_page: p.product_page || (p.id ? '/shop/' + p.id : ''),
    }));
    return new Response(JSON.stringify(randomProducts), {
      headers: {
        'Content-Type': 'application/json; charset=utf-8',
        'Cache-Control': 'public, max-age=60, s-maxage=60',
        'Access-Control-Allow-Origin': getAllowedOrigin(request),
      },
    });
  } catch (e) {
    console.error('Shop random products API error:', e);
    return new Response(JSON.stringify([]), {
      headers: { 'Content-Type': 'application/json; charset=utf-8' },
    });
  }
}


// =============================================================================
// Shop Products API: /api/shop/products
// Supports: ?page=N&per_page=N&q=search&cat=category&sort=field&feed=supplier
// =============================================================================

async function handleShopProductsAPI(url, request, ctx) {
  try {
    const products = await getProducts(ctx);
    if (!products || products.length === 0) {
      return new Response(JSON.stringify({ products: [], total: 0, page: 1, per_page: 30 }), {
        headers: { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'public, max-age=300', 'Access-Control-Allow-Origin': getAllowedOrigin(request) },
      });
    }

    const page = Math.max(1, parseInt(url.searchParams.get('page') || '1', 10));
    const perPage = Math.min(48, Math.max(1, parseInt(url.searchParams.get('per_page') || '30', 10)));
    const query = (url.searchParams.get('q') || '').toLowerCase();
    const category = url.searchParams.get('cat') || '';
    const sort = url.searchParams.get('sort') || 'popular';
    const feed = url.searchParams.get('feed') || '';

    // NOTE: Shop shows ALL products regardless of region (user's request)
    // Filter by feed/search only — no region filtering
    let filtered = products.filter(p => {
      if (feed && (p.feedName || '') !== feed) return false;
      if (category && String(p.categoryId || '') !== String(category)) return false;
      if (query && query.length >= 2) {
        const name = (p.name || '').toLowerCase();
        const desc = (p.description || '').toLowerCase();
        const vendor = (p.vendor || '').toLowerCase();
        if (!name.includes(query) && !desc.includes(query) && !vendor.includes(query)) return false;
      }
      return true;
    });

    // Sort
    if (sort === 'price_asc') filtered.sort((a, b) => (a.price || 0) - (b.price || 0));
    else if (sort === 'price_desc') filtered.sort((a, b) => (b.price || 0) - (a.price || 0));
    else if (sort === 'name') filtered.sort((a, b) => (a.name || '').localeCompare(b.name || ''));
    else if (sort === 'popular') filtered.sort((a, b) => (b.available === true ? 1 : 0) - (a.available === true ? 1 : 0));

    // Paginate
    const total = filtered.length;
    const start = (page - 1) * perPage;
    const pageProducts = filtered.slice(start, start + perPage);

    // Build supplier stats
    const supplierStats = {};
    for (const p of products) {
      const feedName = p.feedName || '';
      if (feedName) supplierStats[feedName] = (supplierStats[feedName] || 0) + 1;
    }

    return new Response(JSON.stringify({
      products: pageProducts,
      total,
      page,
      per_page: perPage,
      total_pages: Math.ceil(total / perPage),
      suppliers: supplierStats,
    }), {
      headers: {
        'Content-Type': 'application/json; charset=utf-8',
        'Cache-Control': 'public, max-age=300, s-maxage=300',
        'Access-Control-Allow-Origin': getAllowedOrigin(request),
      },
    });
  } catch (e) {
    console.error('Shop API error:', e);
    return new Response(JSON.stringify({ error: e.message, products: [], total: 0 }), {
      status: 500,
      headers: { 'Content-Type': 'application/json; charset=utf-8' },
    });
  }
}


// =============================================================================
// Region-filtered Ads API: /api/ads?lang=ru|en&max=6&cat=autoparts
// Returns HTML of region-filtered ad blocks for client-side injection
// =============================================================================

async function handleAdsAPI(url, country, request, ctx) {
  try {
    const lang = url.searchParams.get('lang') === 'en' ? 'en' : 'ru';
    const maxBlocks = Math.min(20, Math.max(1, parseInt(url.searchParams.get('max') || '6', 10)));
    const category = url.searchParams.get('cat') || ''; // Filter by category (e.g. 'autoparts')

    const adBlocksHtml = await renderAdBlocks(lang, [country], ctx, maxBlocks, category);

    return new Response(adBlocksHtml || '', {
      headers: {
        'Content-Type': 'text/html; charset=utf-8',
        'Cache-Control': 'public, max-age=300, s-maxage=300',
        'Vary': 'Accept-Encoding, Cloudflare-Viewer-Country',
        'Access-Control-Allow-Origin': getAllowedOrigin(request),
      },
    });
  } catch (e) {
    console.error('Ads API error:', e);
    return new Response('', {
      headers: { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' },
    });
  }
}


// =============================================================================
// Render ad blocks with regional filtering
// =============================================================================

async function renderAdBlocks(lang, allowedRegions, ctx, maxBlocks = 6, category = '') {
  try {
    const programs = await getAdmitadPrograms(ctx);
    if (!programs || programs.length === 0) return '';

    // Filter by region AND category
    const regionFiltered = programs.filter(prog => {
      if (!prog.allowed_regions || prog.allowed_regions.length === 0) return true;
      return prog.allowed_regions.some(r => allowedRegions.includes(r));
    });

    // Apply category filter if specified
    const categoryFiltered = category
      ? regionFiltered.filter(prog => (prog.jsonCategory || prog.category || 'other') === category)
      : regionFiltered;

    // Shuffle and pick up to maxBlocks
    const shuffled = [...categoryFiltered];
    for (let i = shuffled.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
    }

    // If category is specified, show all matching programs (no one-per-category limit)
    // If no category, pick one per category for variety
    let selectedAds;
    if (category) {
      selectedAds = shuffled.slice(0, maxBlocks);
    } else {
      const seenCategories = new Set();
      selectedAds = [];
      for (const prog of shuffled) {
        const cat = prog.jsonCategory || prog.category || 'other';
        if (!seenCategories.has(cat) && selectedAds.length < maxBlocks) {
          seenCategories.add(cat);
          selectedAds.push(prog);
        }
      }
    }

    if (selectedAds.length === 0) return '';

    const adsHTML = selectedAds.map(prog => {
      const imageUrl = prog.image || prog.logo || '';
      const categoryKey = prog.jsonCategory || prog.category || prog.internalCategory || 'other';
      const categoryLabel = ADMITAD_CATEGORIES[categoryKey]?.[lang] || ADMITAD_CATEGORIES[categoryKey]?.ru || prog.jsonCategory || prog.category || 'Other';
      const description = prog.description || prog.short_description || '';
      const btnText = lang === 'ru' ? 'Перейти' : 'Go';

      return `<a href="/api/${prog.id}" target="_blank" rel="nofollow noopener sponsored" style="text-decoration:none;color:inherit;display:block;">
<div class="ad-block-item">
<div class="ad-block-media">
${imageUrl ? `<img src="${escapeHtml(imageUrl)}" alt="${escapeHtml(prog.name || '')}" loading="lazy" referrerpolicy="no-referrer" onerror="this.onerror=null;this.style.display='none';this.parentNode.innerHTML='<span style=\\'color:var(--text-muted);font-size:2rem;\\'>🛒</span>'">` : '<span style="color:var(--text-muted);font-size:2rem;">🛒</span>'}
</div>
<span class="ad-block-category">${escapeHtml(categoryLabel)}</span>
<h4 class="ad-block-title">${escapeHtml(prog.name || '')}</h4>
<p class="ad-block-desc">${escapeHtml(description.substring(0, 150))}${description.length > 150 ? '...' : ''}</p>
<div class="ad-block-btn">${btnText}<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-left:4px;"><path d="M7 17L17 7M17 7H7M17 7V17"/></svg></div>
${prog.advertiser_legal_info?.name ? `<div class="ad-block-legal">${lang === 'ru' ? 'Реклама' : 'Ad'}: ${escapeHtml(prog.advertiser_legal_info.name)}</div>` : ''}
</div>
</a>`;
    }).join('');

    return `<div class="ad-blocks-container">${adsHTML}</div>`;
  } catch (error) {
    console.error('[renderAdBlocks] Error:', error);
    return '';
  }
}


// =============================================================================
// GitHub Pages proxy
// =============================================================================

async function proxyToGitHubPages(path, request, ctx, country) {
  const headers = new Headers();
  headers.set('User-Agent', USER_AGENT);
  headers.set('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8');

  // Check cache first — include query string in cache key to avoid collisions
  const cache = caches.default;
  const requestUrl = new URL(request.url);
  const cacheKeyUrl = GITHUB_PAGES_BASE + path + (requestUrl.search ? '?' + requestUrl.search : '');
  const cacheKey = new Request(cacheKeyUrl, { method: 'GET' });

  let cachedResponse = await cache.match(cacheKey);
  if (cachedResponse) {
    // Server-Side Ads Injection for cached HTML responses
    const contentType = cachedResponse.headers.get('Content-Type') || '';
    if (contentType.includes('text/html')) {
      let body = await cachedResponse.text();
      body = await injectRegionalAds(body, country, ctx, path);
      const resp = new Response(body, {
        status: cachedResponse.status,
        statusText: cachedResponse.statusText,
        headers: cachedResponse.headers,
      });
      return addSiteHeaders(resp, request.url, request);
    }
    return addSiteHeaders(new Response(cachedResponse.body, cachedResponse), request.url, request);
  }

  // Helper: fetch from GH Pages with given path
  async function fetchFromGH(fetchPath) {
    const ghUrl = GITHUB_PAGES_BASE + fetchPath;
    return await fetch(ghUrl, {
      method: 'GET',
      headers: headers,
      cf: { cacheTtl: CACHE_TTL_EDGE, cacheEverything: true },
    });
  }

  try {
    let response = await fetchFromGH(path);

    // If 404 and path has no extension, try adding .html
    if (response.status === 404 && !path.endsWith('.html') && !path.endsWith('.xml') &&
        !path.endsWith('.json') && !path.endsWith('.txt') && !path.includes('.')) {
      const htmlPath = path + '.html';
      const htmlResponse = await fetchFromGH(htmlPath);
      if (htmlResponse.ok) response = htmlResponse;
    }

    // If still 404, try directory index
    if (response.status === 404 && !path.endsWith('/index.html')) {
      const dirPath = path.replace(/\.html$/, '') + '/index.html';
      const dirResponse = await fetchFromGH(dirPath);
      if (dirResponse.ok) response = dirResponse;
    }

    // If still 404, return custom 404 page
    if (response.status === 404) {
      const isEn = request.url.includes('/en/');
      return new Response(generate404Page(isEn), {
        status: 404,
        headers: { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'public, max-age=60' },
      });
    }

    if (!response.ok) {
      return new Response(`Upstream error: ${response.status}`, {
        status: 502,
        headers: { 'Content-Type': 'text/plain' },
      });
    }

    // Clone and cache the ORIGINAL response (before ad injection,
    // so region-specific ads are not baked into the edge cache)
    const responseToCache = response.clone();
    ctx.waitUntil(cache.put(cacheKey, responseToCache));

    // Server-Side Ads Injection for fresh HTML responses
    const contentType = response.headers.get('Content-Type') || '';
    if (contentType.includes('text/html')) {
      let body = await response.text();
      body = await injectRegionalAds(body, country, ctx, path);
      const resp = new Response(body, {
        status: response.status,
        statusText: response.statusText,
        headers: response.headers,
      });
      return addSiteHeaders(resp, request.url, request);
    }

    return addSiteHeaders(response, request.url, request);

  } catch (error) {
    return new Response(`Worker error: ${error.message}`, {
      status: 500,
      headers: { 'Content-Type': 'text/plain' },
    });
  }
}


// =============================================================================
// Server-Side Ads Injection
// Detects <!-- REGIONAL_ADS_PLACEHOLDER --> (or _RU / _EN variants) in HTML
// and replaces with region-filtered ad blocks
// =============================================================================

async function injectRegionalAds(htmlBody, country, ctx, requestPath) {
  // Quick check: does the HTML contain any ad placeholder?
  const hasPlaceholder = htmlBody.includes('<!-- REGIONAL_ADS_PLACEHOLDER -->') ||
                         htmlBody.includes('<!-- REGIONAL_ADS_PLACEHOLDER_RU -->') ||
                         htmlBody.includes('<!-- REGIONAL_ADS_PLACEHOLDER_EN -->');
  if (!hasPlaceholder) return htmlBody;

  // Detect language from <html lang="...">
  const langMatch = htmlBody.match(/<html[^>]+\blang=["']([a-z]{2})/i);
  const lang = (langMatch && langMatch[1].toLowerCase() === 'en') ? 'en' : 'ru';

  // Detect ad category from request path (e.g. /ads/autoparts.html → 'autoparts')
  let category = '';
  const adsCatMatch = requestPath.match(/\/ads\/([a-z]+)/);
  if (adsCatMatch) {
    category = adsCatMatch[1];
  }
  // Also check for data-cat attribute in the HTML
  if (!category) {
    const catAttrMatch = htmlBody.match(/data-cat=["']([a-z]+)["']/);
    if (catAttrMatch) category = catAttrMatch[1];
  }

  // Render region-filtered ad blocks with detected category
  const adBlocksHtml = await renderAdBlocks(lang, [country], ctx, 6, category);

  let result = htmlBody;

  if (adBlocksHtml) {
    // Replace language-specific placeholders first (more specific match)
    if (lang === 'ru') {
      result = result.replace('<!-- REGIONAL_ADS_PLACEHOLDER_RU -->', adBlocksHtml);
    } else {
      result = result.replace('<!-- REGIONAL_ADS_PLACEHOLDER_EN -->', adBlocksHtml);
    }
    // Replace generic placeholder
    result = result.replace('<!-- REGIONAL_ADS_PLACEHOLDER -->', adBlocksHtml);
  } else {
    // No ads available — remove all placeholders
    result = result.replace(/<!-- REGIONAL_ADS_PLACEHOLDER(?:_RU|_EN)? -->/g, '');
  }

  // Remove <noscript data-ad-fallback>...</noscript> tags
  // (fallback shown when JS disabled, not needed with server-side injection)
  result = result.replace(/<noscript\s+data-ad-fallback>[\s\S]*?<\/noscript>/gi, '');

  return result;
}


// =============================================================================
// Helper functions
// =============================================================================

function addSiteHeaders(response, requestUrl, request) {
  const newHeaders = new Headers(response.headers);

  const contentType = newHeaders.get('Content-Type') || '';
  if (contentType.includes('text/html')) {
    newHeaders.set('Content-Type', 'text/html; charset=utf-8');
    newHeaders.set('Vary', 'Accept-Encoding, Cloudflare-Viewer-Country');
  }
  if (contentType.includes('application/xml') || contentType.includes('text/xml')) {
    newHeaders.set('Content-Type', 'application/xml; charset=utf-8');
  }
  if (contentType.includes('application/json')) {
    newHeaders.set('Content-Type', 'application/json; charset=utf-8');
  }
  if (contentType.includes('text/plain')) {
    newHeaders.set('Content-Type', 'text/plain; charset=utf-8');
  }

  newHeaders.set('X-Content-Type-Options', 'nosniff');
  newHeaders.set('X-Frame-Options', 'SAMEORIGIN');
  newHeaders.set('Referrer-Policy', 'strict-origin-when-cross-origin');
  newHeaders.set('Permissions-Policy', 'camera=(), microphone=(), geolocation=()');
  newHeaders.set('Cache-Control', `public, max-age=${CACHE_TTL_BROWSER}`);

  if (requestUrl.includes('.xml') || requestUrl.includes('/rss') || requestUrl.includes('/feed')) {
    // RSS/feeds need to be accessible from any reader — use wildcard
    newHeaders.set('Access-Control-Allow-Origin', '*');
  } else {
    // For other proxied content, restrict to known origins
    const origin = request.headers?.get('Origin') || '';
    if (ALLOWED_ORIGINS.includes(origin) || origin.endsWith('.sochiautoparts.ru') ||
        origin.includes('localhost') || origin.includes('127.0.0.1')) {
      newHeaders.set('Access-Control-Allow-Origin', origin);
    }
  }

  newHeaders.delete('X-GitHub-Request-Id');
  newHeaders.delete('X-Fastly-Request-ID');

  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: newHeaders,
  });
}


// =============================================================================
// Fetch with retry (for resilience against transient failures)
// =============================================================================

async function fetchWithRetry(url, options, retries = MAX_RETRIES) {
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const response = await fetch(url, options);
      if (response.ok || response.status === 404) return response;
      // Non-2xx but not 404 — retry if attempts remain
      if (attempt < retries) {
        await new Promise(r => setTimeout(r, RETRY_DELAY_MS * (attempt + 1)));
        continue;
      }
      return response;
    } catch (e) {
      if (attempt < retries) {
        console.warn(`fetchWithRetry: attempt ${attempt + 1} failed for ${url}, retrying...`, e.message);
        await new Promise(r => setTimeout(r, RETRY_DELAY_MS * (attempt + 1)));
        continue;
      }
      throw e;
    }
  }
}


// =============================================================================
// CORS: return the request's Origin if it matches our domain, else empty string
// =============================================================================

function getAllowedOrigin(request) {
  const origin = request.headers.get('Origin') || '';
  if (ALLOWED_ORIGINS.includes(origin)) return origin;
  // Also allow subdomains and localhost for development
  if (origin.endsWith('.sochiautoparts.ru') || origin.includes('localhost') || origin.includes('127.0.0.1')) return origin;
  return '';
}


function escapeHtml(str) {
  if (!str) return '';
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}


function generate404Page(isEn = false) {
  const lang = isEn ? 'en' : 'ru';
  return `<!DOCTYPE html>
<html lang="${lang}" data-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>404 — ${isEn ? 'Page not found' : 'Страница не найдена'} | SOCHIAUTOPARTS</title>
<meta name="robots" content="noindex,nofollow">
<link rel="icon" href="/logo.jpg" type="image/jpeg" />
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Manrope:wght@400;500;600;700;800&display=swap" rel="stylesheet" />
<meta http-equiv="refresh" content="8;url=/${isEn ? 'en/' : ''}">
<style>
:root{--primary:#2481CC;--bg-body:#F4F4F5;--text-main:#000;--text-sec:#707579}
[data-theme="dark"]{--bg-body:#0F1115;--text-main:#F0F6FC;--text-sec:#8B949E}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Inter',system-ui,-apple-system,sans-serif;background:var(--bg-body);color:var(--text-main);line-height:1.6;display:flex;align-items:center;justify-content:center;min-height:100vh}
.e404{text-align:center;padding:2rem}
.e404 h1{font-size:6rem;margin:0;color:var(--primary)}
.e404 p{font-size:1.2rem;margin:1rem 0 2rem;color:var(--text-sec)}
.e404 a{display:inline-block;padding:12px 28px;background:var(--primary);color:#fff;text-decoration:none;border-radius:9999px;font-size:1rem;font-weight:600;transition:opacity .15s}
.e404 a:hover{opacity:.85}
</style>
</head>
<body>
<div class="e404">
<h1>404</h1>
<p>${isEn ? 'Page not found. Redirecting to homepage...' : 'Страница не найдена. Перенаправление на главную...'}</p>
<a href="/${isEn ? 'en/' : ''}">${isEn ? 'Go Home' : 'На главную'}</a>
</div>
<script>try{var t=localStorage.getItem('theme');if(t)document.documentElement.setAttribute('data-theme',t)}catch(e){}</script>
</body>
</html>`;
}
