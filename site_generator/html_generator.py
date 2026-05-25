"""
HTML Generator module for the SochiAutoParts static site generator.

This is the MAIN module that generates ALL HTML pages for the static site.
It uses templates.py, seo.py, data_loader.py, i18n.py, css.py, and config.py.
It must produce HTML that exactly matches the Cloudflare Worker v27.0 output.

Each function generates a COMPLETE HTML page (<!DOCTYPE html> to </html>)
and writes it to the output directory.

Usage:
    from html_generator import generate_all_pages
    from data_loader import load_data

    data = load_data()
    generate_all_pages(data, "output")
"""

import json
import math
import os
import re
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import quote as url_quote

from .i18n import t
from .config import (
    SITE_URL,
    SITE_NAME_RU,
    SITE_NAME_EN,
    SITE_DESCRIPTION_RU,
    SITE_DESCRIPTION_EN,
    CHANNEL_USERNAME,
    POSTS_PER_PAGE,
    ARTICLES_PER_PAGE,
    PRODUCTS_PER_PAGE,
    CURRENT_YEAR,
    PRODUCT_CATEGORIES,
    PRODUCTS_CURRENCY_RU,
    PRODUCTS_CURRENCY_EN,
    ADMITAD_CONFIG,
    CONTACT_PHONE,
    CONTACT_PHONE_HREF,
    CONTACT_EMAIL,
    CONTACT_EMAIL_HREF,
    CONTACT_ADDRESS_RU,
    CONTACT_ADDRESS_EN,
    CONTACT_WORKING_HOURS_RU,
    CONTACT_WORKING_HOURS_EN,
    RELATED_POSTS_COUNT,
    RECENT_POSTS_COUNT,
    ARCHIVE_POSTS_PER_PAGE,
    FEATURE_SHOP_ENABLED,
    FEATURE_ARTICLES_ENABLED,
    FEATURE_ARCHIVE_ENABLED,
    FEATURE_ADMITAD_ENABLED,
    GA4_MEASUREMENT_ID,
    GA_ENABLED,
    LOGO_FAVICON_URL,
    LOGO_APPLE_TOUCH_URL,
    LOGO_ICON_192,
    LOGO_ICON_512,
    SOCIAL_LINKS,
    BASE_PATH,
)
from .seo import (
    generate_meta_tags,
    generate_hreflang_links,
    generate_ga4_script,
    generate_web_site_schema,
    generate_news_article_schema,
    generate_article_schema,
    generate_breadcrumb_schema,
    generate_item_list_schema,
    generate_faq_schema,
    generate_product_schema,
    generate_sitemap_index,
    generate_static_sitemap,
    generate_posts_sitemap,
    generate_language_sitemap,
    generate_news_sitemap,
    generate_amp_sitemap,
    generate_tags_sitemap,
    generate_products_sitemap,
    generate_archive_sitemap,
    generate_rss_feed,
    generate_robots_txt,
    generate_manifest_json,
    generate_cookie_consent_html,
    get_common_client_scripts,
    STATIC_ORG_SCHEMA,
    escape_html,
    escape_xml,
    MAX_POSTS_SITEMAP,
    SITEMAP_POSTS_PER_FILE,
    PRODUCTS_SITEMAP_PER_FILE,
    DEFAULT_THUMBNAIL,
    SITE_AUTHOR,
)
from .templates import (
    render_header,
    render_hero,
    render_seo_block,
    render_popular_tags,
    render_post_card,
    render_archive_post_card,
    render_post_gallery,
    render_related_posts,
    render_footer,
    render_numbered_pagination,
    render_ad_blocks,
    render_ad_category_buttons,
    render_shop_widget,
    render_breadcrumbs,
    render_matrix_bg,
    render_fab,
    LOGO_EXTERNAL_URL,
    ADMITAD_CATEGORY_NAMES,
    ADMITAD_CATEGORY_MAPPING,
)
from .css import CSS_STYLES, AMP_CSS, ARCHIVE_CSS
from .data_loader import (
    get_post_by_id,
    get_posts_by_tag,
    get_related_posts,
    get_popular_tags,
    get_admitad_programs,
    search_posts,
    extract_first_image,
    format_post_text,
)
from .telegram_fetcher import (
    get_archive_page_posts,
    get_post_by_id as get_archive_post_by_id,
    get_total_posts_count,
    load_meta as load_archive_meta,
)


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger = logging.getLogger("html_generator")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("[%(name)s] %(levelname)s: %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_ARCHIVE_POST_PAGES: int = 90000  # Generate archive post pages — new posts push old ones out

# GitHub Pages size limits require constraining the number of generated files.
# Each HTML page is ~80KB; GitHub Pages limit is 1GB total.
MAX_TAG_PAGES: int = 500  # Only generate tag pages for the top 500 tags
MAX_POST_PAGES: int = 1000  # Only generate individual post pages for the latest 1000 posts
MAX_PRODUCT_PAGES: int = 200  # Only generate individual product pages for 200 products
GENERATE_AMP: bool = False  # Skip AMP pages to reduce output size
GENERATE_AMP_HOMEPAGE: bool = False  # Skip AMP homepage
GENERATE_INDIVIDUAL_PRODUCT_PAGES: bool = False  # Skip individual product pages (shop listing page only)


# ---------------------------------------------------------------------------
# Helper: Write file
# ---------------------------------------------------------------------------

def _write_file(path: str, content: str):
    """Write content to file, creating directories as needed.

    Handles surrogate characters that may appear in Telegram data
    by using 'surrogatepass' error handling to avoid UnicodeEncodeError.

    Args:
        path: Absolute or relative file path.
        content: String content to write.
    """
    dir_path = os.path.dirname(path)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)
    # Sanitize surrogates: encode with surrogatepass, then re-encode cleanly
    try:
        sanitized = content.encode('utf-8', errors='surrogatepass').decode('utf-8', errors='replace')
    except Exception:
        sanitized = content.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(sanitized)


# ---------------------------------------------------------------------------
# Helper: Build language-aware URL path
# ---------------------------------------------------------------------------

def _lang_path(lang: str) -> str:
    """Return the language prefix path segment (with BASE_PATH)."""
    if lang == "en":
        return BASE_PATH + "/en"
    return BASE_PATH


def _lang_base(lang: str) -> str:
    """Return the base URL for the given language (relative paths, with BASE_PATH)."""
    if lang == "en":
        return BASE_PATH + "/en/"
    return BASE_PATH + "/"


def _canonical_lang_path(lang: str) -> str:
    """Return language path WITHOUT BASE_PATH for canonical/OG URLs (production domain)."""
    return "/en" if lang == "en" else ""


def _bp(path: str) -> str:
    """Prefix a path with BASE_PATH."""
    if path.startswith("/"):
        return BASE_PATH + path
    return BASE_PATH + "/" + path


# ---------------------------------------------------------------------------
# Helper: Build a full HTML page wrapper
# ---------------------------------------------------------------------------

def _build_page(
    lang: str,
    title: str,
    description: str,
    url: str,
    path: str,
    body_content: str,
    og_type: str = "website",
    image: Optional[str] = None,
    canonical: Optional[str] = None,
    article_published: Optional[str] = None,
    article_modified: Optional[str] = None,
    article_tag: Optional[str] = None,
    product_price: Optional[str] = None,
    product_currency: Optional[str] = None,
    product_availability: Optional[str] = None,
    extra_head: str = "",
    extra_schema: str = "",
    active_page: str = "",
    post_id: Optional[int] = None,
    article_id: Optional[int] = None,
    tag: Optional[str] = None,
    robots: str = "index, follow, max-image-preview:large",
    show_hero: bool = False,
    tags_for_footer: Optional[list] = None,
    include_ga: bool = True,
    include_matrix: bool = True,
    css_override: Optional[str] = None,
) -> str:
    """Build a complete HTML page with head, header, body, footer, scripts.

    This is the universal page builder used by all generate_* functions.
    """
    html_lang = "ru" if lang == "ru" else "en"

    # Meta tags
    meta_tags = generate_meta_tags(
        title=title,
        description=description,
        url=url,
        lang=lang,
        og_type=og_type,
        image=image,
        robots=robots,
        canonical=canonical,
        article_published=article_published,
        article_modified=article_modified,
        article_tag=article_tag,
        product_price=product_price,
        product_currency=product_currency,
        product_availability=product_availability,
    )

    # Hreflang
    hreflang = generate_hreflang_links(
        path=path,
        lang=lang,
        post_id=post_id,
        article_id=article_id,
        tag=tag,
    )

    # GA4
    ga_script = ""
    if include_ga and GA_ENABLED:
        ga_script = generate_ga4_script(GA4_MEASUREMENT_ID)

    # Client scripts
    client_scripts = get_common_client_scripts(lang)

    # Header
    header_html = render_header(lang=lang, active_page=active_page)

    # Hero (optional)
    hero_html = ""
    if show_hero:
        hero_html = render_hero(lang=lang)

    # Footer
    footer_html = render_footer(tags=tags_for_footer, lang=lang)

    # FAB
    fab_html = render_fab(lang=lang)

    # Matrix BG
    matrix_html = ""
    if include_matrix:
        matrix_html = render_matrix_bg()

    # CSS
    css_content = css_override if css_override else CSS_STYLES

    # Schema.org
    schema_tags = ""
    if extra_schema:
        # extra_schema can be a JSON string; wrap in <script type="application/ld+json">
        if isinstance(extra_schema, list):
            for schema_json in extra_schema:
                schema_tags += f'\n<script type="application/ld+json">{schema_json}</script>'
        else:
            schema_tags += f'\n<script type="application/ld+json">{extra_schema}</script>'

    # Always include Organization schema
    org_schema_tag = f'<script type="application/ld+json">{STATIC_ORG_SCHEMA}</script>'

    # AMP link for post pages
    amp_link = ""
    if post_id:
        amp_link = f'<link rel="amphtml" href="{_lang_path(lang)}/post/{post_id}/amp" />'

    # Preconnect hints for performance (matching production site)
    preconnect_hints = (
        '<link rel="preconnect" href="https://fonts.googleapis.com" />\n'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />\n'
        '<link rel="preconnect" href="https://t.me" />\n'
        '<link rel="preconnect" href="https://www.googletagmanager.com" />\n'
        '<link rel="dns-prefetch" href="https://raw.githubusercontent.com" />\n'
        '<link rel="dns-prefetch" href="https://cdn.ampproject.org" />'
    )

    # Build full page
    page = f"""<!DOCTYPE html>
<html lang="{html_lang}" data-theme="dark">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
{meta_tags}
{hreflang}
{amp_link}
<link rel="icon" href="{_bp('/logo.jpg')}" type="image/jpeg" />
<link rel="apple-touch-icon" href="{_bp('/logo.jpg')}" />
<link rel="manifest" href="{_bp('/manifest.json')}" />
<meta name="theme-color" content="#2481CC" />
{preconnect_hints}
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Manrope:wght@400;500;600;700;800&display=swap" rel="stylesheet" />
<style>{css_content}</style>
{org_schema_tag}
{schema_tags}
{extra_head}
{ga_script}
</head>
<body>
{matrix_html}
{header_html}
{hero_html}
<main>
{body_content}
</main>
{footer_html}
{fab_html}
{client_scripts}
</body>
</html>"""

    return page


# ===========================================================================
# Master function: generate_all_pages
# ===========================================================================

