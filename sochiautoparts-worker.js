/**
 * SochiAutoParts Cloudflare Worker v2.0
 *
 * Proxies sochiautoparts.ru → GitHub Pages static site
 * AND dynamically renders archive pages from Telegram.
 *
 * Architecture:
 *   1. Static pages  → proxy from GitHub Pages
 *   2. Archive pages → fetch from Telegram t.me/s/sochiautoparts and render HTML
 *   3. All other 404 → custom 404 page
 *
 * GitHub Pages URL: https://creastudioai-beep.github.io/sapapp/
 * Route: sochiautoparts.ru/* → creastudioai-beep.github.io/sapapp/*
 */

const GITHUB_PAGES_BASE = 'https://creastudioai-beep.github.io/sapapp';
const SITE_URL = 'https://sochiautoparts.ru';
const CHANNEL = 'sochiautoparts';
const ARCHIVE_PER_PAGE = 50;

// Cache settings
const CACHE_TTL_BROWSER = 300;    // 5 minutes browser cache
const CACHE_TTL_EDGE = 3600;      // 1 hour edge cache
const CACHE_TTL_ARCHIVE = 1800;   // 30 min for archive pages

// User-Agent for Telegram scraping
const TG_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36';

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    let path = url.pathname;

    // --- Archive dynamic rendering ---
    // Matches: /archive, /archive/, /archive/page/N, /archive/page/N/
    // Also: /en/archive, /en/archive/page/N
    const archiveMatch = path.match(/^\/(en\/)?archive(?:\/page\/(\d+)\/?)?$/);
    if (archiveMatch) {
      const lang = archiveMatch[1] ? 'en' : 'ru';
      const pageNum = parseInt(archiveMatch[2] || '1', 10);
      return handleArchivePage(request, lang, pageNum, ctx);
    }

    // --- Handle root path ---
    if (path === '/') {
      path = '/index.html';
    }

    // --- Handle directory paths ---
    if (path.endsWith('/') && path !== '/') {
      path = path + 'index.html';
    }

    // --- Proxy to GitHub Pages ---
    const githubUrl = GITHUB_PAGES_BASE + path;

    const headers = new Headers();
    headers.set('User-Agent', 'SochiAutoParts-Worker/2.0');
    headers.set('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8');

    // Check cache first
    const cache = caches.default;
    const cacheKey = new Request(githubUrl, { method: 'GET' });

    let response = await cache.match(cacheKey);

    if (response) {
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

      return addSiteHeaders(response, url);

    } catch (error) {
      return new Response(`Worker error: ${error.message}`, {
        status: 500,
        headers: { 'Content-Type': 'text/plain' },
      });
    }
  },
};


// =============================================================================
// Archive page handler — fetches from Telegram and renders HTML
// =============================================================================

async function handleArchivePage(request, lang, pageNum, ctx) {
  const isRu = lang === 'ru';
  const cache = caches.default;
  const cacheKeyUrl = `${SITE_URL}/${lang === 'en' ? 'en/' : ''}archive/page/${pageNum}`;
  const cacheKey = new Request(cacheKeyUrl, { method: 'GET' });

  // Check cache
  let cached = await cache.match(cacheKey);
  if (cached) {
    return addSiteHeaders(cached, new URL(request.url));
  }

  // Calculate the "before" parameter for Telegram pagination
  // We need to figure out which Telegram page corresponds to our logical page
  // Telegram shows 20 posts per page; we show 50 per page
  // Strategy: fetch enough Telegram pages to fill our page

  const postsPerPage = 20; // Telegram shows ~20 posts per t.me/s/ page
  const tgPagesNeeded = Math.ceil(ARCHIVE_PER_PAGE / postsPerPage) + 1;
  const tgStartPage = Math.floor((pageNum - 1) * ARCHIVE_PER_PAGE / postsPerPage);

  let allPosts = [];
  let nextBefore = null;
  let totalFetched = 0;

  // Fetch Telegram pages to get the posts for this archive page
  for (let i = 0; i < tgPagesNeeded + 2; i++) {
    try {
      const [posts, nextBeforeId] = await fetchTelegramPage(CHANNEL, nextBefore);
      if (!posts || posts.length === 0) break;

      allPosts = allPosts.concat(posts);
      totalFetched += posts.length;

      if (nextBeforeId === null) break;
      nextBefore = nextBeforeId;

      // If we've fetched enough posts for this page plus some buffer
      if (totalFetched >= tgStartPage * postsPerPage + ARCHIVE_PER_PAGE + postsPerPage) break;
    } catch (e) {
      console.error('Telegram fetch error:', e);
      break;
    }
  }

  // Calculate which posts to show for this page
  const startIdx = (pageNum - 1) * ARCHIVE_PER_PAGE;
  const endIdx = startIdx + ARCHIVE_PER_PAGE;
  const pagePosts = allPosts.slice(startIdx, endIdx);
  const totalPosts = allPosts.length;
  const totalPages = Math.max(1, Math.ceil(totalPosts / ARCHIVE_PER_PAGE));

  // Generate HTML
  const html = generateArchiveHTML(lang, pageNum, totalPages, pagePosts, totalPosts);

  const response = new Response(html, {
    status: 200,
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
      'Cache-Control': `public, max-age=${CACHE_TTL_ARCHIVE}`,
    },
  });

  // Cache
  ctx.waitUntil(cache.put(cacheKey, response.clone()));

  return addSiteHeaders(response, new URL(request.url));
}


