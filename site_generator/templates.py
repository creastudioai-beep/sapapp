"""
HTML template functions for the SochiAutoParts static site generator.

Generates the common parts of each page (header, hero, footer, post cards, etc.).
Must match the HTML output of the original Cloudflare Worker v27.0 for sochiautoparts.ru.

Imports from: config.py, i18n.py (using t()), seo.py, css.py
"""

import html as _html_module
import math
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import quote as url_quote

from .i18n import t
from .config import (
    SITE_URL,
    SITE_NAME_RU,
    SITE_NAME_EN,
    CHANNEL_USERNAME,
    POSTS_PER_PAGE,
    CURRENT_YEAR,
    PRODUCTS_CURRENCY_RU,
    PRODUCTS_CURRENCY_EN,
)


# =============================================================================
# Constants (matching Worker v27.0)
# =============================================================================

LOGO_EXTERNAL_URL: str = "https://raw.githubusercontent.com/creastudioai-beep/sap/main/main/assets/logo.jpg"
TELEGRAM_URL: str = "https://t.me/sochiautoparts"
INSTAGRAM_URL: str = "https://www.instagram.com/sochi_auto_parts/"
SITE_AUTHOR: str = "SOCHIAUTOPARTS"
SHOP_PATH: str = "/shop"
SHOP_PATH_EN: str = "/en/shop"
CONTACTS_PATH: str = "/contacts"
PRIVACY_PATH: str = "/privacy"

# SVG icons matching the Worker
TELEGRAM_SVG: str = '<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1.03-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69a.2.2 0 00-.05-.18c-.06-.05-.14-.03-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.36.74-.55 2.92-1.27 4.86-2.11 5.83-2.51 2.78-1.16 3.35-1.36 3.73-1.36.08 0 .27.02.39.12.1.08.13.19.14.27-.01.06.01.24 0 .38z"/></svg>'

SUN_ICON: str = '\u2600\ufe0f'
MOON_ICON: str = '\ud83c\udf19'

SEARCH_ICON: str = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>'

# FAB Telegram SVG (circle with arrow)
FAB_TELEGRAM_SVG: str = '<svg width="26" height="26" viewBox="0 0 24 24" fill="white"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1.03-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69a.2.2 0 00-.05-.18c-.06-.05-.14-.03-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.36.74-.55 2.92-1.27 4.86-2.11 5.83-2.51 2.78-1.16 3.35-1.36 3.73-1.36.08 0 .27.02.39.12.1.08.13.19.14.27-.01.06.01.24 0 .38z"/></svg>'

# Admitad category names (matching Worker ADMITAD_CONFIG.CATEGORY_NAMES)
ADMITAD_CATEGORY_NAMES: dict[str, dict[str, str]] = {
    "ru": {
        "PARTS": "\u0410\u0432\u0442\u043e\u0437\u0430\u043f\u0447\u0430\u0441\u0442\u0438",
        "INSURANCE": "\u0410\u0432\u0442\u043e\u0441\u0442\u0440\u0430\u0445\u043e\u0432\u0430\u043d\u0438\u0435",
        "TIRES": "\u0428\u0438\u043d\u044b \u0438 \u0434\u0438\u0441\u043a\u0438",
        "CHECK": "\u041f\u0440\u043e\u0432\u0435\u0440\u043a\u0430 \u0430\u0432\u0442\u043e",
        "RENTAL": "\u041f\u0440\u043e\u043a\u0430\u0442 \u0430\u0432\u0442\u043e",
        "TOOLS": "\u0418\u043d\u0441\u0442\u0440\u0443\u043c\u0435\u043d\u0442\u044b",
        "COUPONS": "\u041a\u0443\u043f\u043e\u043d\u044b \u0438 \u0441\u043a\u0438\u0434\u043a\u0438",
        "OTHER": "\u0414\u0440\u0443\u0433\u043e\u0435",
    },
    "en": {
        "PARTS": "Auto Parts",
        "INSURANCE": "Car Insurance",
        "TIRES": "Tires & Wheels",
        "CHECK": "Car Check",
        "RENTAL": "Car Rental",
        "TOOLS": "Tools",
        "COUPONS": "Coupons & Deals",
        "OTHER": "Other",
    },
}

# Admitad category mapping (jsonCategory -> internal key)
ADMITAD_CATEGORY_MAPPING: dict[str, str] = {
    "autoparts": "PARTS",
    "autoinsurance": "INSURANCE",
    "tires": "TIRES",
    "checkauto": "CHECK",
    "autorent": "RENTAL",
    "tools": "TOOLS",
    "coupons": "COUPONS",
    "other": "OTHER",
}