def generate_all_pages(data: dict, output_dir: str, archive_data_dir: str = "data/telegram_archive"):
    """Master function: Generate ALL pages for both languages.

    Steps:
    1. Homepage (ru + en)
    2. All post pages (ru + en) + AMP versions
    3. Articles listing (ru + en)
    4. All article pages (ru + en)
    5. Archive pages with 50 posts per page (ru + en)
    6. Archive post pages (ru + en)
    7. Shop page (ru + en)
    8. Product pages (ru + en)
    9. Category pages (ru + en)
    10. Tag pages (ru + en)
    11. Privacy page (ru + en)
    12. Contacts page (ru + en)
    13. Ad category pages (ru + en)
    14. 404 page
    15. AMP homepage (ru + en)
    16. All sitemaps, robots.txt, RSS, manifest

    Args:
        data: The data dict returned by data_loader.load_data().
        output_dir: Root output directory for generated files.
        archive_data_dir: Path to the telegram archive data directory.
    """
    os.makedirs(output_dir, exist_ok=True)

    # Copy logo.jpg to output root for relative /logo.jpg references
    import shutil
    logo_src = os.path.join(os.path.dirname(__file__), "..", "static", "logo.jpg")
    if not os.path.isfile(logo_src):
        logo_src = os.path.join("static", "logo.jpg")
    logo_dest = os.path.join(output_dir, "logo.jpg")
    if os.path.isfile(logo_src):
        os.makedirs(os.path.dirname(logo_dest), exist_ok=True)
        shutil.copy2(logo_src, logo_dest)
        logger.info("Copied logo.jpg to output directory")
    else:
        # Download logo from GitHub and save to output
        try:
            import requests as _req
            _logo_url = "https://raw.githubusercontent.com/creastudioai-beep/sap/main/main/assets/logo.jpg"
            _resp = _req.get(_logo_url, timeout=15)
            if _resp.status_code == 200:
                with open(logo_dest, "wb") as _lf:
                    _lf.write(_resp.content)
                logger.info("Downloaded logo.jpg to output directory")
        except Exception as e:
            logger.warning("Could not download logo.jpg: %s", e)

    logger.info("Starting full site generation into %s", output_dir)

    posts = data.get("posts", [])
    articles = data.get("articles", [])
    products = data.get("products", [])
    popular_tags = get_popular_tags(data, limit=12)
    admitad_programs = data.get("admitad_programs", [])

    # ------------------------------------------------------------------
    # 1. Homepage (ru + en)
    # ------------------------------------------------------------------
    for lang in ("ru", "en"):
        logger.info("Generating homepage (%s)", lang)
        html = generate_homepage(data, lang, output_dir)
        if lang == "ru":
            _write_file(os.path.join(output_dir, "index.html"), html)
        else:
            _write_file(os.path.join(output_dir, "en", "index.html"), html)

    # ------------------------------------------------------------------
    # 2. All post pages (ru + en) — limited for GitHub Pages size
    # ------------------------------------------------------------------
    total_posts = len(posts)
    posts_to_generate = posts[:MAX_POST_PAGES]
    logger.info("Generating %d post pages (ru + en) out of %d total", len(posts_to_generate), total_posts)
    for idx, post in enumerate(posts_to_generate):
        post_id = post.get("id")
        if post_id is None:
            continue
        for lang in ("ru", "en"):
            html = generate_post_page(data, post_id, lang, output_dir)
            if lang == "ru":
                _write_file(os.path.join(output_dir, "post", f"{post_id}.html"), html)
            else:
                _write_file(os.path.join(output_dir, "en", "post", f"{post_id}.html"), html)

            # AMP version (optional — skipped by default for size)
            if GENERATE_AMP:
                amp_html = generate_amp_post_page(data, post_id, lang, output_dir)
                if lang == "ru":
                    _write_file(os.path.join(output_dir, "post", str(post_id), "amp.html"), amp_html)
                else:
                    _write_file(os.path.join(output_dir, "en", "post", str(post_id), "amp.html"), amp_html)

        if (idx + 1) % 100 == 0:
            logger.info("  Generated %d/%d posts", idx + 1, len(posts_to_generate))

    # ------------------------------------------------------------------
    # 3. Articles listing (ru + en)
    # ------------------------------------------------------------------
    if FEATURE_ARTICLES_ENABLED:
        for lang in ("ru", "en"):
            logger.info("Generating articles listing (%s)", lang)
            html = generate_articles_page(data, lang, output_dir)
            if lang == "ru":
                _write_file(os.path.join(output_dir, "articles", "index.html"), html)
            else:
                _write_file(os.path.join(output_dir, "en", "articles", "index.html"), html)

    # ------------------------------------------------------------------
    # 4. All article pages (ru + en)
    # ------------------------------------------------------------------
    total_articles = len(articles)
    logger.info("Generating %d article pages (ru + en)", total_articles)
    for idx, article in enumerate(articles):
        article_id = article.get("id")
        if article_id is None:
            continue
        for lang in ("ru", "en"):
            html = generate_article_page(data, article_id, lang, output_dir)
            if lang == "ru":
                _write_file(os.path.join(output_dir, "article", f"{article_id}.html"), html)
            else:
                _write_file(os.path.join(output_dir, "en", "article", f"{article_id}.html"), html)
        if (idx + 1) % 50 == 0:
            logger.info("  Generated %d/%d articles", idx + 1, total_articles)

    # ------------------------------------------------------------------
    # 5. Archive pages (ru + en)
    # ------------------------------------------------------------------
    if FEATURE_ARCHIVE_ENABLED:
        if os.path.isdir(archive_data_dir):
            archive_meta = load_archive_meta(archive_data_dir)
            archive_pages_count = archive_meta.get("pages_count", 0)
            logger.info("Generating %d archive listing pages", archive_pages_count)
            for page_num in range(1, archive_pages_count + 1):
                for lang in ("ru", "en"):
                    html = generate_archive_page(data, lang, output_dir, archive_data_dir, page=page_num)
                    if lang == "ru":
                        if page_num == 1:
                            _write_file(os.path.join(output_dir, "archive", "index.html"), html)
                        else:
                            _write_file(os.path.join(output_dir, "archive", f"page-{page_num}.html"), html)
                    else:
                        if page_num == 1:
                            _write_file(os.path.join(output_dir, "en", "archive", "index.html"), html)
                        else:
                            _write_file(os.path.join(output_dir, "en", "archive", f"page-{page_num}.html"), html)
        else:
            # No archive data — create a placeholder archive page so /archive doesn't 404
            logger.info("No archive data found — creating placeholder archive page")
            for lang in ("ru", "en"):
                html = _build_page(
                    lang=lang,
                    title="Архив публикаций" if lang == "ru" else "Publications Archive",
                    description="Архив публикаций SOCHIAUTOPARTS" if lang == "ru" else "SOCHIAUTOPARTS publications archive",
                    url=f"{SITE_URL}/archive" if lang == "ru" else f"{SITE_URL}/en/archive",
                    path="/archive" if lang == "ru" else "/en/archive",
                    body_content=f'<div class="container"><h1>{"Архив публикаций" if lang == "ru" else "Publications Archive"}</h1><p>{"Архив обновляется. Скоро здесь будут доступны все публикации." if lang == "ru" else "Archive is being updated. All publications will be available here soon."}</p><p><a href="{_lang_base(lang)}" class="btn-outline">{"← На главную" if lang == "ru" else "← Home"}</a></p></div>',
                    active_page="archive",
                )
                if lang == "ru":
                    _write_file(os.path.join(output_dir, "archive", "index.html"), html)
                else:
                    _write_file(os.path.join(output_dir, "en", "archive", "index.html"), html)

    # ------------------------------------------------------------------
    # 6. Archive post pages (ru + en) — limited to first 5000
    # ------------------------------------------------------------------
    if FEATURE_ARCHIVE_ENABLED and os.path.isdir(archive_data_dir):
        logger.info("Generating archive post pages (up to %d)", MAX_ARCHIVE_POST_PAGES)
        generated_count = 0
        archive_meta = load_archive_meta(archive_data_dir)
        total_archive_pages = archive_meta.get("pages_count", 0)
        for page_num in range(1, total_archive_pages + 1):
            if generated_count >= MAX_ARCHIVE_POST_PAGES:
                break
            page_posts, _, _ = get_archive_page_posts(archive_data_dir, page_num)
            for arch_post in page_posts:
                if generated_count >= MAX_ARCHIVE_POST_PAGES:
                    break
                arch_post_id = arch_post.get("id")
                if arch_post_id is None:
                    continue
                for lang in ("ru", "en"):
                    html = generate_archive_post_page(data, arch_post_id, lang, output_dir, archive_data_dir)
                    if lang == "ru":
                        _write_file(os.path.join(output_dir, "archive", "post", f"{arch_post_id}.html"), html)
                    else:
                        _write_file(os.path.join(output_dir, "en", "archive", "post", f"{arch_post_id}.html"), html)
                generated_count += 1
            if generated_count % 500 == 0 and generated_count > 0:
                logger.info("  Generated %d archive post pages", generated_count)

    # ------------------------------------------------------------------
    # 7. Shop page (ru + en)
    # ------------------------------------------------------------------
    if FEATURE_SHOP_ENABLED:
        for lang in ("ru", "en"):
            logger.info("Generating shop page (%s)", lang)
            html = generate_shop_page(data, lang, output_dir)
            if lang == "ru":
                _write_file(os.path.join(output_dir, "shop", "index.html"), html)
            else:
                _write_file(os.path.join(output_dir, "en", "shop", "index.html"), html)

    # ------------------------------------------------------------------
    # 8. Product pages (ru + en) — limited for GitHub Pages size
    # ------------------------------------------------------------------
    if FEATURE_SHOP_ENABLED and GENERATE_INDIVIDUAL_PRODUCT_PAGES:
        total_products = len(products)
        products_to_generate = products[:MAX_PRODUCT_PAGES]
        logger.info("Generating %d product pages (ru + en) out of %d total", len(products_to_generate), total_products)
        for idx, product in enumerate(products_to_generate):
            product_id = product.get("id")
            if product_id is None:
                continue
            for lang in ("ru", "en"):
                html = generate_product_page(data, product_id, lang, output_dir)
                if lang == "ru":
                    _write_file(os.path.join(output_dir, "product", f"{product_id}.html"), html)
                else:
                    _write_file(os.path.join(output_dir, "en", "product", f"{product_id}.html"), html)
            if (idx + 1) % 100 == 0:
                logger.info("  Generated %d/%d products", idx + 1, len(products_to_generate))

    # ------------------------------------------------------------------
    # 9. Category pages (ru + en)
    # ------------------------------------------------------------------
    if FEATURE_SHOP_ENABLED:
        category_map = data.get("category_map", {})
        logger.info("Generating %d category pages (ru + en)", len(category_map))
        for cat_slug in category_map:
            for lang in ("ru", "en"):
                html = generate_category_page(data, cat_slug, lang, output_dir)
                if lang == "ru":
                    _write_file(os.path.join(output_dir, "shop", "category", f"{cat_slug}.html"), html)
                else:
                    _write_file(os.path.join(output_dir, "en", "shop", "category", f"{cat_slug}.html"), html)

    # ------------------------------------------------------------------
    # 10. Tag pages (ru + en)
    # ------------------------------------------------------------------
    # hashtag_index is now unwrapped by data_loader.load_data() automatically
    hashtag_index = data.get("hashtag_index", {})
    # Safety: still check for nested structure in case data was loaded differently
    if isinstance(hashtag_index, dict) and "index" in hashtag_index:
        hashtag_index = hashtag_index["index"]

    # Limit tag pages for GitHub Pages size constraints
    # Sort tags by post count (descending) and take only the top MAX_TAG_PAGES
    if isinstance(hashtag_index, dict):
        sorted_tags = sorted(hashtag_index.items(), key=lambda x: len(x[1]) if isinstance(x[1], list) else 0, reverse=True)
        hashtag_index = dict(sorted_tags[:MAX_TAG_PAGES])
    logger.info("Generating tag pages for %d tags (limited from full index)", len(hashtag_index))
    for tag_key in hashtag_index:
        # Normalize tag name (strip leading #)
        tag_name = re.sub(r"^#+", "", str(tag_key))
        if not tag_name:
            continue
        # URL-encode the tag name for safe filenames
        safe_tag_name = url_quote(tag_name, safe='')
        for lang in ("ru", "en"):
            html = generate_tag_page(data, tag_name, lang, output_dir)
            if lang == "ru":
                _write_file(os.path.join(output_dir, "tag", f"{safe_tag_name}.html"), html)
            else:
                _write_file(os.path.join(output_dir, "en", "tag", f"{safe_tag_name}.html"), html)

    # ------------------------------------------------------------------
    # 11. Privacy page (ru + en)
    # ------------------------------------------------------------------
    for lang in ("ru", "en"):
        html = generate_privacy_page(lang, output_dir)
        if lang == "ru":
            _write_file(os.path.join(output_dir, "privacy", "index.html"), html)
        else:
            _write_file(os.path.join(output_dir, "en", "privacy", "index.html"), html)

    # ------------------------------------------------------------------
    # 12. Contacts page (ru + en)
    # ------------------------------------------------------------------
    for lang in ("ru", "en"):
        html = generate_contacts_page(lang, output_dir)
        if lang == "ru":
            _write_file(os.path.join(output_dir, "contacts", "index.html"), html)
        else:
            _write_file(os.path.join(output_dir, "en", "contacts", "index.html"), html)

    # ------------------------------------------------------------------
    # 13. Ad category pages (ru + en)
    # ------------------------------------------------------------------
    if FEATURE_ADMITAD_ENABLED:
        for category_key in ADMITAD_CONFIG:
            for lang in ("ru", "en"):
                html = generate_ad_category_page(data, category_key, lang, output_dir)
                if lang == "ru":
                    _write_file(os.path.join(output_dir, "ads", f"{category_key}.html"), html)
                else:
                    _write_file(os.path.join(output_dir, "en", "ads", f"{category_key}.html"), html)

    # ------------------------------------------------------------------
    # 14. 404 page
    # ------------------------------------------------------------------
    html_404 = generate_404_page("ru", output_dir)
    _write_file(os.path.join(output_dir, "404.html"), html_404)

    # ------------------------------------------------------------------
    # 15. AMP homepage (ru + en) — optional, skipped for size
    # ------------------------------------------------------------------
    if GENERATE_AMP_HOMEPAGE:
        for lang in ("ru", "en"):
            html = generate_amp_homepage(data, lang, output_dir)
            if lang == "ru":
                _write_file(os.path.join(output_dir, "amp", "index.html"), html)
            else:
                _write_file(os.path.join(output_dir, "en", "amp", "index.html"), html)
    else:
        logger.info("Skipping AMP homepage generation (GENERATE_AMP_HOMEPAGE=False)")

    # ------------------------------------------------------------------
    # 16. Sitemaps, robots.txt, RSS, manifest
    # ------------------------------------------------------------------
    generate_sitemaps(data, output_dir, archive_data_dir)
    generate_rss(data, output_dir)
    generate_robots_txt_file(output_dir)
    generate_manifests(output_dir)
    generate_search_index(data, output_dir)

    logger.info("Site generation complete!")


