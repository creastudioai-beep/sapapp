// ============================================================
// SOCHIAUTOPARTS Cloudflare Worker — Lightweight Static Proxy
// ============================================================
// Replaces the 9000+ line Worker with a lightweight version that
// serves pre-generated static HTML from GitHub Pages.
//
// Architecture: GitHub Actions (Python generator) → GitHub Pages
//   → Cloudflare Worker (this file) → Cache API → Visitor
//
// GitHub Pages: https://creastudioai-beep.github.io/sapapp/
// Production:   https://sochiautoparts.ru
// ============================================================

const DEFAULT_GITHUB_PAGES_URL = 'https://creastudioai-beep.github.io/sapapp';
const DEFAULT_ADMITAD_BASE_URL = 'https://ujhjj.com/g/on8kt46xpp3c08bd9d2c648980e865/';
const DEFAULT_ADMITAD_SUBID = 'TEN';

// MIME types
const MIME = {
  html:'text/html; charset=utf-8', json:'application/json; charset=utf-8',
  xml:'application/xml; charset=utf-8', txt:'text/plain; charset=utf-8',
  jpg:'image/jpeg', png:'image/png', svg:'image/svg+xml', ico:'image/x-icon',
  css:'text/css; charset=utf-8', js:'application/javascript; charset=utf-8',
  woff:'font/woff', woff2:'font/woff2',
};

// Cache TTLs (seconds): s-maxage + stale-while-revalidate
const TTL = {
  html:  { s:600,    w:3600 },   // 10 min, SWR 1h
  data:  { s:3600,   w:86400 },  // 1h, SWR 1 day  (json/xml)
  asset: { s:604800, w:604800 }, // 7 days (images/fonts)
  code:  { s:86400,  w:86400 },  // 1 day  (css/js)
  other: { s:3600,   w:86400 },
};

// Security headers
const SEC = {
  'X-Content-Type-Options':'nosniff',
  'X-Frame-Options':'SAMEORIGIN',
  'X-XSS-Protection':'1; mode=block',
  'Referrer-Policy':'strict-origin-when-cross-origin',
  'Permissions-Policy':'camera=(), microphone=(), geolocation=()',
  'Strict-Transport-Security':'max-age=31536000; includeSubDomains; preload',
  'Content-Security-Policy':"default-src 'self'; frame-src *.github.io; frame-ancestors 'none'",
};

// Legacy .html URL redirects (301)
const LEGACY_REDIRECTS = {
  '/privacy.html':'/privacy', '/contacts.html':'/contacts',
  '/articles.html':'/articles', '/shop/index.html':'/shop',
};

// ── Helpers ──────────────────────────────────────────────────

function contentType(p) {
  const ext = p.split('.').pop().toLowerCase();
  return MIME[ext] || MIME.html;
}

function cacheTTL(p) {
  const ext = p.split('.').pop().toLowerCase();
  if (['jpg','png','svg','ico','webp'].includes(ext)) return TTL.asset;
  if (['woff','woff2','ttf','otf','eot'].includes(ext)) return TTL.asset;
  if (ext === 'css' || ext === 'js') return TTL.code;
  if (ext === 'json' || ext === 'xml') return TTL.data;
  if (ext === 'html') return TTL.html;
  return TTL.other;
}

function respond(body, status, ct, ttl, extra = {}) {
  return new Response(body, {
    status,
    headers: {
      ...SEC,
      'Content-Type': ct,
      'Cache-Control': `public, s-maxage=${ttl.s}, stale-while-revalidate=${ttl.w}`,
      ...extra,
    },
  });
}

// Shared error page generator (Russian-styled, matches site design)
function errorPage(code, title, message, color, extraMeta = '') {
  const html = `<!DOCTYPE html><html lang="ru"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>${code} — ${title} | SochiAutoParts</title>
<meta name="robots" content="noindex, nofollow">${extraMeta}
<style>*{margin:0;padding:0;box-sizing:border-box}body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f5f5f5;color:#333;display:flex;align-items:center;justify-content:center;min-height:100vh;padding:1rem}.c{text-align:center;max-width:480px}.n{font-size:6rem;font-weight:700;color:${color};line-height:1}h1{font-size:1.5rem;margin:1rem 0 .5rem}p{color:#666;margin-bottom:1.5rem}a{display:inline-block;padding:.75rem 2rem;background:${color};color:#fff;text-decoration:none;border-radius:8px;font-weight:500;transition:background .2s}a:hover{filter:brightness(.85)}.r{color:#999;font-size:.875rem;margin-top:1rem}</style></head><body><div class="c"><div class="n">${code}</div><h1>${title}</h1><p>${message}</p><a href="/">На главную</a></div></body></html>`;
  return respond(html, code, MIME.html, TTL.html);
}