# =============================================================================
# Escape helpers
# =============================================================================

def escape_html(text: str) -> str:
    """Escape HTML special characters. Matches Worker's escapeHTML."""
    if not isinstance(text, str):
        return ""
    return _html_module.escape(str(text), quote=True)


# =============================================================================
# Helper: current year
# =============================================================================

def _get_current_year() -> int:
    """Return the current year."""
    return datetime.now(timezone.utc).year


# =============================================================================
# Helper: get poster/thumbnail for a post
# =============================================================================

def _get_poster_for_post(post: dict) -> str:
    """Extract the first image URL from a post for thumbnails."""
    media = post.get("media", [])
    if isinstance(media, list) and len(media) > 0:
        first = media[0]
        if isinstance(first, dict):
            if first.get("type") == "photo":
                url = first.get("directUrl") or first.get("url") or first.get("src") or ""
                if url:
                    return url
            if first.get("type") == "video":
                poster = first.get("poster") or first.get("thumbnailUrl") or ""
                if poster:
                    return poster
                url = first.get("directUrl") or first.get("url") or ""
                if url:
                    return url
        elif isinstance(first, str) and _looks_like_image_url(first):
            return first

    # Fallback: check various single-image fields
    for field in ("image", "thumbnail", "photo", "media_url", "og_image", "preview"):
        val = post.get(field)
        if val and isinstance(val, str) and _looks_like_image_url(val):
            return val

    return LOGO_EXTERNAL_URL


def _looks_like_image_url(url: str) -> bool:
    """Check if a URL looks like it points to an image."""
    if not url or not isinstance(url, str):
        return False
    lower = url.lower().split("?")[0]
    return any(lower.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".avif"))


# =============================================================================
# Helper: format post text without hashtags
# =============================================================================

def _format_post_text_no_tags(text: str, lang: str = "ru") -> str:
    """Format post text for card preview: escape HTML, convert hashtags to links, preserve newlines."""
    if not text:
        return ""
    safe = escape_html(str(text))

    def _hashtag_link(match: re.Match) -> str:
        hashtag = match.group(0)
        tag_name = match.group(1)
        escaped_hashtag = escape_html(hashtag)
        escaped_tag = escape_html(tag_name)
        prefix = "/en/" if lang == "en" else "/"
        return f'<a href="{prefix}tag/{url_quote(escaped_tag)}" class="hashtag">{escaped_hashtag}</a>'

    safe = re.sub(r"#([a-zA-Zа-яА-ЯёЁ0-9_]+)", _hashtag_link, safe)
    safe = safe.replace("\n", "<br>\n")
    return safe


# =============================================================================
# Helper: format date
# =============================================================================

def _format_date(date_str: str, lang: str = "ru") -> str:
    """Format a date string for display."""
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
                    return dt.strftime("%d %B %Y, %H:%M")
                else:
                    return dt.strftime("%B %d, %Y, %I:%M %p")
            except (ValueError, TypeError):
                continue
    except Exception:
        pass
    return str(date_str)


def _format_date_short(date_str: str, lang: str = "ru") -> str:
    """Format a date string for short display (archive cards)."""
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
                    months = ["янв", "фев", "мар", "апр", "мая", "июн",
                              "июл", "авг", "сен", "окт", "ноя", "дек"]
                    return f"{dt.day} {months[dt.month - 1]} {dt.year}"
                else:
                    return dt.strftime("%b %d, %Y")
            except (ValueError, TypeError):
                continue
    except Exception:
        pass
    return str(date_str)


# =============================================================================
# Helper: build language-aware URL
# =============================================================================

def _lang_path(lang: str) -> str:
    """Return the language prefix path segment."""
    return "/en" if lang == "en" else ""


def _lang_base(lang: str) -> str:
    """Return the base URL for the given language."""
    if lang == "en":
        return f"{SITE_URL}/en/"
    return f"{SITE_URL}/"


# =============================================================================
# render_header
# =============================================================================