# ===========================================================================
# Homepage
# ===========================================================================

def generate_homepage(data: dict, lang: str, output_dir: str) -> str:
    """Generate homepage with posts feed, pagination, SEO, ads.

    Args:
        data: The data dict from data_loader.
        lang: Language code ('ru' or 'en').
        output_dir: Output directory (not used directly, for API compat).

    Returns:
        Complete HTML page string.
    """
    posts = data.get("posts", [])
    popular_tags = get_popular_tags(data, limit=12)
    admitad_programs = get_admitad_programs(data)

    # First page of posts
    page_posts = posts[:POSTS_PER_PAGE]
    total_posts = len(posts)
    total_pages = max(1, math.ceil(total_posts / POSTS_PER_PAGE))

    # SEO
    site_name = SITE_NAME_RU if lang == "ru" else SITE_NAME_EN
    site_desc = SITE_DESCRIPTION_RU if lang == "ru" else SITE_DESCRIPTION_EN
    page_url = f"{SITE_URL}{_canonical_lang_path(lang)}/"
    if lang == "ru":
        title = "SOCHIAUTOPARTS - Мировые автоновости, обзоры и тест-драйвы"
    else:
        title = "SOCHIAUTOPARTS - Global Automotive News, Reviews & Test Drives"

    # Schemas
    website_schema = generate_web_site_schema(lang)
    item_list_schema = generate_item_list_schema(page_posts, lang)
    faq_schema = generate_faq_schema(lang)
    breadcrumb_schema_home = generate_breadcrumb_schema([
        {"name": "Главная" if lang == "ru" else "Home", "url": f"{SITE_URL}/"}
    ])
    schemas = [website_schema, item_list_schema, faq_schema, breadcrumb_schema_home]

    # Post cards
    posts_html = ""
    for post in page_posts:
        posts_html += render_post_card(post, lang)

    # SEO block
    seo_block = render_seo_block(lang)

    # Ad blocks
    ads_html = ""
    if admitad_programs:
        ads_html = render_ad_blocks(admitad_programs, lang)

    # Shop widget
    shop_widget = ""
    if FEATURE_SHOP_ENABLED:
        products = data.get("products", [])[:6]
        shop_widget = render_shop_widget(products, lang)

    # Pagination
    pagination_html = render_numbered_pagination(1, total_pages, _lang_base(lang), lang)

    # Ad category buttons (matching original site)
    ad_category_buttons = render_ad_category_buttons(lang)

    body = f"""
<div class="container">
{ad_category_buttons}
<div class="posts-feed">
{posts_html}
</div>
{pagination_html}
{ads_html}
{shop_widget}
{seo_block}
</div>"""

    return _build_page(
        lang=lang,
        title=title,
        description=site_desc,
        url=page_url,
        path="/" if lang == "ru" else "/en/",
        body_content=body,
        og_type="website",
        canonical=f"{SITE_URL}{_canonical_lang_path(lang)}/",
        extra_schema=schemas,
        active_page="home",
        show_hero=True,
        tags_for_footer=popular_tags,
    )


# ===========================================================================
# Individual Post Page
# ===========================================================================

def generate_post_page(data: dict, post_id: int, lang: str, output_dir: str) -> str:
    """Generate individual post page with gallery, related posts, ads, shop widget.

    Args:
        data: The data dict from data_loader.
        post_id: The post ID.
        lang: Language code.
        output_dir: Output directory.

    Returns:
        Complete HTML page string.
    """
    post = get_post_by_id(data, post_id)
    if post is None:
        return generate_404_page(lang, output_dir)

    # SEO data
    seo_posts = data.get("seo_posts", {})
    seo_data = seo_posts.get(str(post_id), seo_posts.get(post_id, {}))

    # Build URLs - canonical/OG use absolute (SITE_URL), content links use relative (with BASE_PATH)
    if lang == "en":
        canonical_url = f"{SITE_URL}/en/post/{post_id}"
        post_url_rel = f"{_lang_path(lang)}/post/{post_id}"
        amp_url_rel = f"{_lang_path(lang)}/post/{post_id}/amp"
    else:
        canonical_url = f"{SITE_URL}/post/{post_id}"
        post_url_rel = f"{_lang_path(lang)}/post/{post_id}"
        amp_url_rel = f"{_lang_path(lang)}/post/{post_id}/amp"

    # Title and description - use per-post SEO data when available
    title = post.get("title", "")
    # Generate description from post text if no SEO data available
    post_text_raw = post.get("textWithHashtags") or post.get("text") or ""
    auto_description = post_text_raw[:200].replace("\n", " ").strip() if post_text_raw else ""
    description = seo_data.get("description", "") or auto_description or (SITE_DESCRIPTION_RU if lang == "ru" else SITE_DESCRIPTION_EN)
    seo_title = seo_data.get("title", title)
    if seo_title:
        page_title = f"{seo_title} | SOCHIAUTOPARTS"
    else:
        page_title = title

    # Keywords from SEO data or hashtags
    post_keywords = seo_data.get("keywords", "")
    if not post_keywords and post.get("hashtags"):
        post_keywords = ", ".join(str(h).lstrip("#") for h in post.get("hashtags", [])[:10])

    # Published/modified time
    published_time = seo_data.get("publishedTime", post.get("date", ""))
    modified_time = seo_data.get("modifiedTime", post.get("date", ""))

    # OG image - use actual post image, not generic logo
    og_image = seo_data.get("ogImage") or extract_first_image(post) or DEFAULT_THUMBNAIL

    # Schema
    news_schema = generate_news_article_schema(post, {
        "ogUrl": canonical_url,
        "publishedTime": published_time,
        "modifiedTime": modified_time,
        "description": description,
    }, lang)

    # Breadcrumbs (relative URLs for clickable links)
    bc_home = t("bc_home", lang)
    bc_items = [
        {"name": bc_home, "url": _lang_base(lang)},
        {"name": post.get("title", "")[:50], "url": post_url_rel},
    ]
    breadcrumb_schema = generate_breadcrumb_schema(bc_items)
    breadcrumbs = render_breadcrumbs(bc_items, lang)

    # Gallery
    gallery_html = render_post_gallery(post, lang)

    # Post text
    post_text = post.get("textWithHashtags") or post.get("text") or ""
    formatted_text = format_post_text(post_text, lang)

    # Date display
    date_str = post.get("date", "")
    date_display = _format_date_display(date_str, lang)

    # AMP link (relative) — only if AMP generation is enabled
    amp_link_html = f'<a href="{amp_url_rel}" class="amp-badge">AMP</a>' if GENERATE_AMP else ""

    # Related posts
    related = get_related_posts(data, post_id, limit=RELATED_POSTS_COUNT)
    related_html = render_related_posts(related, lang)

    # Ads
    admitad_programs = get_admitad_programs(data)
    ads_html = ""
    if admitad_programs:
        ads_html = render_ad_blocks(admitad_programs, lang, max_blocks=4)

    # Shop widget
    shop_widget = ""
    if FEATURE_SHOP_ENABLED:
        products = data.get("products", [])[:6]
        shop_widget = render_shop_widget(products, lang, count=4)

    # Tags
    hashtags = post.get("hashtags", [])
    tags_html = ""
    if hashtags:
        tag_links = []
        for ht in hashtags:
            tag_name = re.sub(r"^#+", "", str(ht))
            if tag_name:
                tag_url = f"{_lang_path(lang)}/tag/{url_quote(tag_name)}.html"
                tag_links.append(f'<a href="{tag_url}" class="hashtag">#{escape_html(tag_name)}</a>')
        tags_html = '<div class="post-tags">' + " ".join(tag_links) + "</div>"

    # Telegram link
    telegram_link = post.get("telegramLink") or f"https://t.me/{CHANNEL_USERNAME}/{post_id}"
    open_in_tg = t("open_in_telegram", lang) if lang == "en" else "Открыть в Telegram"

    # Body
    body = f"""
<div class="container">
<div class="article-content">
{breadcrumbs}
<article>
<div class="article-meta">
<span>📅 {escape_html(date_display)}</span>
{amp_link_html}
</div>
<h1>{escape_html(title)}</h1>
{gallery_html}
<div class="article-body">
{formatted_text}
</div>
{tags_html}
<div class="post-actions" style="margin:1.5rem 0;">
<a href="{telegram_link}" class="btn-cta" target="_blank" rel="nofollow noopener noreferrer">💬 {open_in_tg}</a>
</div>
</article>
{related_html}
{ads_html}
{shop_widget}
</div>
</div>"""

    return _build_page(
        lang=lang,
        title=page_title,
        description=description[:200],
        url=canonical_url,
        path=f"/post/{post_id}" if lang == "ru" else f"/en/post/{post_id}",
        body_content=body,
        og_type="article",
        image=og_image,
        canonical=canonical_url,
        article_published=published_time,
        article_modified=modified_time,
        article_tag=post_keywords,
        extra_schema=[news_schema, breadcrumb_schema],
        active_page="home",
        post_id=post_id,
        include_matrix=False,
    )


# ===========================================================================
# AMP Post Page
# ===========================================================================

