/**
 * SochiAutoParts Cloudflare Worker
 * 
 * Proxies sochiautoparts.ru → GitHub Pages static site
 * GitHub Pages URL: https://creastudioai-beep.github.io/sapapp/
 * 
 * Route: sochiautoparts.ru/* → creastudioai-beep.github.io/sapapp/*
 * 
 * The Worker:
 * 1. Receives requests to sochiautoparts.ru
 * 2. Maps the URL path to the corresponding GitHub Pages path
 * 3. Fetches from GitHub Pages
 * 4. Returns the content with appropriate headers
 */

const GITHUB_PAGES_BASE = 'https://creastudioai-beep.github.io/sapapp';
const SITE_URL = 'https://sochiautoparts.ru';

// Cache settings
const CACHE_TTL_BROWSER = 300;    // 5 minutes browser cache
const CACHE_TTL_EDGE = 3600;      // 1 hour edge cache

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    let path = url.pathname;

    // Handle root path
    if (path === '/') {
      path = '/index.html';
    }

    // Handle directory paths (e.g., /shop → /shop/index.html)
    if (path.endsWith('/') && path !== '/') {
      path = path + 'index.html';
    }

    // Handle paths without extensions — try as directory first, then as file
    let githubUrl = GITHUB_PAGES_BASE + path;

    // Build the fetch request
    const headers = new Headers();
    headers.set('User-Agent', 'SochiAutoParts-Worker/1.0');
    headers.set('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8');

    // Check cache first
    const cache = caches.default;
    const cacheKey = new Request(githubUrl, { method: 'GET' });
    
    let response = await cache.match(cacheKey);
    
    if (response) {
      // Return cached response with site-specific headers
      return addSiteHeaders(new Response(response.body, response), url);
    }

    // Fetch from GitHub Pages
    try {
      response = await fetch(githubUrl, {
        method: 'GET',
        headers: headers,
        cf: {
          cacheTtl: CACHE_TTL_EDGE,
          cacheEverything: true,
        },
      });

      // If 404, try adding /index.html for directory paths
      if (response.status === 404 && !path.endsWith('.html') && !path.endsWith('.xml') && !path.endsWith('.json') && !path.includes('.')) {
        const dirUrl = GITHUB_PAGES_BASE + path + '/index.html';
        const dirResponse = await fetch(dirUrl, {
          method: 'GET',
          headers: headers,
          cf: {
            cacheTtl: CACHE_TTL_EDGE,
            cacheEverything: true,
          },
        });
        
        if (dirResponse.ok) {
          response = dirResponse;
          githubUrl = dirUrl;
        }
      }

      // If still 404, return our custom 404 page
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

      // Clone the response so we can cache it
      const responseToCache = response.clone();

      // Cache the response
      ctx.waitUntil(
        cache.put(cacheKey, responseToCache)
      );

      return addSiteHeaders(response, url);

    } catch (error) {
      return new Response(`Worker error: ${error.message}`, {
        status: 500,
        headers: { 'Content-Type': 'text/plain' },
      });
    }
  },
};

/**
 * Add site-specific headers to the response
 */
function addSiteHeaders(response, url) {
  const newHeaders = new Headers(response.headers);
  
  // Set proper content type for HTML
  const contentType = newHeaders.get('Content-Type') || '';
  if (contentType.includes('text/html')) {
    newHeaders.set('Content-Type', 'text/html; charset=utf-8');
  }
  
  // Security headers
  newHeaders.set('X-Content-Type-Options', 'nosniff');
  newHeaders.set('X-Frame-Options', 'SAMEORIGIN');
  newHeaders.set('Referrer-Policy', 'strict-origin-when-cross-origin');
  newHeaders.set('Permissions-Policy', 'camera=(), microphone=(), geolocation=()');
  
  // Cache control
  newHeaders.set('Cache-Control', `public, max-age=${CACHE_TTL_BROWSER}`);
  
  // Remove GitHub Pages specific headers
  newHeaders.delete('X-GitHub-Request-Id');
  newHeaders.delete('X-Fastly-Request-ID');
  
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: newHeaders,
  });
}

/**
 * Generate custom 404 page
 */
function generate404Page() {
  return `<!DOCTYPE html>
<html lang="ru" data-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>404 — Страница не найдена | SOCHIAUTOPARTS</title>
<meta name="robots" content="noindex,nofollow">
<style>
body{font-family:'Inter',system-ui,-apple-system,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;background:var(--bg-body,#F4F4F5);color:var(--text-main,#000)}
:root[data-theme="dark"] body{background:#0F1115;color:#F0F6FC}
.e404{text-align:center;padding:2rem}
.e404 h1{font-size:6rem;margin:0;color:#2481CC}
.e404 p{font-size:1.2rem;margin:1rem 0 2rem;color:#707579}
.e404 a{display:inline-block;padding:12px 28px;background:#2481CC;color:#fff;text-decoration:none;border-radius:9999px;font-size:1rem;font-weight:600;transition:opacity .15s}
.e404 a:hover{opacity:.85}
</style>
</head>
<body>
<div class="e404">
<h1>404</h1>
<p>Страница не найдена.</p>
<a href="/">На главную</a>
</div>
</body>
</html>`;
}