def render_header(lang: str = "ru", active_page: str = "") -> str:
    """Render site header with navigation.

    Must match the worker's renderHeader() output exactly.
    Includes:
    - Logo with image + fallback text
    - Navigation links
    - Active page highlighting
    - Language switcher (RU/EN buttons)
    - Theme toggle (light/dark)
    - Mobile menu button (hamburger)
    - Preconnect to Google Fonts and GTM
    """
    base_path = _lang_base(lang)
    active_home = " active" if active_page == "home" else ""
    active_articles = " active" if active_page == "articles" else ""
    active_shop = " active" if active_page == "shop" else ""
    active_contacts = " active" if active_page == "contacts" else ""
    active_archive = " active" if active_page == "archive" else ""

    logo_href = _lang_base(lang)
    shop_url = f"{SITE_URL}{SHOP_PATH_EN if lang == 'en' else SHOP_PATH}"
    contacts_url = f"{SITE_URL}{_lang_path(lang)}{CONTACTS_PATH}"
    menu_label = t('nav_home', lang) if lang == 'ru' else 'Menu'

    return f"""<header class="site-header">
<div class="container">
<div class="header-content">
<a href="{logo_href}" class="logo">
<img src="/logo.jpg" alt="SOCHIAUTOPARTS Logo" class="logo-icon" width="44" height="44" loading="eager" fetchpriority="high" referrerpolicy="no-referrer" onerror="this.classList.add('error');">
<span class="logo-fallback">🚗</span>
SOCHIAUTOPARTS
</a>
<nav class="main-nav" id="mainNav">
<a href="{base_path}" class="{active_home}">{t('nav_home', lang)}</a>
<a href="{base_path}articles" class="{active_articles}">{t('nav_articles', lang)}</a>
<a href="{base_path}archive" class="{active_archive}">📁 {'Архив' if lang == 'ru' else 'Archive'}</a>
<a href="{shop_url}" class="{active_shop}">🛒 {t('nav_shop', lang)}</a>
<a href="{contacts_url}" class="{active_contacts}">{t('nav_contacts', lang)}</a>
</nav>
<div class="controls-group">
<button class="mobile-menu-btn" id="mobileMenuBtn" aria-label="{menu_label}">☰</button>
<nav class="lang-switcher">
<a href="{SITE_URL}/" class="lang-btn {'active' if lang == 'ru' else ''}">RU</a>
<a href="{SITE_URL}/en/" class="lang-btn {'active' if lang == 'en' else ''}">EN</a>
</nav>
<div class="theme-toggle">
<button class="theme-btn" data-theme="light" aria-label="Light theme">{SUN_ICON}</button>
<button class="theme-btn" data-theme="dark" aria-label="Dark theme">{MOON_ICON}</button>
</div>
</div>
</div>
</div>
</header>"""


# =============================================================================
# render_hero
# =============================================================================

def render_hero(lang: str = "ru") -> str:
    """Render hero section with search.

    Includes gradient background, title, subtitle, search input with button.
    """
    hero_title = "SOCHIAUTOPARTS"
    if lang == "ru":
        hero_subtitle = "Ежедневные новости, тест-драйвы и обзоры мирового автопрома."
        btn_label = "Подписаться"
        search_placeholder = "Поиск"
    else:
        hero_subtitle = "Daily news, test drives and reviews of the global automotive industry."
        btn_label = "Subscribe"
        search_placeholder = "Search"

    return f"""<header class="hero">
<h1>{hero_title}</h1>
<p>{hero_subtitle}</p>
<div class="search-container">
<input type="search" class="search-input" id="searchInput" placeholder="{search_placeholder}" aria-label="{search_placeholder}" autocomplete="off" value="">
<button class="search-btn" id="searchBtn" aria-label="Search">{SEARCH_ICON}</button>
<div class="search-results" id="searchResults"></div>
</div>
<a href="https://t.me/{CHANNEL_USERNAME}" class="btn-cta" target="_blank" rel="nofollow noopener noreferrer">
{TELEGRAM_SVG}
{btn_label}
</a>
</header>"""


# =============================================================================
# render_seo_block
# =============================================================================

def render_seo_block(lang: str = "ru") -> str:
    """Render SEO text block below posts.

    Includes h2 title and descriptive paragraphs about the site.
    """
    if lang == "ru":
        title = "О канале SOCHIAUTOPARTS"
        p1 = "Мы ежедневно публикуем актуальные автомобильные новости, обзоры новых моделей и экспертные тест-драйвы. Наша цель — держать вас в курсе последних тенденций мирового автопрома."
        p2 = "Подписывайтесь на наш"
    else:
        title = "About SOCHIAUTOPARTS"
        p1 = "We daily publish the latest automotive news, reviews of new models and expert test drives. Our goal is to keep you updated with the latest global automotive trends."
        p2 = "Subscribe to our"

    return f"""
<section class="seo-block">
<h2>{title}</h2>
<p>{p1}</p>
<p>{p2} <a href="https://t.me/{CHANNEL_USERNAME}" target="_blank" rel="nofollow noopener noreferrer">Telegram-канал</a>!</p>
</section>"""


# =============================================================================
# render_popular_tags
# =============================================================================