def generate_amp_post_page(data: dict, post_id: int, lang: str, output_dir: str) -> str:
    """Generate AMP version of post page.

    Args:
        data: The data dict from data_loader.
        post_id: The post ID.
        lang: Language code.
        output_dir: Output directory.

    Returns:
        Complete AMP HTML page string.
    """
    post = get_post_by_id(data, post_id)
    if post is None:
        return generate_404_page(lang, output_dir)

    seo_posts = data.get("seo_posts", {})
    seo_data = seo_posts.get(str(post_id), seo_posts.get(post_id, {}))

    if lang == "en":
        post_url = f"{SITE_URL}/en/post/{post_id}"
        canonical_url = f"{SITE_URL}/en/post/{post_id}"
    else:
        post_url = f"{SITE_URL}/post/{post_id}"
        canonical_url = f"{SITE_URL}/post/{post_id}"

    title = post.get("title", "")
    description = seo_data.get("description", "") or (SITE_DESCRIPTION_RU if lang == "ru" else SITE_DESCRIPTION_EN)
    og_image = seo_data.get("ogImage") or extract_first_image(post) or DEFAULT_THUMBNAIL
    published_time = seo_data.get("publishedTime", post.get("date", ""))

    # AMP schema
    news_schema = generate_news_article_schema(post, {
        "ogUrl": post_url,
        "publishedTime": published_time,
        "modifiedTime": published_time,
        "description": description,
    }, lang)

    # Post text
    post_text = post.get("textWithHashtags") or post.get("text") or ""
    formatted_text = format_post_text(post_text, lang)

    # Date
    date_str = post.get("date", "")
    date_display = _format_date_display(date_str, lang)

    # Media - AMP images
    media_html = ""
    media = post.get("media", [])
    if isinstance(media, list) and len(media) > 0:
        first_media = media[0]
        if isinstance(first_media, dict) and first_media.get("type") == "photo":
            img_url = first_media.get("directUrl") or first_media.get("url", "")
            if img_url:
                media_html = f'<amp-img src="{escape_html(img_url)}" alt="{escape_html(title)}" width="800" height="600" layout="responsive"></amp-img>'

    # Tags
    hashtags = post.get("hashtags", [])
    tags_html = ""
    if hashtags:
        tag_links = []
        for ht in hashtags:
            tag_name = re.sub(r"^#+", "", str(ht))
            if tag_name:
                tag_url = f"{_lang_path(lang)}/tag/{url_quote(tag_name)}.html"
                tag_links.append(f'<a href="{tag_url}" class="hashtag">#{escape_html(tag_name)}</a>')
        tags_html = '<div class="post-tags">' + " ".join(tag_links) + "</div>"

    site_name = SITE_NAME_RU if lang == "ru" else SITE_NAME_EN
    home_url = _lang_base(lang)

    return f"""<!doctype html>
<html amp lang="{lang}">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,minimum-scale=1,initial-scale=1" />
<title>{escape_html(title)} — {escape_html(site_name)}</title>
<link rel="canonical" href="{canonical_url}" />
<meta name="description" content="{escape_html(description[:200])}" />
<meta property="og:title" content="{escape_html(title)}" />
<meta property="og:description" content="{escape_html(description[:200])}" />
<meta property="og:url" content="{post_url}" />
<meta property="og:type" content="article" />
<meta property="og:image" content="{escape_html(og_image)}" />
<meta name="twitter:card" content="summary_large_image" />
<script type="application/ld+json">{news_schema}</script>
<style amp-boilerplate>body{{-webkit-animation:-amp-start 8s steps(1,end) 0s 1 normal both;-moz-animation:-amp-start 8s steps(1,end) 0s 1 normal both;-ms-animation:-amp-start 8s steps(1,end) 0s 1 normal both;animation:-amp-start 8s steps(1,end) 0s 1 normal both}}@-webkit-keyframes -amp-start{{from{{visibility:hidden}}to{{visibility:visible}}}}@-moz-keyframes -amp-start{{from{{visibility:hidden}}to{{visibility:visible}}}}@-ms-keyframes -amp-start{{from{{visibility:hidden}}to{{visibility:visible}}}}@-o-keyframes -amp-start{{from{{visibility:hidden}}to{{visibility:visible}}}}@keyframes -amp-start{{from{{visibility:hidden}}to{{visibility:visible}}}}</style><noscript><style amp-boilerplate>body{{-webkit-animation:none;-moz-animation:none;-ms-animation:none;animation:none}}</style></noscript>
<script async src="https://cdn.ampproject.org/v0.js"></script>
<style amp-custom>{AMP_CSS}</style>
</head>
<body>
<header class="site-header">
<div class="container">
<div class="header-content">
<a href="{home_url}" class="logo">SOCHIAUTOPARTS</a>
</div>
</div>
</header>
<main>
<div class="container">
<div class="article-content">
<article>
<div class="article-meta"><span>{escape_html(date_display)}</span></div>
<h1>{escape_html(title)}</h1>
{media_html}
<div class="article-body">{formatted_text}</div>
{tags_html}
</article>
</div>
</div>
</main>
<footer>
<div class="container">
<p>&copy; {_get_current_year()} {SITE_AUTHOR}. {"Все права защищены." if lang == "ru" else "All rights reserved."}</p>
</div>
</footer>
</body>
</html>"""


# ===========================================================================
# Articles Listing Page
# ===========================================================================

def generate_articles_page(data: dict, lang: str, output_dir: str, page: int = 1) -> str:
    """Generate articles listing page with pagination.

    Args:
        data: The data dict from data_loader.
        lang: Language code.
        output_dir: Output directory.
        page: Page number (1-based).

    Returns:
        Complete HTML page string.
    """
    articles = data.get("articles", [])
    popular_tags = get_popular_tags(data, limit=12)

    total_articles = len(articles)
    total_pages = max(1, math.ceil(total_articles / ARTICLES_PER_PAGE))

    start = (page - 1) * ARTICLES_PER_PAGE
    end = start + ARTICLES_PER_PAGE
    page_articles = articles[start:end]

    # SEO
    page_title = t("articles_title", lang)
    page_desc = t("articles_subtitle", lang)
    if lang == "ru":
        full_title = f"{page_title} | SOCHIAUTOPARTS"
    else:
        full_title = f"{page_title} | SOCHIAUTOPARTS"

    if lang == "en":
        page_url = f"{SITE_URL}/en/articles"
        path = "/en/articles"
    else:
        page_url = f"{SITE_URL}/articles"
        path = "/articles"

    page_url_rel = f"{_lang_path(lang)}/articles"

    # Articles grid
    articles_html = ""
    for article in page_articles:
        article_id = article.get("id", "")
        article_url = f"{_lang_path(lang)}/article/{article_id}"
        article_title = article.get("title", "")
        article_desc = article.get("plainDescription") or ""
        article_thumb = article.get("thumbnail", "")
        article_date = article.get("date", "")
        date_display = _format_date_display(article_date, lang)

        thumb_html = ""
        if article_thumb:
            thumb_html = f'<img src="{escape_html(article_thumb)}" alt="{escape_html(article_title)}" loading="lazy" referrerpolicy="no-referrer" />'

        articles_html += f"""
<article class="post-feed-item">
<div class="post-feed-media">{thumb_html}</div>
<div class="post-feed-content">
<div class="post-feed-meta"><span>📅 {escape_html(date_display)}</span></div>
<h3 class="post-feed-title"><a href="{article_url}">{escape_html(article_title)}</a></h3>
<div class="post-feed-text">{escape_html(article_desc[:200])}</div>
</div>
</article>"""

    # Pagination
    pagination_html = render_numbered_pagination(page, total_pages, page_url_rel, lang)

    # Breadcrumbs
    bc_items = [
        {"name": t("bc_home", lang), "url": _lang_base(lang)},
        {"name": t("bc_articles", lang), "url": page_url_rel},
    ]
    breadcrumbs = render_breadcrumbs(bc_items, lang)
    breadcrumb_schema = generate_breadcrumb_schema(bc_items)

    # Ad blocks on articles page (matching original site)
    admitad_programs = get_admitad_programs(data)
    articles_ads_html = ""
    if admitad_programs:
        articles_ads_html = render_ad_blocks(admitad_programs, lang)

    body = f"""
<div class="container">
{breadcrumbs}
<h1 style="margin:1rem 0;">{page_title}</h1>
<p style="color:var(--text-muted);margin-bottom:1.5rem;">{page_desc}</p>
{articles_ads_html}
<div class="posts-feed">
{articles_html}
</div>
{pagination_html}
</div>"""

    return _build_page(
        lang=lang,
        title=full_title,
        description=page_desc,
        url=page_url,
        path=path,
        body_content=body,
        og_type="website",
        extra_schema=[breadcrumb_schema],
        active_page="articles",
        tags_for_footer=popular_tags,
    )


# ===========================================================================
# Single Article Page
# ===========================================================================

def generate_article_page(data: dict, article_id: int, lang: str, output_dir: str) -> str:
    """Generate single article page.

    Args:
        data: The data dict from data_loader.
        article_id: The article ID.
        lang: Language code.
        output_dir: Output directory.

    Returns:
        Complete HTML page string.
    """
    articles = data.get("articles", [])
    article = None
    for a in articles:
        if str(a.get("id")) == str(article_id):
            article = a
            break

    if article is None:
        return generate_404_page(lang, output_dir)

    # SEO
    seo_articles = data.get("seo_articles", {})
    seo_data = seo_articles.get(str(article_id), seo_articles.get(article_id, {}))

    if lang == "en":
        article_url = f"{SITE_URL}/en/article/{article_id}"
    else:
        article_url = f"{SITE_URL}/article/{article_id}"

    article_url_rel = f"{_lang_path(lang)}/article/{article_id}"

    title = article.get("title", "")
    description = seo_data.get("description") or article.get("plainDescription") or ""
    og_image = article.get("thumbnail") or DEFAULT_THUMBNAIL
    published_time = seo_data.get("publishedTime") or article.get("date", "")
    modified_time = seo_data.get("modifiedTime") or article.get("date", "")

    if lang == "ru":
        page_title = f"{title} | SOCHIAUTOPARTS"
    else:
        page_title = f"{title} | SOCHIAUTOPARTS"

    # Schema
    article_schema = generate_article_schema(article, {
        "ogUrl": article_url,
        "publishedTime": published_time,
        "modifiedTime": modified_time,
        "description": description,
        "keywords": seo_data.get("keywords", ""),
    }, lang)

    # Breadcrumbs
    bc_items = [
        {"name": t("bc_home", lang), "url": _lang_base(lang)},
        {"name": t("bc_articles", lang), "url": f"{_lang_path(lang)}/articles"},
        {"name": title[:50], "url": article_url_rel},
    ]
    breadcrumb_schema = generate_breadcrumb_schema(bc_items)
    breadcrumbs = render_breadcrumbs(bc_items, lang)

    # Date
    date_display = _format_date_display(article.get("date", ""), lang)

    # Content
    content_html = article.get("content") or article.get("plainDescription") or ""
    if content_html and not content_html.strip().startswith("<"):
        content_html = f"<p>{escape_html(content_html)}</p>"

    # Tags
    tags_html = ""
    article_tags = article.get("tags", article.get("hashtags", []))
    if article_tags:
        tag_links = []
        for ht in article_tags:
            tag_name = re.sub(r"^#+", "", str(ht))
            if tag_name:
                tag_url = f"{_lang_path(lang)}/tag/{url_quote(tag_name)}.html"
                tag_links.append(f'<a href="{tag_url}" class="hashtag">#{escape_html(tag_name)}</a>')
        if tag_links:
            tags_html = '<div class="post-tags" style="margin-top:1.5rem;">' + " ".join(tag_links) + "</div>"

    body = f"""
<div class="container">
<div class="article-content">
{breadcrumbs}
<article>
<div class="article-meta">
<span>📅 {escape_html(date_display)}</span>
</div>
<h1>{escape_html(title)}</h1>
<div class="article-body">
{content_html}
</div>
{tags_html}
</article>
</div>
</div>"""

    return _build_page(
        lang=lang,
        title=page_title,
        description=description[:200],
        url=article_url,
        path=f"/article/{article_id}" if lang == "ru" else f"/en/article/{article_id}",
        body_content=body,
        og_type="article",
        image=og_image,
        canonical=article_url,
        article_published=published_time,
        article_modified=modified_time,
        extra_schema=[article_schema, breadcrumb_schema],
        active_page="articles",
        include_matrix=False,
    )


# ===========================================================================
# Archive Listing Page
# ===========================================================================

def generate_archive_page(data: dict, lang: str, output_dir: str, archive_data_dir: str, page: int = 1) -> str:
    """Generate archive listing page (50 posts per page) using telegram_fetcher data.

    Args:
        data: The data dict from data_loader.
        lang: Language code.
        output_dir: Output directory.
        archive_data_dir: Path to the telegram archive data directory.
        page: Page number (1-based).

    Returns:
        Complete HTML page string.
    """
    page_posts, total_posts, total_pages = get_archive_page_posts(archive_data_dir, page)

    # SEO
    page_title = t("archive_title", lang)
    page_desc = t("archive_subtitle", lang)
    if lang == "ru":
        full_title = f"Архив | SOCHIAUTOPARTS (стр. {page})"
    else:
        full_title = f"Archive | SOCHIAUTOPARTS (page {page})"

    if lang == "en":
        page_url = f"{SITE_URL}/en/archive"
        path = "/en/archive"
    else:
        page_url = f"{SITE_URL}/archive"
        path = "/archive"

    page_url_rel = f"{_lang_path(lang)}/archive"

    # Archive cards
    cards_html = ""
    for arch_post in page_posts:
        cards_html += render_archive_post_card(arch_post, lang)

    # Pagination (archive-style prev/next)
    archive_pagination = render_numbered_pagination(page, total_pages, page_url_rel, lang)

    # Counter
    if lang == "ru":
        counter_text = f"Всего {total_posts} публикаций в архиве"
    else:
        counter_text = f"Total {total_posts} posts in archive"
    counter_html = f'<div class="posts-counter">{counter_text}</div>'

    # Breadcrumbs
    bc_items = [
        {"name": t("bc_home", lang), "url": _lang_base(lang)},
        {"name": t("bc_archive", lang), "url": page_url_rel},
    ]
    breadcrumbs = render_breadcrumbs(bc_items, lang)
    breadcrumb_schema = generate_breadcrumb_schema(bc_items)

    body = f"""
<div class="archive-page-container">
{breadcrumbs}
<h1 style="margin:1rem 0;">{page_title}</h1>
<p style="color:var(--text-muted);margin-bottom:1.5rem;">{page_desc}</p>
{counter_html}
<div class="archive-grid">
{cards_html}
</div>
{archive_pagination}
</div>"""

    return _build_page(
        lang=lang,
        title=full_title,
        description=page_desc,
        url=page_url if page == 1 else f"{page_url}?page={page}",
        path=path,
        body_content=body,
        og_type="website",
        extra_schema=[breadcrumb_schema],
        active_page="archive",
        include_matrix=False,
    )


