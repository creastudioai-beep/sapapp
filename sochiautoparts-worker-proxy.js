/**
 * SochiAutoParts Cloudflare Worker v5.0
 *
 * Proxies sochiautoparts.ru → GitHub Pages static site.
 *
 * Architecture:
 *   1. /api/{id}          → Admitad affiliate redirect (lookup by program ID)
 *   2. /rss.xml            → serve from GitHub Pages /rss.xml
 *   3. /feed.xml           → serve from GitHub Pages /rss.xml (compat alias)
 *   4. All other requests  → proxy from GitHub Pages
 *   5. 404 from GH Pages  → try .html, then /index.html, then custom 404
 *
 * GitHub Pages URL: https://creastudioai-beep.github.io/sapapp/
 * Route: sochiautoparts.ru/* → creastudioai-beep.github.io/sapapp/*
 */

const GITHUB_PAGES_BASE = 'https://creastudioai-beep.github.io/sapapp';
const SITE_URL = 'https://sochiautoparts.ru';

// Cache settings
const CACHE_TTL_BROWSER = 300;    // 5 minutes browser cache
const CACHE_TTL_EDGE = 3600;      // 1 hour edge cache

// Admitad program data — fetched from pipeline and cached
const ADMITAD_DATA_URL = 'https://raw.githubusercontent.com/creastudioai-beep/pr/main/data/admitad_ads.json';
let admitadCache = null;
let admitadCacheTime = 0;
const ADMITAD_CACHE_TTL = 3600000; // 1 hour in ms

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

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    let path = url.pathname;

    // --- Admitad affiliate redirect: /api/{programId} ---
    // The static HTML generates links like href="/api/123981"
    // This handler looks up the program by ID and redirects to its goto_link
    const apiMatch = path.match(/^\/api\/(\d+)$/);
    if (apiMatch) {
      return handleAffiliateRedirect(apiMatch[1], request, ctx);
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

    // --- Handle paths without trailing slash that look like directories ---
    // e.g. /ads/autoparts → try /ads/autoparts.html first, then /ads/autoparts/index.html
    if (!path.endsWith('.html') && !path.endsWith('.xml') && !path.endsWith('.json') &&
        !path.endsWith('.txt') && !path.endsWith('.css') && !path.endsWith('.js') &&
        !path.endsWith('.jpg') && !path.endsWith('.png') && !path.endsWith('.ico') &&
        !path.endsWith('.svg') && !path.endsWith('.webp') && !path.endsWith('.woff2') &&
        !path.includes('.') && !path.endsWith('/')) {
      // Will try .html first in the proxy function
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
// Affiliate redirect handler
// =============================================================================

async function handleAffiliateRedirect(programId, request, ctx) {
  try {
    // Fetch Admitad data (with caching)
    const programs = await getAdmitadPrograms(ctx);

    // Find the program by ID (try both string and number comparison)
    const prog = programs.find(p => String(p.id) === String(programId));

    if (prog) {
      // Try all possible affiliate URL fields
      const affiliateUrl = prog.goto_link || prog.gotoLink || prog.affiliateUrl || prog.affiliate_url || '';
      if (affiliateUrl) {
        return Response.redirect(affiliateUrl, 302);
      }
    }

    // Fallback: redirect to homepage if program not found
    return Response.redirect(SITE_URL, 302);
  } catch (e) {
    console.error('Affiliate redirect error:', e);
    return Response.redirect(SITE_URL, 302);
  }
}


async function getAdmitadPrograms(ctx) {
  const now = Date.now();
  if (admitadCache && (now - admitadCacheTime) < ADMITAD_CACHE_TTL) {
    return admitadCache;
  }

  try {
    const response = await fetch(ADMITAD_DATA_URL, {
      headers: { 'User-Agent': 'SochiAutoParts-Worker/5.0' },
      cf: { cacheTtl: 3600, cacheEverything: true },
    });

    if (!response.ok) {
      throw new Error(`Admitad fetch failed: ${response.status}`);
    }

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
// GitHub Pages proxy
// =============================================================================

async function proxyToGitHubPages(path, request, ctx) {
  const headers = new Headers();
  headers.set('User-Agent', 'SochiAutoParts-Worker/5.0');
  headers.set('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8');

  // Check cache first
  const cache = caches.default;
  const cacheKey = new Request(GITHUB_PAGES_BASE + path, { method: 'GET' });

  let cachedResponse = await cache.match(cacheKey);
  if (cachedResponse) {
    return addSiteHeaders(new Response(cachedResponse.body, cachedResponse), request.url);
  }

  // Helper: fetch from GH Pages with given path
  async function fetchFromGH(fetchPath) {
    const ghUrl = GITHUB_PAGES_BASE + fetchPath;
    return await fetch(ghUrl, {
      method: 'GET',
      headers: headers,
      cf: {
        cacheTtl: CACHE_TTL_EDGE,
        cacheEverything: true,
      },
    });
  }

  // Fetch from GitHub Pages
  try {
    let response = await fetchFromGH(path);

    // If 404 and path has no extension, try adding .html
    if (response.status === 404 && !path.endsWith('.html') && !path.endsWith('.xml') &&
        !path.endsWith('.json') && !path.endsWith('.txt') && !path.includes('.')) {
      const htmlPath = path + '.html';
      const htmlResponse = await fetchFromGH(htmlPath);
      if (htmlResponse.ok) {
        response = htmlResponse;
      }
    }

    // If still 404 and path doesn't end with /index.html, try directory index
    if (response.status === 404 && !path.endsWith('/index.html')) {
      const dirPath = path.replace(/\.html$/, '') + '/index.html';
      const dirResponse = await fetchFromGH(dirPath);
      if (dirResponse.ok) {
        response = dirResponse;
      }
    }

    // If still 404, return custom 404 page
    if (response.status === 404) {
      return new Response(generate404Page(), {
        status: 404,
        headers: {
          'Content-Type': 'text/html; charset=utf-8',
          'Cache-Control': 'public, max-age=60',
        },
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

    return addSiteHeaders(response, request.url);

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

function addSiteHeaders(response, requestUrl) {
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

  // CORS headers for RSS/sitemap
  if (requestUrl.includes('.xml') || requestUrl.includes('/rss') || requestUrl.includes('/feed')) {
    newHeaders.set('Access-Control-Allow-Origin', '*');
  }

  newHeaders.delete('X-GitHub-Request-Id');
  newHeaders.delete('X-Fastly-Request-ID');

  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: newHeaders,
  });
}


function generate404Page() {
  return `<!DOCTYPE html>
<html lang="ru" data-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>404 — Страница не найдена | SOCHIAUTOPARTS</title>
<meta name="robots" content="noindex,nofollow">
<link rel="icon" href="/logo.jpg" type="image/jpeg" />
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Manrope:wght@400;500;600;700;800&display=swap" rel="stylesheet" />
<style>
:root{--primary:#2481CC;--primary-dark:#1D6FAD;--bg-body:#F4F4F5;--bg-card:#fff;--text-main:#000;--text-sec:#707579;--border:#E8E8E8;--radius:12px}
[data-theme="dark"]{--bg-body:#0F1115;--bg-card:#181B22;--text-main:#F0F6FC;--text-sec:#8B949E;--border:#2D333B}
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
<p>Страница не найдена.</p>
<a href="/">На главную</a>
</div>
<script>
try{var t=localStorage.getItem('theme');if(t)document.documentElement.setAttribute('data-theme',t)}catch(e){}
</script>
</body>
</html>`;
}