def render_popular_tags(tags: list, lang: str = "ru") -> str:
    """Render popular tags section.

    Shows top 12 tags as clickable links.
    """
    if not tags or len(tags) == 0:
        return ""

    title = t('footer_popular_tags', lang)
    tags_html_parts = []
    for tag_item in tags[:12]:
        # tag_item can be a dict with 'tag' key, or a string
        if isinstance(tag_item, dict):
            tag_name = tag_item.get("tag") or tag_item.get("name") or tag_item.get("hashtag", "")
        elif isinstance(tag_item, str):
            tag_name = tag_item
        else:
            continue
        if not tag_name:
            continue
        tag_url = f"/tag/{url_quote(tag_name)}" if lang == "ru" else f"/en/tag/{url_quote(tag_name)}"
        tags_html_parts.append(f'<a href="{tag_url}" class="footer-tag">#{escape_html(tag_name)}</a>')

    tags_html = "".join(tags_html_parts)
    return f"""
<div class="footer-tags">
<div class="footer-tags-title">{title}</div>
<div class="footer-tags-list">{tags_html}</div>
</div>"""


# =============================================================================
# render_post_card
# =============================================================================

def render_post_card(post: dict, lang: str = "ru") -> str:
    """Render a single post card for the feed.

    Must match the worker's post card HTML exactly:
    - Photo/video media at top
    - Content section with meta (date, views), title, text preview
    - Hashtags as links
    - Action buttons (Read more, In Telegram)
    """
    post_id = post.get("id", 0)
    title = post.get("title", "")
    text = post.get("textWithHashtags") or post.get("text") or ""
    date_str = post.get("date", "")

    # Build media block
    media_block = ""
    media = post.get("media", [])
    if isinstance(media, list) and len(media) > 0:
        first_media = media[0]
        if isinstance(first_media, dict):
            if first_media.get("type") == "video":
                video_src = first_media.get("directUrl", "")
                poster = _get_poster_for_post(post)
                media_block = (
                    f'<div class="post-feed-media">\n'
                    f'<div class="video-container">\n'
                    f'<div class="video-thumbnail" data-video-src="{escape_html(video_src)}" '
                    f'data-video-title="{escape_html(title)}" data-video-type="video/mp4">\n'
                    f'<img src="{escape_html(poster)}" alt="{escape_html(title)}" '
                    f'loading="lazy" decoding="async" referrerpolicy="no-referrer">\n'
                    f'</div>\n'
                    f'</div>\n'
                    f'</div>'
                )
            else:
                img_src = first_media.get("directUrl") or first_media.get("url") or ""
                if img_src:
                    media_block = (
                        f'<div class="post-feed-media">\n'
                        f'<img src="{escape_html(img_src)}" alt="{escape_html(title)}" '
                        f'loading="lazy" decoding="async" '
                        f'style="width: 100%; height: auto; max-height: 600px; object-fit: contain;" '
                        f'referrerpolicy="no-referrer">\n'
                        f'</div>'
                    )

    # Build URLs
    post_url = post.get("postUrl") if lang == "ru" else post.get("postUrlEn", "")
    if not post_url:
        post_url = f"{SITE_URL}{_lang_path(lang)}/post/{post_id}"

    amp_url = post.get("ampUrl") if lang == "ru" else post.get("ampUrlEn", "")
    if not amp_url:
        amp_url = f"{SITE_URL}{_lang_path(lang)}/post/{post_id}/amp"

    btn_text = "Подробнее" if lang == "ru" else "More Details"
    date_display = _format_date(date_str, lang)

    return (
        f'\n'
        f'<article class="post-feed-item" data-post-id="{escape_html(str(post_id))}">\n'
        f'{media_block}\n'
        f'<div class="post-feed-content">\n'
        f'<div class="post-feed-meta">\n'
        f'<span>📅 {escape_html(date_display)}</span>\n'
        f'<a href="{amp_url}" class="amp-badge">AMP</a>\n'
        f'</div>\n'
        f'<h3 class="post-feed-title">\n'
        f'<a href="{post_url}">{escape_html(title)}</a>\n'
        f'</h3>\n'
        f'<div class="post-feed-text">{_format_post_text_no_tags(text, lang)}</div>\n'
        f'<div class="post-feed-actions">\n'
        f'<a href="{post_url}" class="btn-outline">{btn_text}</a>\n'
        f'</div>\n'
        f'</div>\n'
        f'</article>'
    )


# =============================================================================
# render_archive_post_card
# =============================================================================

