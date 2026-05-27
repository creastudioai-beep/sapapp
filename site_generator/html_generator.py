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
    generate_scripts_js,
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
    render_product_page,
    render_regional_ads_script,
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
# NOTE: Archive pages are now generated as real static HTML using pipeline data.
# The Cloudflare Worker proxies these and adds region-based affiliate filtering.


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

# GitHub Pages size limits require constraining the number of generated files.
MAX_TAG_PAGES: int = 500  # Only generate tag pages for the top tags (size constraint)
MAX_POST_PAGES: int = 100000  # Generate individual post pages for all posts (up to 100K)
GENERATE_AMP: bool = False  # Skip AMP pages to reduce output size
GENERATE_AMP_HOMEPAGE: bool = False  # Skip AMP homepage


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
    """Return the language prefix path segment (with BASE_PATH).

    Since i18n is now handled client-side via JavaScript, all pages are generated
    only in Russian. The lang parameter is kept for API compatibility but always
    returns the root path.
    """
    return BASE_PATH


def _lang_base(lang: str) -> str:
    """Return the base URL for the given language (relative paths, with BASE_PATH).

    Since i18n is now handled client-side via JavaScript, all pages are generated
    only in Russian. The lang parameter is kept for API compatibility but always
    returns the root path.
    """
    return BASE_PATH + "/"


