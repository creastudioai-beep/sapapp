"""
SochiAutoParts Static Site Generator package.

Generates a complete static website for sochiautoparts.ru from pipeline data,
including bilingual pages (Russian and English), SEO optimization, sitemaps,
RSS feeds, and archive pages with pagination.

Archive pages are generated as static HTML by the Python generator using
pipeline data (posts.json). The Cloudflare Worker proxies these pages and
adds region-based affiliate filtering on top.

Modules:
    main            - CLI entry point and build orchestration
    config          - Site configuration constants
    data_loader     - Pipeline data fetching and caching
    telegram_fetcher- Telegram channel archive fetcher (kept for standalone use)
    html_generator  - HTML page generation for all site sections
    templates       - Reusable HTML template components
    css             - CSS stylesheets (main, AMP, archive)
    seo             - SEO meta tags, Schema.org, sitemaps, RSS
    i18n            - Internationalization strings (ru/en)

Usage:
    python -m site_generator.main [options]

    from site_generator import main
    main.main()
"""

__version__ = "1.0.0"
__author__ = "SOCHIAUTOPARTS"
__description__ = "Static site generator for sochiautoparts.ru"