def _render_archive_pagination(current_page: int, total_pages: int, base_url: str, lang: str) -> str:
    """Render archive-specific prev/next pagination."""
    if total_pages <= 1:
        return ""

    newer_text = t("archive_newer", lang)
    older_text = t("archive_older", lang)

    html = '<div class="archive-pagination">\n'
    if current_page > 1:
        prev_url = base_url if current_page == 2 else f"{base_url}?page={current_page - 1}"
        html += f'<a href="{prev_url}">{newer_text}</a>\n'
    if current_page < total_pages:
        next_url = f"{base_url}?page={current_page + 1}"
        html += f'<a href="{next_url}">{older_text}</a>\n'
    html += '</div>\n'

    return html


# ===========================================================================
# Archive Post Page
# ===========================================================================

def generate_archive_post_page(data: dict, post_id: int, lang: str, output_dir: str, archive_data_dir: str) -> str:
    """Generate single archive post page.

    Args:
        data: The data dict from data_loader.
        post_id: The archive post ID.
        lang: Language code.
        output_dir: Output directory.
        archive_data_dir: Path to the telegram archive data directory.

    Returns:
        Complete HTML page string.
    """
    post = get_archive_post_by_id(archive_data_dir, post_id)
    if post is None:
        return generate_404_page(lang, output_dir)

    if lang == "en":
        post_url = f"{SITE_URL}/en/archive/post/{post_id}"
    else:
        post_url = f"{SITE_URL}/archive/post/{post_id}"

    post_url_rel = f"{_lang_path(lang)}/archive/post/{post_id}"

    # Title - use first line of text or post ID
    raw_text = post.get("text", "")
    title_line = raw_text.split("\n")[0][:100] if raw_text else f"Post #{post_id}"
    description = raw_text[:200] if raw_text else ""

    if lang == "ru":
        page_title = f"{title_line} | SOCHIAUTOPARTS"
    else:
        page_title = f"{title_line} | SOCHIAUTOPARTS"

    # Date
    date_str = post.get("date", "")
    date_display = _format_date_display(date_str, lang)

    # Photos
    photos = post.get("photos", [])
    photo_html = ""
    for photo_url in photos:
        photo_html += f'<div class="gallery-item"><img src="{escape_html(photo_url)}" alt="" loading="lazy" referrerpolicy="no-referrer" /></div>\n'

    # Videos
    videos = post.get("videos", [])
    video_html = ""
    for video_url in videos:
        video_html += f'<div class="gallery-item"><video src="{escape_html(video_url)}" controls preload="metadata" referrerpolicy="no-referrer"></video></div>\n'

    gallery_html = ""
    if photo_html or video_html:
        gallery_html = f'<div class="post-gallery">{photo_html}{video_html}</div>'

    # Text
    formatted_text = ""
    if raw_text:
        formatted_text = escape_html(raw_text).replace("\n", "<br>\n")

    # Views
    views = post.get("views", 0)
    views_html = f"<span>👁 {views}</span>" if views else ""

    # Telegram link
    telegram_link = f"https://t.me/{CHANNEL_USERNAME}/{post_id}"
    open_in_tg = "Открыть в Telegram" if lang == "ru" else "Open in Telegram"

    # Breadcrumbs
    bc_items = [
        {"name": t("bc_home", lang), "url": _lang_base(lang)},
        {"name": t("bc_archive", lang), "url": f"{_lang_path(lang)}/archive"},
        {"name": f"#{post_id}", "url": post_url_rel},
    ]
    breadcrumbs = render_breadcrumbs(bc_items, lang)
    breadcrumb_schema = generate_breadcrumb_schema(bc_items)

    # Partner ad blocks (matching production site)
    admitad_programs = get_admitad_programs(data)
    ads_html = ""
    if admitad_programs:
        ads_html = render_ad_blocks(admitad_programs, lang, max_blocks=4)

    # Shop widget
    shop_widget = ""
    if FEATURE_SHOP_ENABLED:
        products = data.get("products", [])[:6]
        shop_widget = render_shop_widget(products, lang, count=4)

    body = f"""
<div class="archive-post-container">
{breadcrumbs}
<article>
<div class="article-meta">
<span>📅 {escape_html(date_display)}</span>
{views_html}
</div>
{gallery_html}
<div class="article-body">{formatted_text}</div>
<div style="margin:1.5rem 0;">
<a href="{telegram_link}" class="btn-cta" target="_blank" rel="nofollow noopener noreferrer">💬 {open_in_tg}</a>
</div>
</article>
{ads_html}
{shop_widget}
</div>"""

    return _build_page(
        lang=lang,
        title=page_title,
        description=description[:200],
        url=post_url,
        path=f"/archive/post/{post_id}" if lang == "ru" else f"/en/archive/post/{post_id}",
        body_content=body,
        og_type="article",
        canonical=post_url,
        extra_schema=[breadcrumb_schema],
        active_page="archive",
        include_matrix=False,
    )


# ===========================================================================
# Shop Page
# ===========================================================================

def generate_shop_page(data: dict, lang: str, output_dir: str) -> str:
    """Generate shop page with client-side product loading from /api/shop/products.

    The shop page generates a static HTML shell with client-side JavaScript
    that fetches from /api/shop/products (handled by the Cloudflare Worker).

    Args:
        data: The data dict from data_loader.
        lang: Language code.
        output_dir: Output directory.

    Returns:
        Complete HTML page string.
    """
    popular_tags = get_popular_tags(data, limit=12)

    # SEO
    page_title = t("shop_title", lang)
    page_desc = t("shop_subtitle", lang)
    if lang == "ru":
        full_title = f"Магазин автозапчастей | SOCHIAUTOPARTS"
    else:
        full_title = f"Auto Parts Shop | SOCHIAUTOPARTS"

    if lang == "en":
        page_url = f"{SITE_URL}/en/shop"
        path = "/en/shop"
    else:
        page_url = f"{SITE_URL}/shop"
        path = "/shop"

    # Category buttons
    categories_html = ""
    for cat_key, cat_names in PRODUCT_CATEGORIES.items():
        cat_label = cat_names.get(lang, cat_names.get("ru", cat_key))
        cat_url = f"{_lang_path(lang)}/shop/category/{cat_key}"
        categories_html += f'<a href="{cat_url}" class="btn-secondary" style="display:inline-flex;align-items:center;gap:6px;padding:10px 20px;border-radius:9999px;font-size:0.875rem;font-weight:600;text-decoration:none;border:1px solid var(--border-color);color:var(--text-main);transition:all 0.15s;">{escape_html(cat_label)}</a>\n'

    # Search placeholder
    search_placeholder = t("shop_search_placeholder", lang)
    search_btn = "🔍" if lang == "ru" else "🔍"

    # Features
    feature_delivery = t("shop_feature_delivery", lang)
    feature_verified = t("shop_feature_verified", lang)
    feature_prices = t("shop_feature_prices", lang)
    feature_guarantee = t("shop_feature_guarantee", lang)

    # Breadcrumbs
    bc_items = [
        {"name": t("bc_home", lang), "url": _lang_base(lang)},
        {"name": t("bc_shop", lang), "url": f"{_lang_path(lang)}/shop"},
    ]
    breadcrumbs = render_breadcrumbs(bc_items, lang)
    breadcrumb_schema = generate_breadcrumb_schema(bc_items)

    # Pre-load product data for static rendering
    products_json = json.dumps(data.get("products", [])[:200], ensure_ascii=True)
    currency = PRODUCTS_CURRENCY_RU if lang == "ru" else PRODUCTS_CURRENCY_EN
    empty_text = t("shop_empty", lang)
    empty_reset = t("shop_empty_reset", lang) if lang == "ru" else "Reset"
    in_stock_text = "В наличии" if lang == "ru" else "In Stock"
    backorder_text = "Под заказ" if lang == "ru" else "Backorder"

    shop_js = f"""
<script>
(function() {{
  var allProducts = {products_json};
  var grid = document.getElementById('shopProductGrid');
  var searchInput = document.getElementById('shopSearchInput');
  var categoryBtns = document.querySelectorAll('.shop-category-btn');
  var loadMoreBtn = document.getElementById('shopLoadMore');
  var currentCategory = '';
  var currentQuery = '';
  var displayed = 0;
  var PER_PAGE = {PRODUCTS_PER_PAGE};

  function filterProducts() {{
    var filtered = allProducts.filter(function(p) {{
      if (currentCategory && p.category) {{
        var catSlug = String(p.category).toLowerCase().trim().replace(/ /g, '-');
        if (catSlug !== currentCategory) return false;
      }}
      if (currentQuery) {{
        var q = currentQuery.toLowerCase();
        var name = (p.name || '').toLowerCase();
        var desc = (p.description || '').toLowerCase();
        if (name.indexOf(q) === -1 && desc.indexOf(q) === -1) return false;
      }}
      return true;
    }});
    return filtered;
  }}

  function renderProducts(reset) {{
    var products = filterProducts();
    if (reset) {{ displayed = 0; grid.innerHTML = ''; }}
    var end = Math.min(displayed + PER_PAGE, products.length);
    if (products.length === 0) {{
      grid.innerHTML = '<div style="text-align:center;padding:2rem;"><p>{escape_html(empty_text)}</p></div>';
      if (loadMoreBtn) loadMoreBtn.style.display = 'none';
      return;
    }}
    var html = '';
    for (var i = displayed; i < end; i++) {{
      var p = products[i];
      var price = p.price ? Number(p.price).toLocaleString() + ' {currency}' : '';
      var avail = p.available ? '<div class="product-availability in-stock">{in_stock_text}</div>' : '<div class="product-availability out-of-stock">{backorder_text}</div>';
      html += '<div class="shop-product-card"><div class="product-image">';
      if (p.image) html += '<img src="' + p.image + '" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()">';
      html += '</div><div class="product-info"><div class="product-name">';
      var pid = p.id || '';
      var langPrefix = '{_lang_path(lang)}';
      html += '<a href="' + langPrefix + '/product/' + pid + '">' + (p.name || '').substring(0, 80) + '</a></div>';
      if (price) html += '<div class="product-price">' + price + '</div>';
      html += avail + '</div></div>';
    }}
    grid.innerHTML += html;
    displayed = end;
    if (loadMoreBtn) loadMoreBtn.style.display = displayed < products.length ? 'inline-flex' : 'none';
  }}

  window.resetShop = function() {{
    currentCategory = '';
    currentQuery = '';
    searchInput.value = '';
    categoryBtns.forEach(function(b) {{ b.classList.remove('active'); }});
    renderProducts(true);
  }};

  if (searchInput) {{
    var timeout = null;
    searchInput.addEventListener('input', function() {{
      clearTimeout(timeout);
      timeout = setTimeout(function() {{
        currentQuery = searchInput.value.trim();
        renderProducts(true);
      }}, 300);
    }});
  }}

  categoryBtns.forEach(function(btn) {{
    btn.addEventListener('click', function() {{
      currentCategory = this.dataset.category;
      categoryBtns.forEach(function(b) {{ b.classList.remove('active'); }});
      this.classList.add('active');
      renderProducts(true);
    }});
  }});

  if (loadMoreBtn) {{
    loadMoreBtn.addEventListener('click', function() {{
      renderProducts(false);
    }});
  }}

  renderProducts(true);
}})();
</script>"""

    # Load more button text
    load_more_text = "Загрузить ещё" if lang == "ru" else "Load more"

    # Partner ad blocks (matching production site)
    admitad_programs = get_admitad_programs(data)
    ads_html = ""
    if admitad_programs:
        ads_html = render_ad_blocks(admitad_programs, lang, max_blocks=5)

    # Ad category buttons (matching production site)
    ad_category_buttons = render_ad_category_buttons(lang)

    body = f"""
<div class="shop-hero">
<h1>{page_title}</h1>
<p>{page_desc}</p>
</div>
<div class="shop-page-container">
{breadcrumbs}
<div class="shop-search-bar">
<input type="search" id="shopSearchInput" placeholder="{search_placeholder}" autocomplete="off" />
<button id="shopSearchBtn">{search_btn}</button>
</div>
{ad_category_buttons}
<div class="ad-section-buttons">
{categories_html}
</div>
<div class="shop-product-grid" id="shopProductGrid">
<div style="text-align:center;padding:3rem;color:var(--text-muted);">{"Загрузка..." if lang == "ru" else "Loading..."}</div>
</div>
<div style="text-align:center;margin:1.5rem 0;">
<button id="shopLoadMore" style="display:none;padding:12px 32px;border-radius:12px;background:var(--primary);color:#fff;border:none;font-weight:600;cursor:pointer;font-size:0.9375rem;">{load_more_text}</button>
</div>
{ads_html}
<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:1rem;margin:2rem 0;">
<div style="text-align:center;padding:1.5rem;background:var(--bg-card);border-radius:12px;border:1px solid var(--border-light);">🚚 {feature_delivery}</div>
<div style="text-align:center;padding:1.5rem;background:var(--bg-card);border-radius:12px;border:1px solid var(--border-light);">✅ {feature_verified}</div>
<div style="text-align:center;padding:1.5rem;background:var(--bg-card);border-radius:12px;border:1px solid var(--border-light);">💰 {feature_prices}</div>
<div style="text-align:center;padding:1.5rem;background:var(--bg-card);border-radius:12px;border:1px solid var(--border-light);">🛡️ {feature_guarantee}</div>
</div>
</div>
{shop_js}"""

    return _build_page(
        lang=lang,
        title=full_title,
        description=page_desc,
        url=page_url,
        path=path,
        body_content=body,
        og_type="website",
        extra_schema=[breadcrumb_schema],
        active_page="shop",
        tags_for_footer=popular_tags,
    )


