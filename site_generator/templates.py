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
    ADMITAD_CONFIG,
    BASE_PATH,
)


# =============================================================================
# Constants (matching Worker v27.0)
# =============================================================================

LOGO_EXTERNAL_URL: str = "/logo.jpg"
TELEGRAM_URL: str = "https://t.me/sochiautoparts"
INSTAGRAM_URL: str = "https://www.instagram.com/sochi_auto_parts/"
SITE_AUTHOR: str = "SOCHIAUTOPARTS"
SHOP_PATH: str = "/shop"
CONTACTS_PATH: str = "/contacts"
PRIVACY_PATH: str = "/privacy"


def _bp(path: str) -> str:
    """Prefix a path with BASE_PATH."""
    if path.startswith("/"):
        return BASE_PATH + path
    return BASE_PATH + "/" + path

# SVG icons matching the Worker
TELEGRAM_SVG: str = '<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1.03-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69a.2.2 0 00-.05-.18c-.06-.05-.14-.03-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.36.74-.55 2.92-1.27 4.86-2.11 5.83-2.51 2.78-1.16 3.35-1.36 3.73-1.36.08 0 .27.02.39.12.1.08.13.19.14.27-.01.06.01.24 0 .38z"/></svg>'

SUN_ICON: str = '\u2600\ufe0f'
MOON_ICON: str = '\U0001f319'

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
    """Extract the first image URL from a post for thumbnails.

    For video posts: only returns a poster/thumbnail URL if it's an actual
    image (.jpg/.png/.webp etc.). Never returns .mp4 URLs as they can't be
    used in <img> tags. Falls back to LOGO_EXTERNAL_URL for videos without
    real thumbnails.
    """
    media = post.get("media", [])
    if isinstance(media, list) and len(media) > 0:
        first = media[0]
        if isinstance(first, dict):
            if first.get("type") == "photo":
                url = first.get("directUrl") or first.get("url") or first.get("src") or ""
                if url and _looks_like_image_url(url):
                    return url
                elif url:
                    return url  # photo URLs are generally safe even without image extension
            if first.get("type") == "video":
                # Only accept actual image URLs as poster, NOT .mp4 files
                poster = first.get("poster") or first.get("thumbnailUrl") or ""
                if poster and _looks_like_image_url(poster):
                    return poster
                elif poster and not poster.lower().split("?")[0].endswith(".mp4"):
                    return poster
                # No real thumbnail available — return logo fallback
                return LOGO_EXTERNAL_URL
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
    """Format post text for card preview: escape HTML, STRIP hashtags, linkify URLs, preserve newlines.

    Matches the old Worker's formatPostTextNoTags() — hashtags are REMOVED
    from the feed preview. Tags are only shown inside individual post pages.
    Also supports Arabic hashtags (e.g. #أخبارالسيارات).
    """
    if not text:
        return ""
    safe = escape_html(str(text))

    # Strip hashtags (including Arabic, Cyrillic, Latin, digits, underscores)
    # Broad Unicode coverage: \w (letters/digits/_), Arabic basic + Supplement + Extended-A
    safe = re.sub(r"\s*#[\w\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]+", "", safe, flags=re.UNICODE)

    # Convert URLs to clickable links
    def _url_link(match: re.Match) -> str:
        url = match.group(0)
        escaped_url = escape_html(url)
        display = escaped_url
        if len(display) > 60:
            display = display[:57] + "..."
        return f'<a href="{escaped_url}" target="_blank" rel="nofollow ugc noopener">{display}</a>'

    safe = re.sub(r"https?://[^\s<>\"]+", _url_link, safe)

    # Convert @username to Telegram links
    safe = re.sub(
        r"@([a-zA-Z0-9_]{5,32})",
        r'<a href="https://t.me/\1" target="_blank" rel="nofollow ugc noopener">@\1</a>',
        safe,
    )

    # Preserve line breaks
    safe = safe.replace("\n", "<br>\n")

    # Clean up excessive whitespace
    safe = re.sub(r"(<br>\s*){2,}", "<br><br>", safe)
    safe = re.sub(r"\s{2,}", " ", safe)
    safe = safe.strip()

    return safe


# =============================================================================
# Helper: format date
# =============================================================================