def _canonical_lang_path(lang: str) -> str:
    """Return language path WITHOUT BASE_PATH for canonical/OG URLs (production domain).

    Since all pages are now generated in Russian only, this always returns empty string.
    """
    return ""


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
    html_lang = "ru"

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

    # CSS — now loaded from external /style.css instead of inline
    css_content = css_override  # only used if override is provided

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
<link rel="stylesheet" href="/style.css" />
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
<script src="/i18n.js"></script>
</body>
</html>"""

    return page


# ===========================================================================
# Master function: generate_all_pages
# ===========================================================================

def generate_all_pages(data: dict, output_dir: str):
    """Master function: Generate ALL pages (Russian only, English via client-side i18n).

    Steps:
    1. Homepage with pagination
    2. All post pages + AMP versions
    3. Articles listing with pagination
    4. All article pages
    5. Archive pages - DISABLED
    5b. Individual product pages
    6. Shop page
    7. Tag pages
    8. Privacy page
    9. Contacts page
    10. Ad category pages
    11. 404 page
    12. AMP homepage
    13. All sitemaps, robots.txt, RSS, manifest

    Only Russian pages are generated. English translation is handled client-side
    via /i18n.js. CSS is loaded from external /style.css instead of inline.

    Args:
        data: The data dict returned by data_loader.load_data().
        output_dir: Root output directory for generated files.
    """
    os.makedirs(output_dir, exist_ok=True)

    # Generate /style.css as a separate file (instead of inlining in every HTML)
    from .css import CSS_STYLES as _CSS_STYLES
    _write_file(os.path.join(output_dir, "style.css"), _CSS_STYLES)
    logger.info("Generated /style.css (%d bytes)", len(_CSS_STYLES))

    # Generate /i18n.js for client-side language switching
    from .i18n_js import generate_i18n_js
    _i18n_js_content = generate_i18n_js()
    _write_file(os.path.join(output_dir, "i18n.js"), _i18n_js_content)
    logger.info("Generated /i18n.js (%d bytes)", len(_i18n_js_content))

    # Generate /scripts.js as a separate file (instead of inlining in every HTML)
    _scripts_js_content = generate_scripts_js()
    _write_file(os.path.join(output_dir, "scripts.js"), _scripts_js_content)
    logger.info("Generated /scripts.js (%d bytes)", len(_scripts_js_content))

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
    # 1. Homepage (ru + en) — with pagination as real HTML files
    # ------------------------------------------------------------------
    lang = "ru"  # Only generate Russian pages; English is handled client-side via i18n.js
    logger.info("Generating homepage (%s)", lang)
    # Page 1 (root index.html)
    html = generate_homepage(data, lang, output_dir, page=1)
    _write_file(os.path.join(output_dir, "index.html"), html)

    # Paginated pages: /page/2/index.html, /page/3/index.html, ...
    total_home_pages = max(1, math.ceil(len(posts) / POSTS_PER_PAGE))
    for page_num in range(2, total_home_pages + 1):
        html = generate_homepage(data, lang, output_dir, page=page_num)
        _write_file(os.path.join(output_dir, "page", str(page_num), "index.html"), html)

    logger.info("Generated %d homepage pages", total_home_pages)

    # ------------------------------------------------------------------
    # 2. All post pages (ru + en) — limited for GitHub Pages size
    # ------------------------------------------------------------------
    total_posts = len(posts)
    posts_to_generate = posts[:MAX_POST_PAGES]
    logger.info("Generating %d post pages (ru only) out of %d total", len(posts_to_generate), total_posts)
    for idx, post in enumerate(posts_to_generate):
        post_id = post.get("id")
        if post_id is None:
            continue
        lang = "ru"
        html = generate_post_page(data, post_id, lang, output_dir)
        _write_file(os.path.join(output_dir, "post", f"{post_id}.html"), html)

        # AMP version (optional — skipped by default for size)
        if GENERATE_AMP:
            amp_html = generate_amp_post_page(data, post_id, lang, output_dir)
            _write_file(os.path.join(output_dir, "post", str(post_id), "amp.html"), amp_html)

        if (idx + 1) % 100 == 0:
            logger.info("  Generated %d/%d posts", idx + 1, len(posts_to_generate))

    # ------------------------------------------------------------------
    # 3. Articles listing (ru + en) — with pagination
    # ------------------------------------------------------------------
    if FEATURE_ARTICLES_ENABLED:
        lang = "ru"
        logger.info("Generating articles listing (%s)", lang)
        # Page 1 (root index.html)
        html = generate_articles_page(data, lang, output_dir, page=1)
        _write_file(os.path.join(output_dir, "articles", "index.html"), html)

        # Paginated pages: /articles/page/2/index.html, etc.
        total_article_pages = max(1, math.ceil(len(articles) / ARTICLES_PER_PAGE))
        for page_num in range(2, total_article_pages + 1):
            html = generate_articles_page(data, lang, output_dir, page=page_num)
            _write_file(os.path.join(output_dir, "articles", "page", str(page_num), "index.html"), html)

        logger.info("Generated %d articles pages", total_article_pages)

    # ------------------------------------------------------------------
    # 4. All article pages (ru + en)
    # ------------------------------------------------------------------
    total_articles = len(articles)
    logger.info("Generating %d article pages (ru only)", total_articles)
    for idx, article in enumerate(articles):
        article_id = article.get("id")
        if article_id is None:
            continue
        lang = "ru"
        html = generate_article_page(data, article_id, lang, output_dir)
        _write_file(os.path.join(output_dir, "article", f"{article_id}.html"), html)
        if (idx + 1) % 50 == 0:
            logger.info("  Generated %d/%d articles", idx + 1, total_articles)

    # ------------------------------------------------------------------
    # 5. Archive pages — DISABLED (removed from site)
    # ------------------------------------------------------------------
    logger.info("Skipping archive pages generation (FEATURE_ARCHIVE_ENABLED=False)")

    # ------------------------------------------------------------------
    # 5b. Individual product pages (ru + en)
    # ------------------------------------------------------------------
    if FEATURE_SHOP_ENABLED and products:
        logger.info("Generating %d individual product pages (ru + en)", len(products))
        # Build category map for related products
        product_by_category: dict[str, list] = {}
        for p in products:
            if not isinstance(p, dict):
                continue
            cat = p.get("category", "uncategorized") or "uncategorized"
            cat_slug = str(cat).lower().strip().replace(" ", "-")
            if cat_slug not in product_by_category:
                product_by_category[cat_slug] = []
            product_by_category[cat_slug].append(p)

        import random as _random
        for idx, product in enumerate(products):
            if not isinstance(product, dict):
                continue
            product_id = product.get("id")
            if product_id is None:
                continue
            # Get related products (same category)
            cat = product.get("category", "uncategorized") or "uncategorized"
            cat_slug = str(cat).lower().strip().replace(" ", "-")
            same_category = product_by_category.get(cat_slug, [])
            related = [p for p in same_category if str(p.get("id", "")) != str(product_id)][:6]
            # Shop widget products are now loaded dynamically via JS, no need for static list
            lang = "ru"
            html = generate_product_page(data, product, lang, output_dir, related_products=related, shop_widget_products=[])
            _write_file(os.path.join(output_dir, "shop", str(product_id), "index.html"), html)
            if (idx + 1) % 500 == 0:
                logger.info("  Generated %d/%d product pages", idx + 1, len(products))

    # ------------------------------------------------------------------
    # 6. Shop page with iframe embed (ru + en)
    # ------------------------------------------------------------------
    if FEATURE_SHOP_ENABLED:
        lang = "ru"
        logger.info("Generating shop page (%s)", lang)
        html = generate_shop_page(data, lang, output_dir)
        _write_file(os.path.join(output_dir, "shop", "index.html"), html)

    # ------------------------------------------------------------------
    # 7. Tag pages (ru + en)
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
        # Use the tag name directly (Unicode) for filenames.
        # GitHub Pages decodes URL-encoded paths before looking up files,
        # so %D0%B0%D0%B2%D1%82%D0%BE.html on disk is NOT found when
        # the browser requests /tag/%D0%B0%D0%B2%D1%82%D0%BE.html
        # (GitHub Pages decodes it to /tag/авто.html and finds nothing).
        # Using the Unicode name directly solves this.
        safe_tag_name = tag_name.replace("/", "_").replace("\\", "_").replace(" ", "_")
        lang = "ru"
        html = generate_tag_page(data, tag_name, lang, output_dir)
        _write_file(os.path.join(output_dir, "tag", f"{safe_tag_name}.html"), html)

    # ------------------------------------------------------------------
    # 8. Privacy page (ru + en)
    # ------------------------------------------------------------------
    lang = "ru"
    html = generate_privacy_page(lang, output_dir)
    _write_file(os.path.join(output_dir, "privacy", "index.html"), html)

    # ------------------------------------------------------------------
    # 9. Contacts page (ru + en)
    # ------------------------------------------------------------------
    lang = "ru"
    html = generate_contacts_page(lang, output_dir)
    _write_file(os.path.join(output_dir, "contacts", "index.html"), html)

    # ------------------------------------------------------------------
    # 10. Ad category pages (ru + en) + /ads/index.html listing page
    # ------------------------------------------------------------------
    if FEATURE_ADMITAD_ENABLED:
        for category_key in ADMITAD_CONFIG:
            lang = "ru"
            html = generate_ad_category_page(data, category_key, lang, output_dir)
            _write_file(os.path.join(output_dir, "ads", f"{category_key}.html"), html)

        # Generate /ads/index.html — listing of all ad categories
        lang = "ru"
        html = generate_ads_index_page(data, lang, output_dir)
        _write_file(os.path.join(output_dir, "ads", "index.html"), html)

    # ------------------------------------------------------------------
    # 11. 404 page
    # ------------------------------------------------------------------
    html_404 = generate_404_page("ru", output_dir)
    _write_file(os.path.join(output_dir, "404.html"), html_404)

    # ------------------------------------------------------------------
    # 12. AMP homepage (ru + en) — optional, skipped for size
    # ------------------------------------------------------------------
    if GENERATE_AMP_HOMEPAGE:
        lang = "ru"
        html = generate_amp_homepage(data, lang, output_dir)
        _write_file(os.path.join(output_dir, "amp", "index.html"), html)
    else:
        logger.info("Skipping AMP homepage generation (GENERATE_AMP_HOMEPAGE=False)")

    # ------------------------------------------------------------------
    # 13. Sitemaps, robots.txt, RSS, manifest
    # ------------------------------------------------------------------
    generate_sitemaps(data, output_dir)
    generate_rss(data, output_dir)
    generate_robots_txt_file(output_dir)
    generate_manifests(output_dir)
    generate_search_index(data, output_dir)

    # ------------------------------------------------------------------
    # 14. Telegram archive data — DISABLED (removed from site)
    # ------------------------------------------------------------------
    logger.info("Skipping Telegram archive data deployment (archive feature disabled)")

    # ------------------------------------------------------------------
    # 15. Deploy products data to GitHub Pages (for Worker to fetch)
    # Files: data/products/{meta.json, page_1.json, page_2.json, ...}
    # ------------------------------------------------------------------
    products_data_src = os.path.join("data", "products")
    products_data_dest = os.path.join(output_dir, "data", "products")
    if os.path.isdir(products_data_src):
        logger.info("Deploying products data to GitHub Pages output…")
        os.makedirs(products_data_dest, exist_ok=True)
        _prod_files_copied = 0
        for fname in os.listdir(products_data_src):
            if fname.endswith(".json"):
                src_path = os.path.join(products_data_src, fname)
                dest_path = os.path.join(products_data_dest, fname)
                shutil.copy2(src_path, dest_path)
                _prod_files_copied += 1
        logger.info(
            "Copied %d products JSON files to output/data/products/",
            _prod_files_copied,
        )
    else:
        logger.warning(
            "No products data found at %s — Worker will not be able to "
            "serve shop products. Generating minimal products from pipeline data.",
            products_data_src,
        )
        # Generate from pipeline data if available
        if products:
            _gen_products = []
            for p in products[:200]:
                if isinstance(p, dict):
                    _gen_products.append({
                        'n': p.get('name', ''),
                        'p': p.get('price', 0),
                        'o': p.get('old_price', p.get('oldPrice', 0)),
                        'u': p.get('url', p.get('productUrl', '#')),
                        'i': p.get('image', p.get('imageUrl', '')),
                        'v': p.get('vendor', p.get('brand', '')),
                        'fn': p.get('feed_name', p.get('feedName', '')),
                        'fi': p.get('feed_icon', p.get('feedIcon', '')),
                        'cat': p.get('category_id', p.get('categoryId', '')),
                        'a': p.get('available', True),
                    })
            if _gen_products:
                os.makedirs(products_data_dest, exist_ok=True)
                with open(os.path.join(products_data_dest, 'page_1.json'), 'w', encoding='utf-8') as f:
                    json.dump(_gen_products, f, ensure_ascii=False, separators=(',', ':'))
                with open(os.path.join(products_data_dest, 'meta.json'), 'w', encoding='utf-8') as f:
                    json.dump({'total_products': len(_gen_products), 'pages_count': 1, 'per_page': 200}, f, ensure_ascii=False)
                logger.info("Generated minimal products data: %d products", len(_gen_products))

    logger.info("Site generation complete!")


# ===========================================================================
# Homepage
# ===========================================================================

def generate_homepage(data: dict, lang: str, output_dir: str, page: int = 1) -> str:
    """Generate homepage with posts feed, pagination, SEO, ads.

    Args:
        data: The data dict from data_loader.
        lang: Language code ('ru' or 'en').
        output_dir: Output directory (not used directly, for API compat).
        page: Page number (1-based) for paginated homepage.

    Returns:
        Complete HTML page string.
    """
    posts = data.get("posts", [])
    popular_tags = get_popular_tags(data, limit=12)
    admitad_programs = get_admitad_programs(data)

    # Paginate posts
    total_posts = len(posts)
    total_pages = max(1, math.ceil(total_posts / POSTS_PER_PAGE))
    start = (page - 1) * POSTS_PER_PAGE
    end = start + POSTS_PER_PAGE
    page_posts = posts[start:end]

    # SEO
    site_name = SITE_NAME_RU if lang == "ru" else SITE_NAME_EN
    site_desc = SITE_DESCRIPTION_RU if lang == "ru" else SITE_DESCRIPTION_EN
    if page == 1:
        page_url = f"{SITE_URL}{_canonical_lang_path(lang)}/"
    else:
        page_url = f"{SITE_URL}{_canonical_lang_path(lang)}/page/{page}/"
    if lang == "ru":
        title = "SOCHIAUTOPARTS - Мировые автоновости, обзоры и тест-драйвы" if page == 1 else f"Страница {page} — SOCHIAUTOPARTS"
    else:
        title = "SOCHIAUTOPARTS - Global Automotive News, Reviews & Test Drives" if page == 1 else f"Page {page} — SOCHIAUTOPARTS"

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

    # SEO block (only on first page)
    seo_block = render_seo_block(lang) if page == 1 else ""

    # Ad blocks
    ads_html = ""
    if admitad_programs:
        ads_html = render_ad_blocks(admitad_programs, lang)

    # Shop widget
    shop_widget = ""
    if FEATURE_SHOP_ENABLED and page == 1:
        products = data.get("products", [])[:20]
        shop_widget = render_shop_widget(products, lang, count=20)

    # Pagination
    pagination_html = render_numbered_pagination(page, total_pages, _lang_base(lang), lang)

    # Ad category buttons (matching original site)
    ad_category_buttons = render_ad_category_buttons(lang)

    # Hero only on page 1
    show_hero = page == 1

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

    canonical = page_url
    robots = "index, follow, max-image-preview:large" if page == 1 else "noindex, follow"

    return _build_page(
        lang=lang,
        title=title,
        description=site_desc,
        url=page_url,
        path="/" if lang == "ru" else "/en/",
        body_content=body,
        og_type="website",
        canonical=canonical,
        extra_schema=schemas,
        active_page="home",
        show_hero=show_hero,
        tags_for_footer=popular_tags,
        robots=robots,
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
        products = data.get("products", [])[:20]
        shop_widget = render_shop_widget(products, lang, count=20)

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

    # Back to home button (for main page post pages, NOT archive)
    home_label = "← Назад на главную" if lang == "ru" else "← Back to Home"
    home_url = _lang_base(lang)

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
<a href="{home_url}" class="btn-cta">🏠 {home_label}</a>
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
<p>&#169; {_get_current_year()} {SITE_AUTHOR}. {"Все права защищены." if lang == "ru" else "All rights reserved."}</p>
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

def generate_archive_page(data: dict, lang: str, output_dir: str, page: int = 1, archive_posts_override: list = None) -> str:
    """Generate archive listing page (50 posts per page) using archive data.

    Args:
        data: The data dict from data_loader.
        lang: Language code.
        output_dir: Output directory.
        page: Page number (1-based).
        archive_posts_override: Override list of archive posts (90K from Telegram).
            If None, falls back to data["archive_posts"] then data["posts"].

    Returns:
        Complete HTML page string.
    """
    from .config import ARCHIVE_POSTS_PER_PAGE, MAX_ARCHIVE_PAGES
    from .css import ARCHIVE_CSS

    # Use Telegram archive data (90K+) if available, else pipeline posts (10K)
    if archive_posts_override is not None:
        all_posts = archive_posts_override
    else:
        all_posts = data.get("archive_posts", []) or data.get("posts", [])
    total_posts = len(all_posts)
    total_pages = min(
        max(1, math.ceil(total_posts / ARCHIVE_POSTS_PER_PAGE)),
        MAX_ARCHIVE_PAGES,
    )

    # Paginate
    start = (page - 1) * ARCHIVE_POSTS_PER_PAGE
    end = start + ARCHIVE_POSTS_PER_PAGE
    page_posts = all_posts[start:end]

    # SEO
    is_ru = lang == "ru"
    page_title = "Архив публикаций" if is_ru else "Publications Archive"
    page_desc = (
        "Архив всех публикаций канала sochiautoparts в Telegram. Автоновости, обзоры, тест-драйвы и акции."
        if is_ru else
        "Archive of all sochiautoparts Telegram channel publications. Auto news, reviews, test drives and promos."
    )
    if page == 1:
        full_title = f"Архив публикаций — SOCHIAUTOPARTS" if is_ru else "Publications Archive — SOCHIAUTOPARTS"
    else:
        full_title = f"Архив публикаций — стр. {page} | SOCHIAUTOPARTS" if is_ru else f"Publications Archive — page {page} | SOCHIAUTOPARTS"

    if lang == "en":
        canonical_url = f"{SITE_URL}/en/archive" if page == 1 else f"{SITE_URL}/en/archive/page/{page}/"
        path = "/en/archive"
    else:
        canonical_url = f"{SITE_URL}/archive" if page == 1 else f"{SITE_URL}/archive/page/{page}/"
        path = "/archive"

    archive_base = f"{_lang_path(lang)}/archive"

    # Archive cards
    cards_html = ""
    for arch_post in page_posts:
        cards_html += render_archive_post_card(arch_post, lang)

    # Link to Telegram for more posts (if last page)
    telegram_link_html = ""
    if page == total_pages:
        tg_text = "Ещё больше публикаций в Telegram →" if is_ru else "More posts on Telegram →"
        telegram_link_html = (
            f'<div style="text-align:center;margin:2rem 0;">'
            f'<a href="https://t.me/s/sochiautoparts" target="_blank" rel="nofollow noopener noreferrer" '
            f'style="display:inline-flex;align-items:center;gap:8px;padding:12px 24px;border-radius:9999px;'
            f'background:var(--primary);color:white;font-weight:700;text-decoration:none;">'
            f'📁 {tg_text}</a></div>'
        )

    # Numbered pagination with real file paths
    pagination_html = render_numbered_pagination(page, total_pages, f"{archive_base}/", lang)

    # Counter
    counter_text = f"Всего {total_posts} публикаций в архиве" if is_ru else f"Total {total_posts} posts in archive"
    counter_html = f'<div class="posts-counter">{counter_text}</div>'

    # Breadcrumbs
    bc_items = [
        {"name": t("bc_home", lang), "url": _lang_base(lang)},
        {"name": t("bc_archive", lang), "url": archive_base},
    ]
    breadcrumbs = render_breadcrumbs(bc_items, lang)
    breadcrumb_schema = generate_breadcrumb_schema(bc_items)

    # Ad category buttons (matching other pages)
    ad_category_buttons = render_ad_category_buttons(lang)

    # Ads
    admitad_programs = get_admitad_programs(data)
    ads_html = ""
    if admitad_programs:
        ads_html = render_ad_blocks(admitad_programs, lang)

    body = f"""
