"""
CSS styles for the static site generator.
ALL CSS styles as Python string constants.
Must exactly match the CSS from the original Cloudflare Worker (v27.0).
"""

CSS_STYLES = """
:root {
  --primary: #2481CC; --primary-dark: #1D6FAD; --primary-light: #E6F3FF;
  --secondary: #2AABEE; --accent: #0088cc; --bg-body: #F4F4F5; --bg-card: #FFFFFF;
  --bg-header: rgba(255, 255, 255, 0.95); --bg-footer: #FFFFFF; --bg-hover: #F0F2F5;
  --text-main: #000000; --text-muted: #707579; --text-light: #999999; --text-link: #2481CC;
  --border-color: #DADCE0; --border-light: #E8E8E8;
  --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05); --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
  --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1); --shadow-telegram: 0 1px 2px rgba(0,0,0,0.12);
  --radius-sm: 8px; --radius-md: 12px; --radius-lg: 16px; --radius-xl: 24px; --radius-full: 9999px;
  --transition-fast: 0.15s cubic-bezier(0.4, 0, 0.2, 1); --transition-normal: 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  --font-main: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  --font-display: 'Manrope', 'Inter', sans-serif;
}
[data-theme="dark"] {
  --bg-body: #0F1115; --bg-card: #161B22; --bg-header: rgba(22, 27, 34, 0.95);
  --bg-footer: #161B22; --bg-hover: #21262D; --text-main: #F0F6FC; --text-muted: #8B949E;
  --text-light: #6E7681; --text-link: #58A6FF; --border-color: #30363D; --border-light: #21262D;
  --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.3); --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.4);
  --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.5);
}

*, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }
html { scroll-behavior: smooth; -webkit-text-size-adjust: 100%; }
body {
  font-family: var(--font-main);
  background: var(--bg-body);
  color: var(--text-main);
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  min-height: 100vh;
}
a { color: var(--text-link); text-decoration: none; transition: color var(--transition-fast); }
a:hover { color: var(--primary-dark); }
img { max-width: 100%; height: auto; display: block; }
button { cursor: pointer; font-family: inherit; }
ul, ol { list-style: none; }

.container { max-width: 1200px; margin: 0 auto; padding: 0 16px; position: relative; z-index: 1; }

.site-header {
  position: sticky; top: 0; z-index: 100;
  background: var(--bg-header);
  backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
  border-bottom: 1px solid var(--border-light);
  transition: background var(--transition-normal);
}
.header-content {
  display: flex; align-items: center; justify-content: space-between;
  max-width: 1200px; margin: 0 auto; padding: 0 16px;
  height: 60px;
}
.logo {
  display: flex; align-items: center; gap: 8px;
  font-family: var(--font-display); font-weight: 800; font-size: 1.25rem;
  color: var(--text-main); text-decoration: none;
}
.logo svg { width: 32px; height: 32px; }
.main-nav { display: flex; align-items: center; gap: 4px; }
.main-nav a {
  padding: 8px 16px; border-radius: var(--radius-full);
  font-size: 0.875rem; font-weight: 600;
  color: var(--text-muted); text-decoration: none;
  transition: all var(--transition-fast);
}
.main-nav a:hover, .main-nav a.active {
  color: var(--primary); background: var(--primary-light);
}
.mobile-menu-btn {
  display: none; background: none; border: none;
  padding: 8px; color: var(--text-main);
}
.controls-group { display: flex; align-items: center; gap: 8px; }
.lang-switcher {
  position: relative; display: flex; align-items: center;
}
.lang-switcher select {
  appearance: none; -webkit-appearance: none;
  background: var(--bg-hover); border: 1px solid var(--border-color);
  border-radius: var(--radius-full); padding: 6px 28px 6px 12px;
  font-size: 0.8125rem; font-weight: 600; color: var(--text-main);
  cursor: pointer; outline: none;
  transition: all var(--transition-fast);
}
.lang-switcher select:hover { border-color: var(--primary); }
.lang-switcher::after {
  content: ''; position: absolute; right: 10px;
  width: 0; height: 0; pointer-events: none;
  border-left: 4px solid transparent; border-right: 4px solid transparent;
  border-top: 5px solid var(--text-muted);
}
.lang-btn {
  padding: 4px 10px; border-radius: var(--radius-full);
  font-size: 0.8125rem; font-weight: 600; color: var(--text-muted);
  text-decoration: none; transition: all var(--transition-fast);
}
.lang-btn.active { background: var(--primary); color: #fff; }
.lang-btn:hover:not(.active) { background: var(--bg-hover); color: var(--primary); }
.theme-toggle {
  display: flex; align-items: center; justify-content: center;
  width: 36px; height: 36px; border-radius: var(--radius-full);
  background: var(--bg-hover); border: 1px solid var(--border-color);
  color: var(--text-main); cursor: pointer;
  transition: all var(--transition-fast);
}
.theme-toggle:hover { background: var(--primary-light); border-color: var(--primary); color: var(--primary); }
.theme-toggle svg { width: 18px; height: 18px; }

.hero {
  background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
  padding: 3rem 0; text-align: center; color: #fff;
  position: relative; overflow: hidden;
}
.hero::before {
  content: ''; position: absolute; top: 0; left: 0; right: 0; bottom: 0;
  background: radial-gradient(circle at 30% 50%, rgba(255,255,255,0.1) 0%, transparent 50%);
}
.hero h1 {
  font-family: var(--font-display); font-size: 2.5rem; font-weight: 800;
  margin-bottom: 0.5rem; position: relative; z-index: 1;
}
.hero p {
  font-size: 1.125rem; opacity: 0.9; margin-bottom: 1.5rem;
  position: relative; z-index: 1;
}
.search-container {
  max-width: 600px; margin: 0 auto; position: relative; z-index: 1;
}
.search-input {
  width: 100%; padding: 14px 52px 14px 20px;
  border-radius: var(--radius-full); border: none;
  font-size: 1rem; background: rgba(255,255,255,0.95);
  color: #000; outline: none;
  box-shadow: var(--shadow-md);
  transition: all var(--transition-fast);
}
.search-input:focus { box-shadow: 0 0 0 3px rgba(255,255,255,0.3), var(--shadow-lg); }
.search-input::placeholder { color: #999; }
.search-btn {
  position: absolute; right: 6px; top: 50%; transform: translateY(-50%);
  width: 40px; height: 40px; border-radius: var(--radius-full);
  background: var(--primary); border: none; color: #fff;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; transition: background var(--transition-fast);
}
.search-btn:hover { background: var(--primary-dark); }
.search-btn svg { width: 18px; height: 18px; }
.search-results {
  position: absolute; top: calc(100% + 8px); left: 0; right: 0;
  background: var(--bg-card); border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg); border: 1px solid var(--border-light);
  max-height: 400px; overflow-y: auto; z-index: 50;
  display: none;
}
.search-results.active { display: block; }
.search-results a {
  display: block; padding: 12px 16px;
  color: var(--text-main); text-decoration: none;
  border-bottom: 1px solid var(--border-light);
  transition: background var(--transition-fast);
}
.search-results a:last-child { border-bottom: none; }
.search-results a:hover { background: var(--bg-hover); }
.search-results .search-result-title { font-weight: 600; font-size: 0.9375rem; }
.search-results .search-result-snippet { font-size: 0.8125rem; color: var(--text-muted); margin-top: 2px; }
.btn-cta {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 12px 24px; border-radius: var(--radius-full);
  background: #fff; color: var(--primary); font-weight: 700;
  font-size: 1rem; text-decoration: none;
  transition: all var(--transition-fast);
  position: relative; z-index: 1;
}
.btn-cta:hover { transform: translateY(-1px); box-shadow: var(--shadow-lg); }

.seo-block {
  background: var(--bg-card); border-radius: var(--radius-lg);
  padding: 1.5rem; margin: 1.5rem 0;
  border: 1px solid var(--border-light);
  box-shadow: var(--shadow-sm);
}
.seo-block h2 { font-family: var(--font-display); font-size: 1.25rem; font-weight: 700; margin-bottom: 0.75rem; }
.seo-block p { font-size: 0.9375rem; color: var(--text-muted); line-height: 1.7; }

.posts-feed {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 1rem; padding: 1.5rem 0;
}
.post-feed-item {
  background: var(--bg-card); border-radius: var(--radius-lg);
  overflow: hidden; border: 1px solid var(--border-light);
  box-shadow: var(--shadow-telegram);
  transition: all var(--transition-normal);
}
.post-feed-item:hover { box-shadow: var(--shadow-lg); border-color: var(--primary-light); transform: translateY(-2px); }
.post-feed-media {
  position: relative; width: 100%; height: 220px;
  background: var(--bg-hover); overflow: hidden;
}
.post-feed-media img { width: 100%; height: 100%; object-fit: cover; transition: transform var(--transition-normal); }
.post-feed-item:hover .post-feed-media img { transform: scale(1.03); }
.post-feed-media .video-badge {
  position: absolute; top: 12px; right: 12px;
  background: rgba(0,0,0,0.7); color: #fff;
  padding: 4px 10px; border-radius: var(--radius-full);
  font-size: 0.75rem; font-weight: 600;
  display: flex; align-items: center; gap: 4px;
}
.post-feed-content { padding: 1rem; }
.post-feed-content h3 {
  font-family: var(--font-display); font-size: 1rem; font-weight: 700;
  line-height: 1.4; margin-bottom: 0.5rem;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.post-feed-content h3 a { color: var(--text-main); text-decoration: none; }
.post-feed-content h3 a:hover { color: var(--primary); }
.post-feed-text {
  font-size: 0.875rem; color: var(--text-muted); line-height: 1.5;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;
  margin-bottom: 0.75rem;
}
.post-feed-meta {
  display: flex; justify-content: space-between; align-items: center;
  font-size: 0.75rem; color: var(--text-light);
}
.post-feed-meta .post-date { display: flex; align-items: center; gap: 4px; }
.post-feed-meta .post-views { display: flex; align-items: center; gap: 4px; }
.post-feed-actions { margin-top: 0.5rem; }
.post-tags {
  display: flex; flex-wrap: wrap; gap: 0.5rem;
  margin-top: 1rem;
}

.post-gallery {
  position: relative; margin-bottom: 1rem;
  border-radius: var(--radius-lg); overflow: hidden;
}
.post-gallery .gallery-slide {
  width: 100%; aspect-ratio: 16/9; object-fit: cover;
  display: block;
}
.gallery-controls {
  position: absolute; bottom: 12px; left: 50%; transform: translateX(-50%);
  display: flex; gap: 6px; z-index: 2;
}
.gallery-controls .dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: rgba(255,255,255,0.5); cursor: pointer;
  transition: all var(--transition-fast);
}
.gallery-controls .dot.active { background: #fff; width: 24px; border-radius: 4px; }
.gallery-item {
  position: relative; width: 100%; aspect-ratio: 16/9;
  background: var(--bg-hover); overflow: hidden;
}
.gallery-item img { width: 100%; height: 100%; object-fit: cover; }
.gallery-nav {
  position: absolute; top: 50%; transform: translateY(-50%);
  width: 36px; height: 36px; border-radius: 50%;
  background: rgba(0,0,0,0.5); color: #fff; border: none;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; z-index: 3;
  transition: background var(--transition-fast);
}
.gallery-nav:hover { background: rgba(0,0,0,0.8); }
.gallery-nav.prev { left: 8px; }
.gallery-nav.next { right: 8px; }

.breadcrumbs {
  padding: 1rem 0; font-size: 0.8125rem;
  display: flex; align-items: center; gap: 4px;
  color: var(--text-muted); flex-wrap: wrap;
}
.breadcrumbs a { color: var(--text-muted); text-decoration: none; }
.breadcrumbs a:hover { color: var(--primary); }
.breadcrumbs .separator { color: var(--text-light); }

footer {
  background: var(--bg-footer); border-top: 1px solid var(--border-light);
  padding: 2rem 0 1rem; margin-top: 3rem;
}
.footer-links {
  display: flex; flex-wrap: wrap; gap: 1rem;
  justify-content: center; margin-bottom: 1.5rem;
}
.footer-links a {
  font-size: 0.8125rem; color: var(--text-muted);
  text-decoration: none; transition: color var(--transition-fast);
}
.footer-links a:hover { color: var(--primary); }
.footer-tags {
  display: flex; flex-wrap: wrap; gap: 0.5rem;
  justify-content: center; margin-bottom: 1.5rem;
}
.footer-tags a {
  font-size: 0.75rem; padding: 4px 10px;
  border-radius: var(--radius-full); background: var(--bg-hover);
  color: var(--text-muted); text-decoration: none;
  transition: all var(--transition-fast);
}
.footer-tags a:hover { background: var(--primary-light); color: var(--primary); }
footer .copyright {
  text-align: center; font-size: 0.75rem; color: var(--text-light);
  padding-top: 1rem; border-top: 1px solid var(--border-light);
}

.fab {
  position: fixed; bottom: 24px; right: 24px; z-index: 90;
  width: 56px; height: 56px; border-radius: var(--radius-full);
  background: var(--primary); color: #fff; border: none;
  box-shadow: var(--shadow-lg); cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: all var(--transition-fast);
}
.fab:hover { transform: scale(1.1); box-shadow: 0 14px 28px rgba(0,0,0,0.15); }
.fab svg { width: 24px; height: 24px; }

.article-content {
  max-width: 800px; margin: 0 auto; padding: 2rem 16px;
}
.article-meta {
  display: flex; align-items: center; gap: 1rem;
  margin-bottom: 1.5rem; font-size: 0.875rem; color: var(--text-muted);
}
.article-meta .meta-item { display: flex; align-items: center; gap: 4px; }
.article-body {
  font-size: 1.0625rem; line-height: 1.8;
  color: var(--text-main);
}
.article-body p { margin-bottom: 1rem; }
.article-body h2 {
  font-family: var(--font-display); font-size: 1.5rem; font-weight: 700;
  margin: 2rem 0 1rem;
}
.article-body h3 {
  font-family: var(--font-display); font-size: 1.25rem; font-weight: 700;
  margin: 1.5rem 0 0.75rem;
}
.article-body ul, .article-body ol {
  margin: 1rem 0; padding-left: 1.5rem;
  list-style: disc;
}
.article-body ol { list-style: decimal; }
.article-body li { margin-bottom: 0.5rem; }
.article-body blockquote {
  border-left: 3px solid var(--primary); padding: 0.75rem 1rem;
  margin: 1rem 0; background: var(--primary-light); border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  font-style: italic; color: var(--text-muted);
}
.article-body img {
  border-radius: var(--radius-md); margin: 1.5rem 0;
  box-shadow: var(--shadow-sm);
}
.article-body a { color: var(--text-link); text-decoration: underline; text-underline-offset: 2px; }
.article-body a:hover { color: var(--primary-dark); }

.hashtag {
  display: inline-flex; align-items: center;
  padding: 4px 12px; border-radius: var(--radius-full);
  background: var(--primary-light); color: var(--primary);
  font-size: 0.8125rem; font-weight: 600;
  text-decoration: none; transition: all var(--transition-fast);
}
.hashtag:hover { background: var(--primary); color: #fff; }

.ad-section-buttons {
  display: flex; flex-wrap: wrap; gap: 0.5rem;
  justify-content: center; margin: 1.5rem 0;
}
.ad-section-buttons a {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 10px 20px; border-radius: var(--radius-full);
  font-size: 0.875rem; font-weight: 600;
  text-decoration: none; transition: all var(--transition-fast);
}
.ad-section-buttons .btn-primary {
  background: var(--primary); color: #fff;
}
.ad-section-buttons .btn-primary:hover { background: var(--primary-dark); transform: translateY(-1px); }
.ad-section-buttons .btn-secondary {
  background: var(--bg-hover); color: var(--text-main); border: 1px solid var(--border-color);
}
.ad-section-buttons .btn-secondary:hover { border-color: var(--primary); color: var(--primary); }
.ad-category-btn {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 8px 16px; border-radius: var(--radius-full);
  font-size: 0.875rem; font-weight: 600;
  color: var(--text-muted); text-decoration: none;
  background: var(--bg-card); border: 1px solid var(--border-color);
  transition: all var(--transition-fast);
}
.ad-category-btn:hover {
  color: var(--primary); border-color: var(--primary);
  background: var(--primary-light);
}
.ad-blocks-container {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1rem; margin: 1.5rem 0;
}
.ad-block-item {
  background: var(--bg-card); border-radius: var(--radius-lg);
  padding: 1.25rem; border: 1px solid var(--border-light);
  box-shadow: var(--shadow-sm);
  transition: all var(--transition-normal);
}
.ad-block-item:hover { box-shadow: var(--shadow-md); border-color: var(--primary-light); }
.ad-block-item .ad-block-title {
  font-family: var(--font-display); font-weight: 700; font-size: 1rem;
  margin-bottom: 0.5rem;
}
.ad-block-item .ad-block-desc {
  font-size: 0.875rem; color: var(--text-muted); line-height: 1.5;
  margin-bottom: 0.75rem;
}
.ad-block-item .ad-block-link {
  display: inline-flex; align-items: center; gap: 4px;
  font-size: 0.875rem; font-weight: 600; color: var(--primary);
  text-decoration: none;
}
.ad-block-item .ad-block-link:hover { color: var(--primary-dark); }
.ad-block-media {
  width: 100%; height: 140px; background: var(--bg-hover);
  overflow: hidden; border-radius: var(--radius-md) var(--radius-md) 0 0;
  margin: -1.25rem -1.25rem 0.75rem -1.25rem; width: calc(100% + 2.5rem);
}
.ad-block-media img { width: 100%; height: 100%; object-fit: cover; }
.ad-block-category {
  display: inline-block; padding: 3px 10px; border-radius: var(--radius-full);
  background: var(--primary-light); color: var(--primary);
  font-size: 0.75rem; font-weight: 600; margin-bottom: 0.5rem;
}
.ad-block-btn {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 8px 16px; border-radius: var(--radius-full);
  background: var(--primary); color: #fff;
  font-size: 0.875rem; font-weight: 600;
  transition: background var(--transition-fast);
}
.ad-block-btn:hover { background: var(--primary-dark); }
.ad-block-legal {
  font-size: 0.6875rem; color: var(--text-light);
  margin-top: 0.75rem; padding-top: 0.5rem;
  border-top: 1px solid var(--border-light);
}

.cookie-consent {
  position: fixed; bottom: 0; left: 0; right: 0; z-index: 200;
  background: var(--bg-card); border-top: 1px solid var(--border-color);
  padding: 1rem 2rem; display: flex; align-items: center;
  justify-content: space-between; gap: 1rem;
  box-shadow: 0 -2px 10px rgba(0,0,0,0.1);
}
.cookie-consent p { font-size: 0.875rem; color: var(--text-muted); }
.cookie-consent .cookie-btn {
  padding: 8px 20px; border-radius: var(--radius-full);
  background: var(--primary); color: #fff; border: none;
  font-size: 0.875rem; font-weight: 600;
  cursor: pointer; white-space: nowrap;
  transition: background var(--transition-fast);
}
.cookie-consent .cookie-btn:hover { background: var(--primary-dark); }

.pagination {
  display: flex; justify-content: center; align-items: center;
  gap: 0.5rem; margin: 2rem 0;
}
.pagination a, .pagination span {
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 40px; height: 40px; padding: 0 12px;
  border-radius: var(--radius-md); font-size: 0.875rem; font-weight: 600;
  text-decoration: none; transition: all var(--transition-fast);
}
.pagination a {
  background: var(--bg-card); border: 1px solid var(--border-color);
  color: var(--text-main);
}
.pagination a:hover { border-color: var(--primary); color: var(--primary); background: var(--primary-light); }
.pagination .active {
  background: var(--primary); color: #fff; border: 1px solid var(--primary);
}
.pagination .disabled {
  opacity: 0.4; pointer-events: none;
}
.posts-counter {
  text-align: center; font-size: 0.8125rem; color: var(--text-muted);
  margin: 1rem 0;
}
.video-container { position: relative; width: 100%; }
.video-thumbnail {
  position: relative; cursor: pointer;
}
.video-thumbnail::after {
  content: '\\25B6'; position: absolute; top: 50%; left: 50%;
  transform: translate(-50%, -50%); width: 56px; height: 56px;
  background: rgba(0,0,0,0.6); border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 1.25rem; color: #fff; pointer-events: none;
}
.btn-outline {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 6px 14px; border-radius: var(--radius-full);
  border: 1px solid var(--border-color); color: var(--text-muted);
  font-size: 0.8125rem; font-weight: 600; text-decoration: none;
  transition: all var(--transition-fast);
}
.btn-outline:hover { border-color: var(--primary); color: var(--primary); background: var(--primary-light); }
.amp-badge {
  display: inline-flex; align-items: center; padding: 2px 8px;
  border-radius: var(--radius-full); background: var(--bg-hover);
  color: var(--text-muted); font-size: 0.6875rem; font-weight: 700;
  text-decoration: none;
}
.amp-badge:hover { background: var(--primary-light); color: var(--primary); }

#matrix-bg {
  position: fixed; top: 0; left: 0; width: 100%; height: 100%;
  z-index: -1; opacity: 0.2; pointer-events: none;
}
[data-theme="dark"] #matrix-bg {
  opacity: 0.3;
}

.shop-hero {
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
  padding: 4rem 0; text-align: center; color: #fff;
  position: relative; overflow: hidden;
}
.shop-hero::before {
  content: ''; position: absolute; top: -50%; right: -50%;
  width: 100%; height: 100%;
  background: radial-gradient(circle, rgba(42,171,238,0.15) 0%, transparent 50%);
}
.shop-hero h1 {
  font-family: var(--font-display); font-size: 2.5rem; font-weight: 800;
  margin-bottom: 0.5rem; position: relative; z-index: 1;
}
.shop-hero p {
  font-size: 1.125rem; opacity: 0.85; margin-bottom: 1.5rem;
  position: relative; z-index: 1;
}
.shop-page-container {
  max-width: 1200px; margin: 0 auto; padding: 1.5rem 16px;
  position: relative; z-index: 1;
}
.shop-search-bar {
  display: flex; gap: 0.75rem; margin-bottom: 1.5rem;
  padding: 0.5rem; background: var(--bg-card);
  border-radius: var(--radius-lg); border: 1px solid var(--border-color);
  box-shadow: var(--shadow-sm);
}
.shop-search-bar input {
  flex: 1; padding: 12px 16px; border: none; outline: none;
  font-size: 1rem; background: transparent; color: var(--text-main);
}
.shop-search-bar input::placeholder { color: var(--text-light); }
.shop-search-bar button {
  padding: 12px 24px; border-radius: var(--radius-md);
  background: var(--primary); color: #fff; border: none;
  font-weight: 600; font-size: 0.9375rem;
  cursor: pointer; transition: background var(--transition-fast);
}
.shop-search-bar button:hover { background: var(--primary-dark); }
.shop-product-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 1rem; margin-bottom: 2rem;
}
.shop-product-card {
  background: var(--bg-card); border-radius: var(--radius-lg);
  overflow: hidden; border: 1px solid var(--border-light);
  box-shadow: var(--shadow-telegram);
  transition: all var(--transition-normal);
}
.shop-product-card:hover { box-shadow: var(--shadow-lg); border-color: var(--primary-light); transform: translateY(-2px); }
.shop-product-card .product-image {
  width: 100%; height: 200px; background: var(--bg-hover);
  overflow: hidden; position: relative;
}
.shop-product-card .product-image img { width: 100%; height: 100%; object-fit: cover; transition: transform var(--transition-normal); }
.shop-product-card:hover .product-image img { transform: scale(1.05); }
.shop-product-card .product-info { padding: 1rem; }
.shop-product-card .product-name {
  font-family: var(--font-display); font-size: 0.9375rem; font-weight: 700;
  line-height: 1.4; margin-bottom: 0.5rem;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.shop-product-card .product-name a { color: var(--text-main); text-decoration: none; }
.shop-product-card .product-name a:hover { color: var(--primary); }
.shop-product-card .product-price {
  font-size: 1.125rem; font-weight: 800; color: var(--primary);
  margin-bottom: 0.5rem;
}
.shop-product-card .product-category {
  font-size: 0.75rem; color: var(--text-muted);
  display: inline-flex; align-items: center; gap: 4px;
  padding: 3px 8px; background: var(--bg-hover);
  border-radius: var(--radius-full);
}
.shop-product-card .product-availability {
  font-size: 0.75rem; font-weight: 600; margin-top: 0.5rem;
}
.shop-product-card .product-availability.in-stock { color: #2da44e; }
.shop-product-card .product-availability.out-of-stock { color: #cf222e; }
.shop-widget {
  background: var(--bg-card); border-radius: var(--radius-lg);
  border: 1px solid var(--border-light); padding: 1.25rem;
  margin: 1.5rem 0; box-shadow: var(--shadow-sm);
}
.widget-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 1rem; padding-bottom: 0.75rem;
  border-bottom: 1px solid var(--border-light);
}
.widget-title {
  font-family: var(--font-display); font-weight: 700; font-size: 1rem;
}
.widget-link {
  font-size: 0.8125rem; color: var(--primary); text-decoration: none;
  font-weight: 600;
}
.widget-link:hover { text-decoration: underline; }
.widget-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 0.75rem;
}
.widget-product {
  display: block; padding: 0.75rem; border-radius: var(--radius-md);
  border: 1px solid var(--border-light); text-decoration: none;
  transition: all var(--transition-fast); background: var(--bg-body);
}
.widget-product:hover { border-color: var(--primary); transform: translateY(-1px); }
.widget-product img {
  width: 100%; height: 80px; object-fit: cover;
  border-radius: var(--radius-sm); margin-bottom: 0.5rem;
}
.wp-name {
  font-size: 0.8125rem; font-weight: 600; color: var(--text-main);
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden; margin-bottom: 0.25rem;
}
.wp-price {
  font-size: 0.875rem; font-weight: 800; color: var(--primary);
}

.archive-page-container { max-width: 1200px; margin: 0 auto; padding: 0 16px; position: relative; z-index: 1; }
.archive-post-container { max-width: 800px; margin: 0 auto; padding: 0 16px; position: relative; z-index: 1; }
.archive-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
.archive-card {
  background: var(--bg-card); border-radius: var(--radius-lg); overflow: hidden;
  box-shadow: var(--shadow-telegram); border: 1px solid var(--border-light);
  transition: all var(--transition-normal);
}
.archive-card:hover { box-shadow: var(--shadow-lg); border-color: var(--primary-light); transform: translateY(-2px); }
.archive-card-media { position: relative; width: 100%; height: 200px; background: var(--bg-hover); overflow: hidden; }
.archive-card-media img { width: 100%; height: 100%; object-fit: cover; }
.archive-card-video { position: relative; width: 100%; height: 200px; background: #000; }
.archive-card-video::after {
  content: '\\25B6'; position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
  width: 48px; height: 48px; background: rgba(0,0,0,0.7); border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 1.25rem; color: white;
}
.archive-card-body { padding: 0.75rem; }
.archive-card-image {
  width: 100%; height: 180px; object-fit: cover;
  border-radius: var(--radius-lg) var(--radius-lg) 0 0;
}
.archive-card-noimg {
  width: 100%; height: 80px; display: flex; align-items: center;
  justify-content: center; background: var(--bg-hover);
  font-size: 2rem; border-radius: var(--radius-lg) var(--radius-lg) 0 0;
}
.archive-video-card {
  width: 100%; height: 180px; position: relative;
  border-radius: var(--radius-lg) var(--radius-lg) 0 0;
  overflow: hidden;
}
.archive-video-play-btn {
  position: absolute; top: 50%; left: 50%;
  transform: translate(-50%, -50%); width: 48px; height: 48px;
  background: rgba(0,0,0,0.7); border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
}
.archive-video-play-btn::after {
  content: '\\25B6'; color: white; font-size: 1rem; margin-left: 3px;
}
.archive-card-content { padding: 1rem; }
.archive-card-text {
  font-size: 0.875rem; color: var(--text-main); line-height: 1.5;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;
  margin-bottom: 0.75rem;
}
.archive-card-meta {
  font-size: 0.75rem; color: var(--text-muted);
  display: flex; justify-content: space-between; align-items: center;
}
.archive-pagination {
  display: flex; justify-content: center; gap: 1rem; margin: 2rem 0;
}
.archive-pagination a {
  display: inline-flex; align-items: center; gap: 0.5rem;
  padding: 0.75rem 1.5rem; border-radius: var(--radius-md);
  border: 1px solid var(--border-color); background: var(--bg-card);
  color: var(--text-main); font-weight: 600; font-size: 0.875rem;
  text-decoration: none; transition: all var(--transition-fast);
}
.archive-pagination a:hover { border-color: var(--primary); color: var(--primary); background: var(--primary-light); }

.product-detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 2rem; margin-bottom: 2rem; }

@media (max-width: 768px) {
  .header-content { padding: 0 12px; }
  .main-nav { display: none; }
  .main-nav.open {
    display: flex; flex-direction: column;
    position: absolute; top: 60px; left: 0; right: 0;
    background: var(--bg-card); border-bottom: 1px solid var(--border-light);
    padding: 8px; box-shadow: var(--shadow-md); z-index: 99;
  }
  .mobile-menu-btn { display: flex; }
  .hero h1 { font-size: 1.75rem; }
  .hero p { font-size: 1rem; }
  .posts-feed { grid-template-columns: 1fr; }
  .post-feed-media { height: 200px; }
  .ad-blocks-container { grid-template-columns: 1fr; }
  .shop-product-grid { grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); }
  .archive-grid { grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); }
  .product-detail-grid { grid-template-columns: 1fr; }
  .cookie-consent { flex-direction: column; text-align: center; }
  .footer-links { flex-direction: column; align-items: center; }
}
@media (max-width: 480px) {
  .hero { padding: 2rem 0; }
  .hero h1 { font-size: 1.5rem; }
  .hero p { font-size: 0.875rem; }
  .search-input { padding: 12px 48px 12px 16px; font-size: 0.9375rem; }
  .btn-cta { padding: 10px 20px; font-size: 0.9375rem; }
  .posts-feed { gap: 0.75rem; }
  .post-feed-content h3 { font-size: 0.9375rem; }
  .shop-search-bar { flex-direction: column; }
  .shop-search-bar button { width: 100%; }
  .shop-product-grid { grid-template-columns: 1fr; }
  .archive-grid { grid-template-columns: 1fr; }
  .product-detail-grid { grid-template-columns: 1fr; }
  .fab { bottom: 16px; right: 16px; width: 48px; height: 48px; }
  .fab svg { width: 20px; height: 20px; }
  .pagination a, .pagination span { min-width: 36px; height: 36px; font-size: 0.8125rem; }
}
"""