def _format_date(date_str: str, lang: str = "ru") -> str:
    """Format a date string for display with proper Russian month names."""
    if not date_str:
        return ""
    _RU_MONTHS = [
        "января", "февраля", "марта", "апреля", "мая", "июня",
        "июля", "августа", "сентября", "октября", "ноября", "декабря",
    ]
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
                    month_name = _RU_MONTHS[dt.month - 1]
                    return f"{dt.day} {month_name} {dt.year} г. в {dt.hour:02d}:{dt.minute:02d}"
                else:
                    return dt.strftime("%B %d, %Y at %I:%M %p")
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

    logo_href = _lang_base(lang)
    shop_url = f"{_bp(SHOP_PATH)}"
    contacts_url = f"{_bp(CONTACTS_PATH)}"
    menu_label = "\u041c\u0435\u043d\u044e"

    return f"""<header class="site-header">
<div class="container">
<div class="header-content">
<a href="{logo_href}" class="logo">
<img src="{_bp('/logo.jpg')}" alt="SOCHIAUTOPARTS Logo" class="logo-icon" width="44" height="44" loading="eager" fetchpriority="high" referrerpolicy="no-referrer" onerror="this.classList.add('error')">
<span class="logo-fallback">🚗</span>
SOCHIAUTOPARTS
</a>
<nav class="main-nav" id="mainNav">
<a href="{_bp('/')}" class="{active_home}" data-i18n="nav_home">{t('nav_home', 'ru')}</a>
<a href="{_bp('/articles')}" class="{active_articles}" data-i18n="nav_articles">{t('nav_articles', 'ru')}</a>
<a href="{shop_url}" class="{active_shop}" data-i18n="nav_shop">🛒 {t('nav_shop', 'ru')}</a>
<a href="{contacts_url}" class="{active_contacts}" data-i18n="nav_contacts">{t('nav_contacts', 'ru')}</a>
</nav>
<div class="controls-group">
<button class="mobile-menu-btn" id="mobileMenuBtn" aria-label="{menu_label}" data-i18n-aria-label="menu_label">☰</button>
<nav class="lang-switcher">
<button class="lang-btn active" data-lang="ru" onclick="window.SAPI18n.setLang('ru')">RU</button>
<button class="lang-btn" data-lang="en" onclick="window.SAPI18n.setLang('en')">EN</button>
</nav>
<div class="theme-toggle">
<button class="theme-btn" data-theme="light" aria-label="Light theme">{SUN_ICON}</button>
<button class="theme-btn active" data-theme="dark" aria-label="Dark theme">{MOON_ICON}</button>
</div>
</div>
</div>
</div>
</header>"""


# =============================================================================
# render_hero
# =============================================================================

def render_hero(lang: str = "ru", total_posts: int = 0) -> str:
    """Render hero section with search.

    Includes gradient background, title, subtitle, search input with button.
    The total_posts count is injected into the subtitle text dynamically.
    """
    hero_title = "SOCHIAUTOPARTS"
    posts_display = f"{total_posts:,}".replace(",", " ") if total_posts else ""
    if posts_display:
        hero_subtitle = f"Ежедневные новости, тест-драйвы и обзоры мирового автопрома. В архиве {posts_display} публикаций"
    else:
        hero_subtitle = "Ежедневные новости, тест-драйвы и обзоры мирового автопрома"
    btn_label = "Подписаться"
    search_placeholder = "Поиск"

    return f"""<header class="hero">
<h1>{hero_title}</h1>
<p data-i18n="hero_subtitle">{hero_subtitle}</p>
<div class="search-container">
<input type="search" class="search-input" id="searchInput" placeholder="{search_placeholder}" data-i18n-placeholder="search_placeholder" aria-label="{search_placeholder}" data-i18n-aria-label="search_placeholder" autocomplete="off" value="">
<button class="search-btn" id="searchBtn" aria-label="Search">{SEARCH_ICON}</button>
<div class="search-results" id="searchResults"></div>
</div>
<a href="https://t.me/{CHANNEL_USERNAME}" class="btn-cta" target="_blank" rel="nofollow noopener noreferrer">
{TELEGRAM_SVG}
<span data-i18n="hero_cta">{btn_label}</span>
</a>
</header>"""