// =============================================================================
// Telegram page fetcher
// =============================================================================

async function fetchTelegramPage(channel, beforeId = null) {
  let url = `https://t.me/s/${channel}`;
  if (beforeId) {
    url += `?before=${beforeId}`;
  }

  const response = await fetch(url, {
    headers: {
      'User-Agent': TG_USER_AGENT,
      'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
      'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
    },
  });

  if (!response.ok) {
    throw new Error(`Telegram returned ${response.status}`);
  }

  const html = await response.text();
  return parseTelegramHTML(html, channel);
}


function parseTelegramHTML(html, channel) {
  const posts = [];
  let nextBeforeId = null;

  // Extract data-before for pagination
  const beforeMatch = html.match(/data-before="(\d+)"/);
  if (beforeMatch) {
    nextBeforeId = parseInt(beforeMatch[1], 10);
  }

  // Extract posts using regex (matching Telegram's HTML structure)
  const postRegex = /<div[^>]*class="tgme_widget_message_wrap"[^>]*>[\s\S]*?<\/div>\s*<\/div>\s*<\/div>\s*<\/div>/g;
  let match;

  // Simpler approach: find all message blocks
  const messageBlocks = html.split('tgme_widget_message_wrap');

  for (let i = 1; i < messageBlocks.length; i++) {
    const block = messageBlocks[i];

    // Extract post ID
    const postIdMatch = block.match(/data-post="[^\/]*\/(\d+)"/);
    if (!postIdMatch) continue;
    const postId = parseInt(postIdMatch[1], 10);

    // Extract text
    let text = '';
    const textMatch = block.match(/tgme_widget_message_text[^>]*>([\s\S]*?)<\/div>/);
    if (textMatch) {
      text = textMatch[1]
        .replace(/<br[^>]*>/g, '\n')
        .replace(/<\/?[^>]+(>|$)/g, '')
        .replace(/&amp;/g, '&')
        .replace(/&lt;/g, '<')
        .replace(/&gt;/g, '>')
        .replace(/&quot;/g, '"')
        .replace(/&#39;/g, "'")
        .replace(/&nbsp;/g, ' ')
        .trim();
    }

    // Extract photos
    const photos = [];
    const photoRegex = /background-image:url\('([^']+)'\)/g;
    let photoMatch;
    while ((photoMatch = photoRegex.exec(block)) !== null) {
      const photoUrl = photoMatch[1];
      // Skip emoji images
      if (!photoUrl.includes('cdn.jsdelivr.net/gh/twitter/twemoji') &&
          !photoUrl.includes('cdn.jsdelivr.net/gh/joypixels/emoji')) {
        photos.push(photoUrl);
      }
    }

    // Extract video thumbnails
    const videoThumbs = [];
    const videoMatch = block.match(/tgme_widget_message_video_player[^>]*style="[^"]*background-image:url\('([^']+)'\)/);
    if (videoMatch) {
      videoThumbs.push(videoMatch[1]);
    }

    // Extract date
    let date = '';
    const dateMatch = block.match(/datetime="([^"]+)"/);
    if (dateMatch) {
      date = dateMatch[1];
    }

    // Extract views
    let views = 0;
    const viewsMatch = block.match(/tgme_widget_message_views[^>]*>([\s\S]*?)<\/span>/);
    if (viewsMatch) {
      const viewsText = viewsMatch[1].trim().replace(/,/g, '').replace(/\s/g, '');
      if (viewsText.endsWith('K')) {
        views = Math.round(parseFloat(viewsText) * 1000);
      } else if (viewsText.endsWith('M')) {
        views = Math.round(parseFloat(viewsText) * 1000000);
      } else {
        views = parseInt(viewsText, 10) || 0;
      }
    }

    posts.push({
      id: postId,
      text: text,
      photos: photos,
      videoThumbnails: videoThumbs,
      date: date,
      views: views,
    });
  }

  return [posts, nextBeforeId];
}