# ===========================================================================
# Product Page
# ===========================================================================

def generate_product_page(data: dict, product_id: str, lang: str, output_dir: str) -> str:
    """Generate product detail page with Schema.org Product markup.

    Args:
        data: The data dict from data_loader.
        product_id: The product ID string.
        lang: Language code.
        output_dir: Output directory.

    Returns:
        Complete HTML page string.
    """
    product_map = data.get("product_map", {})
    product = product_map.get(str(product_id))
    if product is None:
        return generate_404_page(lang, output_dir)

    # URLs
    if lang == "en":
        product_url = f"{SITE_URL}/en/product/{product_id}"
    else:
        product_url = f"{SITE_URL}/product/{product_id}"

    product_url_rel = f"{_lang_path(lang)}/product/{product_id}"

    name = product.get("name", "")
    description = (product.get("description") or name)[:200]
    price = product.get("price", 0)
    currency = product.get("currency", "RUB")
    available = product.get("available", False)
    image = product.get("image", "")
    vendor = product.get("vendor") or product.get("brand", "")
    model = product.get("model", "")
    cat_name = product.get("category", "")
    if isinstance(cat_name, dict):
        cat_name = cat_name.get(lang, cat_name.get("ru", ""))

    # Title
    if lang == "ru":
        page_title = f"{name} | SOCHIAUTOPARTS"
    else:
        page_title = f"{name} | SOCHIAUTOPARTS"

    # Schema.org Product
    product_schema = generate_product_schema(product, lang)

    # Breadcrumbs
    bc_items = [
        {"name": t("bc_home", lang), "url": _lang_base(lang)},
        {"name": t("bc_shop", lang), "url": f"{_lang_path(lang)}/shop"},
        {"name": name[:50], "url": product_url_rel},
    ]
    breadcrumb_schema = generate_breadcrumb_schema(bc_items)
    breadcrumbs = render_breadcrumbs(bc_items, lang)

    # Price formatting
    try:
        price_formatted = f"{int(price):,} {currency}"
    except (ValueError, TypeError):
        price_formatted = f"{price} {currency}"

    availability_text = "В наличии" if available else "Под заказ"
    availability_class = "in-stock" if available else "out-of-stock"
    if lang == "en":
        availability_text = "In Stock" if available else "Backorder"

    # Category link
    category_html = ""
    cat_id = product.get("categoryId") or product.get("category_id", "")
    if cat_id or cat_name:
        cat_slug = str(cat_name).lower().strip().replace(" ", "-") if cat_name else str(cat_id)
        cat_url = f"{_lang_path(lang)}/shop/category/{cat_slug}"
        _cat_label = t("product_category", lang)
        category_html = f'<div class="product-category"><span>{_cat_label}:</span> <a href="{cat_url}">{escape_html(str(cat_name))}</a></div>'

    # Vendor
    vendor_html = ""
    if vendor:
        _vendor_label = t("product_vendor", lang)
        vendor_html = f'<div class="product-vendor"><span>{_vendor_label}:</span> {escape_html(vendor)}</div>'

    # Model
    model_html = ""
    if model:
        model_html = f'<div class="product-model"><span>Model:</span> {escape_html(model)}</div>'

    # Image
    image_html = ""
    if image:
        image_html = f'<div class="product-detail-image"><img src="{escape_html(image)}" alt="{escape_html(name)}" referrerpolicy="no-referrer" style="width:100%;border-radius:12px;" onerror="this.remove()" /></div>'

    # Telegram link
    telegram_link = f"https://t.me/{CHANNEL_USERNAME}"
    buy_text = t("shop_buy", lang) if lang == "en" else "Купить"

    body = f"""
<div class="container">
{breadcrumbs}
<div class="product-detail-grid">
<div>
{image_html}
</div>
<div>
<h1>{escape_html(name)}</h1>
<div class="product-price" style="font-size:1.5rem;font-weight:800;color:var(--primary);margin:0.75rem 0;">{price_formatted}</div>
<div class="product-availability {availability_class}" style="font-weight:600;margin:0.5rem 0;">{availability_text}</div>
{category_html}
{vendor_html}
{model_html}
<p style="color:var(--text-muted);margin:1rem 0;line-height:1.7;">{escape_html(description)}</p>
<div style="margin:1.5rem 0;">
<a href="{telegram_link}" class="btn-cta" target="_blank" rel="nofollow noopener noreferrer">💬 {buy_text}</a>
</div>
</div>
</div>
</div>"""

    return _build_page(
        lang=lang,
        title=page_title,
        description=description,
        url=product_url,
        path=f"/product/{product_id}" if lang == "ru" else f"/en/product/{product_id}",
        body_content=body,
        og_type="product",
        image=image or None,
        canonical=product_url,
        product_price=str(price),
        product_currency=currency,
        extra_schema=[product_schema, breadcrumb_schema],
        active_page="shop",
        include_matrix=False,
    )


# ===========================================================================
# Category Page
# ===========================================================================

def generate_category_page(data: dict, category_id: str, lang: str, output_dir: str) -> str:
    """Generate product category page.

    Args:
        data: The data dict from data_loader.
        category_id: The category slug.
        lang: Language code.
        output_dir: Output directory.

    Returns:
        Complete HTML page string.
    """
    category_map = data.get("category_map", {})
    cat_products = category_map.get(category_id, [])

    # Category name
    cat_display = category_id.replace("-", " ").title()
    for cat_key, cat_names in PRODUCT_CATEGORIES.items():
        if cat_key.lower() == category_id.lower():
            cat_display = cat_names.get(lang, cat_names.get("ru", category_id))
            break

    if lang == "en":
        page_url = f"{SITE_URL}/en/shop/category/{category_id}"
        path = f"/en/shop/category/{category_id}"
    else:
        page_url = f"{SITE_URL}/shop/category/{category_id}"
        path = f"/shop/category/{category_id}"

    page_url_rel = f"{_lang_path(lang)}/shop/category/{category_id}"

    page_title = f"{cat_display} | SOCHIAUTOPARTS"
    currency = PRODUCTS_CURRENCY_RU if lang == "ru" else PRODUCTS_CURRENCY_EN

    # Products grid
    products_html = ""
    for product in cat_products[:PRODUCTS_PER_PAGE]:
        name = product.get("name", "")
        if len(name) > 60:
            name = name[:60] + "..."
        price = product.get("price", 0)
        image = product.get("image", "")
        pid = product.get("id", "")
        available = product.get("available", False)

        try:
            price_formatted = f"{int(price):,} {currency}"
        except (ValueError, TypeError):
            price_formatted = f"{price} {currency}"

        avail_class = "in-stock" if available else "out-of-stock"
        avail_text = ("В наличии" if lang == "ru" else "In Stock") if available else ("Под заказ" if lang == "ru" else "Backorder")

        product_url = f"{_lang_path(lang)}/product/{pid}"

        # Build product image HTML separately to avoid backslash in f-string
        # (Python 3.11 does not allow backslashes inside f-string expressions)
        _img_onerror = "this.style.display='none'"
        _img_html = f'<img src="{escape_html(image)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="{_img_onerror}">' if image else ''
        products_html += f"""
<div class="shop-product-card">
<div class="product-image">{_img_html}</div>
<div class="product-info">
<div class="product-name"><a href="{product_url}">{escape_html(name)}</a></div>
<div class="product-price">{price_formatted}</div>
<div class="product-availability {avail_class}">{avail_text}</div>
</div>
</div>"""

    # Breadcrumbs
    bc_items = [
        {"name": t("bc_home", lang), "url": _lang_base(lang)},
        {"name": t("bc_shop", lang), "url": f"{_lang_path(lang)}/shop"},
        {"name": cat_display, "url": page_url_rel},
    ]
    breadcrumbs = render_breadcrumbs(bc_items, lang)
    breadcrumb_schema = generate_breadcrumb_schema(bc_items)

    body = f"""
<div class="container">
{breadcrumbs}
<h1 style="margin:1rem 0;">{cat_display}</h1>
<div class="shop-product-grid">
{products_html}
</div>
</div>"""

    return _build_page(
        lang=lang,
        title=page_title,
        description=f"{cat_display} — {'Автозапчасти в Сочи' if lang == 'ru' else 'Auto Parts in Sochi'}",
        url=page_url,
        path=path,
        body_content=body,
        og_type="website",
        extra_schema=[breadcrumb_schema],
        active_page="shop",
        include_matrix=False,
    )


# ===========================================================================
# Tag Page
# ===========================================================================

def generate_tag_page(data: dict, tag: str, lang: str, output_dir: str, page: int = 1) -> str:
    """Generate tag page with posts filtered by tag.

    Args:
        data: The data dict from data_loader.
        tag: The tag name (without #).
        lang: Language code.
        output_dir: Output directory.
        page: Page number (1-based).

    Returns:
        Complete HTML page string.
    """
    tag_posts, total, total_pages = get_posts_by_tag(data, tag, page=page, per_page=POSTS_PER_PAGE)
    popular_tags = get_popular_tags(data, limit=12)

    if lang == "en":
        page_url = f"{SITE_URL}/en/tag/{tag}"
        path = f"/en/tag/{tag}"
    else:
        page_url = f"{SITE_URL}/tag/{tag}"
        path = f"/tag/{tag}"

    page_url_rel = f"{_lang_path(lang)}/tag/{tag}"

    if lang == "ru":
        page_title = f"#{tag} | SOCHIAUTOPARTS"
    else:
        page_title = f"#{tag} | SOCHIAUTOPARTS"

    # Post cards
    posts_html = ""
    for post in tag_posts:
        posts_html += render_post_card(post, lang)

    # Pagination
    pagination_html = render_numbered_pagination(page, total_pages, page_url_rel, lang)

    # Breadcrumbs
    bc_items = [
        {"name": t("bc_home", lang), "url": _lang_base(lang)},
        {"name": f"#{tag}", "url": page_url_rel},
    ]
    breadcrumbs = render_breadcrumbs(bc_items, lang)
    breadcrumb_schema = generate_breadcrumb_schema(bc_items)

    # Counter
    if lang == "ru":
        counter = f"{total} публикаций с тегом #{escape_html(tag)}"
    else:
        counter = f"{total} posts tagged #{escape_html(tag)}"

    body = f"""
<div class="container">
{breadcrumbs}
<h1 style="margin:1rem 0;">#{escape_html(tag)}</h1>
<p style="color:var(--text-muted);margin-bottom:1.5rem;">{counter}</p>
<div class="posts-feed">
{posts_html}
</div>
{pagination_html}
</div>"""

    return _build_page(
        lang=lang,
        title=page_title,
        description=f"{'Публикации с тегом' if lang == 'ru' else 'Posts tagged'} #{tag}",
        url=page_url,
        path=path,
        body_content=body,
        og_type="website",
        extra_schema=[breadcrumb_schema],
        active_page="home",
        tags_for_footer=popular_tags,
        tag=tag,
    )


# ===========================================================================
# Privacy Page
# ===========================================================================