# =============================================================================
# render_seo_block
# =============================================================================

def render_seo_block(lang: str = "ru", total_posts: int = 0) -> str:
    """Render SEO text block below posts.

    Includes h2 title and descriptive paragraphs about the site.
    The total_posts count is injected into the SEO text dynamically.
    """
    title = "О канале SOCHIAUTOPARTS"
    posts_display = f"{total_posts:,}".replace(",", " ") if total_posts else ""
    if posts_display:
        p1 = f"Мы ежедневно публикуем актуальные автомобильные новости, обзоры новых моделей и экспертные тест-драйвы. Наша цель — держать вас в курсе последних тенденций мирового автопрома. 📊 В архиве: <b>{posts_display}</b> публикаций"
    else:
        p1 = "Мы ежедневно публикуем актуальные автомобильные новости, обзоры новых моделей и экспертные тест-драйвы. Наша цель — держать вас в курсе последних тенденций мирового автопрома."
    p2 = "Подписывайтесь на наш"

    return f"""
<section class="seo-block">
<h2 data-i18n="seo_block_title">{title}</h2>
<p data-i18n="seo_block_text">{p1}</p>
<p data-i18n="seo_block_subscribe">{p2} <a href="https://t.me/{CHANNEL_USERNAME}" target="_blank" rel="nofollow noopener noreferrer">Telegram-канал</a>!</p>
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
        # Strip leading # from tag_name for display (avoid ##hashtag)
        tag_display = tag_name.lstrip('#')
        tag_url = f"{_bp('/tag')}/{url_quote(tag_display)}.html"
        tags_html_parts.append(f'<a href="{tag_url}" class="footer-tag">#{escape_html(tag_display)}</a>')

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
    post_slug = post.get("slug", str(post_id))
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
                is_logo_fallback = (poster == LOGO_EXTERNAL_URL or poster.endswith("/logo.jpg"))
                # All video cards link to post page for playback
                post_link = f"{_bp('/post')}/{post_slug}"
                if not is_logo_fallback:
                    # We have a real poster image — show it with play overlay
                    media_block = (
                        f'<div class="post-feed-media">\n'
                        f'<a href="{post_link}" class="video-card-link">\n'
                        f'<div class="video-container video-card-preview">\n'
                        f'<img src="{escape_html(poster)}" alt="{escape_html(title)}" '
                        f'loading="lazy" decoding="async" referrerpolicy="no-referrer" '
                        f'style="width:100%;max-height:400px;object-fit:cover;">\n'
                        f'<div class="video-play-overlay"></div>\n'
                        f'</div>\n'
                        f'</a>\n'
                        f'</div>'
                    )
                else:
                    # No thumbnail — show styled video placeholder with play button
                    media_block = (
                        f'<div class="post-feed-media">\n'
                        f'<a href="{post_link}" class="video-card-link">\n'
                        f'<div class="video-placeholder-card">\n'
                        f'<div class="video-placeholder-icon">▶</div>\n'
                        f'<div class="video-placeholder-text">Видео</div>\n'
                        f'</div>\n'
                        f'</a>\n'
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

    # Build URLs (relative paths — use slug)
    post_url = post.get("postUrl", "")
    if not post_url or post_url.startswith("http"):
        post_url = f"{_bp('/post')}/{post_slug}"
    else:
        # postUrl may be a relative path without BASE_PATH
        if not post_url.startswith(BASE_PATH):
            post_url = _bp(post_url)

    amp_url = post.get("ampUrl", "")
    if not amp_url or amp_url.startswith("http"):
        amp_url = f"{_bp('/post')}/{post_slug}/amp"
    else:
        if not amp_url.startswith(BASE_PATH):
            amp_url = _bp(amp_url)

    btn_text = "Подробнее"
    date_display = _format_date(date_str, lang)

    return (
        f'\n'
        f'<article class="post-feed-item" data-post-id="{escape_html(str(post_id))}">\n'
        f'{media_block}\n'
        f'<div class="post-feed-content">\n'
        f'<div class="post-feed-meta">\n'
        f'<span>📅 {escape_html(date_display)}</span>\n'
        f'</div>\n'
        f'<h3 class="post-feed-title">\n'
        f'<a href="{post_url}">{escape_html(title)}</a>\n'
        f'</h3>\n'
        f'<div class="post-feed-text">{_format_post_text_no_tags(text, lang)}</div>\n'
        f'<div class="post-feed-actions">\n'
        f'<a href="{post_url}" class="btn-outline" data-i18n="read_more">{btn_text}</a>\n'
        f'</div>\n'
        f'</div>\n'
        f'</article>'
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
        rp_slug = rp.get("slug", str(rp.get('id', '')))
        rp_url = rp.get("postUrl", "")
        if not rp_url or rp_url.startswith("http"):
            rp_url = f"{_bp('/post')}/{rp_slug}"
        else:
            if not rp_url.startswith(BASE_PATH):
                rp_url = _bp(rp_url)

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
    rights_text = "Все права защищены."
    privacy_url = f"{_bp(PRIVACY_PATH)}"
    contacts_url = f"{_bp(CONTACTS_PATH)}"

    home_label = t('nav_home', 'ru')
    articles_label = t('nav_articles', 'ru')
    contacts_label = t('nav_contacts', 'ru')
    privacy_label = t('nav_privacy', 'ru')

    # Popular tags HTML
    popular_tags_html = ""
    if tags and len(tags) > 0:
        popular_tags_html = render_popular_tags(tags, lang)

    return f"""<footer>