// =============================================================================
// Archive HTML generator
// =============================================================================

function generateArchiveHTML(lang, pageNum, totalPages, posts, totalPosts) {
  const isRu = lang === 'ru';
  const htmlLang = isRu ? 'ru' : 'en';

  const title = isRu ? 'Архив публикаций' : 'Publications Archive';
  const description = isRu
    ? `Архив всех публикаций SOCHIAUTOPARTS. Страница ${pageNum} из ${totalPages}. Более 90000 публикаций.`
    : `Archive of all SOCHIAUTOPARTS publications. Page ${pageNum} of ${totalPages}. Over 90,000 publications.`;

  const heading = isRu ? 'Архив публикаций' : 'Publications Archive';
  const counterText = isRu
    ? `Показано ${posts.length} из ${totalPosts} публикаций`
    : `Showing ${posts.length} of ${totalPosts} publications`;
  const homeLabel = isRu ? 'На главную' : 'Home';
  const prevLabel = isRu ? 'Предыдущая' : 'Previous';
  const nextLabel = isRu ? 'Следующая' : 'Next';
  const readMore = isRu ? 'Читать далее' : 'Read more';
  const noText = isRu ? 'Публикация без текста' : 'Post without text';

  const archiveBase = isRu ? '/archive' : '/en/archive';
  const langBase = isRu ? '/' : '/en/';

  // Post cards
  let postCards = '';
  for (const post of posts) {
    const text = post.text || noText;
    const truncText = text.length > 200 ? text.substring(0, 200) + '...' : text;
    const dateStr = formatDate(post.date, lang);
    const viewsStr = post.views ? `👁 ${post.views}` : '';

    let mediaHtml = '';
    const firstPhoto = post.photos && post.photos.length > 0 ? post.photos[0] : null;
    const firstVideoThumb = post.videoThumbnails && post.videoThumbnails.length > 0 ? post.videoThumbnails[0] : null;
    const thumb = firstPhoto || firstVideoThumb;

    if (thumb) {
      const hasVideo = post.videoThumbnails && post.videoThumbnails.length > 0;
      if (hasVideo) {
        mediaHtml = `<div class="archive-video-card" style="background-image:url('${escapeAttr(thumb)}');background-size:cover;background-position:center"><div class="archive-video-play-btn"></div></div>`;
      } else {
        mediaHtml = `<img class="archive-card-image" src="${escapeAttr(thumb)}" alt="" referrerpolicy="no-referrer" loading="lazy" />`;
      }
    } else {
      mediaHtml = '<div class="archive-card-noimg">📋</div>';
    }

    const tgLink = `https://t.me/${CHANNEL}/${post.id}`;
    postCards += `
<a href="${tgLink}" class="archive-card" target="_blank" rel="nofollow noopener noreferrer">
${mediaHtml}
<div class="archive-card-body">
<div class="archive-card-text">${escapeHTML(truncText)}</div>
<div class="archive-card-meta">
${dateStr ? `<span>📅 ${escapeHTML(dateStr)}</span>` : ''}
${viewsStr ? `<span>${viewsStr}</span>` : ''}
</div>
</div>
</a>`;
  }

  // Pagination
  let pagination = '';
  if (totalPages > 1) {
    pagination = '<nav class="pagination" aria-label="' + (isRu ? 'Навигация по страницам' : 'Page navigation') + '">\n';

    if (pageNum > 1) {
      const prevUrl = pageNum === 2 ? archiveBase : `${archiveBase}/page/${pageNum - 1}`;
      pagination += `<a href="${prevUrl}" aria-label="${prevLabel}">&laquo;</a>\n`;
    } else {
      pagination += '<span class="disabled" aria-disabled="true">&laquo;</span>\n';
    }

    // Page numbers
    const maxVisible = 7;
    let startPage = 1;
    let endPage = totalPages;
    if (totalPages > maxVisible) {
      const half = Math.floor(maxVisible / 2);
      startPage = Math.max(1, pageNum - half);
      endPage = Math.min(totalPages, pageNum + half);
      if (pageNum - half < 1) endPage = Math.min(totalPages, maxVisible);
      if (pageNum + half > totalPages) startPage = Math.max(1, totalPages - maxVisible + 1);
    }

    if (startPage > 1) {
      pagination += `<a href="${archiveBase}">1</a>\n`;
      if (startPage > 2) pagination += '<span class="dots">...</span>\n';
    }

    for (let i = startPage; i <= endPage; i++) {
      const pUrl = i === 1 ? archiveBase : `${archiveBase}/page/${i}`;
      if (i === pageNum) {
        pagination += `<span class="active" aria-current="page">${i}</span>\n`;
      } else {
        pagination += `<a href="${pUrl}">${i}</a>\n`;
      }
    }

    if (endPage < totalPages) {
      if (endPage < totalPages - 1) pagination += '<span class="dots">...</span>\n';
      pagination += `<a href="${archiveBase}/page/${totalPages}">${totalPages}</a>\n`;
    }

    if (pageNum < totalPages) {
      pagination += `<a href="${archiveBase}/page/${pageNum + 1}" aria-label="${nextLabel}">&raquo;</a>\n`;
    } else {
      pagination += '<span class="disabled" aria-disabled="true">&raquo;</span>\n';
    }

    pagination += '</nav>\n';
  }

  return `<!DOCTYPE html>
<html lang="${htmlLang}" data-theme="dark">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>${escapeHTML(title)} | SOCHIAUTOPARTS</title>
<meta name="description" content="${escapeAttr(description)}" />
<link rel="canonical" href="${SITE_URL}${archiveBase}/page/${pageNum}" />
<meta property="og:title" content="${escapeAttr(title)} | SOCHIAUTOPARTS" />
<meta property="og:description" content="${escapeAttr(description)}" />
<meta property="og:url" content="${SITE_URL}${archiveBase}/page/${pageNum}" />
<meta property="og:type" content="website" />
<meta property="og:site_name" content="SOCHIAUTOPARTS" />
<meta property="og:image" content="${SITE_URL}/logo.jpg" />
<meta name="robots" content="${pageNum === 1 ? 'index, follow' : 'noindex, follow'}" />
<link rel="icon" href="/logo.jpg" type="image/jpeg" />
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Manrope:wght@400;500;600;700;800&display=swap" rel="stylesheet" />
<style>${ARCHIVE_CSS}</style>
</head>
<body>
<header class="site-header">
<div class="container">
<div class="header-content">
<a href="${langBase}" class="logo">
<img src="/logo.jpg" alt="SOCHIAUTOPARTS Logo" class="logo-icon" width="44" height="44" loading="eager" referrerpolicy="no-referrer" onerror="this.classList.add('error')">
<span class="logo-fallback">🚗</span>
SOCHIAUTOPARTS
</a>
<nav class="main-nav" id="mainNav">
<a href="${langBase}" >${isRu ? 'Главная' : 'Home'}</a>
<a href="${isRu ? '/articles' : '/en/articles'}">${isRu ? 'Статьи' : 'Articles'}</a>
<a href="${archiveBase}" class="active">${isRu ? 'Архив' : 'Archive'}</a>
<a href="${isRu ? '/shop' : '/en/shop'}">${isRu ? 'Магазин' : 'Shop'}</a>
<a href="${isRu ? '/contacts' : '/en/contacts'}">${isRu ? 'Контакты' : 'Contacts'}</a>
</nav>
<div class="controls-group">
<button class="mobile-menu-btn" id="mobileMenuBtn" aria-label="${isRu ? 'Меню' : 'Menu'}">☰</button>
<nav class="lang-switcher">
<a href="/" class="lang-btn ${isRu ? 'active' : ''}">RU</a>
<a href="/en/" class="lang-btn ${!isRu ? 'active' : ''}">EN</a>
</nav>
<div class="theme-toggle">
<button class="theme-btn" data-theme="light" aria-label="Light theme">☀️</button>
<button class="theme-btn" data-theme="dark" aria-label="Dark theme">🌙</button>
</div>
</div>
</div>
</div>
</header>
<main>
<div class="container">
<div class="archive-page-container">
<h1>${heading}</h1>
<div class="posts-counter">${counterText}</div>
<div class="archive-grid">
${postCards}
</div>
${pagination}
<div style="margin:2rem 0;text-align:center;">
<a href="${langBase}" class="btn-outline">← ${homeLabel}</a>
</div>
</div>
</div>
</main>
<footer>
<p>&copy; 2026 SOCHIAUTOPARTS. ${isRu ? 'Все права защищены.' : 'All rights reserved.'}</p>
</footer>
<script>
(function(){
  var menuBtn=document.getElementById('mobileMenuBtn');
  var nav=document.getElementById('mainNav');
  if(menuBtn&&nav){menuBtn.addEventListener('click',function(){nav.classList.toggle('open');menuBtn.classList.toggle('active')});}
  var themeBtns=document.querySelectorAll('.theme-btn');
  themeBtns.forEach(function(btn){btn.addEventListener('click',function(){
    var t=btn.getAttribute('data-theme');
    document.documentElement.setAttribute('data-theme',t);
    try{localStorage.setItem('theme',t)}catch(e){}
  });});
  try{var saved=localStorage.getItem('theme');if(saved)document.documentElement.setAttribute('data-theme',saved)}catch(e){}
})();
</script>
</body>
</html>`;
}