AMP_CSS = """
/* AMP-specific minimal CSS */
:root {
  --primary: #2481CC; --primary-dark: #1D6FAD; --primary-light: #E6F3FF;
  --secondary: #2AABEE; --accent: #0088cc; --bg-body: #F4F4F5; --bg-card: #FFFFFF;
  --text-main: #000000; --text-muted: #707579; --text-link: #2481CC;
  --border-color: #DADCE0; --border-light: #E8E8E8;
  --radius-sm: 8px; --radius-md: 12px; --radius-lg: 16px; --radius-full: 9999px;
  --font-main: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  --font-display: 'Manrope', 'Inter', sans-serif;
}
*, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: var(--font-main); background: var(--bg-body); color: var(--text-main); line-height: 1.6; }
a { color: var(--text-link); text-decoration: none; }
img { max-width: 100%; height: auto; display: block; }
.container { max-width: 1200px; margin: 0 auto; padding: 0 16px; }
.site-header { background: rgba(255,255,255,0.95); border-bottom: 1px solid var(--border-light); }
.header-content { display: flex; align-items: center; justify-content: space-between; max-width: 1200px; margin: 0 auto; padding: 0 16px; height: 60px; }
.logo { font-family: var(--font-display); font-weight: 800; font-size: 1.25rem; color: var(--text-main); text-decoration: none; }
.hero { background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%); padding: 3rem 0; text-align: center; color: #fff; }
.hero h1 { font-family: var(--font-display); font-size: 2.5rem; font-weight: 800; margin-bottom: 0.5rem; }
.hero p { font-size: 1.125rem; opacity: 0.9; margin-bottom: 1.5rem; }
.posts-feed { display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 1rem; padding: 1.5rem 0; }
.post-feed-item { background: var(--bg-card); border-radius: var(--radius-lg); overflow: hidden; border: 1px solid var(--border-light); }
.post-feed-media { width: 100%; height: 220px; background: var(--bg-body); overflow: hidden; }
.post-feed-media img { width: 100%; height: 100%; object-fit: cover; }
.post-feed-content { padding: 1rem; }
.post-feed-content h3 { font-family: var(--font-display); font-size: 1rem; font-weight: 700; line-height: 1.4; margin-bottom: 0.5rem; }
.post-feed-content h3 a { color: var(--text-main); text-decoration: none; }
.post-feed-text { font-size: 0.875rem; color: var(--text-muted); line-height: 1.5; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; margin-bottom: 0.75rem; }
.post-feed-meta { display: flex; justify-content: space-between; align-items: center; font-size: 0.75rem; color: var(--text-muted); }
footer { background: #fff; border-top: 1px solid var(--border-light); padding: 2rem 0 1rem; margin-top: 3rem; }
.footer-links { display: flex; flex-wrap: wrap; gap: 1rem; justify-content: center; margin-bottom: 1.5rem; }
.footer-links a { font-size: 0.8125rem; color: var(--text-muted); text-decoration: none; }
footer .copyright { text-align: center; font-size: 0.75rem; color: #999; padding-top: 1rem; border-top: 1px solid var(--border-light); }
.article-content { max-width: 800px; margin: 0 auto; padding: 2rem 16px; }
.article-body { font-size: 1.0625rem; line-height: 1.8; color: var(--text-main); }
.article-body p { margin-bottom: 1rem; }
.article-body h2 { font-family: var(--font-display); font-size: 1.5rem; font-weight: 700; margin: 2rem 0 1rem; }
.article-body h3 { font-family: var(--font-display); font-size: 1.25rem; font-weight: 700; margin: 1.5rem 0 0.75rem; }
.article-body img { border-radius: var(--radius-md); margin: 1.5rem 0; }
.hashtag { display: inline-flex; align-items: center; padding: 4px 12px; border-radius: var(--radius-full); background: var(--primary-light); color: var(--primary); font-size: 0.8125rem; font-weight: 600; text-decoration: none; }
@media (max-width: 768px) { .posts-feed { grid-template-columns: 1fr; } .hero h1 { font-size: 1.75rem; } }
@media (max-width: 480px) { .hero h1 { font-size: 1.5rem; } .posts-feed { gap: 0.75rem; } }
"""