def generate_privacy_page(lang: str, output_dir: str) -> str:
    """Generate privacy policy page.

    Args:
        lang: Language code.
        output_dir: Output directory.

    Returns:
        Complete HTML page string.
    """
    if lang == "en":
        page_url = f"{SITE_URL}/en/privacy"
        path = "/en/privacy"
    else:
        page_url = f"{SITE_URL}/privacy"
        path = "/privacy"

    page_title = t("privacy_title", lang)
    if lang == "ru":
        full_title = f"Политика конфиденциальности | SOCHIAUTOPARTS"
    else:
        full_title = f"Privacy Policy | SOCHIAUTOPARTS"

    # Privacy content
    if lang == "ru":
        privacy_content = """
<h2>1. Общие положения</h2>
<p>Настоящая Политика конфиденциальности определяет порядок обработки и защиты персональных данных пользователей сайта sochiautoparts.ru (далее — Сайт).</p>
<p>Используя Сайт, вы подтверждаете своё согласие с правилами обработки персональных данных, изложенными в настоящей Политике.</p>

<h2>2. Сбор данных</h2>
<p>Мы можем собирать следующие данные:</p>
<ul>
<li>IP-адрес и данные браузера</li>
<li>Данные файлов cookie</li>
<li>Информация о поведении на сайте</li>
<li>Данные, предоставленные добровольно через формы обратной связи</li>
</ul>

<h2>3. Использование данных</h2>
<p>Собранные данные используются для:</p>
<ul>
<li>Улучшения работы сайта</li>
<li>Персонализации контента</li>
<li>Статистического анализа посещаемости</li>
<li>Связи с пользователями при необходимости</li>
</ul>

<h2>4. Файлы cookie</h2>
<p>Сайт использует файлы cookie для улучшения пользовательского опыта. Вы можете отключить cookie в настройках браузера.</p>

<h2>5. Защита данных</h2>
<p>Мы принимаем необходимые организационные и технические меры для защиты персональных данных от несанкционированного доступа.</p>

<h2>6. Контактная информация</h2>
<p>По вопросам, связанным с обработкой персональных данных, обращайтесь по адресу: info@sochiautoparts.ru</p>
"""
    else:
        privacy_content = """
<h2>1. General Provisions</h2>
<p>This Privacy Policy defines the processing and protection of personal data of users of the sochiautoparts.ru website (hereinafter — the Site).</p>
<p>By using the Site, you confirm your agreement with the personal data processing rules set forth in this Policy.</p>

<h2>2. Data Collection</h2>
<p>We may collect the following data:</p>
<ul>
<li>IP address and browser data</li>
<li>Cookie data</li>
<li>Behavioral information on the site</li>
<li>Data provided voluntarily through feedback forms</li>
</ul>

<h2>3. Use of Data</h2>
<p>Collected data is used for:</p>
<ul>
<li>Improving site performance</li>
<li>Content personalization</li>
<li>Statistical analysis of traffic</li>
<li>Communication with users when necessary</li>
</ul>

<h2>4. Cookies</h2>
<p>The site uses cookies to improve user experience. You can disable cookies in your browser settings.</p>

<h2>5. Data Protection</h2>
<p>We take necessary organizational and technical measures to protect personal data from unauthorized access.</p>

<h2>6. Contact Information</h2>
<p>For questions related to personal data processing, please contact: info@sochiautoparts.ru</p>
"""

    # Breadcrumbs
    bc_items = [
        {"name": t("bc_home", lang), "url": _lang_base(lang)},
        {"name": t("nav_privacy", lang), "url": f"{_lang_path(lang)}/privacy"},
    ]
    breadcrumbs = render_breadcrumbs(bc_items, lang)

    body = f"""
<div class="container">
<div class="article-content">
{breadcrumbs}
<h1>{page_title}</h1>
<div class="article-body">
{privacy_content}
</div>
</div>
</div>"""

    return _build_page(
        lang=lang,
        title=full_title,
        description=t("privacy_title", lang),
        url=page_url,
        path=path,
        body_content=body,
        og_type="website",
        active_page="",
        include_matrix=False,
        robots="noindex, follow",
    )


# ===========================================================================
# Contacts Page
# ===========================================================================

def generate_contacts_page(lang: str, output_dir: str) -> str:
    """Generate contacts page.

    Args:
        lang: Language code.
        output_dir: Output directory.

    Returns:
        Complete HTML page string.
    """
    if lang == "en":
        page_url = f"{SITE_URL}/en/contacts"
        path = "/en/contacts"
    else:
        page_url = f"{SITE_URL}/contacts"
        path = "/contacts"

    page_title = t("contacts_title", lang)
    if lang == "ru":
        full_title = f"Контакты | SOCHIAUTOPARTS"
    else:
        full_title = f"Contacts | SOCHIAUTOPARTS"

    # Contact info
    address = CONTACT_ADDRESS_RU if lang == "ru" else CONTACT_ADDRESS_EN
    hours = CONTACT_WORKING_HOURS_RU if lang == "ru" else CONTACT_WORKING_HOURS_EN

    email_label = t("contacts_email", lang)
    telegram_label = t("contacts_telegram", lang)
    instagram_label = t("contacts_instagram", lang)

    # Breadcrumbs
    bc_items = [
        {"name": t("bc_home", lang), "url": _lang_base(lang)},
        {"name": t("nav_contacts", lang), "url": f"{_lang_path(lang)}/contacts"},
    ]
    breadcrumbs = render_breadcrumbs(bc_items, lang)

    phone_section = ""
    if CONTACT_PHONE:
        phone_section = f'''<div style="margin:1.5rem 0;">
<h2>📞 {"Телефон" if lang == "ru" else "Phone"}</h2>
<p><a href="{CONTACT_PHONE_HREF}">{escape_html(CONTACT_PHONE)}</a></p>
</div>'''

    body = f"""
<div class="container">
<div class="article-content">
{breadcrumbs}
<h1>{page_title}</h1>
<div class="article-body">
<div style="margin:1.5rem 0;">
<h2>📍 {"Адрес" if lang == "ru" else "Address"}</h2>
<p>{escape_html(address)}</p>
</div>
{phone_section}
<div style="margin:1.5rem 0;">
<h2>📧 {email_label}</h2>
<p><a href="{CONTACT_EMAIL_HREF}">{escape_html(CONTACT_EMAIL)}</a></p>
</div>
<div style="margin:1.5rem 0;">
<h2>💬 {telegram_label}</h2>
<p><a href="https://t.me/{CHANNEL_USERNAME}" target="_blank" rel="nofollow noopener noreferrer">@{CHANNEL_USERNAME}</a></p>
</div>
<div style="margin:1.5rem 0;">
<h2>📷 {instagram_label}</h2>
<p><a href="{SOCIAL_LINKS.get('instagram', '#')}" target="_blank" rel="nofollow noopener noreferrer">Instagram</a></p>
</div>
<div style="margin:1.5rem 0;">
<h2>🕐 {"Часы работы" if lang == "ru" else "Working Hours"}</h2>
<p>{escape_html(hours)}</p>
</div>
</div>
</div>
</div>"""

    return _build_page(
        lang=lang,
        title=full_title,
        description="Контакты" if lang == "ru" else "Contacts",
        url=page_url,
        path=path,
        body_content=body,
        og_type="website",
        active_page="contacts",
        include_matrix=False,
    )


# ===========================================================================
# Ad Category Page
# ===========================================================================

def generate_ad_category_page(data: dict, category: str, lang: str, output_dir: str) -> str:
    """Generate Admitad ad category page.

    Args:
        data: The data dict from data_loader.
        category: The Admitad category key (e.g., 'autodoc').
        lang: Language code.
        output_dir: Output directory.

    Returns:
        Complete HTML page string.
    """
    cat_config = ADMITAD_CONFIG.get(category, {})
    cat_name = cat_config.get(lang, cat_config.get("ru", category))
    cat_url = cat_config.get("url", "#")
    cat_logo = cat_config.get("logo", "")

    # Also get matching programs from pipeline data
    admitad_programs = get_admitad_programs(data)
    matching_programs = []
    for prog in admitad_programs:
        if not isinstance(prog, dict):
            continue
        prog_cat = prog.get("jsonCategory", "")
        if prog_cat == category:
            matching_programs.append(prog)
    
    # If no config name, try pipeline data
    if not cat_config and matching_programs:
        first_prog = matching_programs[0]
        cat_name = first_prog.get("name", category)
        cat_logo = first_prog.get("image") or first_prog.get("logo", "")

    if lang == "en":
        page_url = f"{SITE_URL}/en/ads/{category}"
        path = f"/en/ads/{category}"
    else:
        page_url = f"{SITE_URL}/ads/{category}"
        path = f"/ads/{category}"

    page_url_rel = f"{_lang_path(lang)}/ads/{category}"

    if lang == "ru":
        full_title = f"{cat_name} | SOCHIAUTOPARTS"
    else:
        full_title = f"{cat_name} | SOCHIAUTOPARTS"

    # Logo
    logo_html = ""
    if cat_logo:
        logo_html = f'<img src="{escape_html(cat_logo)}" alt="{escape_html(cat_name)}" style="max-width:200px;margin-bottom:1rem;" referrerpolicy="no-referrer" onerror="this.remove()" />'

    # Description
    if lang == "ru":
        desc_text = f"Партнёрская программа {cat_name}. Переходите по ссылке для получения специальных предложений и скидок на автозапчасти."
        visit_text = "Перейти на сайт партнёра"
        legal_text = "Реклама. Вознаграждение за размещение."
    else:
        desc_text = f"Partner program {cat_name}. Follow the link for special offers and discounts on auto parts."
        visit_text = "Visit partner website"
        legal_text = "Advertisement. Compensation for placement."

    # Programs cards HTML
    programs_cards_html = ""
    for prog in matching_programs:
        prog_name = prog.get("name", "")
        prog_desc = prog.get("description", "")
        prog_image = prog.get("image") or prog.get("logo", "")
        prog_url = prog.get("affiliateUrl") or prog.get("url") or prog.get("gotoLink", cat_url)
        
        card_html = f'<div class="ad-block-item">'
        if prog_image:
            card_html += f'<div class="ad-block-media"><img src="{escape_html(prog_image)}" alt="{escape_html(prog_name)}" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()"></div>'
        card_html += f'<h4 class="ad-block-title">{escape_html(prog_name)}</h4>'
        if prog_desc:
            card_html += f'<p class="ad-block-desc">{escape_html(prog_desc[:200])}</p>'
        card_html += f'<a href="{escape_html(prog_url)}" class="btn-cta" target="_blank" rel="nofollow noopener sponsored">{visit_text}</a>'
        card_html += '</div>'
        programs_cards_html += card_html
    
    programs_section = ""
    if programs_cards_html:
        programs_section = f'<div class="ad-blocks-container">{programs_cards_html}</div>'

    # Breadcrumbs
    bc_items = [
        {"name": t("bc_home", lang), "url": _lang_base(lang)},
        {"name": cat_name, "url": page_url_rel},
    ]
    breadcrumbs = render_breadcrumbs(bc_items, lang)

    body = f"""
<div class="container">
<div class="article-content">
{breadcrumbs}
<h1>{escape_html(cat_name)}</h1>
<div style="text-align:center;margin:1.5rem 0;">
{logo_html}
</div>
<p style="color:var(--text-muted);margin-bottom:1.5rem;line-height:1.7;">{desc_text}</p>
<div style="text-align:center;margin:2rem 0;">
<a href="{cat_url}" class="btn-cta" target="_blank" rel="nofollow noopener sponsored">{visit_text}</a>
</div>
{programs_section}
<p style="font-size:0.75rem;color:var(--text-light);text-align:center;">{legal_text}</p>
</div>
</div>"""

    return _build_page(
        lang=lang,
        title=full_title,
        description=desc_text[:200],
        url=page_url,
        path=path,
        body_content=body,
        og_type="website",
        active_page="",
        include_matrix=False,
        robots="noindex, follow",
    )


# ===========================================================================
# AMP Homepage
# ===========================================================================