// =============================================================================
// Archive CSS (matching the main site's CSS module)
// =============================================================================

const ARCHIVE_CSS = `
:root{--primary:#2481CC;--primary-dark:#1D6FAD;--bg-body:#F4F4F5;--bg-card:#fff;--text-main:#000;--text-sec:#707579;--border:#E8E8E8;--radius:12px}
:root[data-theme="dark"]{--bg-body:#0F1115;--bg-card:#181B22;--text-main:#F0F6FC;--text-sec:#8B949E;--border:#2D333B}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Inter',system-ui,-apple-system,sans-serif;background:var(--bg-body);color:var(--text-main);line-height:1.6;transition:background .2s,color .2s}
a{color:var(--primary);text-decoration:none}
.container{max-width:1200px;margin:0 auto;padding:0 1rem}
.site-header{background:var(--bg-card);border-bottom:1px solid var(--border);position:sticky;top:0;z-index:100}
.header-content{display:flex;align-items:center;justify-content:space-between;padding:.75rem 0;gap:1rem}
.logo{display:flex;align-items:center;gap:.5rem;font-weight:800;font-size:1.25rem;color:var(--text-main)}
.logo-icon{width:44px;height:44px;border-radius:10px;object-fit:cover}
.logo-fallback{display:none}
.logo-icon.error{display:none}
.logo-icon.error+.logo-fallback{display:inline}
.main-nav{display:flex;gap:.25rem}
.main-nav a{padding:.5rem .75rem;border-radius:8px;font-weight:500;font-size:.9rem;color:var(--text-sec);transition:all .15s}
.main-nav a:hover,.main-nav a.active{color:var(--primary);background:rgba(36,129,204,.08)}
.controls-group{display:flex;align-items:center;gap:.5rem}
.mobile-menu-btn{display:none;background:none;border:none;font-size:1.5rem;cursor:pointer;color:var(--text-main)}
.lang-switcher{display:flex;gap:2px}
.lang-btn{padding:.25rem .5rem;border-radius:6px;font-size:.8rem;font-weight:600;color:var(--text-sec)}
.lang-btn.active{color:#fff;background:var(--primary)}
.theme-toggle{display:flex;gap:2px}
.theme-btn{background:none;border:none;cursor:pointer;padding:.25rem;font-size:1.1rem;border-radius:6px}
.theme-btn:hover{background:rgba(36,129,204,.1)}
@media(max-width:768px){.main-nav{display:none;position:absolute;top:100%;left:0;right:0;background:var(--bg-card);flex-direction:column;padding:1rem;border-bottom:1px solid var(--border);box-shadow:0 4px 12px rgba(0,0,0,.1)}.main-nav.open{display:flex}.mobile-menu-btn{display:block}}
.archive-page-container{padding:2rem 0}
.archive-page-container h1{font-size:2rem;margin-bottom:1rem}
.archive-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:1rem;margin:1.5rem 0}
.archive-card{display:flex;flex-direction:column;background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius);overflow:hidden;transition:transform .15s,box-shadow .15s}
.archive-card:hover{transform:translateY(-2px);box-shadow:0 4px 12px rgba(0,0,0,.1)}
.archive-card-image{width:100%;height:180px;object-fit:cover}
.archive-video-card{width:100%;height:180px;position:relative;display:flex;align-items:center;justify-content:center}
.archive-video-play-btn{width:48px;height:48px;border-radius:50%;background:rgba(0,0,0,.6);display:flex;align-items:center;justify-content:center}
.archive-video-play-btn::after{content:'';display:block;width:0;height:0;border-top:10px solid transparent;border-bottom:10px solid transparent;border-left:16px solid #fff;margin-left:4px}
.archive-card-noimg{width:100%;height:180px;display:flex;align-items:center;justify-content:center;background:var(--bg-body);font-size:3rem}
.archive-card-body{padding:.75rem;flex:1;display:flex;flex-direction:column}
.archive-card-text{font-size:.9rem;line-height:1.4;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;color:var(--text-main)}
.archive-card-meta{margin-top:auto;padding-top:.5rem;font-size:.8rem;color:var(--text-sec);display:flex;gap:.75rem}
.pagination{display:flex;flex-wrap:wrap;gap:.25rem;justify-content:center;padding:1.5rem 0}
.pagination a,.pagination span{padding:.5rem .75rem;border-radius:8px;font-size:.9rem;border:1px solid var(--border);background:var(--bg-card)}
.pagination a:hover{background:rgba(36,129,204,.08)}
.pagination .active{background:var(--primary);color:#fff;border-color:var(--primary)}
.pagination .disabled{opacity:.4;cursor:default}
.pagination .dots{border:none;background:none}
.posts-counter{text-align:center;color:var(--text-sec);font-size:.9rem;padding:.5rem 0}
.btn-outline{display:inline-block;padding:.5rem 1.5rem;border:1px solid var(--primary);border-radius:9999px;color:var(--primary);font-weight:600;transition:all .15s}
.btn-outline:hover{background:var(--primary);color:#fff}
footer{text-align:center;padding:2rem 1rem;color:var(--text-sec);font-size:.85rem;border-top:1px solid var(--border);margin-top:2rem}
`;