def render_archive_post_card(post: dict, lang: str = "ru") -> str:
    """Render a single archive post card for the grid.

    - Photo thumbnail or video thumbnail with play overlay
    - Text preview (3 lines clamped)
    - Meta: date and views
    - Link to /archive/post/{id}
    """
    is_ru = lang == "ru"
    date_str = post.get("dateISO") or post.get("date", "")
    date_display = _format_date_short(date_str, lang)

    # Truncate text
    raw_text = post.get("text", "")
    if raw_text and len(raw_text) > 300:
        trunc_text = raw_text[:300] + "\u2026"
    else:
        trunc_text = raw_text or ("Публикация без текста" if is_ru else "Post without text")

    # Media
    has_video = bool(post.get("videoUrls") and len(post.get("videoUrls", [])) > 0)
    has_video_thumb = bool(post.get("videoThumbnails") and len(post.get("videoThumbnails", [])) > 0)
    photo_urls = post.get("photoUrls", [])
    video_thumbnails = post.get("videoThumbnails", [])
    first_img = photo_urls[0] if photo_urls else (video_thumbnails[0] if has_video_thumb else None)

    media_html = ""
    if has_video and has_video_thumb:
        media_html = (
            f'<div class="archive-video-card" style="background-image:url(\'{escape_html(video_thumbnails[0])}\');'
            f'background-size:cover;background-position:center">'
            f'<div class="archive-video-play-btn"></div></div>'
        )
    elif has_video:
        media_html = (
            '<div class="archive-video-card" style="background:#000">'
            '<div class="archive-video-play-btn"></div></div>'
        )
    elif first_img:
        media_html = (
            f'<img class="archive-card-image" src="{escape_html(first_img)}" alt="" '
            f'referrerpolicy="no-referrer" loading="lazy" />'
        )
    else:
        media_html = '<div class="archive-card-noimg">📋</div>'

    archive_base = "/en/archive/post/" if lang == "en" else "/archive/post/"
    post_id = post.get("postId") or post.get("id", "")
    views = post.get("views", "")

    return (
        f'<a href="{archive_base}{url_quote(str(post_id))}" class="archive-card">'
        f'{media_html}'
        f'<div class="archive-card-body">'
        f'<div class="archive-card-text">{escape_html(trunc_text)}</div>'
        f'<div class="archive-card-meta">'
        f'{f"<span>📅 {escape_html(date_display)}</span>" if date_display else ""}'
        f'{f"<span>🎬 {escape_html("Видео" if is_ru else "Video")}</span>" if has_video else ""}'
        f'{f"<span>👁 {escape_html(str(views))}</span>" if views else ""}'
        f'</div>'
        f'</div>'
        f'</a>'
    )


# =============================================================================
# render_post_gallery
# =============================================================================