def generate_amp_homepage(data: dict, lang: str, output_dir: str) -> str:
    """Generate AMP homepage.

    Args:
        data: The data dict from data_loader.
        lang: Language code.
        output_dir: Output directory.

    Returns:
        Complete AMP HTML page string.
    """
    posts = data.get("posts", [])
    page_posts = posts[:POSTS_PER_PAGE]

    site_name = SITE_NAME_RU if lang == "ru" else SITE_NAME_EN
    site_desc = SITE_DESCRIPTION_RU if lang == "ru" else SITE_DESCRIPTION_EN
    home_url = _lang_base(lang)
    canonical_url = home_url

    if lang == "ru":
        page_title = f"SOCHIAUTOPARTS - Мировые автоновости, обзоры и тест-драйвы"
    else:
        page_title = f"SOCHIAUTOPARTS - Global Automotive News, Reviews & Test Drives"

    # Schema
    website_schema = generate_web_site_schema(lang)

    # Post cards
    posts_html = ""
    for post in page_posts:
        post_id = post.get("id", 0)
        title = post.get("title", "")
        post_url = f"{_lang_path(lang)}/post/{post_id}"
        text = (post.get("text") or "")[:200]
        date_display = _format_date_display(post.get("date", ""), lang)

        # AMP image
        media_html = ""
        media = post.get("media", [])
        if isinstance(media, list) and len(media) > 0:
            first_media = media[0]
            if isinstance(first_media, dict) and first_media.get("type") == "photo":
                img_url = first_media.get("directUrl") or first_media.get("url", "")
                if img_url:
                    media_html = f'<amp-img src="{escape_html(img_url)}" alt="{escape_html(title)}" width="800" height="600" layout="responsive"></amp-img>'

        posts_html += f"""
<div class="post-feed-item">
<div class="post-feed-media">{media_html}</div>
<div class="post-feed-content">
<div class="post-feed-meta"><span>{escape_html(date_display)}</span></div>
<h3 class="post-feed-title"><a href="{post_url}">{escape_html(title)}</a></h3>
<div class="post-feed-text">{escape_html(text)}</div>
</div>
</div>"""

    current_year = _get_current_year()

    return f"""<!doctype html>
<html amp lang="{lang}">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,minimum-scale=1,initial-scale=1" />
<title>{escape_html(page_title)}</title>
<link rel="canonical" href="{canonical_url}" />
<meta name="description" content="{escape_html(site_desc)}" />
<script type="application/ld+json">{website_schema}</script>
<style amp-boilerplate>body{{-webkit-animation:-amp-start 8s steps(1,end) 0s 1 normal both;-moz-animation:-amp-start 8s steps(1,end) 0s 1 normal both;-ms-animation:-amp-start 8s steps(1,end) 0s 1 normal both;animation:-amp-start 8s steps(1,end) 0s 1 normal both}}@-webkit-keyframes -amp-start{{from{{visibility:hidden}}to{{visibility:visible}}}}@-moz-keyframes -amp-start{{from{{visibility:hidden}}to{{visibility:visible}}}}@-ms-keyframes -amp-start{{from{{visibility:hidden}}to{{visibility:visible}}}}@-o-keyframes -amp-start{{from{{visibility:hidden}}to{{visibility:visible}}}}@keyframes -amp-start{{from{{visibility:hidden}}to{{visibility:visible}}}}</style><noscript><style amp-boilerplate>body{{-webkit-animation:none;-moz-animation:none;-ms-animation:none;animation:none}}</style></noscript>
<script async src="https://cdn.ampproject.org/v0.js"></script>
<style amp-custom>{AMP_CSS}</style>
</head>
<body>
<header class="site-header">
<div class="container">
<div class="header-content">
<a href="{home_url}" class="logo">SOCHIAUTOPARTS</a>
</div>
</div>
</header>
<header class="hero">
<h1>SOCHIAUTOPARTS</h1>
<p>{"Ежедневные новости, тест-драйвы и обзоры мирового автопрома." if lang == "ru" else "Daily news, test drives and reviews of the global automotive industry."}</p>
</header>
<main>
<div class="container">
<div class="posts-feed">
{posts_html}
</div>
</div>
</main>
<footer>
<div class="container">
<p>&copy; {current_year} {SITE_AUTHOR}. {"Все права защищены." if lang == "ru" else "All rights reserved."}</p>
</div>
</footer>
</body>
</html>"""


# ===========================================================================
# 404 Page
# ===========================================================================

def generate_404_page(lang: str, output_dir: str) -> str:
    """Generate 404 error page.

    Args:
        lang: Language code.
        output_dir: Output directory.

    Returns:
        Complete HTML page string.
    """
    title_text = t("404_title", lang)
    body_text = t("404_text", lang)
    redirect_text = t("404_redirect", lang)
    home_url = _lang_base(lang)

    if lang == "ru":
        full_title = f"404 — Страница не найдена | SOCHIAUTOPARTS"
    else:
        full_title = f"404 — Page Not Found | SOCHIAUTOPARTS"

    body = f"""
<div class="container" style="text-align:center;padding:4rem 1rem;">
<h1 style="font-size:4rem;font-weight:800;color:var(--primary);margin-bottom:0.5rem;">404</h1>
<h2 style="margin-bottom:1rem;">{title_text}</h2>
<p style="color:var(--text-muted);margin-bottom:1rem;">{body_text}</p>
<p style="color:var(--text-muted);font-size:0.875rem;">{redirect_text}</p>
<a href="{home_url}" class="btn-cta" style="margin-top:1.5rem;">{"На главную" if lang == "ru" else "Go Home"}</a>
</div>
<script>setTimeout(function(){{ window.location.href = "{home_url}"; }}, 8000);</script>"""

    return _build_page(
        lang=lang,
        title=full_title,
        description="404 Page Not Found",
        url=SITE_URL,
        path="/404",
        body_content=body,
        og_type="website",
        active_page="",
        include_matrix=False,
        robots="noindex, nofollow",
    )


# ===========================================================================
# Sitemaps
# ===========================================================================

def generate_sitemaps(data: dict, output_dir: str, archive_data_dir: str):
    """Generate all sitemap XML files.

    Args:
        data: The data dict from data_loader.
        output_dir: Root output directory.
        archive_data_dir: Path to the telegram archive data directory.
    """
    posts = data.get("posts", [])
    products = data.get("products", [])
    # hashtag_index is now unwrapped by data_loader.load_data() automatically
    hashtag_index = data.get("hashtag_index", {})
    # Safety: still check for nested structure in case data was loaded differently
    if isinstance(hashtag_index, dict) and "index" in hashtag_index:
        hashtag_index = hashtag_index["index"]
    archive_meta = load_archive_meta(archive_data_dir) if os.path.isdir(archive_data_dir) else {}

    # Calculate number of post sitemap files
    total_posts_for_sitemap = min(len(posts), MAX_POSTS_SITEMAP)
    post_sitemap_count = max(1, math.ceil(total_posts_for_sitemap / SITEMAP_POSTS_PER_FILE))

    # Calculate number of product sitemap files
    product_sitemap_count = max(1, math.ceil(len(products) / PRODUCTS_SITEMAP_PER_FILE))

    # sitemap-index.xml
    _write_file(
        os.path.join(output_dir, "sitemap-index.xml"),
        generate_sitemap_index(post_sitemap_count, product_sitemap_count, has_archive=bool(archive_meta)),
    )

    # sitemap.xml (static pages)
    _write_file(
        os.path.join(output_dir, "sitemap.xml"),
        generate_static_sitemap(),
    )

    # sitemap-posts-N.xml
    for i in range(1, post_sitemap_count + 1):
        start = (i - 1) * SITEMAP_POSTS_PER_FILE
        end = start + SITEMAP_POSTS_PER_FILE
        batch = posts[start:end]
        _write_file(
            os.path.join(output_dir, f"sitemap-posts-{i}.xml"),
            generate_posts_sitemap(batch, i),
        )

    # sitemap-ru.xml and sitemap-en.xml
    _write_file(
        os.path.join(output_dir, "sitemap-ru.xml"),
        generate_language_sitemap(posts, "ru"),
    )
    _write_file(
        os.path.join(output_dir, "sitemap-en.xml"),
        generate_language_sitemap(posts, "en"),
    )

    # sitemap-news.xml
    _write_file(
        os.path.join(output_dir, "sitemap-news.xml"),
        generate_news_sitemap(posts),
    )

    # sitemap-amp.xml
    _write_file(
        os.path.join(output_dir, "sitemap-amp.xml"),
        generate_amp_sitemap(posts),
    )

    # sitemap-tags.xml
    _write_file(
        os.path.join(output_dir, "sitemap-tags.xml"),
        generate_tags_sitemap(hashtag_index),
    )

    # sitemap-products-N.xml
    for i in range(1, product_sitemap_count + 1):
        start = (i - 1) * PRODUCTS_SITEMAP_PER_FILE
        end = start + PRODUCTS_SITEMAP_PER_FILE
        batch = products[start:end]
        _write_file(
            os.path.join(output_dir, f"sitemap-products-{i}.xml"),
            generate_products_sitemap(batch, i),
        )

    # sitemap-archive.xml
    _write_file(
        os.path.join(output_dir, "sitemap-archive.xml"),
        generate_archive_sitemap(archive_meta, archive_data_dir),
    )

    logger.info("Generated all sitemap files")


# ===========================================================================
# RSS
# ===========================================================================

def generate_rss(data: dict, output_dir: str):
    """Generate RSS feeds for both languages.

    Args:
        data: The data dict from data_loader.
        output_dir: Root output directory.
    """
    posts = data.get("posts", [])
    articles = data.get("articles", [])

    # Russian RSS
    _write_file(
        os.path.join(output_dir, "rss.xml"),
        generate_rss_feed(posts, articles, "ru"),
    )

    # English RSS
    _write_file(
        os.path.join(output_dir, "en", "rss.xml"),
        generate_rss_feed(posts, articles, "en"),
    )

    logger.info("Generated RSS feeds for ru and en")


# ===========================================================================
# robots.txt
# ===========================================================================

def generate_robots_txt_file(output_dir: str):
    """Generate robots.txt file.

    Args:
        output_dir: Root output directory.
    """
    _write_file(
        os.path.join(output_dir, "robots.txt"),
        generate_robots_txt(),
    )
    logger.info("Generated robots.txt")


# ===========================================================================
# Manifests
# ===========================================================================

def generate_manifests(output_dir: str):
    """Generate manifest.json for both languages.

    Args:
        output_dir: Root output directory.
    """
    # Russian manifest
    _write_file(
        os.path.join(output_dir, "manifest.json"),
        generate_manifest_json("ru"),
    )

    # English manifest
    _write_file(
        os.path.join(output_dir, "en", "manifest.json"),
        generate_manifest_json("en"),
    )

    logger.info("Generated manifest.json for ru and en")


# ===========================================================================
# Internal helpers
# ===========================================================================

def _get_current_year() -> int:
    """Return the current year."""
    return datetime.now(timezone.utc).year


def _format_date_display(date_str: str, lang: str = "ru") -> str:
    """Format a date string for display.

    Args:
        date_str: Date string in any common format.
        lang: Language code.

    Returns:
        Formatted date string.
    """
    if not date_str:
        return ""
    try:
        for fmt in (
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ):
            try:
                dt = datetime.strptime(str(date_str).strip(), fmt)
                if lang == "ru":
                    months = ["января", "февраля", "марта", "апреля", "мая", "июня",
                              "июля", "августа", "сентября", "октября", "ноября", "декабря"]
                    return f"{dt.day} {months[dt.month - 1]} {dt.year} г. в {dt.strftime('%H:%M')}"
                else:
                    return dt.strftime("%B %d, %Y, %I:%M %p")
            except (ValueError, TypeError):
                continue
    except Exception:
        pass
    return str(date_str)


# ===========================================================================
# Search Index (compact, for client-side search)
# ===========================================================================

def generate_search_index(data: dict, output_dir: str):
    """Generate compact search-index.json for client-side search.

    Creates an inverted index (token -> list of post IDs) limited to the
    top 2000 most frequent tokens with at most 20 post IDs per token.
    Also includes a title lookup table for displaying search results.

    The output file is placed at output/search-index.json so it can be
    loaded by the client-side JavaScript search in get_common_client_scripts().

    Args:
        data: The data dict from data_loader.
        output_dir: Root output directory.
    """
    import json as _json

    search_index_data = data.get("search_index", [])
    if not search_index_data or not isinstance(search_index_data, list):
        # Try loading from cache file
        cache_path = os.path.join("data", "search-index.json")
        if os.path.isfile(cache_path):
            try:
                with open(cache_path, "r", encoding="utf-8") as fh:
                    search_index_data = _json.load(fh)
            except (json.JSONDecodeError, OSError):
                pass

    if not search_index_data or not isinstance(search_index_data, list):
        logger.warning("No search index data available — skipping search-index.json generation")
        return

    # Count token frequencies
    token_counts: dict[str, int] = {}
    for item in search_index_data:
        if not isinstance(item, dict):
            continue
        for t in item.get("tokens", []):
            t = t.lower()
            if len(t) >= 3:
                token_counts[t] = token_counts.get(t, 0) + 1

    # Keep top 2000 tokens
    top_tokens = sorted(token_counts.items(), key=lambda x: -x[1])[:2000]
    top_token_set = set(t for t, _ in top_tokens)

    # Build inverted index: token -> list of post IDs
    inverted: dict[str, list] = {}
    for item in search_index_data:
        if not isinstance(item, dict):
            continue
        pid = item.get("id")
        if pid is None:
            continue
        for t in item.get("tokens", []):
            t = t.lower()
            if t in top_token_set:
                if t not in inverted:
                    inverted[t] = []
                inverted[t].append(pid)

    # Deduplicate and limit IDs per token
    for t in inverted:
        inverted[t] = list(set(inverted[t]))[:20]

    # Title lookup for search results: post_id -> title (truncated)
    titles: dict[str, str] = {}
    for item in search_index_data:
        if not isinstance(item, dict):
            continue
        pid = item.get("id")
        if pid is not None:
            titles[str(pid)] = (item.get("title", "") or "")[:50]

    compact = {"i": inverted, "t": titles}
    out_path = os.path.join(output_dir, "search-index.json")
    _write_file(out_path, _json.dumps(compact, ensure_ascii=True))

    size_kb = os.path.getsize(out_path) / 1024
    logger.info("Generated compact search-index.json (%d tokens, %d titles, %.0f KB)",
                len(inverted), len(titles), size_kb)