<p>© {current_year} {SITE_AUTHOR}. <span data-i18n="footer_rights">{rights_text}</span></p>
<div class="footer-links">
<a href="{_bp('/')}">{home_label}</a> |
<a href="{_bp('/articles')}">{articles_label}</a> |
<a href="{contacts_url}">{contacts_label}</a> |
<a href="{_bp('/rss.xml')}">RSS</a> |
<a href="{_bp('/sitemap.xml')}">Карта сайта</a> |
<a href="{_bp('/sitemap-tags.xml')}">Tags</a> |
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

    Uses real HTML file paths (/page/N/index.html) instead of ?page=X
    because GitHub Pages does NOT support query string routing.
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

    # Build page URL helper — uses /page/N/ instead of ?page=N
    def _page_url(page_num: int) -> str:
        if page_num == 1:
            return base_url
        return f"{base_url}page/{page_num}/"

    html = f'<nav class="pagination" aria-label="{aria_label}">\n'

    # Previous button
    if current_page > 1:
        prev_url = _page_url(current_page - 1)
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
        html += f'<a href="{_page_url(1)}">1</a>\n'
        if start_page > 2:
            html += '<span class="dots">...</span>\n'

    # Page numbers
    for i in range(start_page, end_page + 1):
        if i == current_page:
            html += f'<span class="active" aria-current="page">{i}</span>\n'
        else:
            html += f'<a href="{_page_url(i)}">{i}</a>\n'

    # Last page + dots
    if end_page < total_pages:
        if end_page < total_pages - 1:
            html += '<span class="dots">...</span>\n'
        html += f'<a href="{_page_url(total_pages)}">{total_pages}</a>\n'

    # Next button
    if current_page < total_pages:
        html += f'<a href="{_page_url(current_page + 1)}" aria-label="{next_label}">&raquo;</a>\n'
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

def render_ad_category_buttons(lang: str = "ru") -> str:
    """Render ad category pill-buttons for the homepage (matching original site).

    Shows 7 category buttons: Автозапчасти, Автострахование, Шины и диски,
    Проверка авто, Прокат авто, Инструменты, Купоны и скидки.
    Each links to /ads/{category_key}.
    """
    if not ADMITAD_CONFIG:
        return ""

    buttons_html = ""
    for cat_key, cat_data in ADMITAD_CONFIG.items():
        cat_label = cat_data.get(lang, cat_data.get("ru", cat_key))
        cat_icon = cat_data.get("icon", "")
        cat_url = f"{_bp('/ads')}/{cat_key}"
        buttons_html += f'<a href="{cat_url}" class="ad-category-btn">{cat_icon} {escape_html(cat_label)}</a>\n'

    # NOTE: render_ad_category_buttons already uses _lang_path which includes BASE_PATH

    return f'<div class="ad-section-buttons">{buttons_html}</div>'