function page404() {
  return errorPage(404, 'Страница не найдена',
    'Запрашиваемая страница не существует или была перемещена.', '#d32f2f',
    '<meta http-equiv="refresh" content="8;url=/">');
}
function page410() {
  return errorPage(410, 'Ресурс удалён',
    'Запрашиваемый ресурс был окончательно удалён.', '#e65100');
}
function page502() {
  return errorPage(502, 'Временная ошибка',
    'Сервер временно недоступен. Попробуйте позже.', '#1565c0');
}

// ============================================================
// Path resolution: pretty URL → GitHub Pages file path
// ============================================================
function resolvePath(pathname) {
  let path = decodeURIComponent(pathname).replace(/\/+/g, '/');
  if (path === '/' || path === '') return '/index.html';

  const c = path.replace(/^\//, ''); // remove leading slash

  // Static files served as-is
  if (['robots.txt','manifest.json','rss.xml','logo.jpg'].includes(c)) return '/' + c;
  if (/^sitemap.*\.xml$/.test(c)) return '/' + c;

  // Trailing slash → directory index (/en/ → /en/index.html)
  if (c.endsWith('/')) return '/' + c + 'index.html';

  // /post/{id}/amp → /post/{id}/amp.html (also /en/post/{id}/amp)
  const amp = c.match(/^(en\/)?post\/([^/]+)\/amp$/);
  if (amp) return `/${amp[1]||''}post/${amp[2]}/amp.html`;

  // /archive/page-{N} → /archive/page-{N}.html (also /en/archive/page-{N})
  const ap = c.match(/^(en\/)?archive\/page-(\d+)$/);
  if (ap) return `/${ap[1]||''}archive/page-${ap[2]}.html`;

  // Collection routes → directory index (no trailing slash version)
  // e.g. /archive → /archive/index.html, /en/shop → /en/shop/index.html
  const dirs = ['archive','articles','shop','contacts','privacy','amp',
    'en/archive','en/articles','en/shop','en/contacts','en/privacy','en/amp'];
  if (dirs.includes(c)) return '/' + c + '/index.html';

  // Everything else → append .html
  // /post/{id} /en/post/{id} /tag/{name} /product/{id}
  // /article/{id} /ads/{cat} /shop/category/{slug}
  // /archive/post/{id} /en/archive/post/{id} /en/ads/{cat} etc.
  return '/' + c + '.html';
}

// ============================================================
// API endpoint handler
// ============================================================
function handleAPI(pathname, url, admitadBase, admitadSubId) {
  // /api/{campaignId} → 302 redirect to Admitad affiliate URL
  const m = pathname.match(/^\/api\/([a-zA-Z0-9_-]+)$/);
  if (m) {
    const id = m[1];
    // Skip reserved API words
    if (!['search','stats','health','cache','sync','shop'].includes(id)) {
      return Response.redirect(`${admitadBase}?erid=${id}&subid=${admitadSubId}`, 302);
    }
  }

  // /api/search?q=...&lang=ru|en → 302 redirect to search page
  if (pathname === '/api/search') {
    const q = url.searchParams.get('q') || '';
    const lang = url.searchParams.get('lang') || 'ru';
    return Response.redirect(`${lang==='en'?'/en/':'/'}?q=${encodeURIComponent(q)}`, 302);
  }

  // /api/stats → JSON with site stats
  if (pathname === '/api/stats') {
    return respond(JSON.stringify({
      status:'ok', version:'1.0.0', architecture:'github-pages-proxy',
      limits:{ max_posts:10000, archive_max_posts:90000 },
      routes:['/','/en/','/post/{id}','/en/post/{id}','/post/{id}/amp',
        '/en/post/{id}/amp','/archive','/archive/post/{id}','/en/archive/post/{id}',
        '/archive/page-{N}','/tag/{name}','/en/tag/{name}','/articles','/en/articles',
        '/article/{id}','/en/article/{id}','/shop','/en/shop','/product/{id}',
        '/en/product/{id}','/shop/category/{slug}','/en/shop/category/{slug}',
        '/ads/{category}','/en/ads/{category}','/contacts','/en/contacts',
        '/privacy','/en/privacy','/amp/','/en/amp/'],
      static_files:['robots.txt','manifest.json','rss.xml','sitemap*.xml','logo.jpg'],
      api_endpoints:['/api/{campaignId}','/api/search','/api/stats'],
    }, null, 2), 200, MIME.json, TTL.data);
  }

  return respond(JSON.stringify({error:'Not Found'}), 404, MIME.json, TTL.data);
}

// ============================================================
// Main fetch handler
// ============================================================
export default {
  async fetch(request, env, ctx) {
    const baseUrl    = env.GITHUB_PAGES_URL  || DEFAULT_GITHUB_PAGES_URL;
    const admitadBase = env.ADMITAD_BASE_URL || DEFAULT_ADMITAD_BASE_URL;
    const admitadSubId = env.ADMITAD_SUBID   || DEFAULT_ADMITAD_SUBID;

    let url;
    try { url = new URL(request.url); } catch {
      return respond('Bad Request', 400, MIME.txt, TTL.other);
    }
    const pathname = url.pathname;

    // ── 1. Legacy: /ru/* → /* (Russian is default, no prefix needed) ──
    if (pathname.startsWith('/ru/') || pathname === '/ru') {
      const target = pathname === '/ru' ? '/' : pathname.slice(3);
      return Response.redirect(new URL(target, request.url).href, 301);
    }

    // ── 2. Legacy: /m/* → 410 Gone (removed media proxy) ──
    if (pathname.startsWith('/m/') || pathname === '/m') return page410();

    // ── 3. Legacy .html redirects (301) ──
    if (LEGACY_REDIRECTS[pathname]) {
      return Response.redirect(new URL(LEGACY_REDIRECTS[pathname], request.url).href, 301);
    }

    // ── 4. API endpoints ──
    if (pathname.startsWith('/api/')) return handleAPI(pathname, url, admitadBase, admitadSubId);

    // ── 5. Resolve path & proxy from GitHub Pages ──
    const filePath = resolvePath(pathname);
    const upstreamUrl = baseUrl + filePath;

    // Check Cloudflare Cache API first
    const cache = caches.default;
    const cacheKey = new Request(upstreamUrl, { method: 'GET' });
    try {
      const cached = await cache.match(cacheKey);
      if (cached) {
        const ct = cached.headers.get('Content-Type') || contentType(filePath);
        return respond(cached.body, 200, ct, cacheTTL(filePath), { 'X-Cache':'HIT' });
      }
    } catch { /* Cache API unavailable, proceed to fetch */ }

    // Fetch from GitHub Pages
    let upstreamResp;
    try {
      upstreamResp = await fetch(upstreamUrl, {
        headers:{ 'User-Agent':'SochiAutoParts-Worker/1.0' },
        cf:{ cacheTtl:300 }, // CDN cache 5 min for upstream fetches
      });
    } catch { return page502(); }

    // 404: try directory index fallback before giving up
    if (upstreamResp.status === 404) {
      if (!filePath.endsWith('/index.html')) {
        const dirPath = filePath.replace(/\.html$/, '/index.html');
        try {
          const dirResp = await fetch(baseUrl + dirPath, {
            headers:{ 'User-Agent':'SochiAutoParts-Worker/1.0' }, cf:{ cacheTtl:300 },
          });
          if (dirResp.ok) {
            const body = await dirResp.text();
            const ct = contentType(dirPath);
            const resp = respond(body, 200, ct, cacheTTL(dirPath), { 'X-Cache':'MISS' });
            ctx.waitUntil(cache.put(cacheKey, resp.clone()));
            return resp;
          }
        } catch { /* fall through to 404 */ }
      }
      return page404();
    }

    // Other upstream errors → 502
    if (!upstreamResp.ok) return page502();

    // Success: return with security + cache headers
    const body = await upstreamResp.text();
    const ct = contentType(filePath);
    const resp = respond(body, 200, ct, cacheTTL(filePath), { 'X-Cache':'MISS' });

    // Store in Cache API (background, non-blocking)
    ctx.waitUntil(cache.put(cacheKey, new Response(body, {
      headers:{ 'Content-Type':ct },
    })));

    return resp;
  },
};
