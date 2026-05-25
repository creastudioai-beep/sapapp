/**
 * SochiAutoParts Cloudflare Worker v6.1
 *
 * Proxies sochiautoparts.ru → GitHub Pages static site.
 * Dynamically generates /archive/post/{id} pages from Telegram archive data.
 *
 * Architecture:
 *   1. /api/{id}              → Admitad affiliate redirect (lookup by program ID)
 *   2. /archive/post/{id}     → Dynamic archive post page (from Telegram data on GH Pages)
 *   3. /rss.xml               → serve from GitHub Pages /rss.xml
 *   4. /feed.xml              → serve from GitHub Pages /rss.xml (compat alias)
 *   5. All other requests     → proxy from GitHub Pages
 *   6. 404 from GH Pages      → try .html, then /index.html, then custom 404
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

// Telegram archive data — cached per-page
// Primary: GitHub Pages (deployed from build output)
// Fallback: raw.githubusercontent.com (if GH Pages not yet deployed)
const TELEGRAM_ARCHIVE_BASE = GITHUB_PAGES_BASE + '/data/telegram_archive';
const TELEGRAM_ARCHIVE_FALLBACK = 'https://raw.githubusercontent.com/creastudioai-beep/sapapp/main/data/telegram_archive';
let telegramIndexCache = null;
let telegramIndexCacheTime = 0;
const TELEGRAM_INDEX_CACHE_TTL = 3600000; // 1 hour in ms
let telegramPageCache = {};  // page_num -> { data, time }

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
    const apiMatch = path.match(/^\/api\/(\d+)$/);
    if (apiMatch) {
      return handleAffiliateRedirect(apiMatch[1], request, ctx);
    }

    // --- Dynamic archive post page: /archive/post/{id} or /en/archive/post/{id} ---
    const archivePostMatch = path.match(/^\/(?:en\/)?archive\/post\/(\d+)$/);
    if (archivePostMatch) {
      const postId = archivePostMatch[1];
      const isEn = path.startsWith('/en/');
      return handleArchivePost(postId, isEn, request, ctx);
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
    const programs = await getAdmitadPrograms(ctx);
    const prog = programs.find(p => String(p.id) === String(programId));

    if (prog) {
      const affiliateUrl = prog.goto_link || prog.gotoLink || prog.affiliateUrl || prog.affiliate_url || '';
      if (affiliateUrl) {
        return Response.redirect(affiliateUrl, 302);
      }
    }

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
      headers: { 'User-Agent': 'SochiAutoParts-Worker/6.0' },
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
// Dynamic archive post page handler
// =============================================================================

async function handleArchivePost(postId, isEn, request, ctx) {
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
      return new Response(generate404Page(), {
        status: 404,
        headers: { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'public, max-age=60' },
      });
    }

    // Step 2: Fetch the page that contains this post
    const pageNum = entry.page || entry.p;
    const pos = entry.pos || entry.i || 0;
    const pageData = await getTelegramPage(pageNum, ctx);

    if (!pageData || !Array.isArray(pageData) || pos >= pageData.length) {
      return new Response(generate404Page(), {
        status: 404,
        headers: { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'public, max-age=60' },
      });
    }

    const post = pageData[pos];
    if (!post || String(post.id) !== String(postId)) {
      // Position mismatch — search the page for the post
      const found = pageData.find(p => String(p.id) === String(postId));
      if (!found) {
        return new Response(generate404Page(), {
          status: 404,
          headers: { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'public, max-age=60' },
        });
      }
      return generateArchivePostResponse(found, isEn);
    }

    return generateArchivePostResponse(post, isEn);

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
      const response = await fetch(`${baseUrl}/posts_index.json`, {
        headers: { 'User-Agent': 'SochiAutoParts-Worker/6.1' },
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
      const response = await fetch(`${baseUrl}/page_${pageNum}.json`, {
        headers: { 'User-Agent': 'SochiAutoParts-Worker/6.1' },
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


function generateArchivePostResponse(post, isEn) {
  const lang = isEn ? 'en' : 'ru';
  const postId = post.id || 0;
  const title = escapeHtml(post.title || post.text?.substring(0, 100) || `Post ${postId}`);
  const text = (post.text || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\n/g, '<br>\n');
  const date = post.date || '';

  // Format date
  let dateDisplay = date;
  try {
    const d = new Date(date);
    if (!isNaN(d.getTime())) {
      const months = ['января','февраля','марта','апреля','мая','июня','июля','августа','сентября','октября','ноября','декабря'];
      dateDisplay = `${d.getDate()} ${months[d.getMonth()]} ${d.getFullYear()} г.`;
    }
  } catch(e) {}

  // Build media HTML
  let mediaHtml = '';
  const photos = post.photos || [];
  const videos = post.videos || [];
  const videoThumbs = post.video_thumbnails || [];

  if (photos.length > 0) {
    for (const photo of photos.slice(0, 5)) {
      mediaHtml += `<img src="${escapeHtml(photo)}" alt="${title}" loading="lazy" referrerpolicy="no-referrer" style="width:100%;height:auto;max-height:600px;object-fit:contain;border-radius:8px;margin-bottom:8px;">`;
    }
  }
  if (videos.length > 0) {
    const poster = videoThumbs.length > 0 ? `poster="${escapeHtml(videoThumbs[0])}"` : '';
    mediaHtml += `<video src="${escapeHtml(videos[0])}" ${poster} controls playsinline preload="metadata" referrerpolicy="no-referrer" style="width:100%;max-height:600px;border-radius:8px;margin-bottom:8px;"></video>`;
  }

  // Build hashtags
  let tagsHtml = '';
  const textForTags = post.text || '';
  const hashtagMatches = textForTags.match(/#[a-zA-Zа-яА-ЯёЁ0-9_]+/g) || [];
  if (hashtagMatches.length > 0) {
    const tagLinks = hashtagMatches.slice(0, 15).map(tag => {
      const tagName = tag.substring(1);
      return `<a href="/tag/${encodeURIComponent(tagName)}.html" class="hashtag">${escapeHtml(tag)}</a>`;
    }).join(' ');
    tagsHtml = `<div class="post-tags">${tagLinks}</div>`;
  }

  const canonicalUrl = isEn ? `${SITE_URL}/en/archive/post/${postId}` : `${SITE_URL}/archive/post/${postId}`;
  const telegramLink = `https://t.me/sochiautoparts/${postId}`;

  const html = `<!DOCTYPE html>
<html lang="${lang}" data-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>${title} | SOCHIAUTOPARTS</title>
<meta name="description" content="${escapeHtml((post.text || '').substring(0, 200))}">
<link rel="canonical" href="${canonicalUrl}">
<meta property="og:title" content="${escapeHtml(title)}">
<meta property="og:description" content="${escapeHtml((post.text || '').substring(0, 200))}">
<meta property="og:url" content="${canonicalUrl}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="SOCHIAUTOPARTS">
<meta property="og:locale" content="${isEn ? 'en_US' : 'ru_RU'}">
<meta name="robots" content="index, follow">
<meta name="theme-color" content="#2481CC">
<link rel="icon" href="/logo.jpg" type="image/jpeg">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Manrope:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
:root{--primary:#2481CC;--primary-dark:#1D6FAD;--primary-light:#E6F3FF;--secondary:#2AABEE;--accent:#0088cc;--bg-body:#F4F4F5;--bg-card:#FFFFFF;--bg-header:rgba(255,255,255,0.95);--text-main:#000;--text-muted:#707579;--border-color:#DADCE0;--border-light:#E8E8E8;--radius:12px;--font-main:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}
[data-theme="dark"]{--bg-body:#0F1115;--bg-card:#161B22;--bg-header:rgba(22,27,34,0.95);--text-main:#F0F6FC;--text-muted:#8B949E;--border-color:#30363D;--border-light:#21262D}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:var(--font-main);background:var(--bg-body);color:var(--text-main);line-height:1.6}
a{color:var(--primary);text-decoration:none}
.container{max-width:800px;margin:0 auto;padding:0 16px}
.site-header{background:var(--bg-header);padding:0.75rem 0;border-bottom:1px solid var(--border-color);position:sticky;top:0;z-index:1000;backdrop-filter:blur(20px)}
.header-content{display:flex;justify-content:space-between;align-items:center}
.logo{font-size:1.375rem;font-weight:700;color:var(--text-main);display:flex;align-items:center;gap:0.625rem;font-family:'Manrope','Inter',sans-serif}
.logo-icon{width:40px;height:40px;border-radius:50%;object-fit:cover;border:2px solid var(--border-light)}
.article-content{padding:2rem 0}
.article-meta{color:var(--text-muted);font-size:0.875rem;margin-bottom:1rem}
.article-body{font-size:1.0625rem;line-height:1.7;margin:1.5rem 0}
.post-tags{margin:1.5rem 0;display:flex;flex-wrap:wrap;gap:0.5rem}
.hashtag{display:inline-block;padding:4px 12px;background:var(--primary-light);color:var(--primary);border-radius:9999px;font-size:0.8125rem;font-weight:600}
[data-theme="dark"] .hashtag{background:#1a3a5c;color:#58A6FF}
.btn-cta{display:inline-flex;align-items:center;gap:8px;padding:12px 24px;background:var(--primary);color:white;font-weight:700;text-decoration:none;border-radius:9999px;transition:opacity .15s}
.btn-cta:hover{opacity:.85}
.post-actions{margin:1.5rem 0}
footer{text-align:center;padding:2rem 0;color:var(--text-muted);font-size:0.875rem;border-top:1px solid var(--border-color);margin-top:2rem}
</style>
<script async src="https://www.googletagmanager.com/gtag/js?id=G-2GZ7FKV6CK"></script>
<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments)}gtag('js',new Date());gtag('config','G-2GZ7FKV6CK');</script>
</head>
<body>
<header class="site-header"><div class="container"><div class="header-content">
<a href="/" class="logo"><img src="/logo.jpg" alt="SOCHIAUTOPARTS" class="logo-icon" width="40" height="40" referrerpolicy="no-referrer">SOCHIAUTOPARTS</a>
</div></div></header>
<main><div class="container"><div class="article-content">
<article>
<div class="article-meta"><span>${dateDisplay}</span></div>
<h1>${title}</h1>
${mediaHtml ? '<div class="post-gallery">' + mediaHtml + '</div>' : ''}
<div class="article-body">${text}</div>
${tagsHtml}
<div class="post-actions">
<a href="${telegramLink}" class="btn-cta" target="_blank" rel="nofollow noopener noreferrer">💬 ${isEn ? 'Open in Telegram' : 'Открыть в Telegram'}</a>
</div>
</article>
</div></div></main>
<footer><p>&#169; 2026 SOCHIAUTOPARTS. ${isEn ? 'All rights reserved.' : 'Все права защищены.'}</p></footer>
<script>try{var t=localStorage.getItem('theme');if(t)document.documentElement.setAttribute('data-theme',t)}catch(e){}</script>
</body>
</html>`;

  return new Response(html, {
    status: 200,
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
      'Cache-Control': 'public, max-age=3600',
    },
  });
}


function escapeHtml(str) {
  if (!str) return '';
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}


// =============================================================================
// GitHub Pages proxy
// =============================================================================

async function proxyToGitHubPages(path, request, ctx) {
  const headers = new Headers();
  headers.set('User-Agent', 'SochiAutoParts-Worker/6.0');
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
      return new Response(generate404Page(), {
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