<div class="container">
{breadcrumbs}
<h1 style="margin:1rem 0;">{page_title}</h1>
<p style="color:var(--text-muted);margin-bottom:1.5rem;">{page_desc}</p>
{counter_html}
<div class="archive-grid">
{cards_html}
</div>
{telegram_link_html}
{pagination_html}
{ads_html}
</div>"""

    return _build_page(
        lang=lang,
        title=full_title,
        description=page_desc,
        url=canonical_url,
        path=path,
        body_content=body,
        og_type="website",
        extra_schema=[breadcrumb_schema],
        active_page="archive",
        include_matrix=True,
        css_override=CSS_STYLES + ARCHIVE_CSS,
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

def generate_archive_post_page(data: dict, post_id: int, lang: str, output_dir: str) -> str:
    """Generate individual archive post page with gallery, related posts, ads, shop widget.

    Uses get_post_by_id() from data_loader to look up posts from pipeline data,
    then falls back to archive_post_map (90K+ Telegram posts).

    Args:
        data: The data dict from data_loader.
        post_id: The post ID.
        lang: Language code ('ru' or 'en').
        output_dir: Output directory.

    Returns:
        Complete HTML page string.
    """
    post = get_post_by_id(data, post_id)
    # Also check the archive_post_map (90K+ Telegram posts) if not found in pipeline
    if post is None:
        archive_post_map = data.get("archive_post_map", {})
        try:
            post = archive_post_map[int(post_id)]
        except (KeyError, ValueError, TypeError):
            pass
    if post is None:
        return generate_404_page(lang, output_dir)

    # SEO data (same as regular post pages)
    seo_posts = data.get("seo_posts", {})
    seo_data = seo_posts.get(str(post_id), seo_posts.get(post_id, {}))

    # Build URLs — canonical/OG use absolute (SITE_URL), content links use relative (with BASE_PATH)
    if lang == "en":
        canonical_url = f"{SITE_URL}/en/archive/post/{post_id}"
        post_url_rel = f"{_lang_path(lang)}/archive/post/{post_id}"
    else:
        canonical_url = f"{SITE_URL}/archive/post/{post_id}"
        post_url_rel = f"{_lang_path(lang)}/archive/post/{post_id}"

    # Title and description — use per-post SEO data when available
    title = post.get("title", "")
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

    # OG image — use actual post image, not generic logo
    og_image = seo_data.get("ogImage") or extract_first_image(post) or DEFAULT_THUMBNAIL

    # NewsArticle schema
    news_schema = generate_news_article_schema(post, {
        "ogUrl": canonical_url,
        "publishedTime": published_time,
        "modifiedTime": modified_time,
        "description": description,
    }, lang)

    # Breadcrumbs: Главная / Архив / {Post Title}
    bc_home = t("bc_home", lang)
    bc_archive = t("bc_archive", lang)
    bc_items = [
        {"name": bc_home, "url": _lang_base(lang)},
        {"name": bc_archive, "url": f"{_lang_path(lang)}/archive"},
        {"name": title[:50] if title else f"#{post_id}", "url": post_url_rel},
    ]
    breadcrumb_schema = generate_breadcrumb_schema(bc_items)
    breadcrumbs = render_breadcrumbs(bc_items, lang)

    # Media gallery — handle the media list with {type, directUrl, poster} structure
    media = post.get("media", [])
    gallery_html = ""
    if isinstance(media, list) and len(media) > 0:
        gallery_items = ""
        for i, item in enumerate(media):
            if not isinstance(item, dict):
                continue
            media_type = str(item.get("type", "photo")).lower()
            direct_url = item.get("directUrl") or item.get("url", "")
            loading = "eager" if i == 0 else "lazy"

            if media_type == "video":
                # For video posts, use poster if available, otherwise logo as fallback
                poster = item.get("poster") or item.get("thumbnailUrl", "")
                if not poster:
                    # Try to find a photo in the media list to use as poster
                    for m in media:
                        if isinstance(m, dict) and m.get("type") == "photo":
                            poster = m.get("directUrl") or m.get("url", "")
                            if poster:
                                break
                    # If still no poster, use the logo as fallback
                    if not poster:
                        poster = _bp("/logo.jpg")
                gallery_items += (
                    f'<div class="gallery-item">\n'
                    f'<video src="{escape_html(direct_url)}" poster="{escape_html(poster)}" '
                    f'preload="metadata" controls playsinline referrerpolicy="no-referrer">\n'
                    f'<source src="{escape_html(direct_url)}" type="video/mp4">\n'
                    f'</video>\n'
                    f'</div>\n'
                )
            elif media_type == "document":
                filename = item.get("filename", f"Файл {i + 1}" if lang == "ru" else f"File {i + 1}")
                gallery_items += (
                    f'<div class="gallery-item">\n'
                    f'<div style="padding:2rem;text-align:center;">\n'
                    f'<a href="{escape_html(direct_url)}" class="btn-primary" download>'
                    f'  📥  {escape_html(filename)}'
                    f'</a>\n'
                    f'</div>\n'
                    f'</div>\n'
                )
            else:
                # Photo
                fetch_priority = "high" if i == 0 else "auto"
                gallery_items += (
                    f'<div class="gallery-item">\n'
                    f'<img src="{escape_html(direct_url)}" alt="{escape_html(title)} {i + 1}" '
                    f'loading="{loading}" fetchpriority="{fetch_priority}" referrerpolicy="no-referrer" />\n'
                    f'</div>\n'
                )
        if gallery_items:
            gallery_html = f'<div class="post-gallery" data-post-id="{escape_html(str(post_id))}">\n{gallery_items}</div>'

    # Post text — formatted with hashtag links
    post_text = post.get("textWithHashtags") or post.get("text") or ""
    formatted_text = format_post_text(post_text, lang)

    # Date display
    date_str = post.get("date", "")
    date_display = _format_date_display(date_str, lang)

    # Views
    views = post.get("views", 0)
    views_html = f"<span>👁 {views}</span>" if views else ""

    # Hashtags
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

    # Related posts
    related = get_related_posts(data, post_id, limit=RELATED_POSTS_COUNT)
    related_html = render_related_posts(related, lang)

    # Ad blocks
    admitad_programs = get_admitad_programs(data)
    ads_html = ""
    if admitad_programs:
        ads_html = render_ad_blocks(admitad_programs, lang, max_blocks=4)

    # Shop widget (6 products)
    shop_widget = ""
    if FEATURE_SHOP_ENABLED:
        products = data.get("products", [])[:20]
        shop_widget = render_shop_widget(products, lang, count=20)

    # Body
    body = f"""