ARCHIVE_CSS = """
.archive-page-container { max-width: 1200px; margin: 0 auto; padding: 0 16px; position: relative; z-index: 1; }
.archive-post-container { max-width: 800px; margin: 0 auto; padding: 0 16px; position: relative; z-index: 1; }
.archive-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
.archive-card {
  background: var(--bg-card); border-radius: var(--radius-lg); overflow: hidden;
  box-shadow: var(--shadow-telegram); border: 1px solid var(--border-light);
  transition: all var(--transition-normal);
}
.archive-card:hover { box-shadow: var(--shadow-lg); border-color: var(--primary-light); transform: translateY(-2px); }
.archive-card-media { position: relative; width: 100%; height: 200px; background: var(--bg-hover); overflow: hidden; }
.archive-card-media img { width: 100%; height: 100%; object-fit: cover; }
.archive-card-video { position: relative; width: 100%; height: 200px; background: #000; }
.archive-card-video::after {
  content: '\\25B6'; position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
  width: 48px; height: 48px; background: rgba(0,0,0,0.7); border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 1.25rem; color: white;
}
.archive-card-content { padding: 1rem; }
.archive-card-text {
  font-size: 0.875rem; color: var(--text-main); line-height: 1.5;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;
  margin-bottom: 0.75rem;
}
.archive-card-meta {
  font-size: 0.75rem; color: var(--text-muted);
  display: flex; justify-content: space-between; align-items: center;
}
.archive-pagination {
  display: flex; justify-content: center; gap: 1rem; margin: 2rem 0;
}
.archive-pagination a {
  display: inline-flex; align-items: center; gap: 0.5rem;
  padding: 0.75rem 1.5rem; border-radius: var(--radius-md);
  border: 1px solid var(--border-color); background: var(--bg-card);
  color: var(--text-main); font-weight: 600; font-size: 0.875rem;
  text-decoration: none; transition: all var(--transition-fast);
}
.archive-pagination a:hover { border-color: var(--primary); color: var(--primary); background: var(--primary-light); }
@media (max-width: 768px) { .archive-grid { grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); } }
@media (max-width: 480px) { .archive-grid { grid-template-columns: 1fr; } }
"""