def render_post_gallery(post: dict, lang: str = "ru") -> str:
    """Render post media gallery for single post page.

    Shows all photos and videos from the post.
    """
    media = post.get("media", [])
    if not media or not isinstance(media, list) or len(media) == 0:
        return ""

    post_id = post.get("id", 0)
    gallery_html = f'<div class="post-gallery" data-post-id="{escape_html(str(post_id))}">\n'

    for i, item in enumerate(media):
        if not isinstance(item, dict):
            continue

        loading = "eager" if i == 0 else "lazy"
        fetch_priority = "high" if i == 0 else "auto"
        media_type = item.get("type", "photo")
        direct_url = item.get("directUrl", "")

        if media_type == "video":
            poster = _get_poster_for_post(post)
            gallery_html += (
                f'<div class="gallery-item">\n'
                f'<video src="{escape_html(direct_url)}" poster="{escape_html(poster)}" '
                f'preload="metadata" controls playsinline referrerpolicy="no-referrer">\n'
                f'<source src="{escape_html(direct_url)}" type="video/mp4">\n'
                f'</video>\n'
                f'</div>\n'
            )
        elif media_type == "document":
            filename = item.get("filename", f"Файл {i + 1}" if lang == "ru" else f"File {i + 1}")
            gallery_html += (
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
            title = post.get("title", "")
            gallery_html += (
                f'<div class="gallery-item">\n'
                f'<img src="{escape_html(direct_url)}" alt="{escape_html(title)} {i + 1}" '
                f'loading="{loading}" fetchpriority="{fetch_priority}" referrerpolicy="no-referrer" />\n'
                f'</div>\n'
            )

    gallery_html += '</div>'
    return gallery_html


# =============================================================================
# render_related_posts
# =============================================================================

def render_related_posts(posts: list, lang: str = "ru") -> str:
    """Render related posts grid.

    Shows related post cards in a grid layout.
    """
    if not posts or len(posts) == 0:
        return ""

    section_title = "Похожие публикации" if lang == "ru" else "Related Posts"

    cards_html = ""
    for rp in posts:
        rp_url = rp.get("postUrl") if lang == "ru" else rp.get("postUrlEn", "")
        if not rp_url:
            rp_url = f"{SITE_URL}{_lang_path(lang)}/post/{rp.get('id', '')}"

        # Get poster image
        rp_media = rp.get("media", [])
        rp_poster = LOGO_EXTERNAL_URL
        if isinstance(rp_media, list) and len(rp_media) > 0:
            first = rp_media[0]
            if isinstance(first, dict):
                if first.get("type") == "photo":
                    rp_poster = first.get("directUrl") or LOGO_EXTERNAL_URL
                elif first.get("type") == "video":
                    rp_poster = _get_poster_for_post(rp)
        else:
            rp_poster = _get_poster_for_post(rp)

        rp_title = rp.get("title", "")
        rp_date = _format_date_short(rp.get("date", ""), lang)

        cards_html += (
            f'<a href="{rp_url}" class="related-card">\n'
            f'<div class="related-card-media">\n'
            f'<img src="{escape_html(rp_poster)}" alt="{escape_html(rp_title)}" '
            f'loading="lazy" decoding="async" referrerpolicy="no-referrer">\n'
            f'</div>\n'
            f'<div class="related-card-content">\n'
            f'<div class="related-card-title">{escape_html(rp_title)}</div>\n'
            f'<div class="related-card-date">📅 {escape_html(rp_date)}</div>\n'
            f'</div>\n'
            f'</a>'
        )

    return (
        f'\n'
        f'<div class="related-posts">\n'
        f'<h3>{section_title}</h3>\n'
        f'<div class="related-grid">\n'
        f'{cards_html}\n'
        f'</div>\n'
        f'</div>'
    )


# =============================================================================
# render_footer
# =============================================================================

def render_footer(tags: Optional[list] = None, lang: str = "ru") -> str:
    """Render site footer.

    Includes:
    - Copyright notice with current year
    - Footer links (Privacy, Contacts, RSS)
    - Popular tags section (if tags provided)
    - Telegram FAB button
    """
    current_year = _get_current_year()
    rights_text = "Все права защищены." if lang == "ru" else "All rights reserved."
    privacy_url = f"{SITE_URL}{_lang_path(lang)}{PRIVACY_PATH}"
    contacts_url = f"{SITE_URL}{_lang_path(lang)}{CONTACTS_PATH}"

    home_label = t('nav_home', lang)
    articles_label = t('nav_articles', lang)
    contacts_label = t('nav_contacts', lang)
    privacy_label = t('nav_privacy', lang)

    # Popular tags HTML
    popular_tags_html = ""
    if tags and len(tags) > 0:
        popular_tags_html = render_popular_tags(tags, lang)

    return f"""<footer>
<p>© {current_year} {SITE_AUTHOR}. {rights_text}</p>
<div class="footer-links">
<a href="{SITE_URL}">{home_label}</a> |
<a href="{SITE_URL}{_lang_path(lang)}/articles">{articles_label}</a> |
<a href="{contacts_url}">{contacts_label}</a> |
<a href="/rss.xml">RSS</a> |
<a href="/sitemap.xml">{"Карта сайта" if lang == "ru" else "Sitemap"}</a> |
<a href="/sitemap-tags.xml">Tags</a> |
<a href="/sitemap-amp.xml">AMP Sitemap</a> |
<a href="/api/stats">Stats</a> |
<a href="{privacy_url}">{privacy_label}</a> |
<a href="https://t.me/{CHANNEL_USERNAME}" target="_blank" rel="nofollow noopener noreferrer">Telegram</a>
</div>
{popular_tags_html}
</footer>"""


# =============================================================================
# render_numbered_pagination
# =============================================================================

def render_numbered_pagination(
    current_page: int,
    total_pages: int,
    base_url: str,
    lang: str = "ru",
) -> str:
    """Render numbered pagination (1,2,3... prev/next).

    Must match the worker's generateNumberedPagination() output.
    Smart page range display: show first, last, and pages around current.
    """
    if total_pages <= 1:
        counter_text = (
            f"Всего {current_page} публикаций" if lang == "ru"
            else f"Total {current_page} posts"
        )
        return f'<div class="posts-counter">{counter_text}</div>'

    aria_label = "Навигация по страницам" if lang == "ru" else "Page navigation"
    prev_label = "Предыдущая страница" if lang == "ru" else "Previous page"
    next_label = "Следующая страница" if lang == "ru" else "Next page"

    html = f'<nav class="pagination" aria-label="{aria_label}">\n'

    # Previous button
    if current_page > 1:
        prev_url = base_url if current_page == 2 else f"{base_url}?page={current_page - 1}"
        html += f'<a href="{prev_url}" aria-label="{prev_label}">&laquo;</a>\n'
    else:
        html += '<span class="disabled" aria-disabled="true">&laquo;</span>\n'

    # Determine page range to show
    max_visible_pages = 7
    if total_pages <= max_visible_pages:
        start_page = 1
        end_page = total_pages
    else:
        half = max_visible_pages // 2
        start_page = max(1, current_page - half)
        end_page = min(total_pages, current_page + half)
        if current_page - half < 1:
            end_page = min(total_pages, max_visible_pages)
        if current_page + half > total_pages:
            start_page = max(1, total_pages - max_visible_pages + 1)

    # First page + dots
    if start_page > 1:
        html += f'<a href="{base_url}">1</a>\n'
        if start_page > 2:
            html += '<span class="dots">...</span>\n'

    # Page numbers
    for i in range(start_page, end_page + 1):
        if i == current_page:
            html += f'<span class="active" aria-current="page">{i}</span>\n'
        else:
            page_url = base_url if i == 1 else f"{base_url}?page={i}"
            html += f'<a href="{page_url}">{i}</a>\n'

    # Last page + dots
    if end_page < total_pages:
        if end_page < total_pages - 1:
            html += '<span class="dots">...</span>\n'
        html += f'<a href="{base_url}?page={total_pages}">{total_pages}</a>\n'

    # Next button
    if current_page < total_pages:
        html += f'<a href="{base_url}?page={current_page + 1}" aria-label="{next_label}">&raquo;</a>\n'
    else:
        html += '<span class="disabled" aria-disabled="true">&raquo;</span>\n'

    html += '</nav>\n'

    # Counter below pagination
    shown_from = (current_page - 1) * POSTS_PER_PAGE + 1
    shown_to = min(current_page * POSTS_PER_PAGE, current_page * POSTS_PER_PAGE)  # approximate
    if lang == "ru":
        counter_text = f"{shown_from}&ndash;{shown_to} из {current_page * POSTS_PER_PAGE} публикаций"
    else:
        counter_text = f"{shown_from}&ndash;{shown_to} of {current_page * POSTS_PER_PAGE} posts"

    html += f'<div class="posts-counter">{counter_text}</div>'

    return html


# =============================================================================
# render_ad_blocks
# =============================================================================

def render_ad_blocks(programs: list, lang: str = "ru", max_blocks: int = 6) -> str:
    """Render Admitad ad blocks.

    Shows category buttons + ad cards with images, titles, descriptions, and affiliate links.
    URLs format: /api/{program_id} (simplified affiliate links)
    """
    if not programs or len(programs) == 0:
        return ""

    # Select up to max_blocks programs, one per category
    seen_categories = set()
    selected_ads = []
    for prog in programs:
        if not isinstance(prog, dict):
            continue
        cat = prog.get("jsonCategory") or "other"
        if cat not in seen_categories and len(selected_ads) < max_blocks:
            seen_categories.add(cat)
            selected_ads.append(prog)

    if len(selected_ads) == 0:
        return ""

    ads_html_parts = []
    for prog in selected_ads:
        # Get image URL
        raw_image_url = prog.get("image") or prog.get("logo") or LOGO_EXTERNAL_URL

        # Get category label
        json_category = prog.get("jsonCategory") or "other"
        internal_cat = ADMITAD_CATEGORY_MAPPING.get(json_category, "OTHER")
        category_label = ADMITAD_CATEGORY_NAMES.get(lang, ADMITAD_CATEGORY_NAMES["ru"]).get(
            internal_cat, json_category
        )

        # Get description
        description = prog.get("description") or prog.get("name", "")
        btn_text = "Перейти" if lang == "ru" else "Go"
        prog_name = prog.get("name", "")
        prog_id = prog.get("id", "")

        # Legal info
        legal_html = ""
        advertiser_info = prog.get("advertiser_legal_info")
        if isinstance(advertiser_info, dict) and advertiser_info.get("name"):
            ad_label = "Реклама" if lang == "ru" else "Ad"
            legal_html = f'<div class="ad-block-legal">{ad_label}: {escape_html(advertiser_info["name"])}</div>'

        desc_truncated = description[:150] + ("..." if len(description) > 150 else "")

        ads_html_parts.append(
            f"""
<a href="/api/{escape_html(str(prog_id))}" target="_blank" rel="nofollow noopener sponsored" style="text-decoration:none;color:inherit;display:block;">
<div class="ad-block-item">
  <div class="ad-block-media">
    <img src="{escape_html(raw_image_url)}"
         alt="{escape_html(prog_name)}"
         loading="lazy"
         referrerpolicy="no-referrer"
         onerror="this.onerror=null; this.style.display='none'; this.parentNode.innerHTML='<span style=\\'color:var(--text-muted);font-size:2rem;\\'>🛒</span>'">
  </div>
  <span class="ad-block-category">{escape_html(category_label)}</span>
  <h4 class="ad-block-title">{escape_html(prog_name)}</h4>
  <p class="ad-block-desc">{escape_html(desc_truncated)}</p>
  <div class="ad-block-btn">
    {btn_text}
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-left:4px;"><path d="M7 17L17 7M17 7H7M17 7V17"/></svg>
  </div>
  {legal_html}
</div>
</a>"""
        )

    ads_html = "".join(ads_html_parts)
    return f'<div class="ad-blocks-container">{ads_html}</div>'


# =============================================================================
# render_shop_widget
# =============================================================================

def render_shop_widget(products: list, lang: str = "ru", count: int = 6) -> str:
    """Render compact shop widget for post/archive pages.

    Shows a few products with images, names, prices, and "Visit Shop" link.
    Language-aware: /shop for ru, /en/shop for en.
    """
    shop_path = SHOP_PATH_EN if lang == "en" else SHOP_PATH
    widget_title = "🛒 Магазин автозапчастей" if lang == "ru" else "🛒 Auto Parts Shop"
    all_products_link = "Все товары →" if lang == "ru" else "All products →"
    visit_shop_link = "Перейти в магазин →" if lang == "ru" else "Visit shop →"
    currency = PRODUCTS_CURRENCY_RU if lang == "ru" else PRODUCTS_CURRENCY_EN

    # Build product cards
    product_cards_html = ""
    displayed = 0
    for product in products:
        if displayed >= count:
            break
        if not isinstance(product, dict):
            continue

        name = product.get("name", "")
        if len(name) > 50:
            name = name[:50] + "..."
        image = product.get("image", "")
        price = product.get("price", 0)
        url = product.get("url", "#")

        try:
            price_formatted = f"{int(price):,} {currency}"
        except (ValueError, TypeError):
            price_formatted = f"{price} {currency}"

        product_cards_html += (
            f'<a href="{escape_html(url)}" class="widget-product" target="_blank" rel="nofollow noopener sponsored">'
            f'<img src="{escape_html(image)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.style.display=\'none\'">'
            f'<div class="wp-name">{escape_html(name)}</div>'
            f'<div class="wp-price">{price_formatted}</div>'
            f'</a>'
        )
        displayed += 1

    return (
        f'<div class="shop-widget" id="shopWidget">\n'
        f'<div class="widget-header">'
        f'<span class="widget-title">{widget_title}</span>'
        f'<a href="{shop_path}" class="widget-link">{all_products_link}</a>'
        f'</div>\n'
        f'<div class="widget-grid" id="shopWidgetGrid">{product_cards_html}</div>\n'
        f'</div>\n'
    )


# =============================================================================
# render_breadcrumbs
# =============================================================================

def render_breadcrumbs(items: list, lang: str = "ru") -> str:
    """Render breadcrumb navigation.

    items = [{'name': 'Главная', 'url': '/'}, {'name': 'Статьи', 'url': '/articles'}]
    Last item has no link.
    """
    if not items or len(items) == 0:
        return ""

    html = '<nav class="breadcrumbs">\n'
    for i, item in enumerate(items):
        name = item.get("name", "")
        url = item.get("url", "")
        is_last = i == len(items) - 1

        if is_last:
            html += f'<span>{escape_html(name)}</span>\n'
        else:
            html += f'<a href="{escape_html(url)}">{escape_html(name)}</a>\n'
            html += '<span>›</span>\n'

    html += '</nav>\n'
    return html


# =============================================================================
# render_matrix_bg
# =============================================================================

def render_matrix_bg() -> str:
    """Render matrix-bg canvas element for visual effect."""
    return '<canvas id="matrix-bg"></canvas>'


# =============================================================================
# render_fab
# =============================================================================

def render_fab(lang: str = "ru") -> str:
    """Render floating action button (Telegram link)."""
    return (
        f'<a href="https://t.me/{CHANNEL_USERNAME}" class="fab" target="_blank" '
        f'rel="nofollow noopener noreferrer" aria-label="Telegram">\n'
        f'{FAB_TELEGRAM_SVG}\n'
        f'</a>'
    )