<div class="container">
<div class="article-content">
{breadcrumbs}
<article>
<div class="article-meta">
<span>📅 {escape_html(date_display)}</span>
{views_html}
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
        path=f"/archive/post/{post_id}" if lang == "ru" else f"/en/archive/post/{post_id}",
        body_content=body,
        og_type="article",
        image=og_image,
        canonical=canonical_url,
        article_published=published_time,
        article_modified=modified_time,
        article_tag=post_keywords,
        extra_schema=[news_schema, breadcrumb_schema],
        active_page="archive",
        include_matrix=False,
    )


# ===========================================================================
# Shop Page
# ===========================================================================

def generate_shop_page(data: dict, lang: str, output_dir: str) -> str:
    """Generate NATIVE shop page with product cards from pipeline data.

    The shop page displays products natively from the pipeline products.json,
    with search, sort, supplier filters, and a product grid. No iframe.
    The proxy Worker provides /api/shop/products endpoint for dynamic filtering.

    Args:
        data: The data dict from data_loader.
        lang: Language code.
        output_dir: Output directory.

    Returns:
        Complete HTML page string.
    """
    popular_tags = get_popular_tags(data, limit=12)
    products = data.get("products", [])

    # SEO
    page_title = t("shop_title", lang)
    page_desc = t("shop_subtitle", lang)
    if lang == "ru":
        full_title = "Магазин автозапчастей | SOCHIAUTOPARTS"
    else:
        full_title = "Auto Parts Shop | SOCHIAUTOPARTS"

    if lang == "en":
        page_url = f"{SITE_URL}/en/shop"
        path = "/en/shop"
    else:
        page_url = f"{SITE_URL}/shop"
        path = "/shop"

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

    # Build unique supplier list from products
    suppliers = {}
    for p in products:
        feed_name = p.get("feedName") or p.get("feed_name") or ""
        if feed_name and feed_name not in suppliers:
            suppliers[feed_name] = len([x for x in products if (x.get("feedName") or x.get("feed_name") or "") == feed_name])

    # Supplier filter cards
    supplier_cards = ""
    for sname, scount in suppliers.items():
        supplier_cards += f'<button class="supplier-filter-btn" data-supplier="{escape_html(sname)}">{escape_html(sname)} <span style="opacity:0.7;font-size:0.8em;">({scount})</span></button>\n'

    # Build initial product grid (first PRODUCTS_PER_PAGE products)
    currency = PRODUCTS_CURRENCY_RU if lang == "ru" else PRODUCTS_CURRENCY_EN
    buy_text = t("shop_buy", lang)
    products_json_data = json.dumps(products[:30], ensure_ascii=True)  # Embed first 30 for initial display; API fetches the rest

    product_cards_html = ""
    for p in products[:30]:
        if not isinstance(p, dict):
            continue
        p_name = p.get("name", "")
        p_price = p.get("price", "")
        p_old_price = p.get("old_price", "")
        p_image = p.get("image", "")
        p_url = p.get("url", "#")
        p_feed = p.get("feedName") or p.get("feed_name", "")
        p_available = p.get("available", True)

        price_display = f'{p_price:,.0f} {currency}' if isinstance(p_price, (int, float)) else f'{p_price} {currency}' if p_price else ""
        old_price_display = f'{p_old_price:,.0f}' if isinstance(p_old_price, (int, float)) and p_old_price else ""

        available_badge = ""
        if not p_available:
            available_badge = '<span class="product-badge badge-unavailable">Под заказ</span>' if lang == "ru" else '<span class="product-badge badge-unavailable">On order</span>'
        elif p_old_price:
            available_badge = '<span class="product-badge badge-sale">Скидка</span>' if lang == "ru" else '<span class="product-badge badge-sale">Sale</span>'

        feed_badge = f'<span class="product-badge badge-supplier">{escape_html(p_feed)}</span>' if p_feed else ""

        product_cards_html += (
            f'<div class="shop-product-card" data-supplier="{escape_html(p_feed)}" data-price="{p_price if isinstance(p_price, (int, float)) else 0}" data-name="{escape_html(p_name.lower())}">'
            f'<a href="{escape_html(p_url)}" target="_blank" rel="nofollow noopener sponsored" style="text-decoration:none;color:inherit;">'
            f'<div class="product-card-image"><img src="{escape_html(p_image)}" alt="{escape_html(p_name[:80])}" loading="lazy" referrerpolicy="no-referrer" onerror="this.onerror=null;this.src=\'/logo.jpg\'"></div>'
            f'<div class="product-card-body">'
            f'<h3 class="product-card-name">{escape_html(p_name[:80])}</h3>'
            f'<div class="product-card-badges">{available_badge}{feed_badge}</div>'
            f'<div class="product-card-price">{escape_html(price_display)}{f" <s>{escape_html(old_price_display)}</s>" if old_price_display else ""}</div>'
            f'<div class="product-card-btn">{buy_text}</div>'
            f'</div>'
            f'</a>'
            f'</div>\n'
        )

    # Search, sort, filter controls
    search_placeholder = t("shop_search_placeholder", lang)
    sort_popular = t("shop_sort_popular", lang)
    sort_price_asc = t("shop_sort_price_asc", lang)
    sort_price_desc = t("shop_sort_price_desc", lang)
    sort_name = t("shop_sort_name", lang)
    empty_text = t("shop_empty", lang)
    empty_reset = t("shop_empty_reset", lang)
    total_products = len(products)

    # Ad blocks
    admitad_programs = get_admitad_programs(data)
    ads_html = ""
    if admitad_programs:
        ads_html = render_ad_blocks(admitad_programs, lang, max_blocks=5)

    # Ad category buttons
    ad_category_buttons = render_ad_category_buttons(lang)

    # SEO noscript
    seo_noscript = ""
    if lang == "ru":
        seo_noscript = (
            '<noscript>'
            '<h2>Магазин автозапчастей SOCHIAUTOPARTS</h2>'
            '<p>Большой выбор автозапчастей от проверенных поставщиков с доставкой по всей России. '
            'Каталог включает детали двигателя, трансмиссии, тормозной системы, подвески, '
            'электрооборудования, кузова и других категорий. Оригинальные и неоригинальные запчасти, '
            'аналоги от ведущих производителей.</p>'
            '</noscript>'
        )
    else:
        seo_noscript = (
            '<noscript>'
            '<h2>SOCHIAUTOPARTS Auto Parts Shop</h2>'
            '<p>Large selection of auto parts from verified suppliers with delivery across Russia. '
            'The catalog includes engine parts, transmission, brakes, suspension, '
            'electrical, body parts and other categories. OEM and aftermarket parts '
            'from leading manufacturers.</p>'
            '</noscript>'
        )

    # Client-side shop script with numbered pagination (30 products per page)
    loading_text = "Загрузка..." if lang == "ru" else "Loading..."
    showing_text = "Показано" if lang == "ru" else "Showing"
    of_text = "из" if lang == "ru" else "of"
    products_text = "товаров" if lang == "ru" else "products"
    prev_text = "Предыдущая" if lang == "ru" else "Previous"
    next_text = "Следующая" if lang == "ru" else "Next"
    shop_script = f"""
<script>
(function(){{
var initialProducts={products_json_data};
var totalProducts={total_products};
var grid=document.getElementById("shopProductGrid");
var searchInput=document.getElementById("shopSearchInput");
var sortSelect=document.getElementById("shopSortSelect");
var emptyEl=document.getElementById("shopEmpty");
var pageInfoEl=document.getElementById("shopPageInfo");
var paginationEl=document.getElementById("shopPagination");
var currency="{currency}";
var buyText="{buy_text}";
var PER_PAGE=30;
var currentPage=1;
var totalPages=Math.ceil(totalProducts/PER_PAGE)||1;
var isLoading=false;

function renderCard(p){{
  var n=(p.name||"").length>80?(p.name||"").substring(0,80)+"...":(p.name||"");
  var price=p.price;
  var oldPrice=p.old_price||"";
  var pd=typeof price==="number"?price.toLocaleString("ru-RU")+" "+currency:price+" "+currency;
  var od=typeof oldPrice==="number"?oldPrice.toLocaleString("ru-RU"):oldPrice;
  var avail=p.available!==false;
  var feed=p.feedName||p.feed_name||"";
  var badge="";
  if(!avail)badge='<span class="product-badge badge-unavailable">{"Под заказ" if lang=="ru" else "On order"}</span>';
  else if(oldPrice)badge='<span class="product-badge badge-sale">{"Скидка" if lang=="ru" else "Sale"}</span>';
  var feedBadge=feed?'<span class="product-badge badge-supplier">'+feed+'</span>':'';
  return '<div class="shop-product-card" data-supplier="'+feed+'">'+
    '<a href="'+(p.url||"#")+'" target="_blank" rel="nofollow noopener sponsored" style="text-decoration:none;color:inherit;">'+
    '<div class="product-card-image"><img src="'+(p.image||"/logo.jpg")+'" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.onerror=null;this.src=\\'/logo.jpg\\'"></div>'+
    '<div class="product-card-body">'+
    '<h3 class="product-card-name">'+n+'</h3>'+
    '<div class="product-card-badges">'+badge+feedBadge+'</div>'+
    '<div class="product-card-price">'+pd+(od?' <s>'+od+'</s>':'')+'</div>'+
    '<div class="product-card-btn">'+buyText+'</div>'+
    '</div></a></div>';
}}

function updatePageInfo(count){{
  if(!pageInfoEl)return;
  if(count===0){{
    pageInfoEl.textContent="";
    return;
  }}
  var start=(currentPage-1)*PER_PAGE+1;
  var end=Math.min(currentPage*PER_PAGE,totalProducts);
  pageInfoEl.textContent="{showing_text} "+start+"-"+end+" {of_text} "+totalProducts.toLocaleString("ru-RU")+" {products_text}";
}}

function renderPagination(){{
  if(!paginationEl)return;
  if(totalPages<=1){{paginationEl.innerHTML="";return;}}
  var h="";
  // Previous
  if(currentPage>1){{
    h+='<a href="#" data-page="'+(currentPage-1)+'" aria-label="{prev_text}">&laquo;</a>';
  }}else{{
    h+='<span class="disabled" aria-disabled="true">&laquo;</span>';
  }}
  // Page numbers with smart range
  var maxVisible=7;
  var startPage,endPage;
  if(totalPages<=maxVisible){{
    startPage=1;endPage=totalPages;
  }}else{{
    var half=Math.floor(maxVisible/2);
    startPage=Math.max(1,currentPage-half);
    endPage=Math.min(totalPages,currentPage+half);
    if(currentPage-half<1)endPage=Math.min(totalPages,maxVisible);
    if(currentPage+half>totalPages)startPage=Math.max(1,totalPages-maxVisible+1);
  }}
  if(startPage>1){{
    h+='<a href="#" data-page="1">1</a>';
    if(startPage>2)h+='<span class="dots">...</span>';
  }}
  for(var i=startPage;i<=endPage;i++){{
    if(i===currentPage){{
      h+='<span class="active" aria-current="page">'+i+'</span>';
    }}else{{
      h+='<a href="#" data-page="'+i+'">'+i+'</a>';
    }}
  }}
  if(endPage<totalPages){{
    if(endPage<totalPages-1)h+='<span class="dots">...</span>';
    h+='<a href="#" data-page="'+totalPages+'">'+totalPages+'</a>';
  }}
  // Next
  if(currentPage<totalPages){{
    h+='<a href="#" data-page="'+(currentPage+1)+'" aria-label="{next_text}">&raquo;</a>';
  }}else{{
    h+='<span class="disabled" aria-disabled="true">&raquo;</span>';
  }}
  paginationEl.innerHTML=h;
  // Bind click events
  paginationEl.querySelectorAll("a[data-page]").forEach(function(a){{
    a.addEventListener("click",function(e){{
      e.preventDefault();
      var p=parseInt(this.dataset.page,10);
      if(p>=1&&p<=totalPages&&p!==currentPage)goToPage(p);
    }});
  }});
}}

function renderProducts(products){{
  if(!grid)return;
  if(!products||products.length===0){{
    grid.innerHTML="";
    if(emptyEl)emptyEl.style.display="block";
    if(paginationEl)paginationEl.innerHTML="";
    updatePageInfo(0);
    return;
  }}
  if(emptyEl)emptyEl.style.display="none";
  var h="";
  for(var i=0;i<products.length;i++){{
    h+=renderCard(products[i]);
  }}
  grid.innerHTML=h;
  updatePageInfo(products.length);
  renderPagination();
}}

function goToPage(page){{
  if(isLoading||page<1||page>totalPages)return;
  currentPage=page;
  isLoading=true;
  if(grid)grid.style.opacity="0.5";
  // Build API URL with current filters
  var q=(searchInput?searchInput.value:"").toLowerCase();
  var sort=sortSelect?sortSelect.value:"popular";
  var activeSupplier=document.querySelector(".supplier-filter-btn.active");
  var supplier=activeSupplier?activeSupplier.dataset.supplier:"";
  var url="/api/shop/products?page="+page+"&per_page="+PER_PAGE;
  if(q&&q.length>=2)url+="&q="+encodeURIComponent(q);
  if(supplier)url+="&feed="+encodeURIComponent(supplier);
  if(sort&&sort!=="popular")url+="&sort="+sort;
  // If page 1 and no filters, use embedded data
  if(page===1&&!q&&!supplier&&sort==="popular"){{
    isLoading=false;
    if(grid)grid.style.opacity="1";
    renderProducts(initialProducts);
    return;
  }}
  fetch(url).then(function(r){{return r.json();}}).then(function(data){{
    isLoading=false;
    if(grid)grid.style.opacity="1";
    if(data.total)totalProducts=data.total;
    if(data.total_pages)totalPages=data.total_pages;
    else totalPages=Math.ceil(totalProducts/PER_PAGE)||1;
    renderProducts(data.products||[]);
    // Scroll to top of product grid
    var rect=grid.getBoundingClientRect();
    if(rect.top<0||rect.top>window.innerHeight){{
      grid.scrollIntoView({{behavior:"smooth",block:"start"}});
    }}
  }}).catch(function(){{
    isLoading=false;
    if(grid)grid.style.opacity="1";
    renderProducts([]);
  }});
}}

function filterAndSort(){{
  goToPage(1);
}}

var searchTimer=null;
if(searchInput)searchInput.addEventListener("input",function(){{
  clearTimeout(searchTimer);
  searchTimer=setTimeout(function(){{filterAndSort();}},300);
}});
if(sortSelect)sortSelect.addEventListener("change",function(){{filterAndSort();}});
document.querySelectorAll(".supplier-filter-btn").forEach(function(btn){{
  btn.addEventListener("click",function(){{
    document.querySelectorAll(".supplier-filter-btn").forEach(function(b){{b.classList.remove("active");}});
    this.classList.toggle("active");
    filterAndSort();
  }});
}});
document.getElementById("shopResetFilters")?.addEventListener("click",function(){{
  if(searchInput)searchInput.value="";
  if(sortSelect)sortSelect.value="popular";
  document.querySelectorAll(".supplier-filter-btn").forEach(function(b){{b.classList.remove("active");}});
  filterAndSort();
}});
// Initial render with embedded page 1 data
renderProducts(initialProducts);
}})();
</script>"""

    body = f"""
<div class="shop-hero">
<h1>{page_title}</h1>
<p>{page_desc}</p>
</div>
<div class="shop-page-container">
{breadcrumbs}
{ad_category_buttons}
<div class="shop-controls">
  <input type="search" id="shopSearchInput" class="shop-search-input" placeholder="{search_placeholder}" autocomplete="off">
  <select id="shopSortSelect" class="shop-sort-select">
    <option value="popular">{sort_popular}</option>
    <option value="price_asc">{sort_price_asc}</option>
    <option value="price_desc">{sort_price_desc}</option>
    <option value="name">{sort_name}</option>
  </select>
</div>
<div class="shop-suppliers">
  {supplier_cards}
</div>
<div class="shop-product-count" id="shopPageInfo">{showing_text} 1-{min(total_products, 30)} {of_text} {total_products:,} {products_text}</div>
<div class="shop-product-grid" id="shopProductGrid">
  {product_cards_html}
</div>
<nav id="shopPagination" class="shop-pagination" aria-label="{"Навигация по страницам" if lang=="ru" else "Page navigation"}"></nav>
<div id="shopEmpty" style="display:none;text-align:center;padding:3rem 1rem;">
  <p style="color:var(--text-muted);margin-bottom:1rem;">{empty_text}</p>
  <button id="shopResetFilters" class="btn-outline">{empty_reset}</button>
</div>
{seo_noscript}
{ads_html}
<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:1rem;margin:2rem 0;">
<div style="text-align:center;padding:1.5rem;background:var(--bg-card);border-radius:12px;border:1px solid var(--border-light);">🚚 {feature_delivery}</div>
<div style="text-align:center;padding:1.5rem;background:var(--bg-card);border-radius:12px;border:1px solid var(--border-light);">✅ {feature_verified}</div>
<div style="text-align:center;padding:1.5rem;background:var(--bg-card);border-radius:12px;border:1px solid var(--border-light);">💰 {feature_prices}</div>
<div style="text-align:center;padding:1.5rem;background:var(--bg-card);border-radius:12px;border:1px solid var(--border-light);">🛡️ {feature_guarantee}</div>
</div>
</div>
{shop_script}"""

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