// =============================================================================
// Helper functions
// =============================================================================

function addSiteHeaders(response, url) {
  const newHeaders = new Headers(response.headers);

  const contentType = newHeaders.get('Content-Type') || '';
  if (contentType.includes('text/html')) {
    newHeaders.set('Content-Type', 'text/html; charset=utf-8');
  }

  newHeaders.set('X-Content-Type-Options', 'nosniff');
  newHeaders.set('X-Frame-Options', 'SAMEORIGIN');
  newHeaders.set('Referrer-Policy', 'strict-origin-when-cross-origin');
  newHeaders.set('Permissions-Policy', 'camera=(), microphone=(), geolocation=()');
  newHeaders.set('Cache-Control', `public, max-age=${CACHE_TTL_BROWSER}`);

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
<style>
body{font-family:'Inter',system-ui,-apple-system,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;background:#F4F4F5;color:#333}
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
<script>
try{var t=localStorage.getItem('theme');if(t)document.documentElement.setAttribute('data-theme',t)}catch(e){}
</script>
</body>
</html>`;
}


function formatDate(dateStr, lang) {
  if (!dateStr) return '';
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    if (lang === 'ru') {
      const months = ['января','февраля','марта','апреля','мая','июня','июля','августа','сентября','октября','ноября','декабря'];
      return `${d.getDate()} ${months[d.getMonth()]} ${d.getFullYear()}`;
    }
    return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
  } catch (e) {
    return dateStr;
  }
}


function escapeHTML(str) {
  if (!str) return '';
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}


function escapeAttr(str) {
  if (!str) return '';
  return String(str).replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/'/g,'&#39;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
