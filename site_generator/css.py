"""
CSS Stylesheets for the SochiAutoParts static site generator.

Contains the EXACT CSS from the original Cloudflare Worker v27.0,
extracted directly from the Worker source. This ensures pixel-perfect
design parity between the static site and the original Worker site.
"""

# =============================================================================
# Main CSS — extracted from Worker v27.0 CSS_STYLES constant
# =============================================================================

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
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html { scroll-behavior: smooth; -webkit-text-size-adjust: 100%; font-size: 16px; text-rendering: optimizeLegibility; }
body { font-family: var(--font-main); background-color: var(--bg-body); color: var(--text-main); line-height: 1.6; min-height: 100vh; display: flex; flex-direction: column; }
a { text-decoration: none; color: inherit; transition: color var(--transition-fast); cursor: pointer; }
img, video { max-width: 100%; height: auto; display: block; }
.container { max-width: 800px; margin: 0 auto; padding: 0 16px; position: relative; z-index: 1; }
@media (max-width: 768px) { .container { padding: 0 12px; max-width: 100%; box-sizing: border-box; } }
.site-header { background: var(--bg-header); padding: 0.75rem 0; border-bottom: 1px solid var(--border-color); position: sticky; top: 0; z-index: 1000; backdrop-filter: blur(20px); transition: all var(--transition-normal); box-shadow: var(--shadow-sm); }
.header-content { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem; }
.logo { font-size: 1.375rem; font-weight: 700; color: var(--text-main); display: flex; align-items: center; gap: 0.625rem; font-family: var(--font-display); white-space: nowrap; }
.logo-icon { width: 40px; height: 40px; border-radius: var(--radius-full); object-fit: cover; box-shadow: var(--shadow-sm); border: 2px solid var(--border-light); }
.logo-fallback { display: none; font-size: 1.5rem; }
.logo img.error + .logo-fallback { display: inline-block; }
.logo img.error { display: none; }
.main-nav { display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap; }
.main-nav a { color: var(--text-main); text-decoration: none; font-size: 0.875rem; font-weight: 600; opacity: 0.85; transition: opacity 0.2s; white-space: nowrap; }
.main-nav a:hover { opacity: 1; }
.main-nav a.active { color: var(--accent); opacity: 1; font-weight: 700; }
.mobile-menu-btn { display: none; width: 40px; height: 40px; border: 1px solid var(--border-color); border-radius: var(--radius-sm); background: var(--bg-card); color: var(--text-main); cursor: pointer; align-items: center; justify-content: center; font-size: 1.25rem; transition: all var(--transition-fast); flex-shrink: 0; }
.mobile-menu-btn:hover { background: var(--bg-hover); }
.controls-group { display: flex; gap: 0.5rem; align-items: center; }
.lang-switcher, .theme-toggle { display: flex; background: var(--bg-hover); padding: 3px; border-radius: var(--radius-md); border: 1px solid var(--border-color); gap: 2px; }
.lang-btn, .theme-btn { padding: 6px 14px; border: none; background: transparent; color: var(--text-muted); font-weight: 600; border-radius: var(--radius-sm); cursor: pointer; transition: all var(--transition-fast); font-size: 0.8125rem; }
.lang-btn:hover, .theme-btn:hover { color: var(--text-main); background: var(--bg-card); }
.lang-btn.active, .theme-btn.active { background: var(--bg-card); color: var(--primary); box-shadow: var(--shadow-sm); font-weight: 700; }
@media (max-width: 768px) {
  .header-content { gap: 0.5rem; }
  .mobile-menu-btn { display: flex; }
  .main-nav { display: none; width: 100%; flex-direction: column; gap: 0; padding: 0.75rem 0; border-top: 1px solid var(--border-light); order: 10; }
  .main-nav.open { display: flex; }
  .main-nav a { padding: 0.625rem 0; font-size: 0.9375rem; width: 100%; }
  .controls-group { gap: 0.375rem; }
  .logo { font-size: 1.125rem; gap: 0.5rem; }
  .logo-icon { width: 36px; height: 36px; }
}
.hero { background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%); padding: 3rem 1rem; text-align: center; border-radius: 0 0 24px 24px; margin-bottom: 2rem; position: relative; overflow: hidden; box-shadow: var(--shadow-lg); }
.hero h1 { font-family: var(--font-display); font-size: clamp(1.75rem, 4vw, 2.5rem); font-weight: 800; margin-bottom: 0.75rem; letter-spacing: -0.03em; color: #FFFFFF; line-height: 1.1; }
.hero p { font-size: 1rem; color: rgba(255, 255, 255, 0.95); max-width: 600px; margin: 0 auto 1rem; }
.search-container { max-width: 500px; margin: 0 auto; position: relative; }
.search-input { width: 100%; padding: 14px 48px 14px 20px; border: none; border-radius: var(--radius-full); font-size: 0.9375rem; font-family: var(--font-main); background: rgba(255, 255, 255, 0.95); color: #1A1A1A; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15); transition: all var(--transition-normal); outline: none; }
.search-input::placeholder { color: rgba(0, 0, 0, 0.5); }
.search-input:focus { background: #FFFFFF; box-shadow: 0 6px 30px rgba(0, 0, 0, 0.25); transform: translateY(-2px); }
.search-btn { position: absolute; right: 6px; top: 50%; transform: translateY(-50%); width: 40px; height: 40px; border: none; border-radius: var(--radius-full); background: var(--primary); color: white; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all var(--transition-fast); }
.search-btn:hover { background: var(--primary-dark); transform: translateY(-50%) scale(1.05); }
.search-btn:active { transform: translateY(-50%) scale(0.95); }
.search-results { display: none; position: absolute; top: 100%; left: 0; right: 0; margin-top: 8px; background: var(--bg-card); border-radius: var(--radius-lg); box-shadow: var(--shadow-lg); border: 1px solid var(--border-color); overflow: hidden; z-index: 100; max-height: 400px; overflow-y: auto; }
.search-results.active { display: block; animation: fadeIn 0.2s ease-out; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(-10px); } to { opacity: 1; transform: translateY(0); } }
.search-result-item { padding: 12px 16px; border-bottom: 1px solid var(--border-light); cursor: pointer; transition: all var(--transition-fast); }
.search-result-item:hover { background: var(--bg-hover); }
.search-result-item:last-child { border-bottom: none; }
.search-result-title { font-size: 0.875rem; font-weight: 600; color: var(--text-main); margin-bottom: 4px; }
.search-result-meta { font-size: 0.75rem; color: var(--text-muted); }
.search-no-results { padding: 20px; text-align: center; color: var(--text-muted); font-size: 0.875rem; }
.btn-cta { display: inline-flex; align-items: center; justify-content: center; gap: 10px; background: #FFFFFF; color: var(--primary); padding: 12px 28px; font-weight: 700; border-radius: var(--radius-full); box-shadow: 0 8px 20px rgba(0, 0, 0, 0.2); transition: all var(--transition-normal); font-size: 0.9375rem; border: none; cursor: pointer; margin-top: 1rem; }
.btn-cta:hover { transform: translateY(-3px); box-shadow: 0 12px 28px rgba(0, 0, 0, 0.25); background: var(--primary-light); }
.seo-block { background: var(--bg-card); padding: 1.5rem; border-radius: var(--radius-lg); box-shadow: var(--shadow-telegram); margin-bottom: 2rem; border: 1px solid var(--border-color); position: relative; z-index: 2; }
.seo-block h2 { margin-bottom: 0.75rem; color: var(--text-main); font-size: 1.25rem; font-weight: 700; font-family: var(--font-display); }
.seo-block p { margin-bottom: 0.75rem; color: var(--text-muted); line-height: 1.7; font-size: 0.9375rem; }
.seo-block a { color: var(--text-link); font-weight: 600; }
.posts-feed { display: flex; flex-direction: column; gap: 1rem; margin-bottom: 2rem; position: relative; z-index: 2; }
.post-feed-item { background: var(--bg-card); border-radius: var(--radius-lg); box-shadow: var(--shadow-telegram); overflow: hidden; border: 1px solid var(--border-light); transition: all var(--transition-normal); position: relative; opacity: 0; animation: fadeInUp 0.5s ease-out forwards; }
@keyframes fadeInUp { from { opacity: 0; transform: translateY(15px); } to { opacity: 1; transform: translateY(0); } }
.post-feed-item:hover { box-shadow: var(--shadow-lg); border-color: var(--primary-light); }
.post-feed-media { position: relative; width: 100%; max-height: 600px; background: var(--bg-hover); overflow: hidden; }
.post-feed-media img { width: 100%; height: auto; max-height: 600px; object-fit: contain; transition: transform var(--transition-normal); }
.post-feed-item:hover .post-feed-media img { transform: scale(1.02); }
.video-container { width: 100%; max-height: 600px; background: #000; position: relative; }
.video-thumbnail { width: 100%; height: auto; max-height: 600px; object-fit: contain; cursor: pointer; position: relative; }
.video-thumbnail::after { content: '▶'; position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 64px; height: 64px; background: rgba(0, 0, 0, 0.7); backdrop-filter: blur(8px); border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 1.5rem; color: white; transition: all var(--transition-fast); border: 3px solid rgba(255,255,255,0.5); }
.video-thumbnail:hover::after { transform: translate(-50%, -50%) scale(1.15); background: var(--primary); border-color: #FFFFFF; }
.video-card-link { display: block; text-decoration: none; color: inherit; }
.video-card-preview { position: relative; cursor: pointer; overflow: hidden; border-radius: var(--radius-lg) var(--radius-lg) 0 0; }
.video-card-preview img { display: block; width: 100%; max-height: 400px; object-fit: cover; transition: transform var(--transition-normal); }
.video-card-link:hover .video-card-preview img { transform: scale(1.03); }
.video-play-overlay { position: absolute; top: 0; left: 0; width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; z-index: 2; pointer-events: none; }
.video-play-overlay::after { content: '▶'; width: 64px; height: 64px; background: rgba(0, 0, 0, 0.7); backdrop-filter: blur(8px); border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 1.5rem; color: white; transition: all var(--transition-fast); border: 3px solid rgba(255,255,255,0.5); }
.video-card-link:hover .video-play-overlay::after { transform: scale(1.15); background: var(--primary); border-color: #FFFFFF; }
.video-placeholder-card { background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 220px; cursor: pointer; transition: background var(--transition-fast); }
.video-card-link:hover .video-placeholder-card { background: linear-gradient(135deg, #1a1a3e 0%, #16214e 100%); }
.video-placeholder-icon { font-size: 3rem; color: white; margin-bottom: 0.5rem; width: 80px; height: 80px; background: rgba(0,0,0,0.5); border-radius: 50%; display: flex; align-items: center; justify-content: center; border: 3px solid rgba(255,255,255,0.3); transition: all var(--transition-fast); }
.video-card-link:hover .video-placeholder-icon { background: var(--primary); border-color: #FFFFFF; transform: scale(1.1); }
.video-placeholder-text { color: rgba(255,255,255,0.7); font-size: 0.875rem; font-weight: 600; letter-spacing: 1px; text-transform: uppercase; }
.post-feed-content { padding: 1.25rem; }
.post-feed-meta { font-size: 0.75rem; color: var(--text-muted); margin-bottom: 0.5rem; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.post-feed-title { font-size: 1.125rem; font-weight: 700; line-height: 1.4; margin-bottom: 0.75rem; color: var(--text-main); font-family: var(--font-display); }
.post-feed-title a:hover { color: var(--text-link); }
.post-feed-text { font-size: 0.9375rem; color: var(--text-main); margin-bottom: 1rem; line-height: 1.7; word-wrap: break-word; white-space: pre-wrap; }
.post-feed-text .hashtag { color: var(--text-link); font-weight: 500; cursor: pointer; transition: all var(--transition-fast); display: inline-block; padding: 0 2px; border-radius: 4px; }
.post-feed-text .hashtag:hover { color: var(--primary-dark); background: var(--primary-light); }
.post-feed-actions { display: flex; gap: 10px; flex-wrap: wrap; padding-top: 0.75rem; border-top: 1px solid var(--border-light); }
.btn-outline, .btn-primary { flex: 1; min-width: 100px; padding: 10px 16px; text-align: center; border-radius: var(--radius-md); font-weight: 600; font-size: 0.875rem; transition: all var(--transition-fast); cursor: pointer; border: none; font-family: var(--font-main); }
.btn-outline { border: 1px solid var(--border-color); color: var(--text-main); background: transparent; }
.btn-outline:hover { border-color: var(--text-main); background: var(--bg-hover); }
.btn-primary { background: var(--primary); color: white; box-shadow: 0 3px 10px rgba(36, 129, 204, 0.3); }
.btn-primary:hover { background: var(--primary-dark); transform: translateY(-2px); box-shadow: 0 5px 15px rgba(36, 129, 204, 0.4); }
.load-more-container { text-align: center; padding: 2rem 0 2.5rem; position: relative; z-index: 2; }
.btn-load-more { display: inline-flex; align-items: center; gap: 10px; padding: 12px 36px; background: var(--bg-card); color: var(--text-main); border: 1px solid var(--border-color); border-radius: var(--radius-full); font-weight: 700; font-size: 0.9375rem; cursor: pointer; transition: all var(--transition-normal); font-family: var(--font-main); box-shadow: var(--shadow-sm); }
.btn-load-more:hover { border-color: var(--primary); color: var(--primary); transform: translateY(-2px); box-shadow: var(--shadow-md); }
.btn-load-more:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
.btn-load-more .spinner { width: 18px; height: 18px; border: 2px solid var(--border-color); border-top-color: var(--primary); border-radius: 50%; animation: spin 0.8s linear infinite; display: none; }
.btn-load-more.loading .spinner { display: block; }
.btn-load-more.loading .btn-text { display: none; }
@keyframes spin { to { transform: rotate(360deg); } }
.related-posts { margin-top: 3rem; padding-top: 2rem; border-top: 1px solid var(--border-color); position: relative; z-index: 2; margin-bottom: 3rem; }
.related-posts h3 { font-size: 1.25rem; margin-bottom: 1.5rem; color: var(--text-main); font-weight: 700; font-family: var(--font-display); }
.related-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 1rem; }
.related-card { background: var(--bg-card); border-radius: var(--radius-lg); overflow: hidden; box-shadow: var(--shadow-telegram); transition: all var(--transition-normal); border: 1px solid var(--border-light); }
.related-card:hover { transform: translateY(-4px); box-shadow: var(--shadow-lg); }
.related-card-media { height: 140px; background: var(--bg-hover); overflow: hidden; }
.related-card-media img { width: 100%; height: 100%; object-fit: cover; transition: transform var(--transition-normal); }
.related-card:hover .related-card-media img { transform: scale(1.08); }
.related-card-content { padding: 0.875rem; }
.related-card-title { font-size: 0.875rem; font-weight: 600; color: var(--text-main); line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; margin-bottom: 0.5rem; font-family: var(--font-display); }
.related-card-date { font-size: 0.75rem; color: var(--text-muted); }
.single-post-media { width: 100%; border-radius: var(--radius-lg); margin-bottom: 1.5rem; overflow: hidden; box-shadow: var(--shadow-md); }
.single-post-media img, .single-post-media video { width: 100%; height: auto; max-height: 600px; display: block; object-fit: contain; background: #000; }
.post-gallery { position: relative; width: 100%; border-radius: var(--radius-lg); overflow: hidden; margin-bottom: 1.5rem; display: flex; flex-direction: column; gap: 12px; }
.gallery-item { display: block; width: 100%; }
.gallery-item img, .gallery-item video { width: 100%; height: auto; max-height: 600px; object-fit: contain; background: #000; display: block; border-radius: var(--radius-md); }
.gallery-controls { display: none; }
.gallery-counter { display: none; }
.breadcrumbs { padding: 1rem 0; font-size: 0.875rem; color: var(--text-muted); }
.breadcrumbs a { color: var(--text-link); font-weight: 500; }
.breadcrumbs a:hover { text-decoration: underline; }
.breadcrumbs span { margin: 0 0.5rem; opacity: 0.5; }
footer { text-align: center; padding: 3rem 1rem; border-top: 1px solid var(--border-color); color: var(--text-muted); margin-top: auto; background: var(--bg-footer); position: relative; z-index: 2; max-width: 800px; margin-left: auto; margin-right: auto; width: 100%; }
footer a { color: var(--text-muted); transition: color var(--transition-fast); }
footer a:hover { color: var(--text-link); }
.footer-links { display: flex; justify-content: center; gap: 1.5rem; margin-top: 1.5rem; flex-wrap: wrap; font-size: 0.875rem; }
.footer-tags { margin-top: 2rem; padding-top: 1.5rem; border-top: 1px solid var(--border-light); }
.footer-tags-title { font-size: 0.875rem; font-weight: 600; color: var(--text-muted); margin-bottom: 0.75rem; }
.footer-tags-list { display: flex; flex-wrap: wrap; justify-content: center; gap: 0.5rem; }
.footer-tag { display: inline-block; padding: 4px 10px; background: var(--bg-hover); color: var(--text-link); border-radius: var(--radius-sm); font-size: 0.8125rem; transition: all var(--transition-fast); }
.footer-tag:hover { background: var(--primary-light); color: var(--primary-dark); transform: translateY(-1px); }
.fab { position: fixed; bottom: 20px; right: 20px; width: 52px; height: 52px; background: #0088cc; color: white; border-radius: 50%; display: flex; align-items: center; justify-content: center; box-shadow: 0 6px 20px rgba(0, 136, 104, 0.4); z-index: 1000; font-size: 22px; transition: all var(--transition-normal); border: none; cursor: pointer; }
.fab:hover { transform: scale(1.12); box-shadow: 0 10px 30px rgba(0, 136, 104, 0.5); }
.article-content { background: var(--bg-card); padding: 2rem; border-radius: var(--radius-lg); box-shadow: var(--shadow-telegram); margin-bottom: 2rem; border: 1px solid var(--border-color); position: relative; z-index: 2; }
.article-content h1 { font-size: 1.75rem; line-height: 1.3; margin-bottom: 1.25rem; color: var(--text-main); font-weight: 800; font-family: var(--font-display); }
.article-meta { color: var(--text-muted); font-size: 0.875rem; margin-bottom: 1.5rem; display: flex; align-items: center; gap: 1rem; flex-wrap: wrap; }
.article-body { font-size: 1rem; line-height: 1.75; color: var(--text-main); }
.article-body p { margin-bottom: 1rem; }
.article-body a { color: var(--text-link); font-weight: 600; text-decoration: underline; text-underline-offset: 3px; }
.article-body a:hover { color: var(--primary-dark); }
.article-body .hashtag { color: var(--text-link); font-weight: 500; cursor: pointer; transition: all var(--transition-fast); display: inline-block; padding: 0 4px; border-radius: 4px; margin-right: 4px; }
.article-body .hashtag:hover { color: var(--primary-dark); background: var(--primary-light); }
.hashtag { color: var(--text-link); font-weight: 500; margin-right: 6px; display: inline-block; position: relative; }
.ad-section-buttons { display: flex; flex-wrap: wrap; gap: 0.75rem; justify-content: center; margin: 2rem 0 1.5rem; }
.ad-btn-category { padding: 0.6rem 1.25rem; border-radius: var(--radius-full); background: var(--bg-card); color: var(--text-main); border: 1px solid var(--border-color); font-weight: 600; font-size: 0.875rem; transition: all var(--transition-fast); text-decoration: none; display: inline-flex; align-items: center; justify-content: center; }
.ad-btn-category:hover { background: var(--primary); color: white; border-color: var(--primary); transform: translateY(-2px); box-shadow: var(--shadow-md); }
.ad-btn-category.active { background: var(--primary); color: white; border-color: var(--primary); }
.ad-blocks-container { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1.5rem; margin: 2rem 0; }
.ad-block-item { background: var(--bg-card); border-radius: var(--radius-lg); padding: 0; border: 1px solid var(--border-light); box-shadow: var(--shadow-sm); transition: all var(--transition-normal); display: flex; flex-direction: column; align-items: center; text-align: center; overflow: hidden; position: relative; cursor: pointer; }
.ad-block-item:hover { transform: translateY(-6px); box-shadow: 0 12px 28px rgba(0,0,0,0.15); border-color: var(--primary); }
.ad-block-media { width: 100%; height: 200px; display: flex; align-items: center; justify-content: center; background: var(--bg-hover); border-radius: var(--radius-md); margin-bottom: 1rem; overflow: hidden; flex-shrink: 0; }
.ad-block-media img { max-width: 100%; max-height: 100%; object-fit: cover; transition: transform var(--transition-normal); }
.ad-block-item:hover .ad-block-media img { transform: scale(1.05); }
.ad-block-category { display: inline-block; background: var(--primary-light); color: var(--primary-dark); padding: 0.25rem 0.75rem; border-radius: var(--radius-full); font-size: 0.7rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.5rem; }
.ad-block-title { font-size: 1.0625rem; font-weight: 700; color: var(--text-main); margin: 0 0 0.5rem; line-height: 1.3; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.ad-block-desc { font-size: 0.875rem; color: var(--text-muted); margin: 0 0 0.75rem; line-height: 1.5; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; flex-grow: 1; }
.ad-block-btn { width: 100%; padding: 0.875rem 1rem; background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%); color: white; font-weight: 700; font-size: 0.9375rem; text-decoration: none; transition: all var(--transition-normal); border: none; cursor: pointer; display: inline-flex; align-items: center; justify-content: center; gap: 0.5rem; }
.ad-block-btn:hover { background: linear-gradient(135deg, var(--primary-dark) 0%, var(--accent) 100%); transform: translateY(-1px); box-shadow: 0 6px 20px rgba(36, 129, 204, 0.4); }
.ad-block-legal { margin-top: 0.75rem; font-size: 0.65rem; color: var(--text-light); line-height: 1.4; }
.affiliate-program-card { background: var(--bg-card); border: 1px solid var(--border-light); border-radius: var(--radius-lg); padding: 1.5rem; margin-bottom: 1rem; transition: all var(--transition-normal); box-shadow: var(--shadow-sm); }
.affiliate-program-card:hover { transform: translateY(-4px); box-shadow: var(--shadow-lg); border-color: var(--primary-light); }
.cookie-consent { position: fixed; bottom: 0; left: 0; right: 0; background: var(--bg-card); border-top: 1px solid var(--border-color); padding: 1rem; box-shadow: 0 -4px 20px rgba(0,0,0,0.1); z-index: 2000; display: none; }
.cookie-consent.active { display: block; animation: slideUp 0.3s ease-out; }
@keyframes slideUp { from { transform: translateY(100%); } to { transform: translateY(0); } }
.cookie-consent-content { max-width: 800px; margin: 0 auto; display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 1rem; }
.cookie-consent-text { font-size: 0.875rem; color: var(--text-main); flex: 1; min-width: 200px; }
.cookie-consent-text a { color: var(--text-link); text-decoration: underline; }
.cookie-consent-actions { display: flex; gap: 0.5rem; flex-wrap: wrap; }
.cookie-btn { padding: 8px 16px; border-radius: var(--radius-md); font-size: 0.875rem; font-weight: 600; cursor: pointer; border: none; transition: all var(--transition-fast); }
.cookie-btn-accept { background: var(--primary); color: white; }
.cookie-btn-accept:hover { background: var(--primary-dark); }
.cookie-btn-decline { background: var(--bg-hover); color: var(--text-main); }
.cookie-btn-decline:hover { background: var(--border-color); }
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; } html { scroll-behavior: auto; } }
@media (max-width: 480px) {
  .hero { padding: 1.75rem 0.75rem; border-radius: 0 0 16px 16px; }
  .hero h1 { font-size: 1.375rem; }
  .hero p { font-size: 0.875rem; }
  .btn-cta { padding: 10px 20px; font-size: 0.8125rem; }
  .article-content { padding: 1rem; }
  .article-content h1 { font-size: 1.375rem; }
  .fab { bottom: 12px; right: 12px; width: 48px; height: 48px; }
  .search-input { padding: 12px 44px 12px 16px; font-size: 0.875rem; }
  .search-btn { width: 36px; height: 36px; }
  .cookie-consent-content { flex-direction: column; text-align: center; }
  .cookie-consent-actions { width: 100%; justify-content: center; }
  .ad-blocks-container { grid-template-columns: 1fr; gap: 1rem; }
  .ad-section-buttons { gap: 0.5rem; }
  .ad-btn-category { padding: 0.5rem 1rem; font-size: 0.8125rem; }
  .article-body iframe { min-height: 300px; }
  .post-feed-content { padding: 1rem; }
  .post-feed-title { font-size: 1rem; }
  .post-feed-text { font-size: 0.875rem; }
  .post-feed-meta { font-size: 0.6875rem; gap: 6px; }
  .post-feed-actions { gap: 8px; }
  .btn-outline, .btn-primary { padding: 8px 14px; font-size: 0.8125rem; min-width: 80px; }
  .seo-block { padding: 1rem; }
  .seo-block h2 { font-size: 1.0625rem; }
  .seo-block p { font-size: 0.875rem; }
  footer { padding: 2rem 12px; max-width: 100%; }
  .footer-links { gap: 0.5rem; font-size: 0.75rem; flex-wrap: wrap; justify-content: center; }
  .footer-tags-list { gap: 0.375rem; }
  .footer-tag { padding: 3px 8px; font-size: 0.75rem; }
  .load-more-container { padding: 1.5rem 0; }
  .btn-load-more { padding: 10px 28px; font-size: 0.875rem; }
  .posts-counter { font-size: 0.8125rem; }
  .related-grid { grid-template-columns: 1fr; }
  .related-card-content { padding: 0.75rem; }
}
.amp-badge { background: var(--primary); color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.6875rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; }
.posts-counter { text-align: center; color: var(--text-muted); padding: 0.5rem 0 0; font-size: 0.8125rem; }
.crawler-links { position: absolute; left: -9999px; width: 1px; height: 1px; overflow: hidden; }
.pagination{display:flex;justify-content:center;align-items:center;gap:0.375rem;margin:2rem 0 1rem;flex-wrap:wrap}
.pagination a,.pagination span{display:inline-flex;align-items:center;justify-content:center;min-width:38px;height:38px;padding:0 10px;border:1px solid var(--border-color);border-radius:var(--radius-sm);background:var(--bg-card);color:var(--text-main);font-weight:600;font-size:0.8125rem;cursor:pointer;transition:all var(--transition-fast);text-decoration:none;font-family:var(--font-main)}
.pagination a:hover,.pagination span:hover{border-color:var(--primary);color:var(--primary);background:var(--primary-light)}
.pagination .active{background:var(--primary);color:#fff;border-color:var(--primary);pointer-events:none}
.pagination .disabled{opacity:0.35;pointer-events:none;cursor:default}
.pagination .dots{border:none;background:transparent;color:var(--text-muted);cursor:default;min-width:28px}
@media(max-width:520px){.pagination{gap:0.25rem}.pagination a,.pagination span{min-width:34px;height:34px;font-size:0.75rem;padding:0 8px}}
#matrix-bg { position: fixed; top: 0; left: 0; width: 100%; height: 100%; z-index: 0; pointer-events: none; opacity: 0.08; }
[data-theme="dark"] #matrix-bg { opacity: 0.3; }

.shop-hero{background:linear-gradient(135deg,var(--primary) 0%,var(--secondary) 100%);padding:2.5rem 1rem;text-align:center;border-radius:0 0 var(--radius-xl) var(--radius-xl);margin-bottom:2rem;position:relative;overflow:hidden;box-shadow:var(--shadow-lg)}
.shop-hero::before{content:'';position:absolute;top:-50%;left:-50%;width:200%;height:200%;background:radial-gradient(circle,rgba(42,171,238,0.1) 0%,transparent 50%);animation:shopPulse 8s ease-in-out infinite}
@keyframes shopPulse{0%,100%{transform:scale(1);opacity:0.5}50%{transform:scale(1.1);opacity:1}}
.shop-hero h1{font-family:var(--font-display);font-size:clamp(1.5rem,4vw,2.25rem);font-weight:800;margin-bottom:0.5rem;letter-spacing:-0.03em;color:#FFF;position:relative;z-index:1}
.shop-hero p{font-size:0.9375rem;color:rgba(255,255,255,0.85);max-width:600px;margin:0 auto 1.25rem;position:relative;z-index:1}
.zap-iframe-seo-text{position:absolute;left:-9999px;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0)}
.shop-hero[data-theme-inherit]{background:linear-gradient(135deg,var(--primary) 0%,var(--secondary) 100%)}
.shop-page-container{max-width:1400px;margin:0 auto;padding:0 1rem 2rem}
.shop-search-bar{display:flex;align-items:center;gap:0.75rem;margin-bottom:1.5rem;background:var(--bg-card);border:1px solid var(--border-color);border-radius:var(--radius-lg);padding:0.5rem 1rem;box-shadow:var(--shadow-sm)}
.shop-search-bar svg{width:20px;height:20px;flex-shrink:0;color:var(--text-muted)}
.shop-search-bar input{flex:1;border:none;outline:none;background:transparent;font-size:0.9375rem;color:var(--text-main);padding:0.4rem 0}
.shop-search-bar input::placeholder{color:var(--text-muted)}
.shop-sort-select{background:var(--bg-card);border:1px solid var(--border-color);border-radius:var(--radius-md);padding:0.5rem 0.75rem;font-size:0.85rem;color:var(--text-main);cursor:pointer;outline:none;min-width:160px}
.shop-supplier-stats{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:0.75rem;margin-bottom:1.5rem}
.shop-supplier-card{background:var(--bg-card);border:1px solid var(--border-color);border-radius:var(--radius-lg);padding:0.75rem 1rem;cursor:pointer;transition:all 0.15s;display:flex;align-items:center;gap:0.75rem}
.shop-supplier-card:hover,.shop-supplier-card.active{border-color:var(--primary);box-shadow:0 0 0 2px rgba(36,129,204,0.15)}
.shop-supplier-card .supplier-dot{width:12px;height:12px;border-radius:50%;flex-shrink:0}
.shop-supplier-card .supplier-name{font-size:0.85rem;font-weight:600;color:var(--text-main);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.shop-supplier-card .supplier-count{font-size:0.75rem;color:var(--text-muted);margin-left:auto;white-space:nowrap}
.shop-results-info{font-size:0.85rem;color:var(--text-muted);margin-bottom:1rem;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:0.5rem}
.shop-product-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:1rem;margin-bottom:2rem}
.shop-product-card{background:var(--bg-card);border:1px solid var(--border-color);border-radius:var(--radius-lg);overflow:hidden;transition:transform 0.15s,box-shadow 0.15s;display:flex;flex-direction:column}
.shop-product-card:hover{transform:translateY(-2px);box-shadow:var(--shadow-lg)}
.shop-product-card .card-img{position:relative;width:100%;padding-top:100%;background:var(--bg-body);overflow:hidden}
.shop-product-card .card-img img{position:absolute;top:0;left:0;width:100%;height:100%;object-fit:contain;padding:8px;transition:transform 0.2s}
.shop-product-card:hover .card-img img{transform:scale(1.05)}
.shop-product-card .card-badges{position:absolute;top:8px;left:8px;display:flex;flex-wrap:wrap;gap:4px;z-index:2}
.shop-product-card .badge{display:inline-block;padding:2px 8px;border-radius:4px;font-size:0.65rem;font-weight:700;text-transform:uppercase;letter-spacing:0.03em;color:#fff;line-height:1.4}
.shop-product-card .badge.feed{background:#2481CC}
.shop-product-card .badge.category{background:#6c757d}
.shop-product-card .badge.vendor{background:#17a2b8}
.shop-product-card .badge.sale{background:#dc3545}
.shop-product-card .card-body{padding:0.75rem 1rem 1rem;flex:1;display:flex;flex-direction:column}
.shop-product-card .card-name{font-size:0.85rem;font-weight:500;color:var(--text-main);line-height:1.4;margin-bottom:0.5rem;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;min-height:2.4em}
.shop-product-card .card-prices{margin-top:auto;margin-bottom:0.5rem;display:flex;align-items:baseline;gap:0.5rem;flex-wrap:wrap}
.shop-product-card .card-prices .price{font-size:1.1rem;font-weight:700;color:var(--primary)}
.shop-product-card .card-prices .old-price{font-size:0.8rem;color:var(--text-muted);text-decoration:line-through}
.shop-product-card .card-btn{display:inline-flex;align-items:center;justify-content:center;gap:0.4rem;width:100%;padding:0.55rem 1rem;border-radius:var(--radius-md);background:var(--primary);color:#fff;font-size:0.8rem;font-weight:600;text-decoration:none;border:none;cursor:pointer;transition:background 0.15s;text-align:center}
.shop-product-card .card-btn:hover{background:var(--primary-dark)}
.shop-pagination{display:flex;align-items:center;justify-content:center;gap:0.4rem;margin:2rem 0;flex-wrap:wrap}
.shop-pagination a,.shop-pagination span{display:inline-flex;align-items:center;justify-content:center;min-width:36px;height:36px;padding:0 0.5rem;border-radius:var(--radius-md);font-size:0.85rem;font-weight:500;text-decoration:none;transition:all 0.15s}
.shop-pagination a{background:var(--bg-card);border:1px solid var(--border-color);color:var(--text-main)}
.shop-pagination a:hover{border-color:var(--primary);color:var(--primary)}
.shop-pagination .active{background:var(--primary);color:#fff;border:1px solid var(--primary)}
.shop-pagination .disabled{opacity:0.4;pointer-events:none;background:var(--bg-card);border:1px solid var(--border-color);color:var(--text-muted)}
.shop-pagination .dots{border:none;background:transparent;color:var(--text-muted);cursor:default;min-width:28px}
.shop-features{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:1rem;margin:2rem 0;padding:1.5rem 0;border-top:1px solid var(--border-color)}
.shop-features .feature-card{text-align:center;padding:1rem;background:var(--bg-card);border-radius:var(--radius-lg);border:1px solid var(--border-color)}
.shop-features .feature-card .feature-icon{font-size:1.5rem;margin-bottom:0.5rem}
.shop-features .feature-card .feature-title{font-size:0.9rem;font-weight:600;color:var(--text-main);margin-bottom:0.25rem}
.shop-features .feature-card .feature-desc{font-size:0.75rem;color:var(--text-muted)}
.shop-category-nav{display:flex;flex-wrap:wrap;gap:0.5rem;justify-content:center;padding:1rem 0;margin-bottom:1rem}
.shop-category-nav a{display:inline-block;padding:0.4rem 1rem;border-radius:var(--radius-lg);border:1px solid var(--border-color);color:var(--text-main);text-decoration:none;font-size:0.85rem;font-weight:500;transition:all 0.15s}
.shop-category-nav a:hover,.shop-category-nav a.active{background:var(--primary);color:#fff;border-color:var(--primary)}
.shop-loading{display:flex;align-items:center;justify-content:center;padding:4rem 1rem;color:var(--text-muted);font-size:0.9375rem;gap:0.75rem}
.shop-loading .spinner{width:24px;height:24px;border:3px solid var(--border-color);border-top-color:var(--primary);border-radius:50%;animation:spin 0.8s linear infinite}
.shop-empty{text-align:center;padding:3rem 1rem;color:var(--text-muted)}
.shop-empty .empty-icon{font-size:3rem;margin-bottom:1rem;opacity:0.5}
.shop-empty .empty-text{font-size:1rem;margin-bottom:1rem}
.shop-empty a{color:var(--primary);font-weight:600;text-decoration:none}
.shop-widget{background:var(--bg-card);border:1px solid var(--border-color);border-radius:var(--radius-lg);padding:1.25rem;margin:2rem 0}
.shop-widget .widget-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:1rem}
.shop-widget .widget-title{font-size:1rem;font-weight:700;color:var(--text-main)}
.shop-widget .widget-link{font-size:0.8rem;color:var(--primary);text-decoration:none;font-weight:600}
.shop-widget .widget-link:hover{text-decoration:underline}
.shop-widget .widget-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:0.75rem}
.shop-widget .widget-product{display:flex;flex-direction:column;gap:0.4rem;padding:0.5rem;border-radius:var(--radius-md);border:1px solid var(--border-color);text-decoration:none;color:inherit;transition:border-color 0.15s}
.shop-widget .widget-product:hover{border-color:var(--primary)}
.shop-widget .widget-product img{width:100%;aspect-ratio:1;object-fit:contain;border-radius:4px;background:var(--bg-body)}
.shop-widget .widget-product .wp-name{font-size:0.75rem;color:var(--text-main);line-height:1.3;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.shop-widget .widget-product .wp-price{font-size:0.85rem;font-weight:700;color:var(--primary)}
.wp-buy-btn{display:block;text-align:center;padding:4px 0;background:var(--primary);color:#fff;font-size:0.72rem;font-weight:600;border-radius:4px;text-decoration:none;margin-top:4px;transition:background 0.15s}
.wp-buy-btn:hover{background:var(--primary-dark)}
.shop-controls-row{display:flex;align-items:center;gap:0.75rem;margin-bottom:1.5rem;flex-wrap:wrap}
.shop-controls{display:flex;align-items:center;gap:0.75rem;margin-bottom:1rem;flex-wrap:wrap}
.shop-search-input{flex:1;min-width:200px;background:var(--bg-card);border:1px solid var(--border-color);border-radius:var(--radius-md);padding:0.55rem 0.85rem;font-size:0.9rem;color:var(--text-main);outline:none;transition:border-color 0.15s}
.shop-search-input:focus{border-color:var(--primary)}
.shop-suppliers{display:flex;flex-wrap:wrap;gap:0.5rem;margin-bottom:1rem}
.supplier-filter-btn{background:var(--bg-card);border:1px solid var(--border-color);border-radius:var(--radius-lg);padding:0.4rem 0.85rem;font-size:0.8rem;font-weight:500;color:var(--text-main);cursor:pointer;transition:all 0.15s}
.supplier-filter-btn:hover,.supplier-filter-btn.active{background:var(--primary);color:#fff;border-color:var(--primary)}
.shop-product-count{font-size:0.85rem;color:var(--text-muted);margin-bottom:0.75rem}
.shop-widget-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:0.75rem}
.product-card-image{position:relative;width:100%;padding-top:100%;background:var(--bg-body);overflow:hidden}
.product-card-image img{position:absolute;top:0;left:0;width:100%;height:100%;object-fit:contain;padding:8px;transition:transform 0.2s}
.shop-product-card:hover .product-card-image img{transform:scale(1.05)}
.product-card-body{padding:0.75rem 1rem 1rem;flex:1;display:flex;flex-direction:column}
.product-card-name{font-size:0.85rem;font-weight:500;color:var(--text-main);line-height:1.4;margin-bottom:0.5rem;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;min-height:2.4em}
.product-card-badges{display:flex;flex-wrap:wrap;gap:4px;margin-bottom:0.35rem}
.product-badge{display:inline-block;padding:2px 8px;border-radius:4px;font-size:0.65rem;font-weight:700;text-transform:uppercase;letter-spacing:0.03em;color:#fff;line-height:1.4}
.product-badge.badge-sale{background:#dc3545}
.product-badge.badge-unavailable{background:#6c757d}
.product-badge.badge-supplier{background:#2481CC}
.product-card-price{font-size:1.05rem;font-weight:700;color:var(--primary);margin-bottom:0.5rem}
.product-card-price s{font-size:0.8rem;color:var(--text-muted);margin-left:0.4rem}
.product-card-btn{display:inline-flex;align-items:center;justify-content:center;gap:0.4rem;width:100%;padding:0.55rem 1rem;border-radius:var(--radius-md);background:var(--primary);color:#fff;font-size:0.8rem;font-weight:600;text-decoration:none;border:none;cursor:pointer;transition:background 0.15s;text-align:center;box-sizing:border-box}
.product-card-btn:hover{background:var(--primary-dark);color:#fff}
.shop-product-card .product-card-btn{margin:0 1rem 1rem;border-radius:0 0 var(--radius-lg) var(--radius-lg)}
.product-card-desc{font-size:0.78rem;color:var(--text-sec);line-height:1.35;margin:0.3rem 0 0.5rem;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
@media(max-width:768px){.shop-product-grid{grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:0.75rem}.shop-supplier-stats{grid-template-columns:repeat(auto-fill,minmax(140px,1fr))}.shop-page-container{padding:0 0.5rem 1.5rem}.shop-controls-row{flex-direction:column;align-items:stretch}.shop-sort-select{min-width:auto;width:100%}.shop-widget .widget-grid{grid-template-columns:repeat(2,1fr)}.shop-features{grid-template-columns:repeat(2,1fr)}}
@media(max-width:480px){.shop-product-grid{grid-template-columns:repeat(2,1fr);gap:0.5rem}.shop-product-card .card-body{padding:0.5rem 0.75rem 0.75rem}.shop-product-card .card-name{font-size:0.78rem;min-height:auto;-webkit-line-clamp:1}.shop-product-card .card-prices .price{font-size:0.95rem}.shop-product-card .card-btn{font-size:0.72rem;padding:0.45rem 0.5rem}.shop-supplier-stats{grid-template-columns:1fr 1fr;gap:0.5rem}.shop-widget .widget-grid{grid-template-columns:repeat(2,1fr)}.shop-features{grid-template-columns:1fr 1fr}}

"""

# =============================================================================
# AMP CSS — from Worker v27.0 AMP_CSS constant (simplified for AMP pages)
# =============================================================================

AMP_CSS = """
:root{--primary:#2481CC;--primary-dark:#1D6FAD;--bg:#fff;--bg-card:#fff;--bg-hover:#F0F2F5;--text:#000;--text-main:#000;--text-muted:#707579;--border:#DADCE0;--radius-md:12px;--radius-lg:16px;--shadow:0 4px 6px -1px rgba(0,0,0,0.1)}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#F4F4F5;color:var(--text);line-height:1.6}
a{color:var(--primary);text-decoration:none}
.container{max-width:600px;margin:0 auto;padding:0 16px}
.header{background:var(--bg);padding:12px 0;border-bottom:1px solid var(--border);position:sticky;top:0;z-index:100}
.header-inner{display:flex;justify-content:space-between;align-items:center}
.logo{font-size:1.25rem;font-weight:700;color:var(--primary)}
.post-item{padding:16px;border-bottom:1px solid var(--border);background:var(--bg);margin-bottom:8px;border-radius:12px}
.post-title{font-size:1rem;font-weight:600;margin-bottom:8px}
.post-meta{font-size:.75rem;color:var(--text-muted);margin-bottom:4px}
.btn{padding:8px 16px;border-radius:8px;font-size:.8125rem;font-weight:600;display:inline-block}
.btn-outline{border:1px solid var(--primary);color:var(--primary)}
.btn-primary{background:var(--primary);color:#fff}
.footer{padding:24px 16px;text-align:center;color:var(--text-muted);font-size:.8125rem;margin-top:24px}
.footer a{color:var(--text-muted)}
.footer-links{margin-top:12px;display:flex;flex-wrap:wrap;justify-content:center;gap:8px;font-size:0.75rem}
.article-media{margin:16px 0;border-radius:12px;overflow:hidden}
.article-media amp-img,.article-media amp-video{width:100%;height:auto}
.related{margin-top:32px;padding-top:24px;border-top:1px solid var(--border);margin-bottom:24px}
.related h3{font-size:1.25rem;margin-bottom:16px}
.related-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}
.related-item{display:block}
.related-media{width:100%;height:100px;border-radius:8px;object-fit:cover}
.related-content{margin-top:8px}
.related-title{font-size:.875rem;font-weight:600;line-height:1.3}
.ad-section{margin:16px 0;text-align:center}
.ad-btn{display:inline-block;margin:4px;padding:8px 16px;border:1px solid var(--primary);color:var(--primary);border-radius:999px;font-size:.75rem;font-weight:600;transition:all .2s}
.ad-btn:hover{background:var(--primary);color:#fff}
.ad-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px;margin:16px 0}
.ad-card{background:var(--bg-card);padding:12px;border-radius:var(--radius-md);border:1px solid var(--border);box-shadow:0 1px 3px rgba(0,0,0,0.05);display:flex;flex-direction:column;align-items:center;text-align:center}
.ad-card amp-img{width:120px;height:120px;object-fit:cover;margin:0 auto 8px;background:var(--bg-hover);border-radius:8px;padding:4px}
.ad-card h4{font-size:.85rem;margin:4px 0;color:var(--text-main);line-height:1.3;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.ad-card p{font-size:.7rem;color:var(--text-muted);margin:4px 0 8px;line-height:1.4;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;flex-grow:1}
.ad-card .btn{width:100%;font-size:.7rem;padding:6px 8px}
@media(max-width:480px){.container{padding:0 12px}.related-grid{grid-template-columns:1fr}.ad-grid{grid-template-columns:repeat(2,1fr)}}
"""