def generate_product_page(data: dict, product, lang: str, output_dir: str,
                         related_products: list = None, shop_widget_products: list = None) -> str:
    """Generate product detail page with Schema.org Product markup.

    Generates individual product pages at /shop/{product_id}/index.html
    with full description, price, affiliate link, Schema.org Product markup,
    related products, shop widget, breadcrumbs, and regional ad blocks.

    Args:
        data: The data dict from data_loader.
        product: The product dict (already expanded keys).
        lang: Language code.
        output_dir: Output directory.
        related_products: List of related product dicts (same category).
        shop_widget_products: List of product dicts for the shop widget.

    Returns:
        Complete HTML page string.
    """
    if isinstance(product, str):
        # Legacy call with product_id string
        product_map = data.get("product_map", {})
        product = product_map.get(str(product))
        if product is None:
            return generate_404_page(lang, output_dir)

    product_id = product.get("id", "")
    product_map = data.get("product_map", {})

    # URLs — using /shop/{product_id} pattern
    if lang == "en":
        product_url = f"{SITE_URL}/en/shop/{product_id}"
    else:
        product_url = f"{SITE_URL}/shop/{product_id}"

    name = product.get("name", "")
    description = (product.get("description") or name)[:300]
    price = product.get("price", 0)
    currency = product.get("currency", "RUB")
    available = product.get("available", False)
    image = product.get("image", "")

    # Title
    page_title = f"{name} | SOCHIAUTOPARTS"

    # Schema.org Product
    product_schema = generate_product_schema(product, lang)

    # Breadcrumb schema (using new /shop/{id} pattern)
    bc_items = [
        {"name": t("bc_home", lang), "url": f"{SITE_URL}{_canonical_lang_path(lang)}/"},
        {"name": t("bc_shop", lang), "url": f"{SITE_URL}{_canonical_lang_path(lang)}/shop"},
        {"name": name[:50], "url": product_url},
    ]
    breadcrumb_schema = generate_breadcrumb_schema(bc_items)

    # Render product page body using the templates function
    body = render_product_page(
        product=product,
        lang=lang,
        related_products=related_products,
        shop_widget_products=shop_widget_products,
    )

    # Regional ads script
    regional_ads_script = render_regional_ads_script()

    return _build_page(
        lang=lang,
        title=page_title,
        description=description,
        url=product_url,
        path=f"/shop/{product_id}" if lang == "ru" else f"/en/shop/{product_id}",
        body_content=body,
        og_type="product",
        image=image or None,
        canonical=product_url,
        product_price=str(price),
        product_currency=currency,
        extra_schema=[product_schema, breadcrumb_schema],
        extra_head=regional_ads_script,
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

        product_url = f"{_lang_path(lang)}/shop/{pid}"

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

    # URL-encode the tag for canonical URLs and paths (needed for Arabic/Unicode tags)
    encoded_tag = url_quote(tag)
    if lang == "en":
        page_url = f"{SITE_URL}/en/tag/{encoded_tag}"
        path = f"/en/tag/{encoded_tag}"
    else:
        page_url = f"{SITE_URL}/tag/{encoded_tag}"
        path = f"/tag/{encoded_tag}"

    page_url_rel = f"{_lang_path(lang)}/tag/{encoded_tag}"

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
        prog_cat = prog.get("jsonCategory") or prog.get("category") or ""
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
        legal_text = "Реклама"
    else:
        desc_text = f"Partner program {cat_name}. Follow the link for special offers and discounts on auto parts."
        visit_text = "Visit partner website"
        legal_text = "Advertisement"

    # Programs cards HTML
    programs_cards_html = ""
    for prog in matching_programs:
        prog_name = prog.get("name", "")
        prog_desc = prog.get("description", "")
        prog_image = prog.get("image") or prog.get("logo", "")
        prog_id = prog.get("id", "")

        # Use /api/{prog_id} format for Worker-based affiliate redirect
        # The proxy Worker looks up the program ID and redirects to goto_link
        if prog_id:
            prog_url = f"/api/{prog_id}"
        else:
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

    # Main CTA button — use /api/{id} for first matching program, or category URL
    main_cta_url = cat_url
    if matching_programs:
        first_prog_id = matching_programs[0].get("id", "")
        if first_prog_id:
            main_cta_url = f"/api/{first_prog_id}"

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
<a href="{main_cta_url}" class="btn-cta" target="_blank" rel="nofollow noopener sponsored">{visit_text}</a>
</div>
{programs_section}
<p style="font-size:0.75rem;color:var(--text-light);text-align:center;">{legal_text}</p>
</div>
</div>
<script>
(function(){{
  // Region-aware partner program filtering
  // Each program card has data-regions attribute; hide programs not available in user's region
  var userCountry = null;
  // Try to get country from Cloudflare headers (set by Worker as CF-IPCountry response header)
  // Since we can't read response headers from JS, we use the /api/ads endpoint to get region-filtered programs
  fetch('/api/ads?lang={"ru" if lang == "ru" else "en"}&max=20&cat={category}')
    .then(function(r) {{ return r.text(); }})
    .then(function(html) {{
      if (!html) return;
      var container = document.querySelector('.ad-blocks-container');
      if (container) {{
        // Replace the static programs with region-filtered ones
        var temp = document.createElement('div');
        temp.innerHTML = html;
        var filteredItems = temp.querySelectorAll('.ad-block-item');
        if (filteredItems.length > 0) {{
          // Check which of our static programs are in the filtered set
          var filteredLinks = new Set();
          filteredItems.forEach(function(item) {{
            var link = item.querySelector('a[href*="/api/"]');
            if (link) filteredLinks.add(link.getAttribute('href'));
          }});
          // Hide programs not in filtered set
          var staticItems = container.querySelectorAll('.ad-block-item');
          var hiddenCount = 0;
          staticItems.forEach(function(item) {{
            var link = item.querySelector('a[href*="/api/"]');
            if (link && !filteredLinks.has(link.getAttribute('href'))) {{
              item.style.display = 'none';
              hiddenCount++;
            }}
          }});
          // If all programs hidden, show region message
          if (hiddenCount >= staticItems.length) {{
            var msg = document.createElement('p');
            msg.style.cssText = 'text-align:center;color:var(--text-muted);padding:2rem;';
            msg.textContent = '{"В вашем регионе нет доступных предложений" if lang == "ru" else "No offers available in your region"}';
            container.parentNode.appendChild(msg);
          }}
        }}
      }}
    }})
    .catch(function() {{}});  // Silently fail — static content still visible
}})();
</script>"""

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
# Ads Index Page (/ads/index.html)
# ===========================================================================

def generate_ads_index_page(data: dict, lang: str, output_dir: str) -> str:
    """Generate /ads/index.html — listing of all ad categories.

    Args:
        data: The data dict from data_loader.
        lang: Language code.
        output_dir: Output directory.

    Returns:
        Complete HTML page string.
    """
    is_ru = lang == "ru"
    page_title = "Партнёрские программы" if is_ru else "Partner Programs"
    page_desc = (
        "Партнёрские программы и специальные предложения от SOCHIAUTOPARTS. Автозапчасти, страхование, шины, проверка авто и многое другое."
        if is_ru else
        "Partner programs and special offers from SOCHIAUTOPARTS. Auto parts, insurance, tires, car check and more."
    )
    full_title = f"{page_title} | SOCHIAUTOPARTS"

    if lang == "en":
        page_url = f"{SITE_URL}/en/ads/"
        path = "/en/ads/"
    else:
        page_url = f"{SITE_URL}/ads/"
        path = "/ads/"

    # Get all programs from pipeline data
    admitad_programs = get_admitad_programs(data)

    # Build category cards
    category_cards = ""
    for cat_key, cat_data in ADMITAD_CONFIG.items():
        cat_name = cat_data.get(lang, cat_data.get("ru", cat_key))
        cat_icon = cat_data.get("icon", "")
        cat_url_path = f"{_lang_path(lang)}/ads/{cat_key}"

        # Count matching programs
        matching = [p for p in admitad_programs if isinstance(p, dict) and (p.get("jsonCategory") or p.get("category")) == cat_key]
        count_text = f"{len(matching)} {'программ' if is_ru else 'programs'}" if matching else ""

        # Get first program's affiliate URL for the main button
        main_url = cat_url_path
        if matching:
            first_prog_id = matching[0].get("id", "")
            if first_prog_id:
                main_url = f"/api/{first_prog_id}"

        category_cards += f"""
<div class="ad-block-item" style="cursor:default;">
<div style="padding:1.5rem;text-align:center;">
<div style="font-size:2.5rem;margin-bottom:0.75rem;">{cat_icon}</div>
<h4 class="ad-block-title">{escape_html(cat_name)}</h4>
{f'<p class="ad-block-desc">{escape_html(count_text)}</p>' if count_text else ''}
<div style="display:flex;gap:0.5rem;justify-content:center;margin-top:1rem;">
<a href="{main_url}" class="btn-cta" target="_blank" rel="nofollow noopener sponsored" style="font-size:0.85rem;padding:8px 20px;">
{"Перейти" if is_ru else "Visit"}
</a>
<a href="{cat_url_path}" class="btn-outline" style="font-size:0.85rem;padding:8px 20px;">
{"Все" if is_ru else "All"}
</a>
</div>
</div>
</div>"""

    # Breadcrumbs
    bc_items = [
        {"name": t("bc_home", lang), "url": _lang_base(lang)},
        {"name": page_title, "url": f"{_lang_path(lang)}/ads/"},
    ]
    breadcrumbs = render_breadcrumbs(bc_items, lang)

    body = f"""
<div class="container">
{breadcrumbs}
<h1 style="margin:1rem 0;">{page_title}</h1>
<p style="color:var(--text-muted);margin-bottom:1.5rem;">{page_desc}</p>
<div class="ad-blocks-container">
{category_cards}
</div>
</div>"""

    return _build_page(
        lang=lang,
        title=full_title,
        description=page_desc[:200],
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
<p>&#169; {current_year} {SITE_AUTHOR}. {"Все права защищены." if lang == "ru" else "All rights reserved."}</p>
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

def generate_sitemaps(data: dict, output_dir: str):
    """Generate all sitemap XML files.

    Args:
        data: The data dict from data_loader.
        output_dir: Root output directory.
    """
    posts = data.get("posts", [])
    products = data.get("products", [])
    # hashtag_index is now unwrapped by data_loader.load_data() automatically
    hashtag_index = data.get("hashtag_index", {})
    # Safety: still check for nested structure in case data was loaded differently
    if isinstance(hashtag_index, dict) and "index" in hashtag_index:
        hashtag_index = hashtag_index["index"]

    # Calculate number of post sitemap files
    total_posts_for_sitemap = min(len(posts), MAX_POSTS_SITEMAP)
    post_sitemap_count = max(1, math.ceil(total_posts_for_sitemap / SITEMAP_POSTS_PER_FILE))

    # Calculate number of product sitemap files
    product_sitemap_count = max(1, math.ceil(len(products) / PRODUCTS_SITEMAP_PER_FILE))

    # sitemap-index.xml
    has_archive = bool(posts)
    _write_file(
        os.path.join(output_dir, "sitemap-index.xml"),
        generate_sitemap_index(post_sitemap_count, product_sitemap_count, has_archive=has_archive),
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

    # sitemap-ru.xml (English sitemap no longer generated - i18n is client-side)
    _write_file(
        os.path.join(output_dir, "sitemap-ru.xml"),
        generate_language_sitemap(posts, "ru"),
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

    # sitemap-archive.xml — listing pages + individual archive post URLs
    _write_file(
        os.path.join(output_dir, "sitemap-archive.xml"),
        generate_archive_sitemap(posts),
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

    # English RSS is no longer generated separately (i18n is client-side)
    logger.info("Generated RSS feed for ru")


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

    # English manifest is no longer generated separately (i18n is client-side)
    logger.info("Generated manifest.json for ru")


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
