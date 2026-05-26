/**
 * SochiAutoParts Cloudflare Worker v10.0
 *
 * Proxies sochiautoparts.ru → GitHub Pages static site.
 * Dynamically generates /archive/post/{id} pages from Telegram archive data.
 * Handles regional filtering for Admitad partner programs.
 * Provides /api/shop/products and /api/ads endpoints for client-side dynamic content.
 *
 * Architecture:
 *   1. /api/{id}              → Admitad affiliate redirect (region-filtered lookup by program ID)
 *   2. /api/shop/products     → Products API for shop page pagination/filtering
 *   3. /api/ads               → Region-filtered ad blocks HTML (for static pages)
 *   4. /archive/post/{id}     → Dynamic archive post page (full layout, ads, shop widget)
 *   5. /archive/page/{n}      → Dynamic archive pagination (for large archives)
 *   6. /rss.xml               → serve from GitHub Pages /rss.xml
 *   7. /feed.xml              → serve from GitHub Pages /rss.xml (compat alias)
 *   8. All other requests     → proxy from GitHub Pages
 *   9. 404 from GH Pages      → try .html, then /index.html, then custom 404
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

// Telegram archive data — cached per-page
const TELEGRAM_ARCHIVE_BASE = GITHUB_PAGES_BASE + '/data/telegram_archive';
const TELEGRAM_ARCHIVE_FALLBACK = 'https://raw.githubusercontent.com/creastudioai-beep/sapapp/main/data/telegram_archive';
let telegramIndexCache = null;
let telegramIndexCacheTime = 0;
const TELEGRAM_INDEX_CACHE_TTL = 3600000; // 1 hour in ms
let telegramPageCache = {};  // page_num -> { data, time }
let telegramMetaCache = null;
let telegramMetaCacheTime = 0;

// Products data (for shop widget) — paginated from sapapp repo
const PRODUCTS_BASE_URL = GITHUB_PAGES_BASE + '/data/products';
const PRODUCTS_FALLBACK_URL = 'https://raw.githubusercontent.com/creastudioai-beep/sapapp/main/data/products';
let productsMetaCache = null;     // { pages_count, total_products }
let productsMetaCacheTime = 0;
let productsPageCache = {};       // page_num -> { data, time }
const PRODUCTS_CACHE_TTL = 3600000; // 1 hour in ms

const USER_AGENT = 'SochiAutoParts-Worker/10.0';

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
  '/archive': '/archive/index.html',
  '/archive/': '/archive/index.html',
  '/shop': '/shop/index.html',
  '/shop/': '/shop/index.html',
  '/articles': '/articles/index.html',
  '/articles/': '/articles/index.html',
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

    // --- Admitad affiliate redirect: /api/{programId} ---
    const apiMatch = path.match(/^\/api\/(\d+)$/);
    if (apiMatch) {
      return handleAffiliateRedirect(apiMatch[1], country, request, ctx);
    }

    // --- Shop Products API: /api/shop/products ---
    if (path === '/api/shop/products') {
      return handleShopProductsAPI(url, request, ctx);
    }

    // --- Region-filtered Ads API: /api/ads ---
    if (path === '/api/ads') {
      return handleAdsAPI(url, country, request, ctx);
    }

    // --- Dynamic archive post page: /archive/post/{id} or /en/archive/post/{id} ---
    const archivePostMatch = path.match(/^\/(?:en\/)?archive\/post\/(\d+)$/);
    if (archivePostMatch) {
      const postId = archivePostMatch[1];
      const isEn = path.startsWith('/en/');
      return handleArchivePost(postId, isEn, country, request, ctx);
    }

    // --- Dynamic archive pagination: /archive/page/{n} or /en/archive/page/{n} ---
    const archivePageMatch = path.match(/^\/(?:en\/)?archive\/page\/(\d+)$/);
    if (archivePageMatch) {
      const pageNum = parseInt(archivePageMatch[1], 10);
      const isEn = path.startsWith('/en/');
      return handleArchivePage(pageNum, isEn, country, request, ctx);
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
    return proxyToGitHubPages(path, request, ctx);
  },
};


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
        // Region check: if program has region restrictions, verify user's region matches
        const regions = prog.allowed_regions || [];
        if (regions.length === 0 || regions.includes(country)) {
          return Response.redirect(affiliateUrl, 302);
        }
        // Region mismatch — skip this program, try fallback below
      }
    }

    // Program not found by ID — try to find a similar program in the same category
    // and redirect there instead of the homepage
    const referer = request.headers.get('Referer') || '';
    const categoryMatch = referer.match(/\/ads\/([a-z]+)/);
    if (categoryMatch) {
      const category = categoryMatch[1];
      const categoryProg = programs.find(p => {
        const pCat = p.jsonCategory || p.category || '';
        const regions = p.allowed_regions || [];
        return pCat === category && (regions.length === 0 || regions.includes(country)) && (p.goto_link || p.gotoLink);
      });
      if (categoryProg) {
        const fallbackUrl = categoryProg.goto_link || categoryProg.gotoLink || '';
        if (fallbackUrl) return Response.redirect(fallbackUrl, 302);
      }
    }

    // Last resort: find any program available in user's region
    const anyProg = programs.find(p => {
      const regions = p.allowed_regions || [];
      return (regions.length === 0 || regions.includes(country)) && (p.goto_link || p.gotoLink);
    });
    if (anyProg) {
      const fallbackUrl = anyProg.goto_link || anyProg.gotoLink || '';
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
// Products data (for shop widget on archive post pages)
// =============================================================================

// Get products meta info (pages count, total). Cached separately from product pages.
async function getProductsMeta(ctx) {
  const now = Date.now();
  if (productsMetaCache && (now - productsMetaCacheTime) < PRODUCTS_CACHE_TTL) {
    return productsMetaCache;
  }

  for (const baseUrl of [PRODUCTS_BASE_URL, PRODUCTS_FALLBACK_URL]) {
    try {
      const metaResp = await fetchWithRetry(`${baseUrl}/meta.json`, {
        headers: { 'User-Agent': USER_AGENT },
        cf: { cacheTtl: 3600, cacheEverything: true },
      });
      if (metaResp.ok) {
        productsMetaCache = await metaResp.json();
        productsMetaCacheTime = now;
        return productsMetaCache;
      }
    } catch (e) {
      console.error(`Failed to fetch products meta from ${baseUrl}:`, e);
    }
  }
  return productsMetaCache || { pages_count: 0, total_products: 0 };
}

// Get a single page of products. Cached per-page.
async function getProductsPage(pageNum, ctx) {
  const now = Date.now();
  const cached = productsPageCache[pageNum];
  if (cached && (now - cached.time) < PRODUCTS_CACHE_TTL) {
    return cached.data;
  }

  const raw = await fetchProductPage(pageNum);
  const mapped = raw.map(p => ({
    id: p.f || p.id,
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
  }));
  productsPageCache[pageNum] = { data: mapped, time: now };
  return mapped;
}

// Get ALL products (loads all pages on demand, cached per-page).
async function getProducts(ctx) {
  const meta = await getProductsMeta(ctx);
  const totalPages = meta.pages_count || 0;
  if (totalPages === 0) return [];

  const allProducts = [];
  const batchSize = 5;
  for (let batch = 0; batch < totalPages; batch += batchSize) {
    const promises = [];
    for (let i = batch + 1; i <= Math.min(batch + batchSize, totalPages); i++) {
      promises.push(getProductsPage(i, ctx));
    }
    const results = await Promise.allSettled(promises);
    for (const result of results) {
      if (result.status === 'fulfilled' && Array.isArray(result.value)) {
        allProducts.push(...result.value);
      }
    }
  }
  return allProducts;
}

// Get a specific page range of products (for shop API pagination).
async function getProductsPageRange(startPage, endPage, ctx) {
  const promises = [];
  for (let i = startPage; i <= endPage; i++) {
    promises.push(getProductsPage(i, ctx));
  }
  const results = await Promise.allSettled(promises);
  const products = [];
  for (const result of results) {
    if (result.status === 'fulfilled' && Array.isArray(result.value)) {
      products.push(...result.value);
    }
  }
  return products;
}

async function fetchProductPage(pageNum) {
  for (const baseUrl of [PRODUCTS_BASE_URL, PRODUCTS_FALLBACK_URL]) {
    try {
      const response = await fetchWithRetry(`${baseUrl}/page_${pageNum}.json`, {
        headers: { 'User-Agent': USER_AGENT },
        cf: { cacheTtl: 3600, cacheEverything: true },
      });
      if (response.ok) {
        return await response.json();
      }
    } catch (e) {
      console.error(`Failed to fetch products page ${pageNum} from ${baseUrl}:`, e);
    }
  }
  return [];
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
// Region-filtered Ads API: /api/ads?lang=ru|en&max=6
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
// Dynamic archive post page handler
// =============================================================================

async function handleArchivePost(postId, isEn, country, request, ctx) {
  try {
    // Step 1: Get the Telegram archive index (post_id -> page mapping)
    const index = await getTelegramIndex(ctx);
    if (!index) {
      // No index available — try static file on GitHub Pages as fallback
      return proxyToGitHubPages(`/archive/post/${postId}.html`, request, ctx);
    }

    const entry = index[postId];
    if (!entry) {
      // Post not found in archive — try static file as fallback
      const fallback = await proxyToGitHubPages(`/archive/post/${postId}.html`, request, ctx);
      if (fallback.status !== 404) return fallback;
      return new Response(generate404Page(isEn), {
        status: 404,
        headers: { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'public, max-age=60' },
      });
    }

    // Step 2: Fetch the page that contains this post
    const pageNum = entry.page || entry.p;
    const pos = entry.pos || entry.i || 0;
    const pageData = await getTelegramPage(pageNum, ctx);

    if (!pageData || !Array.isArray(pageData) || pos >= pageData.length) {
      return new Response(generate404Page(isEn), {
        status: 404,
        headers: { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'public, max-age=60' },
      });
    }

    const post = pageData[pos];
    if (!post || String(post.id) !== String(postId)) {
      // Position mismatch — search the page for the post
      const found = pageData.find(p => String(p.id) === String(postId));
      if (!found) {
        return new Response(generate404Page(isEn), {
          status: 404,
          headers: { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'public, max-age=60' },
        });
      }
      return generateFullArchivePostResponse(found, isEn, country, ctx);
    }

    return generateFullArchivePostResponse(post, isEn, country, ctx);

  } catch (e) {
    console.error('Archive post error:', e);
    // Fallback to static file
    return proxyToGitHubPages(`/archive/post/${postId}.html`, request, ctx);
  }
}


async function getTelegramIndex(ctx) {
  const now = Date.now();
  if (telegramIndexCache && (now - telegramIndexCacheTime) < TELEGRAM_INDEX_CACHE_TTL) {
    return telegramIndexCache;
  }

  // Try primary (GitHub Pages) then fallback (raw.githubusercontent.com)
  for (const baseUrl of [TELEGRAM_ARCHIVE_BASE, TELEGRAM_ARCHIVE_FALLBACK]) {
    try {
      const response = await fetchWithRetry(`${baseUrl}/posts_index.json`, {
        headers: { 'User-Agent': USER_AGENT },
        cf: { cacheTtl: 3600, cacheEverything: true },
      });

      if (response.ok) {
        const data = await response.json();
        telegramIndexCache = data;
        telegramIndexCacheTime = now;
        return data;
      }
    } catch (e) {
      console.error(`Failed to fetch Telegram index from ${baseUrl}:`, e);
    }
  }
  return telegramIndexCache || null;
}


async function getTelegramPage(pageNum, ctx) {
  const now = Date.now();
  const cached = telegramPageCache[pageNum];
  if (cached && (now - cached.time) < TELEGRAM_INDEX_CACHE_TTL) {
    return cached.data;
  }

  // Try primary (GitHub Pages) then fallback (raw.githubusercontent.com)
  for (const baseUrl of [TELEGRAM_ARCHIVE_BASE, TELEGRAM_ARCHIVE_FALLBACK]) {
    try {
      const response = await fetchWithRetry(`${baseUrl}/page_${pageNum}.json`, {
        headers: { 'User-Agent': USER_AGENT },
        cf: { cacheTtl: 3600, cacheEverything: true },
      });

      if (response.ok) {
        const data = await response.json();
        telegramPageCache[pageNum] = { data, time: now };
        return data;
      }
    } catch (e) {
      console.error(`Failed to fetch Telegram page ${pageNum} from ${baseUrl}:`, e);
    }
  }
  return cached ? cached.data : null;
}


async function getTelegramMeta(ctx) {
  const now = Date.now();
  if (telegramMetaCache && (now - telegramMetaCacheTime) < TELEGRAM_INDEX_CACHE_TTL) {
    return telegramMetaCache;
  }

  for (const baseUrl of [TELEGRAM_ARCHIVE_BASE, TELEGRAM_ARCHIVE_FALLBACK]) {
    try {
      const response = await fetchWithRetry(`${baseUrl}/meta.json`, {
        headers: { 'User-Agent': USER_AGENT },
        cf: { cacheTtl: 3600, cacheEverything: true },
      });

      if (response.ok) {
        const data = await response.json();
        telegramMetaCache = data;
        telegramMetaCacheTime = now;
        return data;
      }
    } catch (e) {
      console.error(`Failed to fetch Telegram meta from ${baseUrl}:`, e);
    }
  }
  return telegramMetaCache || {};
}


// =============================================================================
// Full archive post page generator (matches old Worker v27 quality)
// =============================================================================

async function generateFullArchivePostResponse(post, isEn, country, ctx) {
  const lang = isEn ? 'en' : 'ru';
  const postId = post.id || 0;
  const postTitleText = (post.text || '').substring(0, 80).replace(/\n/g, ' ').trim() || (isEn ? 'Post' : 'Публикация');
  const postDescText = (post.text || '').substring(0, 160).replace(/\n/g, ' ').trim() || (isEn ? 'Archived publication' : 'Архивная публикация');
  const pageTitle = `${escapeHtml(postTitleText)} — ${isEn ? 'SOCHIAUTOPARTS Archive' : 'Архив SOCHIAUTOPARTS'}`;
  const canonicalUrl = isEn ? `${SITE_URL}/en/archive/post/${postId}` : `${SITE_URL}/archive/post/${postId}`;
  const telegramLink = `https://t.me/${CHANNEL_USERNAME}/${postId}`;

  // OG image
  const photos = post.photos || [];
  const videoThumbs = post.video_thumbnails || [];
  const ogImage = photos.length > 0 ? photos[0] : (videoThumbs.length > 0 ? videoThumbs[0] : `${SITE_URL}/logo.jpg`);

  // Date formatting
  const isoDate = post.date || '';
  let dateDisplay = '';
  try {
    const d = new Date(isoDate);
    if (!isNaN(d.getTime())) {
      const months = isEn
        ? ['January','February','March','April','May','June','July','August','September','October','November','December']
        : ['января','февраля','марта','апреля','мая','июня','июля','августа','сентября','октября','ноября','декабря'];
      dateDisplay = isEn
        ? `${months[d.getMonth()]} ${d.getDate()}, ${d.getFullYear()}`
        : `${d.getDate()} ${months[d.getMonth()]} ${d.getFullYear()} г.`;
    }
  } catch(e) {}

  // Views
  const views = post.views || 0;

  // Media HTML
  let mediaHtml = '';

  // Videos
  const videos = post.videos || [];
  if (videos.length > 0) {
    for (let i = 0; i < videos.length; i++) {
      const poster = videoThumbs[i] ? `poster="${escapeHtml(videoThumbs[i])}"` : '';
      mediaHtml += `<div class="archive-post-video"><video src="${escapeHtml(videos[i])}" ${poster} controls playsinline preload="metadata" referrerpolicy="no-referrer"><source src="${escapeHtml(videos[i])}" type="video/mp4"></video></div>`;
    }
  } else if (videoThumbs.length > 0) {
    // Has thumbnails but no direct video URLs — show as images with link to Telegram
    for (const thumb of videoThumbs) {
      mediaHtml += `<div class="archive-post-video"><a href="${escapeHtml(telegramLink)}" target="_blank" rel="noopener noreferrer" style="position:relative;display:block"><img src="${escapeHtml(thumb)}" alt="" referrerpolicy="no-referrer" loading="lazy" style="width:100%;max-height:600px;object-fit:contain;display:block;background:#000;border-radius:8px" /><div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:64px;height:64px;background:rgba(0,0,0,.65);border-radius:50%;display:flex;align-items:center;justify-content:center"><span style="color:#fff;font-size:1.5rem;margin-left:4px">▶</span></div></a></div>`;
    }
  }

  // Photos
  if (photos.length > 0) {
    mediaHtml += '<div class="archive-post-images">';
    for (const photo of photos) {
      mediaHtml += `<img class="archive-post-image" src="${escapeHtml(photo)}" alt="" referrerpolicy="no-referrer" loading="lazy" onclick="archiveLightbox(this.src)" />`;
    }
    mediaHtml += '</div>';
  }

  // Post text (formatted with line breaks)
  const textHtml = escapeHtml(post.text || '').replace(/\n/g, '<br>\n');

  // Hashtags (extract from text, support Arabic/Cyrillic/Latin)
  let tagsHtml = '';
  const textForTags = post.text || '';
  // Match hashtags: # followed by letters (including Arabic, Cyrillic), digits, underscores
  const hashtagMatches = textForTags.match(/#[\u0600-\u06FF\u0400-\u04FFa-zA-Z0-9_]+/g) || [];
  if (hashtagMatches.length > 0) {
    const tagLinks = hashtagMatches.slice(0, 15).map(tag => {
      const tagName = tag.substring(1);
      return `<a href="/tag/${encodeURIComponent(tagName)}.html" class="hashtag">${escapeHtml(tag)}</a>`;
    }).join(' ');
    tagsHtml = `<div class="post-tags">${tagLinks}</div>`;
  }

  // Ad blocks (region-filtered)
  const adBlocksHtml = await renderAdBlocks(lang, [country], ctx);

  // Shop widget (products from zap.online) — show 20 products (matching main page posts)
  let shopWidgetHtml = '';
  try {
    const products = await getProducts(ctx);
    // Shuffle products for variety, then take 20
    const shuffled = [...products];
    for (let i = shuffled.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
    }
    const shopProducts = shuffled.slice(0, 20);
    if (shopProducts.length > 0) {
      const shopPath = isEn ? '/en/shop' : '/shop';
      let productCards = '';
      for (const p of shopProducts) {
        const name = (p.name || '').length > 50 ? (p.name || '').substring(0, 50) + '...' : (p.name || '');
        const price = p.price ? Number(p.price).toLocaleString('ru-RU') + ' ₽' : '';
        const oldPrice = p.oldPrice ? Number(p.oldPrice).toLocaleString('ru-RU') + ' ₽' : '';
        const img = p.image || '';
        const pUrl = p.url || '#';
        const feedIcon = p.feedIcon || '';
        const feedName = p.feedName || '';
        productCards += `<a href="${escapeHtml(pUrl)}" class="widget-product" target="_blank" rel="nofollow noopener sponsored">${img ? `<img src="${escapeHtml(img)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.style.display='none'">` : `<span style="font-size:2rem">${feedIcon || '🛒'}</span>`}<div class="wp-name">${escapeHtml(name)}</div>${price ? `<div class="wp-price">${price}${oldPrice ? `<span class="wp-old-price">${oldPrice}</span>` : ''}</div>` : ''}${feedName ? `<div class="wp-feed">${escapeHtml(feedName)}</div>` : ''}</a>`;
      }
      shopWidgetHtml = `<div class="shop-widget"><div class="widget-header"><span class="widget-title">${isEn ? '🛒 Auto Parts Shop' : '🛒 Магазин автозапчастей'}</span><a href="${shopPath}" class="widget-link">${isEn ? 'All products →' : 'Все товары →'}</a></div><div class="widget-grid">${productCards}</div></div>`;
    }
  } catch(e) {
    console.error('Shop widget error:', e);
  }

  // NewsArticle schema
  const newsSchema = JSON.stringify({
    '@context': 'https://schema.org',
    '@type': 'NewsArticle',
    'headline': postTitleText,
    'description': postDescText,
    'datePublished': isoDate,
    'dateModified': isoDate,
    'author': { '@type': 'Organization', 'name': 'SochiAutoParts', 'url': `https://t.me/${CHANNEL_USERNAME}` },
    'publisher': { '@type': 'Organization', 'name': 'SochiAutoParts', 'logo': { '@type': 'ImageObject', 'url': `${SITE_URL}/logo.jpg` } },
    'mainEntityOfPage': { '@type': 'WebPage', '@id': canonicalUrl },
    'image': ogImage !== `${SITE_URL}/logo.jpg` ? ogImage : undefined
  });

  // Breadcrumb schema
  const breadcrumbSchema = JSON.stringify({
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    'itemListElement': [
      { '@type': 'ListItem', 'position': 1, 'name': isEn ? 'Home' : 'Главная', 'item': isEn ? `${SITE_URL}/en/` : `${SITE_URL}/` },
      { '@type': 'ListItem', 'position': 2, 'name': isEn ? 'Archive' : 'Архив', 'item': `${SITE_URL}/archive` },
      { '@type': 'ListItem', 'position': 3, 'name': postTitleText.substring(0, 50), 'item': canonicalUrl }
    ]
  });

  // Org schema
  const orgSchema = JSON.stringify({
    '@context': 'https://schema.org',
    '@type': 'Organization',
    'name': 'SochiAutoParts',
    'url': SITE_URL,
    'logo': `${SITE_URL}/logo.jpg`
  });

  // Verification meta tags
  const verificationMeta = '<meta name="verify-admitad" content="3c08bd9d2c"><meta name="takprodam-verification" content="cf451bd9-e5de-413f-990b-147d25c657e2">';

  const html = `<!DOCTYPE html>
<html lang="${lang}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>${pageTitle}</title>
<meta name="description" content="${escapeHtml(postDescText)}">
<meta name="robots" content="index, follow, max-image-preview:large, max-video-preview:-1">
<meta name="googlebot" content="index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1">
${verificationMeta}
<link rel="canonical" href="${canonicalUrl}">
<link rel="alternate" hreflang="ru" href="${SITE_URL}/archive/post/${postId}">
<link rel="alternate" hreflang="en" href="${SITE_URL}/en/archive/post/${postId}">
<link rel="alternate" hreflang="x-default" href="${SITE_URL}/archive/post/${postId}">
<meta property="og:type" content="article">
<meta property="og:title" content="${escapeHtml(postTitleText)}">
<meta property="og:description" content="${escapeHtml(postDescText)}">
<meta property="og:image" content="${escapeHtml(ogImage)}">
<meta property="og:image:width" content="640">
<meta property="og:image:height" content="640">
<meta property="og:url" content="${canonicalUrl}">
<meta property="og:site_name" content="SOCHIAUTOPARTS">
<meta property="og:locale" content="${isEn ? 'en_US' : 'ru_RU'}">
<meta property="og:locale:alternate" content="${isEn ? 'ru_RU' : 'en_US'}">
<meta property="article:published_time" content="${escapeHtml(isoDate)}">
<meta property="article:section" content="Autos">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="${escapeHtml(postTitleText)}">
<meta name="twitter:description" content="${escapeHtml(postDescText)}">
<meta name="twitter:image" content="${escapeHtml(ogImage)}">
<meta name="twitter:site" content="@sochiautoparts">
<meta name="twitter:creator" content="@sochiautoparts">
<meta name="author" content="SOCHIAUTOPARTS">
<meta name="theme-color" content="#2481CC">
<link rel="icon" href="/logo.jpg" type="image/jpeg">
<link rel="apple-touch-icon" href="/logo.jpg">
<link rel="preconnect" href="https://t.me">
<link rel="preconnect" href="https://www.googletagmanager.com">
<link rel="dns-prefetch" href="https://raw.githubusercontent.com">
<link rel="alternate" type="application/rss+xml" title="RSS" href="${SITE_URL}${isEn ? '/en/rss.xml' : '/rss.xml'}">
<link rel="manifest" href="/manifest.json">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Manrope:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<script type="application/ld+json">${orgSchema}</script>
<script type="application/ld+json">${breadcrumbSchema}</script>
<script type="application/ld+json">${newsSchema}</script>
<script async src="https://www.googletagmanager.com/gtag/js?id=G-2GZ7FKV6CK"></script>
<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments)}gtag('js',new Date());gtag('config','G-2GZ7FKV6CK');</script>
<style>${ARCHIVE_POST_CSS}</style>
</head>
<body>
<canvas id="matrix-bg"></canvas>
${renderHeader(lang, 'archive')}
<main id="main-content" class="archive-post-container" style="padding-top:2rem">
<a href="${isEn ? '/en/archive' : '/archive'}" class="archive-post-back">← ${isEn ? 'Back to archive' : 'Назад к архиву'}</a>
<nav class="archive-breadcrumb">
<a href="${isEn ? '/en/' : '/'}">${isEn ? 'Home' : 'Главная'}</a>
<span class="archive-breadcrumb-sep">/</span>
<a href="${isEn ? '/en/archive' : '/archive'}">${isEn ? 'Archive' : 'Архив'}</a>
<span class="archive-breadcrumb-sep">/</span>
<span>${escapeHtml(postTitleText.substring(0, 50))}</span>
</nav>
<article>
<h1 style="margin-bottom:1rem">${escapeHtml(postTitleText)}</h1>
<div class="archive-post-date">
${dateDisplay ? `<span>📅 ${escapeHtml(dateDisplay)}</span>` : ''}
${views ? `<span>👁 ${views}</span>` : ''}
</div>
${mediaHtml}
<div class="archive-post-text">${textHtml}</div>
${tagsHtml}
<a href="${escapeHtml(telegramLink)}" class="archive-tg-link" target="_blank" rel="noopener noreferrer">${isEn ? 'Open in Telegram' : 'Открыть в Telegram'}</a>
</article>
${adBlocksHtml ? `<div class="archive-ad-section"><h3 class="archive-ad-title">${isEn ? '📢 Recommendations' : '📢 Рекомендации'}</h3>${adBlocksHtml}</div>` : ''}
${shopWidgetHtml}
</main>
<footer>
<p>© 2026 SOCHIAUTOPARTS. ${isEn ? 'All rights reserved.' : 'Все права защищены.'}</p>
<div class="footer-links">
<a href="${isEn ? '/en/privacy' : '/privacy'}">${isEn ? 'Privacy' : 'Конфиденциальность'}</a>
<a href="${isEn ? '/en/contacts' : '/contacts'}">${isEn ? 'Contacts' : 'Контакты'}</a>
<a href="https://t.me/${CHANNEL_USERNAME}" target="_blank" rel="nofollow noopener noreferrer">Telegram</a>
</div>
</footer>
<script>try{var t=localStorage.getItem('theme');if(t)document.documentElement.setAttribute('data-theme',t)}catch(e){}document.querySelectorAll('.theme-btn').forEach(function(b){b.addEventListener('click',function(){document.documentElement.setAttribute('data-theme',this.dataset.theme);localStorage.setItem('theme',this.dataset.theme)})});var mb=document.getElementById('mobileMenuBtn'),mn=document.getElementById('mainNav');if(mb&&mn){mb.addEventListener('click',function(){mn.classList.toggle('active')})}</script>
<script>function archiveLightbox(s){var o=document.createElement("div");o.className="archive-lightbox";o.onclick=function(){o.remove()};var i=document.createElement("img");i.src=s;i.setAttribute("referrerpolicy","no-referrer");o.appendChild(i);document.body.appendChild(o);requestAnimationFrame(function(){o.classList.add("active")});document.addEventListener("keydown",function h(e){if(e.key==="Escape"){o.remove();document.removeEventListener("keydown",h)}})}</script>
</body>
</html>`;

  return new Response(html, {
    status: 200,
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
      'Cache-Control': 'public, max-age=3600, s-maxage=3600, stale-while-revalidate=86400',
      'Content-Language': lang,
      'X-Robots-Tag': 'index, follow, max-image-preview:large, max-video-preview:-1',
      'Vary': 'Accept-Encoding, Cloudflare-Viewer-Country',
    },
  });
}


// =============================================================================
// Render ad blocks with regional filtering (matches old Worker)
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
// Header (matches old Worker v27 structure)
// =============================================================================

function renderHeader(lang, activePage) {
  const basePath = lang === 'en' ? '/en/' : '/';
  const activeHome = activePage === 'home' ? ' active' : '';
  const activeArticles = activePage === 'articles' ? ' active' : '';
  const activeShop = activePage === 'shop' ? ' active' : '';
  const activeArchive = activePage === 'archive' ? ' active' : '';

  return `<header class="site-header">
<div class="container">
<div class="header-content">
<a href="${basePath}" class="logo">
<img src="/logo.jpg" alt="SOCHIAUTOPARTS Logo" class="logo-icon" width="44" height="44" loading="eager" referrerpolicy="no-referrer">
SOCHIAUTOPARTS
</a>
<nav class="main-nav" id="mainNav">
<a href="${basePath}" class="${activeHome}">${lang === 'ru' ? 'Главная' : 'Home'}</a>
<a href="${basePath}articles" class="${activeArticles}">${lang === 'ru' ? 'Статьи' : 'Articles'}</a>
<a href="${basePath}archive" class="${activeArchive}">${lang === 'ru' ? '📁 Архив' : '📁 Archive'}</a>
<a href="${lang === 'en' ? '/en/shop' : '/shop'}" class="${activeShop}">${lang === 'ru' ? '🛒 Магазин' : '🛒 Shop'}</a>
</nav>
<div class="controls-group">
<button class="mobile-menu-btn" id="mobileMenuBtn" aria-label="${lang === 'ru' ? 'Меню' : 'Menu'}">☰</button>
<nav class="lang-switcher">
<a href="/" class="lang-btn ${lang === 'ru' ? 'active' : ''}">RU</a>
<a href="/en/" class="lang-btn ${lang === 'en' ? 'active' : ''}">EN</a>
</nav>
<div class="theme-toggle">
<button class="theme-btn" data-theme="light" aria-label="Light theme">${SUN_ICON}</button>
<button class="theme-btn" data-theme="dark" aria-label="Dark theme">${MOON_ICON}</button>
</div>
</div>
</div>
</div>
</header>`;
}


// =============================================================================
// CSS for archive post pages (matches old Worker v27)
// =============================================================================

const ARCHIVE_POST_CSS = `
:root{--primary:#2481CC;--primary-dark:#1D6FAD;--primary-light:#E6F3FF;--secondary:#2AABEE;--accent:#0088cc;--bg-body:#F4F4F5;--bg-card:#FFFFFF;--bg-header:rgba(255,255,255,0.95);--bg-hover:#F0F0F0;--text-main:#000;--text-muted:#707579;--border-color:#DADCE0;--border-light:#E8E8E8;--radius:12px;--font-main:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;--shadow-sm:0 1px 2px rgba(0,0,0,.05);--shadow-md:0 4px 12px rgba(0,0,0,.08)}
[data-theme="dark"]{--bg-body:#0F1115;--bg-card:#161B22;--bg-header:rgba(22,27,34,0.95);--bg-hover:#1C2128;--text-main:#F0F6FC;--text-muted:#8B949E;--border-color:#30363D;--border-light:#21262D;--shadow-sm:0 1px 2px rgba(0,0,0,.3);--shadow-md:0 4px 12px rgba(0,0,0,.4)}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:var(--font-main);background:var(--bg-body);color:var(--text-main);line-height:1.6}
a{color:var(--primary);text-decoration:none}
a:hover{text-decoration:underline}
.container{max-width:800px;margin:0 auto;padding:0 16px}
.site-header{background:var(--bg-header);padding:0.75rem 0;border-bottom:1px solid var(--border-color);position:sticky;top:0;z-index:1000;backdrop-filter:blur(20px)}
.header-content{display:flex;justify-content:space-between;align-items:center}
.logo{font-size:1.375rem;font-weight:700;color:var(--text-main);display:flex;align-items:center;gap:0.625rem;font-family:'Manrope','Inter',sans-serif;white-space:nowrap}
.logo-icon{width:44px;height:44px;border-radius:50%;object-fit:cover;border:2px solid var(--border-light)}
.main-nav{display:flex;gap:0.25rem}
.main-nav a{padding:0.5rem 0.75rem;border-radius:var(--radius);font-size:0.9rem;font-weight:500;color:var(--text-muted);transition:background .15s,color .15s}
.main-nav a:hover{text-decoration:none;background:var(--bg-hover);color:var(--text-main)}
.main-nav a.active{color:var(--primary);font-weight:600}
.controls-group{display:flex;align-items:center;gap:0.5rem}
.lang-switcher{display:flex;gap:0.25rem}
.lang-btn{padding:4px 8px;border-radius:6px;font-size:0.75rem;font-weight:600;color:var(--text-muted);border:1px solid var(--border-color);transition:all .15s}
.lang-btn.active{background:var(--primary);color:#fff;border-color:var(--primary)}
.theme-toggle{display:flex;gap:0.25rem}
.theme-btn{width:32px;height:32px;border-radius:8px;border:1px solid var(--border-color);background:var(--bg-card);cursor:pointer;font-size:0.875rem;display:flex;align-items:center;justify-content:center;transition:all .15s}
.theme-btn:hover{border-color:var(--primary)}
.mobile-menu-btn{display:none;width:40px;height:40px;border-radius:8px;border:1px solid var(--border-color);background:var(--bg-card);cursor:pointer;font-size:1.25rem;color:var(--text-main)}
.archive-post-container{max-width:800px;margin:0 auto;padding:20px 16px 40px}
.archive-post-back{display:inline-flex;align-items:center;gap:6px;color:var(--text-muted);text-decoration:none;font-size:0.9rem;margin-bottom:24px}
.archive-post-back:hover{color:var(--text-main)}
.archive-breadcrumb{display:flex;align-items:center;flex-wrap:wrap;gap:8px;font-size:0.875rem;color:var(--text-muted);margin-bottom:24px}
.archive-breadcrumb a{color:var(--text-muted);text-decoration:none}
.archive-breadcrumb a:hover{color:var(--primary)}
.archive-breadcrumb-sep{color:var(--border-color)}
.archive-post-date{font-size:0.85rem;color:var(--text-muted);margin-bottom:16px;display:flex;align-items:center;gap:16px;flex-wrap:wrap}
.archive-post-text{font-size:1.05rem;line-height:1.8;color:var(--text-main);margin-bottom:24px;white-space:pre-wrap;word-break:break-word}
.archive-post-images{display:grid;grid-template-columns:1fr;gap:12px;margin-bottom:24px}
@media(min-width:640px){.archive-post-images{grid-template-columns:repeat(2,1fr)}}
.archive-post-image{width:100%;border-radius:8px;cursor:pointer;transition:transform .15s}
.archive-post-image:hover{transform:scale(1.02)}
.archive-post-video{width:100%;border-radius:8px;overflow:hidden;margin-bottom:12px;background:#000}
.archive-post-video video{width:100%;max-height:600px;display:block;object-fit:contain;background:#000}
.archive-tg-link{display:inline-flex;align-items:center;gap:8px;padding:10px 20px;background:#0088cc;color:#fff;border-radius:8px;text-decoration:none;font-size:0.925rem;font-weight:500;transition:opacity .15s}
.archive-tg-link:hover{opacity:.9;text-decoration:none}
.post-tags{margin:1.5rem 0;display:flex;flex-wrap:wrap;gap:0.5rem}
.hashtag{display:inline-block;padding:4px 12px;background:var(--primary-light);color:var(--primary);border-radius:9999px;font-size:0.8125rem;font-weight:600;text-decoration:none;transition:opacity .15s}
.hashtag:hover{opacity:.8;text-decoration:none}
[data-theme="dark"] .hashtag{background:#1a3a5c;color:#58A6FF}
.ad-blocks-container{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:16px;margin:1.5rem 0}
.ad-block-item{background:var(--bg-card);border:1px solid var(--border-light);border-radius:var(--radius);overflow:hidden;transition:box-shadow .2s,transform .15s}
.ad-block-item:hover{box-shadow:var(--shadow-md);transform:translateY(-2px)}
.ad-block-media{width:100%;height:140px;overflow:hidden;display:flex;align-items:center;justify-content:center;background:var(--bg-hover)}
.ad-block-media img{width:100%;height:100%;object-fit:contain;padding:8px}
.ad-block-category{display:inline-block;padding:2px 8px;background:var(--primary-light);color:var(--primary);border-radius:4px;font-size:0.7rem;font-weight:600;margin:8px 12px 0}
[data-theme="dark"] .ad-block-category{background:#1a3a5c;color:#58A6FF}
.ad-block-title{font-size:0.9rem;font-weight:600;margin:6px 12px 0;color:var(--text-main);line-height:1.3}
.ad-block-desc{font-size:0.8rem;color:var(--text-muted);margin:4px 12px 0;line-height:1.4}
.ad-block-btn{margin:8px 12px 12px;display:inline-flex;align-items:center;gap:4px;padding:6px 16px;background:var(--primary);color:#fff;border-radius:6px;font-size:0.8rem;font-weight:600;transition:opacity .15s}
.ad-block-btn:hover{opacity:.85}
.ad-block-legal{font-size:0.7rem;color:var(--text-muted);padding:0 12px 8px}
.archive-ad-section{margin:2rem 0 0;padding:1.5rem 0 0;border-top:1px solid var(--border-color)}
.archive-ad-title{font-size:1.1rem;font-weight:700;margin-bottom:1rem;color:var(--text-main)}
.shop-widget{margin:2rem 0;padding:1.5rem;border-top:1px solid var(--border-color)}
.widget-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem}
.widget-title{font-size:1.1rem;font-weight:700}
.widget-link{color:var(--primary);font-size:0.85rem;font-weight:600}
.widget-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:12px}
.widget-product{display:block;padding:8px;border:1px solid var(--border-light);border-radius:8px;text-decoration:none;color:inherit;transition:box-shadow .15s}
.widget-product:hover{box-shadow:var(--shadow-sm);text-decoration:none}
.widget-product img{width:100%;height:80px;object-fit:contain;margin-bottom:6px}
.wp-name{font-size:0.8rem;color:var(--text-main);line-height:1.3;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}
.wp-price{font-size:0.85rem;font-weight:700;color:var(--primary);margin-top:4px}
footer{text-align:center;padding:2rem 0;color:var(--text-muted);font-size:0.875rem;border-top:1px solid var(--border-color);margin-top:2rem}
.footer-links{display:flex;justify-content:center;gap:1rem;margin-top:0.5rem}
.footer-links a{color:var(--text-muted);text-decoration:none;font-size:0.8rem}
.footer-links a:hover{color:var(--primary)}
.archive-lightbox{position:fixed;inset:0;background:rgba(0,0,0,.85);display:flex;align-items:center;justify-content:center;z-index:9999;cursor:pointer;opacity:0;transition:opacity .2s}
.archive-lightbox.active{opacity:1}
.archive-lightbox img{max-width:90vw;max-height:90vh;border-radius:8px;object-fit:contain}
#matrix-bg{position:fixed;top:0;left:0;width:100%;height:100%;z-index:-1;pointer-events:none;opacity:0.03}
@media(max-width:768px){.main-nav{display:none;position:absolute;top:100%;left:0;right:0;background:var(--bg-card);border-bottom:1px solid var(--border-color);flex-direction:column;padding:1rem;gap:0.5rem;box-shadow:var(--shadow-md)}.main-nav.active{display:flex}.mobile-menu-btn{display:flex;align-items:center;justify-content:center}.archive-post-container{padding:16px 12px 32px}.archive-post-text{font-size:1rem}}
`;


// =============================================================================
// GitHub Pages proxy
// =============================================================================

async function proxyToGitHubPages(path, request, ctx) {
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

    // Clone and cache
    const responseToCache = response.clone();
    ctx.waitUntil(cache.put(cacheKey, responseToCache));

    return addSiteHeaders(response, request.url, request);

  } catch (error) {
    return new Response(`Worker error: ${error.message}`, {
      status: 500,
      headers: { 'Content-Type': 'text/plain' },
    });
  }
}


// =============================================================================
// Helper functions
// =============================================================================

function addSiteHeaders(response, requestUrl, request) {
  const newHeaders = new Headers(response.headers);

  const contentType = newHeaders.get('Content-Type') || '';
  if (contentType.includes('text/html')) {
    newHeaders.set('Content-Type', 'text/html; charset=utf-8');
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


// =============================================================================
// Dynamic archive pagination handler: /archive/page/{n}
// Returns a JSON list of posts for page N (used for infinite scroll / lazy loading)
// =============================================================================

async function handleArchivePage(pageNum, isEn, country, request, ctx) {
  try {
    if (pageNum < 1) pageNum = 1;

    const pageData = await getTelegramPage(pageNum, ctx);
    if (!pageData || !Array.isArray(pageData) || pageData.length === 0) {
      return new Response(JSON.stringify({ posts: [], page: pageNum, has_more: false }), {
        headers: {
          'Content-Type': 'application/json; charset=utf-8',
          'Cache-Control': 'public, max-age=300',
          'Access-Control-Allow-Origin': getAllowedOrigin(request),
        },
      });
    }

    const meta = await getTelegramMeta(ctx);
    const totalPages = meta.pages_count || 1;

    // Return lightweight post summaries for archive listing
    const posts = pageData.map(post => {
      const text = post.text || '';
      const photos = post.photos || [];
      const videoThumbs = post.video_thumbnails || [];
      const thumb = photos.length > 0 ? photos[0] : (videoThumbs.length > 0 ? videoThumbs[0] : '');
      return {
        id: post.id,
        text: text.substring(0, 200),
        date: post.date || '',
        views: post.views || 0,
        thumb,
        has_video: (post.videos || []).length > 0 || videoThumbs.length > 0,
        photo_count: photos.length,
      };
    });

    return new Response(JSON.stringify({
      posts,
      page: pageNum,
      total_pages: totalPages,
      has_more: pageNum < totalPages,
    }), {
      headers: {
        'Content-Type': 'application/json; charset=utf-8',
        'Cache-Control': 'public, max-age=300, s-maxage=300',
        'Access-Control-Allow-Origin': getAllowedOrigin(request),
      },
    });
  } catch (e) {
    console.error('Archive page error:', e);
    return new Response(JSON.stringify({ posts: [], page: pageNum, has_more: false, error: e.message }), {
      status: 500,
      headers: { 'Content-Type': 'application/json; charset=utf-8' },
    });
  }
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