def render_ad_blocks(programs: list, lang: str = "ru", max_blocks: int = 6) -> str:
    """Render Admitad ad blocks with three-level regional filtering.

    Three-level system:
      Level 1 (Worker-Side Injection): Cloudflare Worker replaces the
          <!-- REGIONAL_ADS_PLACEHOLDER --> placeholder in HTML with
          region-filtered ad blocks based on request.cf.country.
      Level 2 (/api/ads): AJAX endpoint for SPA navigation updates.
      Level 3 (Fallback): Static <noscript> fallback with global (WW) programs
          for when Worker cannot determine region (e.g. direct GitHub Pages access).

    The Python generator outputs a placeholder that the Worker replaces at request time.
    A <noscript> fallback with WW-coverage programs ensures content even without Worker/JS.
    """
    # Level 3: Build noscript fallback with global programs (WW coverage or no region restriction)
    fallback_ads_parts = []
    if programs:
        seen_cats = set()
        for prog in programs:
            if not isinstance(prog, dict):
                continue
            # Only include programs with WW/global coverage for fallback
            regions = prog.get("allowed_regions", [])
            if regions and "WW" not in regions and "RU" not in regions:
                continue
            cat = prog.get("jsonCategory") or prog.get("category") or "other"
            if cat in seen_cats:
                continue
            seen_cats.add(cat)
            if len(fallback_ads_parts) >= max_blocks:
                break

            raw_image_url = prog.get("image") or prog.get("logo") or LOGO_EXTERNAL_URL
            json_category = prog.get("jsonCategory") or prog.get("category") or "other"
            internal_cat = ADMITAD_CATEGORY_MAPPING.get(json_category, "OTHER")
            category_label = ADMITAD_CATEGORY_NAMES.get(lang, ADMITAD_CATEGORY_NAMES["ru"]).get(
                internal_cat, json_category
            )
            description = prog.get("description") or prog.get("name", "")
            btn_text = "Перейти" if lang == "ru" else "Go"
            prog_name = prog.get("name", "")
            prog_id = prog.get("id", "")
            affiliate_url = f"/api/{prog_id}" if prog_id else ""

            legal_html = ""
            advertiser_info = prog.get("advertiser_legal_info")
            if isinstance(advertiser_info, dict) and advertiser_info.get("name"):
                ad_label = "Реклама" if lang == "ru" else "Ad"
                legal_html = f'<div class="ad-block-legal">{ad_label}: {escape_html(advertiser_info["name"])}</div>'

            desc_truncated = description[:150] + ("..." if len(description) > 150 else "")

            fallback_ads_parts.append(
                f"""<a href="{escape_html(affiliate_url)}" target="_blank" rel="nofollow noopener sponsored" style="text-decoration:none;color:inherit;display:block;">
<div class="ad-block-item">
  <div class="ad-block-media">
    <img src="{escape_html(raw_image_url)}" alt="{escape_html(prog_name)}" loading="lazy" referrerpolicy="no-referrer" onerror="this.onerror=null;this.remove()">
  </div>
  <span class="ad-block-category">{escape_html(category_label)}</span>
  <h4 class="ad-block-title">{escape_html(prog_name)}</h4>
  <p class="ad-block-desc">{escape_html(desc_truncated)}</p>
  <div class="ad-block-btn">{btn_text}<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-left:4px;"><path d="M7 17L17 7M17 7H7M17 7V17"/></svg></div>
  {legal_html}
</div>
</a>"""
            )

    # Build the complete output:
    # 1. Placeholder for Worker injection (Level 1)
    # 2. Noscript fallback (Level 3) — hidden when Worker replaces the placeholder
    lang_placeholder = f"REGIONAL_ADS_PLACEHOLDER_{lang.upper()}"
    fallback_html = "".join(fallback_ads_parts)
    fallback_container = f'<div class="ad-blocks-container">{fallback_html}</div>' if fallback_html else ''

    result = f'<!-- {lang_placeholder} -->'
    if fallback_container:
        result += f'\n<noscript data-ad-fallback>{fallback_container}</noscript>'

    # Level 2: AJAX script for SPA navigation (loads /api/ads on route change)
    # This only activates if the placeholder was NOT replaced by Worker (direct GH Pages access)
    lang_code = "en" if lang == "en" else "ru"
    result += f"""<script>(function(){{var p=document.querySelector('[data-ad-placeholder]');if(!p)return;fetch('/api/ads?lang={lang_code}&max={max_blocks}').then(function(r){{return r.text();}}).then(function(h){{if(h&&h.trim().length>0)p.innerHTML=h;}}).catch(function(){{}});}})();</script>"""

    return f'<div class="ad-blocks-container" data-ad-placeholder>{result}</div>'


