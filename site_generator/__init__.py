"""
SochiAutoParts Static Site Generator package.

Generates a complete static website for sochiautoparts.ru from local data,
including bilingual pages (Russian and English), SEO optimization, sitemaps,
and RSS feeds.

The Cloudflare Worker proxies these pages and adds region-based affiliate
filtering on top.

Modules:
    main            - CLI entry point and build orchestration
    config          - Site configuration constants
    data_loader     - Local data loading and caching
    telegram_parser - Telegram channel post parser
    html_generator  - HTML page generation for all site sections
    templates       - Reusable HTML template components
    css             - CSS stylesheets (main, AMP)
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
# Build: 2026-05-28