# =============================================================================
# render_shop_widget
# =============================================================================

def render_shop_widget(products: list, lang: str = "ru", count: int = 20) -> str:
    """Render shop widget with static product cards and dynamic JS fallback.

    If a products list is provided and non-empty, renders static product cards
    directly in the HTML. The JS dynamic loader can still refresh/replace them
    as a progressive enhancement. If no products are given, falls back to the
    empty container for JS-only loading.
    """
    shop_path = _bp(SHOP_PATH)
    widget_title = "🛒 Магазин автозапчастей"
    visit_shop_link = "Перейти в магазин →"

    # Render static product cards if products are provided
    static_cards = ""
    if products and len(products) > 0:
        import random as _random
        # Pick random subset
        widget_products = list(products)
        _random.shuffle(widget_products)
        widget_products = widget_products[:count]

        for p in widget_products:
            p_name = p.get("name", "")
            if len(p_name) > 60:
                p_name = p_name[:57] + "..."
            p_price = p.get("price", 0)
            p_currency = p.get("currency", "RUB")
            if p_price:
                try:
                    price_display = f"{int(p_price):,} ₽".replace(",", " ")
                except (ValueError, TypeError):
                    price_display = str(p_price) + " ₽"
            else:
                price_display = ""
            p_image = p.get("image", "") or "/logo.jpg"
            p_url = p.get("url", "")
            p_id = p.get("id", "")
            p_product_page = f"/shop/{p_id}" if p_id else ""
            # Buy URL: direct partner link
            buy_url = p_url if p_url and p_url != "#" else f"/shop/{p_id}" if p_id else "#"

            static_cards += (
                f'<div class="widget-product">'
                f'<a href="{p_product_page}" style="text-decoration:none;color:inherit;">'
                f'<img src="{escape_html(p_image)}" alt="{escape_html(p_name)}" loading="lazy" referrerpolicy="no-referrer" onerror="this.onerror=null;this.src=\'/logo.jpg\'">'
                f'<div class="wp-name">{escape_html(p_name)}</div>'
                f'<div class="wp-price">{escape_html(price_display)}</div>'
                f'</a>'
                f'<a href="{escape_html(buy_url)}" class="wp-buy-btn" target="_blank" rel="nofollow noopener sponsored">Купить</a>'
                f'</div>'
            )

    return (
        f'<div class="shop-widget" id="shopWidget">\n'
        f'<div class="widget-header">'
        f'<span class="widget-title" data-i18n="shop_title">{widget_title}</span>'
        f'<a href="{shop_path}" class="widget-link" data-i18n="shop_visit">{visit_shop_link}</a>'
        f'</div>\n'
        f'<div class="shop-widget-grid" id="shopWidgetGrid" data-shop-widget-count="{count}">\n'
        f'{static_cards}'
        f'</div>\n'
        f'<div style="text-align:center;padding:1rem;">'
        f'<a href="{shop_path}" class="btn-cta" style="display:inline-flex;align-items:center;gap:8px;padding:12px 24px;border-radius:9999px;background:var(--primary);color:#fff;font-weight:700;text-decoration:none;" data-i18n="shop_visit">🛒 {visit_shop_link}</a>'
        f'</div>\n'
        f'</div>'
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


# =============================================================================
# render_product_page
# =============================================================================

def render_product_page(
    product: dict,
    lang: str = "ru",
    related_products: Optional[list] = None,
    shop_widget_products: Optional[list] = None,
) -> str:
    """Render a full individual product page.

    Includes:
    - Product name, image, description, price, old price, vendor/brand
    - Category badge
    - "Buy" button linking to /api/go/{feed_name}/{product_id}
    - Schema.org Product JSON-LD
    - Related products section (same category)
    - Shop widget with 20 random products
    - Breadcrumbs: Home > Shop > Product Name
    - Regional ad blocks (client-side)

    Args:
        product: Product dict with expanded keys (name, price, image, etc.).
        lang: Language code.
        related_products: List of related product dicts (same category).
        shop_widget_products: List of product dicts for the shop widget.

    Returns:
        HTML string for the product page body content.
    """
    if not product or not isinstance(product, dict):
        return ""

    product_id = product.get("id", "")
    product_name = product.get("name", "")
    product_image = product.get("image", "")
    product_description = product.get("description", "")
    product_price = product.get("price", "")
    product_old_price = product.get("old_price", "")
    product_currency = product.get("currency", "RUB")
    product_vendor = product.get("vendor") or product.get("brand", "")
    product_category = product.get("category", "")
    product_feed_name = product.get("feed_name") or product.get("feedName", "")
    product_feed_id = product.get("feed_id") or product.get("feedId", "")
    product_available = product.get("available", True)
    product_model = product.get("model", "")

    # Build affiliate URL for "Buy" button — link directly to partner store (affiliate URL)
    # Fall back to Worker redirect only if no direct URL available
    product_partner_url = product.get("url", "") or ""
    if product_partner_url and product_partner_url != "#":
        buy_url = product_partner_url
    elif product_feed_name or product_feed_id:
        buy_url = f"/api/go/{url_quote(str(product_feed_name or product_feed_id))}/{url_quote(str(product_id))}"
    else:
        buy_url = "#"

    # Currency display
    currency = PRODUCTS_CURRENCY_RU

    # Price display
    if isinstance(product_price, (int, float)):
        price_display = f"{product_price:,.0f} {currency}"
    elif product_price:
        price_display = f"{product_price} {currency}"
    else:
        price_display = ""

    old_price_display = ""
    if product_old_price and isinstance(product_old_price, (int, float)) and product_old_price > 0:
        old_price_display = f"{product_old_price:,.0f} {currency}"

    # Availability badge
    availability_badge = ""
    availability_text = ""
    if not product_available:
        availability_badge = '<span class="product-badge badge-unavailable">Под заказ</span>'
        availability_text = "Под заказ"
    elif product_old_price:
        availability_badge = '<span class="product-badge badge-sale">Скидка</span>'

    # Category badge
    category_badge = ""
    if product_category:
        category_badge = f'<span class="product-badge badge-category">{escape_html(str(product_category))}</span>'

    # Vendor badge
    vendor_badge = ""
    if product_vendor:
        vendor_badge = f'<span class="product-badge badge-vendor">{escape_html(product_vendor)}</span>'

    # Buy button text
    buy_text = "🛒 Купить"
    if not product_available:
        buy_text = "📦 Под заказ"

    # Breadcrumbs
    shop_label = "Магазин"
    bc_items = [
        {"name": "Главная", "url": _lang_base(lang)},
        {"name": shop_label, "url": f"{_bp('/shop')}"},
        {"name": product_name[:50], "url": f"{_bp('/shop')}/{product_id}"},
    ]
    breadcrumbs = render_breadcrumbs(bc_items, lang)

    # Related products section
    related_html = ""
    if related_products:
        related_title = "Похожие товары" if lang == "ru" else "Related Products"
        related_cards = ""
        for rp in related_products[:6]:
            rp_id = rp.get("id", "")
            rp_name = rp.get("name", "")
            rp_image = rp.get("image", "")
            rp_price = rp.get("price", "")
            rp_url = f"{_bp('/shop')}/{rp_id}"
            rp_price_display = f"{rp_price:,.0f} {currency}" if isinstance(rp_price, (int, float)) else f"{rp_price} {currency}" if rp_price else ""
            related_cards += (
                f'<a href="{rp_url}" class="related-card">\n'
                f'<div class="related-card-media">\n'
                f'<img src="{escape_html(rp_image)}" alt="{escape_html(rp_name)}" '
                f'loading="lazy" decoding="async" referrerpolicy="no-referrer"'
                f' onerror="this.onerror=null;this.src=\'/logo.jpg\'">\n'
                f'</div>\n'
                f'<div class="related-card-content">\n'
                f'<div class="related-card-title">{escape_html(rp_name[:80])}</div>\n'
                f'<div class="related-card-date" style="color:var(--primary);font-weight:700;">{escape_html(rp_price_display)}</div>\n'
                f'</div>\n'
                f'</a>'
            )
        if related_cards:
            related_html = (
                f'<div class="related-posts">\n'
                f'<h3>{related_title}</h3>\n'
                f'<div class="related-grid">\n'
                f'{related_cards}\n'
                f'</div>\n'
                f'</div>'
            )

    # Shop widget — loaded dynamically via JS from /api/shop/products?random=6
    # No need to pass static product list
    shop_widget = render_shop_widget([], lang, count=6)

    # Regional ad blocks — uses placeholder for Worker injection
    ad_container = '<!-- REGIONAL_ADS_PLACEHOLDER_RU -->'

    # Build the product page body
    body = f"""
<div class="container">
{breadcrumbs}
<div class="article-content">
<article class="product-detail">
<div class="product-detail-image">
<img src="{escape_html(product_image)}" alt="{escape_html(product_name)}" loading="eager" referrerpolicy="no-referrer" onerror="this.onerror=null;this.src='/logo.jpg'" style="width:100%;max-height:500px;object-fit:contain;border-radius:var(--radius-lg);">
</div>
<div class="product-detail-info">
<div class="product-card-badges" style="margin-bottom:0.75rem;">
{availability_badge}{category_badge}{vendor_badge}
</div>
<h1 style="font-size:1.5rem;font-weight:800;line-height:1.3;margin-bottom:1rem;font-family:var(--font-display);">{escape_html(product_name)}</h1>
<div class="product-card-price" style="font-size:1.5rem;font-weight:800;color:var(--primary);margin-bottom:0.5rem;">
{escape_html(price_display)}
{f'<s style="font-size:0.9rem;color:var(--text-muted);margin-left:0.5rem;">{escape_html(old_price_display)}</s>' if old_price_display else ''}
</div>
{f'<div style="margin-bottom:0.75rem;font-size:0.875rem;color:var(--text-muted);">{escape_html(product_vendor)}{f" — {escape_html(product_model)}" if product_model else ""}</div>' if product_vendor else ''}
<div class="article-body" style="margin-bottom:1.5rem;">
<p>{escape_html(product_description).replace(chr(10), "<br>\n")}</p>
</div>
<div style="display:flex;gap:0.75rem;flex-wrap:wrap;margin-bottom:1.5rem;">
<a href="{buy_url}" class="product-card-btn" style="flex:1;min-width:200px;padding:0.875rem;font-size:1rem;" target="_blank" rel="nofollow noopener sponsored">{buy_text}</a>
<a href="{_bp('/shop')}" class="btn-outline" style="flex:0;min-width:auto;padding:0.875rem 1.25rem;">← Магазин</a>
</div>
{f'<div style="font-size:0.75rem;color:var(--text-light);margin-bottom:1rem;">Артикул: {escape_html(str(product_id))}</div>' if product_id else ''}
</div>
</article>
</div>
{related_html}
{ad_container}
{shop_widget}
</div>"""

    return body


# =============================================================================
# render_regional_ads_script
# =============================================================================

def render_regional_ads_script() -> str:
    """Render client-side JavaScript for regional ad filtering.

    The script calls /api/ads?lang=ru&max=6 (or based on page language)
    and replaces the static ad blocks with region-filtered ones from the Worker.
    The Worker uses request.cf.country for geo-targeting.

    Returns:
        HTML <script> tag with the regional ads JavaScript.
    """
    return """<script>
(function(){
  var adContainers = document.querySelectorAll('.ad-blocks-container');
  if (adContainers.length > 0) {
    var lang = document.documentElement.lang === 'en' ? 'en' : 'ru';
    fetch('/api/ads?lang=' + lang + '&max=6')
      .then(function(r){ return r.text(); })
      .then(function(html){
        if (html) {
          adContainers.forEach(function(c){ c.innerHTML = html; });
        }
      })
      .catch(function(){});
  }
})();
</script>"""
