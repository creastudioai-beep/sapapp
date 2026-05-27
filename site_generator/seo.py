"""
SEO module for the SochiAutoParts static site generator.

Generates all SEO-related HTML: meta tags, Schema.org JSON-LD, hreflang links,
sitemaps, RSS feeds, robots.txt, manifest.json, cookie consent, and client scripts.

Must match the SEO output of the original Cloudflare Worker v27.0-AUDITED.

Usage:
    from seo import generate_meta_tags, generate_hreflang_links, generate_sitemap_index
"""

import json
import math
import re
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from urllib.parse import quote as url_quote

from .i18n import t
from .config import (
    SITE_URL,
    SITE_NAME_RU,
    SITE_NAME_EN,
    SITE_DESCRIPTION_RU,
    SITE_DESCRIPTION_EN,
    SEO_DEFAULT_TITLE_RU,
    SEO_DEFAULT_TITLE_EN,
    CHANNEL_USERNAME,
    GA4_MEASUREMENT_ID,
    LOGO_URL,
    LOGO_SVG_URL,
    LOGO_FAVICON_URL,
    LOGO_APPLE_TOUCH_URL,
    LOGO_ICON_192,
    LOGO_ICON_512,
    SOCIAL_LINKS,
    PRODUCT_CATEGORIES,
    POSTS_PER_PAGE,
    CURRENT_YEAR,
    PRODUCTS_PER_PAGE,
    BASE_PATH,
)


# =============================================================================
# Constants (matching Worker v27.0 CONFIG)
# =============================================================================

SITE_AUTHOR: str = "SOCHIAUTOPARTS"
LOGO_EXTERNAL_URL: str = f"{SITE_URL}/logo.jpg"
LOGO_WIDTH: int = 640
LOGO_HEIGHT: int = 640
DEFAULT_THUMBNAIL: str = f"{SITE_URL}/logo.jpg"
TWITTER_SITE: str = "@sochiautoparts"
GOOGLE_NEWS_CATEGORY: str = "Autos"
PR_EMAIL: str = "pr@sochiautoparts.ru"
TELEGRAM_WEB_URL: str = f"https://t.me/s/{CHANNEL_USERNAME}"
INSTAGRAM_URL: str = "https://www.instagram.com/sochi_auto_parts/"
TWITTER_URL: str = "https://twitter.com/sochiautoparts"
YOUTUBE_URL: str = f"https://www.youtube.com/@{CHANNEL_USERNAME}"
FACEBOOK_URL: str = "https://www.facebook.com/sochiautoparts"
LINKEDIN_URL: str = "https://www.linkedin.com/company/sochiautoparts"
MAX_POSTS_SITEMAP: int = 5000
SITEMAP_POSTS_PER_FILE: int = 1000
MAX_POSTS_RSS: int = 50
TAG_MIN_POSTS_FOR_SITEMAP: int = 2
PRODUCTS_SITEMAP_PER_FILE: int = 1000
SHOP_PATH: str = "/shop"
SHOP_PATH_EN: str = "/en/shop"
CONTACTS_PATH: str = "/contacts"
PRIVACY_PATH: str = "/privacy"


def _bp(path: str) -> str:
    """Prefix a path with BASE_PATH."""
    if path.startswith("/"):
        return BASE_PATH + path
    return BASE_PATH + "/" + path

VERIFICATION_META_TAGS: list = [
    {"name": "verify-admitad", "content": "3c08bd9d2c"},
    {"name": "takprodam-verification", "content": "cf451bd9-e5de-413f-990b-147d25c657e2"},
]

NEWS_KEYWORDS: list = [
    "автоновости", "авторынок", "sochiautoparts", "тест-драйв", "обзоры",
    "премьеры", "новинки", "сравнения", "электрокары", "гибриды", "внедорожники",
    "кроссоверы", "седаны", "автопром", "цены", "дилеры", "запчасти", "тюнинг",
    "сервис", "каршеринг", "автоподбор",
    "global auto news", "car industry", "automotive trends", "world car market",
    "auto analytics", "car sales statistics", "auto show", "motor show",
    "geneva motor show", "frankfurt auto show", "detroit auto show",
    "shanghai auto show", "tokyo motor show", "LA auto show",
    "новости автопрома", "мировой авторынок", "глобальные автоновости",
    "аналитика авторынка", "автосалон", "автоиндустрия",
    "производство автомобилей", "автомобильный рынок",
    "электромобиль", "зарядная станция", "EV", "PHEV", "гибридный двигатель",
    "автопилот", "беспилотное авто", "автономное вождение", "умный автомобиль",
    "electric vehicle", "EV market", "battery technology", "charging infrastructure",
    "autonomous driving", "self-driving car", "connected car", "smart mobility",
    "EV range", "fast charging", "solid state battery", "vehicle-to-grid",
    "моторное масло", "шины", "диски", "автошины", "шиномонтаж",
    "тормозные колодки", "фильтры", "свечи зажигания", "амортизаторы",
    "аккумуляторы", "автостекло", "кузовные запчасти",
    "оригинальные запчасти", "аналоги запчастей", "автохимия",
    "автокосметика", "автоаксессуары",
    "auto parts online", "OEM parts", "aftermarket parts", "car accessories",
    "автострахование", "ОСАГО", "КАСКО", "диагностика авто", "ТО автомобиля",
    "техосмотр", "проверка авто", "автоистория", "автоподбор специалист",
    "автоаукцион", "trade-in",
    "car insurance", "vehicle inspection", "carfax", "auto auction",
]


# =============================================================================
# Escape helpers
# =============================================================================

_ESCAPE_MAP = {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"}
_XML_ESCAPE_MAP = {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&apos;"}


def escape_html(text: str) -> str:
    """Escape HTML special characters.

    Matches the Worker's escapeHTML function:
    replaces &, <, >, ", ' with HTML entities.

    Args:
        text: String to escape.

    Returns:
        HTML-escaped string. Empty string for non-string input.
    """
    if not isinstance(text, str):
        return ""
    return re.sub(r'[&<>"\']', lambda m: _ESCAPE_MAP[m.group()], text)


def escape_xml(text: str) -> str:
    """Escape XML special characters.

    Matches the Worker's escapeXML function:
    replaces &, <, >, ', " with XML entities.

    Args:
        text: String to escape.

    Returns:
        XML-escaped string. Empty string for non-string input.
    """
    if not isinstance(text, str):
        return ""
    return re.sub(r"[<>&'\"]", lambda m: _XML_ESCAPE_MAP[m.group()], text)


# =============================================================================
# Helper: current year
# =============================================================================

def _get_current_year() -> int:
    """Return the current year."""
    return datetime.now(timezone.utc).year


# =============================================================================
# Helper: post URL builder
# =============================================================================

def _post_url(post_id, lang="ru") -> str:
    """Build canonical post URL."""
    if lang == "en":
        return f"{SITE_URL}/en/post/{post_id}"
    return f"{SITE_URL}/post/{post_id}"


def _amp_url(post_id, lang="ru") -> str:
    """Build AMP post URL."""
    if lang == "en":
        return f"{SITE_URL}/en/post/{post_id}/amp"
    return f"{SITE_URL}/post/{post_id}/amp"


def _article_url(article_id, lang="ru") -> str:
    """Build article URL."""
    if lang == "en":
        return f"{SITE_URL}/en/article/{article_id}"
    return f"{SITE_URL}/article/{article_id}"


# =============================================================================
# Helper: get poster/thumbnail for a post
# =============================================================================

def _get_poster_for_post(post: dict) -> str:
    """Extract the first image URL from a post for OG/schema thumbnails.

    Checks media list, then various single-image fields.
    Falls back to DEFAULT_THUMBNAIL.
    """
    media = post.get("media", [])
    if isinstance(media, list) and len(media) > 0:
        first = media[0]
        if isinstance(first, dict):
            if first.get("type") == "photo":
                url = first.get("directUrl") or first.get("url") or first.get("src") or ""
                if url:
                    return url
            # For video, try poster
            if first.get("type") == "video":
                poster = first.get("poster") or first.get("thumbnailUrl") or ""
                if poster:
                    return poster
                # Try directUrl as fallback
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

    return DEFAULT_THUMBNAIL


def _looks_like_image_url(url: str) -> bool:
    """Check if a URL looks like it points to an image."""
    if not url or not isinstance(url, str):
        return False
    lower = url.lower().split("?")[0]
    return any(lower.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".avif"))


# =============================================================================
# Meta tags generator
# =============================================================================

def generate_meta_tags(
    title: str,
    description: str,
    url: str,
    lang: str = "ru",
    og_type: str = "website",
    image: Optional[str] = None,
    image_width: int = 640,
    image_height: int = 640,
    robots: str = "index, follow",
    canonical: Optional[str] = None,
    article_published: Optional[str] = None,
    article_modified: Optional[str] = None,
    article_tag: Optional[str] = None,
    product_price: Optional[str] = None,
    product_currency: Optional[str] = None,
    product_availability: Optional[str] = None,
) -> str:
    """Generate complete <head> meta tags.

    Includes:
    - <title>, <meta name="description">
    - Canonical URL
    - Open Graph tags (og:title, og:description, og:url, og:image, og:type,
      og:locale, og:site_name)
    - og:locale:alternate (ru→en or en→ru)
    - og:image:width, og:image:height
    - Twitter Card tags
    - <meta name="robots">
    - Verification meta tags
    - <meta name="generator" content="sochiautoparts-static v1.0">
    """
    canonical_url = canonical or url
    og_image = image or LOGO_EXTERNAL_URL
    locale = "ru_RU" if lang == "ru" else "en_US"
    locale_alt = "en_US" if lang == "ru" else "ru_RU"
    site_name = SITE_AUTHOR
    twitter_card = "summary_large_image"

    tags = []

    # Title and description
    tags.append(f"<title>{escape_html(title)}</title>")
    tags.append(f'<meta name="description" content="{escape_html(description)}" />')

    # Canonical
    tags.append(f'<link rel="canonical" href="{escape_html(canonical_url)}" />')

    # Open Graph
    tags.append(f'<meta property="og:title" content="{escape_html(title)}" />')
    tags.append(f'<meta property="og:description" content="{escape_html(description)}" />')
    tags.append(f'<meta property="og:url" content="{escape_html(url)}" />')
    tags.append(f'<meta property="og:type" content="{og_type}" />')
    tags.append(f'<meta property="og:locale" content="{locale}" />')
    tags.append(f'<meta property="og:locale:alternate" content="{locale_alt}" />')
    tags.append(f'<meta property="og:locale:alternate" content="{locale}" />')
    tags.append(f'<meta property="og:site_name" content="{escape_html(site_name)}" />')
    tags.append(f'<meta property="og:image" content="{escape_html(og_image)}" />')
    tags.append(f'<meta property="og:image:width" content="{image_width}" />')
    tags.append(f'<meta property="og:image:height" content="{image_height}" />')

    # Article-specific OG tags
    if article_published:
        tags.append(f'<meta property="article:published_time" content="{escape_html(article_published)}" />')
    if article_modified:
        tags.append(f'<meta property="article:modified_time" content="{escape_html(article_modified)}" />')
    if article_tag:
        tags.append(f'<meta property="article:tag" content="{escape_html(article_tag)}" />')
    if og_type == "article":
        tags.append(f'<meta property="article:section" content="{GOOGLE_NEWS_CATEGORY}" />')
        tags.append(f'<meta property="article:author" content="{escape_html(SITE_AUTHOR)}" />')

    # Product-specific OG tags
    if product_price:
        tags.append(f'<meta property="product:price:amount" content="{escape_html(str(product_price))}" />')
    if product_currency:
        tags.append(f'<meta property="product:price:currency" content="{escape_html(product_currency)}" />')

    # Twitter Card
    tags.append(f'<meta name="twitter:card" content="{twitter_card}" />')
    tags.append(f'<meta name="twitter:site" content="{TWITTER_SITE}" />')
    tags.append(f'<meta name="twitter:creator" content="{TWITTER_SITE}" />')
    tags.append(f'<meta name="twitter:title" content="{escape_html(title)}" />')
    tags.append(f'<meta name="twitter:description" content="{escape_html(description)}" />')
    tags.append(f'<meta name="twitter:image" content="{escape_html(og_image)}" />')

    # Robots
    tags.append(f'<meta name="robots" content="{robots}" />')
    tags.append(f'<meta name="googlebot" content="index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1" />')
    tags.append(f'<meta name="bingbot" content="index, follow, max-image-preview:large" />')
    tags.append(f'<meta name="yandex" content="index, follow" />')
    tags.append(f'<meta name="slurp" content="index, follow" />')
    tags.append(f'<meta name="petalbot" content="index, follow" />')

    # Keywords
    keywords_str = ", ".join(NEWS_KEYWORDS)
    tags.append(f'<meta name="keywords" content="{escape_html(keywords_str)}" />')

    # Theme color
    tags.append(f'<meta name="theme-color" content="#2481CC" />')
    tags.append(f'<meta name="msapplication-TileColor" content="#2481CC" />')

    # Author & publisher
    tags.append(f'<meta name="author" content="{escape_html(SITE_AUTHOR)}" />')
    tags.append(f'<meta name="publisher" content="{escape_html(SITE_AUTHOR)}" />')

    # Verification meta tags
    tags.append(generate_verification_meta_tags())

    # Generator
    tags.append('<meta name="generator" content="sochiautoparts-static v1.0" />')

    return "\n".join(tags)


# =============================================================================
# Hreflang links
# =============================================================================

def generate_hreflang_links(
    path: str,
    lang: str = "ru",
    post_id: Optional[int] = None,
    article_id: Optional[int] = None,
    tag: Optional[str] = None,
) -> str:
    """Generate <link rel="alternate" hreflang="..."> tags.

    For ru pages: hreflang="ru" + hreflang="en" + hreflang="x-default"
    Pattern:
    - Homepage: ru=/ , en=/en/
    - Posts: ru=/post/{id}, en=/en/post/{id}
    - Articles: ru=/article/{id}, en=/en/article/{id}
    - Tags: ru=/tag/{tag}, en=/en/tag/{tag}
    - Static: ru=/path, en=/en/path
    - Archive: ru=/archive, en=/en/archive
    - Archive post: ru=/archive/post/{id}, en=/en/archive/post/{id}
    - Shop: ru=/shop, en=/en/shop
    - Product: ru=/shop/{id}, en=/en/shop/{id}
    - Category: ru=/shop/category/{id}, en=/en/shop/category/{id}
    """
    # Homepage
    if path in ("/", "/en/", "/ru/"):
        return (
            f'<link rel="alternate" hreflang="ru" href="{SITE_URL}/" />'
            f'<link rel="alternate" hreflang="en" href="{SITE_URL}/en/" />'
            f'<link rel="alternate" hreflang="x-default" href="{SITE_URL}/" />'
        )

    # Tag pages
    if tag or path.startswith("/tag/") or path.startswith("/en/tag/"):
        tag_match = re.match(r"/(?:en/)?tag/(.+)$", path)
        if tag_match:
            tag_name = tag_match.group(1)
            # URL-encode the tag for proper link resolution (especially Arabic/Unicode tags)
            encoded_tag = url_quote(tag_name)
            return (
                f'<link rel="alternate" hreflang="ru" href="{SITE_URL}/tag/{encoded_tag}" />'
                f'<link rel="alternate" hreflang="en" href="{SITE_URL}/en/tag/{encoded_tag}" />'
                f'<link rel="alternate" hreflang="x-default" href="{SITE_URL}/tag/{encoded_tag}" />'
            )

    # Articles listing page
    if path in ("/articles", "/en/articles"):
        return (
            f'<link rel="alternate" hreflang="ru" href="{SITE_URL}/articles" />'
            f'<link rel="alternate" hreflang="en" href="{SITE_URL}/en/articles" />'
            f'<link rel="alternate" hreflang="x-default" href="{SITE_URL}/articles" />'
        )

    # Single article page
    if article_id or re.match(r"^/(?:en/)?article/\d+$", path):
        article_match = re.match(r"^/(?:en/)?article/(\d+)$", path)
        if article_id:
            a_id = article_id
        elif article_match:
            a_id = article_match.group(1)
        else:
            return ""
        return (
            f'<link rel="alternate" hreflang="ru" href="{SITE_URL}/article/{a_id}" />'
            f'<link rel="alternate" hreflang="en" href="{SITE_URL}/en/article/{a_id}" />'
            f'<link rel="alternate" hreflang="x-default" href="{SITE_URL}/article/{a_id}" />'
        )

    # Post pages
    if post_id or re.match(r"^/(?:en/)?post/\d+", path):
        post_match = re.match(r"^/(?:en/)?post/(\d+)", path)
        if post_id:
            p_id = post_id
        elif post_match:
            p_id = post_match.group(1)
        else:
            return ""
        return (
            f'<link rel="alternate" hreflang="ru" href="{SITE_URL}/post/{p_id}" />'
            f'<link rel="alternate" hreflang="en" href="{SITE_URL}/en/post/{p_id}" />'
            f'<link rel="alternate" hreflang="x-default" href="{SITE_URL}/post/{p_id}" />'
        )

    # Archive pages — DISABLED (archive feature removed)
    # Archive post pages — DISABLED (archive feature removed)

    # Shop page
    if path in ("/shop", "/en/shop"):
        return (
            f'<link rel="alternate" hreflang="ru" href="{SITE_URL}/shop" />'
            f'<link rel="alternate" hreflang="en" href="{SITE_URL}/en/shop" />'
            f'<link rel="alternate" hreflang="x-default" href="{SITE_URL}/shop" />'
        )

    # Product page
    product_match = re.match(r"^/(?:en/)?shop/([a-z0-9_]+)$", path)
    if product_match:
        p_id = product_match.group(1)
        return (
            f'<link rel="alternate" hreflang="ru" href="{SITE_URL}/shop/{p_id}" />'
            f'<link rel="alternate" hreflang="en" href="{SITE_URL}/en/shop/{p_id}" />'
            f'<link rel="alternate" hreflang="x-default" href="{SITE_URL}/shop/{p_id}" />'
        )

    # Category page
    cat_match = re.match(r"^/(?:en/)?shop/category/(\d+)$", path)
    if cat_match:
        cat_id = cat_match.group(1)
        return (
            f'<link rel="alternate" hreflang="ru" href="{SITE_URL}/shop/category/{cat_id}" />'
            f'<link rel="alternate" hreflang="en" href="{SITE_URL}/en/shop/category/{cat_id}" />'
            f'<link rel="alternate" hreflang="x-default" href="{SITE_URL}/shop/category/{cat_id}" />'
        )

    # Static pages (contacts, privacy, etc.)
    if path.startswith("/en/"):
        ru_path = path[3:]  # strip /en prefix
        return (
            f'<link rel="alternate" hreflang="ru" href="{SITE_URL}{ru_path}" />'
            f'<link rel="alternate" hreflang="en" href="{SITE_URL}{path}" />'
            f'<link rel="alternate" hreflang="x-default" href="{SITE_URL}{ru_path}" />'
        )
    else:
        return (
            f'<link rel="alternate" hreflang="ru" href="{SITE_URL}{path}" />'
            f'<link rel="alternate" hreflang="en" href="{SITE_URL}/en{path}" />'
            f'<link rel="alternate" hreflang="x-default" href="{SITE_URL}{path}" />'
        )


# =============================================================================
# Schema.org JSON-LD generators
# =============================================================================

def _static_org_schema() -> str:
    """Generate the static Organization Schema.org JSON-LD.

    This is the same across all pages.
    """
    schema = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": SITE_AUTHOR,
        "url": SITE_URL,
        "logo": {
            "@type": "ImageObject",
            "url": LOGO_EXTERNAL_URL,
            "width": LOGO_WIDTH,
            "height": LOGO_HEIGHT,
        },
        "sameAs": [
            TELEGRAM_WEB_URL,
            INSTAGRAM_URL,
            TWITTER_URL,
            YOUTUBE_URL,
            FACEBOOK_URL,
            LINKEDIN_URL,
        ],
        "contactPoint": {
            "@type": "ContactPoint",
            "contactType": "customer service",
            "email": PR_EMAIL,
            "availableLanguage": ["Russian", "English"],
            "areaServed": "Worldwide",
        },
    }
    return json.dumps(schema, ensure_ascii=False)


# Module-level constant for the static org schema
STATIC_ORG_SCHEMA: str = _static_org_schema()


def generate_web_site_schema(lang: str = "ru") -> str:
    """Generate WebSite Schema.org JSON-LD."""
    schema = {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": SEO_DEFAULT_TITLE_RU if lang == "ru" else SEO_DEFAULT_TITLE_EN,
        "url": SITE_URL,
        "potentialAction": {
            "@type": "SearchAction",
            "target": f"{SITE_URL}/?q={{search_term_string}}",
            "query-input": "required name=search_term_string",
        },
        "inLanguage": "ru-RU" if lang == "ru" else "en-US",
        "publisher": {"@type": "Organization", "name": SITE_AUTHOR},
        "description": SITE_DESCRIPTION_RU if lang == "ru" else SITE_DESCRIPTION_EN,
    }
    return json.dumps(schema, ensure_ascii=False)


def generate_news_article_schema(post: dict, seo_data: dict, lang: str = "ru") -> str:
    """Generate NewsArticle Schema.org JSON-LD for a post.

    Args:
        post: Post dict with fields: title, text, media, id, date, etc.
        seo_data: Dict with SEO fields: ogUrl, publishedTime, modifiedTime, description.
        lang: Language code.
    """
    current_year = _get_current_year()
    schema: Dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": post.get("title", ""),
        "url": seo_data.get("ogUrl", ""),
        "datePublished": seo_data.get("publishedTime", ""),
        "dateModified": seo_data.get("modifiedTime", ""),
        "description": seo_data.get("description", ""),
        "inLanguage": "ru-RU" if lang == "ru" else "en-US",
        "publisher": {
            "@type": "Organization",
            "name": SITE_AUTHOR,
            "url": SITE_URL,
            "logo": {"@type": "ImageObject", "url": LOGO_EXTERNAL_URL},
        },
        "mainEntityOfPage": {"@type": "WebPage", "@id": seo_data.get("ogUrl", "")},
        "author": {"@type": "Organization", "name": SITE_AUTHOR},
        "articleSection": GOOGLE_NEWS_CATEGORY,
        "wordCount": len((post.get("text") or "").split()),
        "thumbnailUrl": _get_poster_for_post(post),
        "image": _get_poster_for_post(post),
        "copyrightHolder": {"@type": "Organization", "name": SITE_AUTHOR},
        "copyrightYear": current_year,
    }

    # Rich image if available
    media = post.get("media", [])
    if isinstance(media, list) and len(media) > 0:
        first_media = media[0]
        if isinstance(first_media, dict) and first_media.get("type") == "photo":
            schema["image"] = {
                "@type": "ImageObject",
                "url": first_media.get("directUrl") or first_media.get("url", ""),
                "width": first_media.get("width", 800),
                "height": first_media.get("height", 600),
            }

    # Video if available
    if isinstance(media, list) and len(media) > 0:
        first_media = media[0]
        if isinstance(first_media, dict) and first_media.get("type") == "video":
            video = first_media
            video_schema: Dict[str, Any] = {
                "@type": "VideoObject",
                "url": video.get("directUrl", ""),
                "thumbnailUrl": _get_poster_for_post(post),
                "uploadDate": seo_data.get("publishedTime", ""),
                "name": post.get("title", ""),
                "description": seo_data.get("description", ""),
                "width": video.get("width", 1280),
                "height": video.get("height", 720),
                "contentUrl": video.get("directUrl", ""),
                "embedUrl": post.get("telegramLink", ""),
            }
            if video.get("duration"):
                dur = video["duration"]
                if isinstance(dur, (int, float)) or re.match(r"^\d+(\.\d+)?$", str(dur)):
                    video_schema["duration"] = f"PT{dur}S"
                elif str(dur).startswith("PT"):
                    video_schema["duration"] = dur
            schema["video"] = video_schema

    return json.dumps(schema, ensure_ascii=False)


def generate_article_schema(article: dict, seo_data: dict, lang: str = "ru") -> str:
    """Generate Article Schema.org JSON-LD for an article.

    Args:
        article: Article dict with fields: title, content, plainDescription, thumbnail, date, etc.
        seo_data: Dict with SEO fields: ogUrl, publishedTime, modifiedTime, description, keywords.
        lang: Language code.
    """
    current_year = _get_current_year()

    # Calculate word count
    content_text = article.get("content") or ""
    if content_text:
        plain_text = re.sub(r"<[^>]+>", "", content_text)
    else:
        plain_text = article.get("plainDescription") or ""
    word_count = len(plain_text.split()) if plain_text else 0

    schema: Dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": article.get("title", ""),
        "url": seo_data.get("ogUrl", ""),
        "datePublished": seo_data.get("publishedTime", ""),
        "dateModified": seo_data.get("modifiedTime", ""),
        "description": seo_data.get("description", ""),
        "inLanguage": "ru-RU" if lang == "ru" else "en-US",
        "publisher": {
            "@type": "Organization",
            "name": SITE_AUTHOR,
            "url": SITE_URL,
            "logo": {"@type": "ImageObject", "url": LOGO_EXTERNAL_URL},
        },
        "mainEntityOfPage": {"@type": "WebPage", "@id": seo_data.get("ogUrl", "")},
        "author": {"@type": "Organization", "name": SITE_AUTHOR},
        "articleSection": GOOGLE_NEWS_CATEGORY,
        "wordCount": word_count,
        "copyrightHolder": {"@type": "Organization", "name": SITE_AUTHOR},
        "copyrightYear": current_year,
    }

    # Thumbnail image
    thumbnail = article.get("thumbnail") or DEFAULT_THUMBNAIL
    if thumbnail and thumbnail != DEFAULT_THUMBNAIL:
        schema["image"] = {"@type": "ImageObject", "url": thumbnail}
        schema["thumbnailUrl"] = thumbnail

    # Keywords
    if seo_data.get("keywords"):
        schema["keywords"] = seo_data["keywords"]

    return json.dumps(schema, ensure_ascii=False)


def generate_breadcrumb_schema(items: list) -> str:
    """Generate BreadcrumbList Schema.org JSON-LD.

    Args:
        items: List of dicts with 'name' and 'url' keys.
            Example: [{'name': 'Главная', 'url': 'https://...'}, ...]
    """
    schema = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": index + 1,
                "name": item["name"],
                "item": item["url"],
            }
            for index, item in enumerate(items)
        ],
    }
    return json.dumps(schema, ensure_ascii=False)


def generate_item_list_schema(posts: list, lang: str = "ru") -> str:
    """Generate ItemList Schema.org JSON-LD (30 items).

    Args:
        posts: List of post dicts with fields: title, id, postUrl, postUrlEn.
        lang: Language code.
    """
    schema = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": "Лента публикаций SOCHIAUTOPARTS" if lang == "ru" else "Publications Feed SOCHIAUTOPARTS",
        "description": SITE_DESCRIPTION_RU if lang == "ru" else SITE_DESCRIPTION_EN,
        "numberOfItems": len(posts),
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": index + 1,
                "url": post.get("postUrlEn" if lang == "en" else "postUrl", _post_url(post.get("id", ""), lang)),
                "name": post.get("title", ""),
            }
            for index, post in enumerate(posts[:POSTS_PER_PAGE])
        ],
    }
    return json.dumps(schema, ensure_ascii=False)


def generate_faq_schema(lang: str = "ru") -> str:
    """Generate FAQ Schema.org JSON-LD.

    FAQ content matches the real site's FAQ schema.
    """
    faqs = (
        [
            {
                "q": "Что такое SOCHIAUTOPARTS?",
                "a": "SOCHIAUTOPARTS — глобальный медиа-канал о мировых автомобильных новостях, экспертных обзорах и тест-драйвах.",
            },
            {
                "q": "Как подписаться на канал?",
                "a": "Подпишитесь на наш Telegram-канал @sochiautoparts для ежедневных обновлений автоновостей со всего мира.",
            },
            {
                "q": "Какие автомобили вы обозреваете?",
                "a": "Мы обозреваем автомобили всех марок: от бюджетных до премиум сегмента, включая электромобили.",
            },
        ]
        if lang == "ru"
        else [
            {
                "q": "What is SOCHIAUTOPARTS?",
                "a": "SOCHIAUTOPARTS is a global media channel covering worldwide automotive news, expert reviews and test drives.",
            },
            {
                "q": "How to subscribe?",
                "a": "Subscribe to our Telegram channel @sochiautoparts for daily global auto news updates.",
            },
            {
                "q": "What cars do you review?",
                "a": "We review cars of all brands: from budget to premium segment, including electric vehicles.",
            },
        ]
    )
    schema = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": faq["q"],
                "acceptedAnswer": {"@type": "Answer", "text": faq["a"]},
            }
            for faq in faqs
        ],
    }
    return json.dumps(schema, ensure_ascii=False)


def generate_product_schema(product: dict, lang: str = "ru") -> str:
    """Generate Product Schema.org JSON-LD.

    Args:
        product: Product dict with fields: name, image, description, vendor/brand,
                 model, category, categoryId, price, currency, available, feedName, id.
        lang: Language code.
    """
    description = (product.get("description") or product.get("name", ""))[:200]
    description = re.sub(r"&nbsp;", " ", description)
    description = re.sub(r"<[^>]+>", "", description)

    cat_name = product.get("category", "")
    if isinstance(cat_name, dict):
        cat_name = cat_name.get(lang, cat_name.get("ru", ""))
    cat_id = product.get("categoryId") or product.get("category_id", "")

    canonical_url = f"{SITE_URL}/shop/{product.get('id', '')}"
    availability = (
        "https://schema.org/InStock"
        if product.get("available", False)
        else "https://schema.org/OutOfStock"
    )

    schema: Dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": product.get("name", ""),
        "image": product.get("image") or DEFAULT_THUMBNAIL,
        "description": description,
        "category": cat_name,
        "offers": {
            "@type": "Offer",
            "url": canonical_url,
            "priceCurrency": product.get("currency", "RUB"),
            "price": product.get("price", 0),
            "availability": availability,
            "seller": {
                "@type": "Organization",
                "name": product.get("feedName", SITE_AUTHOR),
            },
        },
    }

    # Brand
    vendor = product.get("vendor") or product.get("brand", "")
    if vendor:
        schema["brand"] = {"@type": "Brand", "name": vendor}

    # Model
    model = product.get("model", "")
    if model:
        schema["model"] = model

    return json.dumps(schema, ensure_ascii=False)


# =============================================================================
# Verification meta tags
# =============================================================================

def generate_verification_meta_tags() -> str:
    """Generate verification meta tags.

    Supports both 'name' and 'property' based meta tags.
    """
    if not VERIFICATION_META_TAGS or not isinstance(VERIFICATION_META_TAGS, list):
        return ""

    tags = []
    for tag in VERIFICATION_META_TAGS:
        if not isinstance(tag, dict):
            continue
        if tag.get("name") and tag.get("content"):
            _tag_name = tag["name"]
            _tag_content = tag["content"]
            tags.append(
                f'<meta name="{escape_html(_tag_name)}" content="{escape_html(_tag_content)}" />'
            )
        elif tag.get("property") and tag.get("content"):
            _tag_prop = tag["property"]
            _tag_content = tag["content"]
            tags.append(
                f'<meta property="{escape_html(_tag_prop)}" content="{escape_html(_tag_content)}" />'
            )

    return "\n".join(tags)


# =============================================================================
# Google Analytics 4 script
# =============================================================================

def generate_ga4_script(measurement_id: str = "G-2GZ7FKV6CK") -> str:
    """Generate Google Analytics 4 script.

    Includes event tracking for Telegram links, post clicks, AMP badge, and shop actions.
    Matches the Worker's generateGoogleAnalyticsScript function.
    """
    return f"""
<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id={measurement_id}" onerror="console.log('GA4 blocked or unavailable')"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  try {{
    gtag('js', new Date());
    gtag('config', '{measurement_id}', {{
      'page_title': document.title,
      'page_location': window.location.href,
      'send_page_view': true,
      'anonymize_ip': true
    }});
  }} catch(e) {{
    console.log('GA4 initialization error:', e);
  }}
  document.addEventListener('DOMContentLoaded', function() {{
    document.querySelectorAll('a[href*="t.me"], .btn-primary[href*="t.me"], .fab[href*="t.me"]').forEach(function(el) {{
      el.addEventListener('click', function() {{
        try {{ gtag('event', 'click_telegram', {{ 'event_category': 'engagement', 'event_label': 'telegram_cta', 'location': this.classList.contains('fab') ? 'fab' : 'header' }}); }} catch(e) {{}}
      }});
    }});
    document.querySelectorAll('.post-feed-title a, .post-feed-item h3 a').forEach(function(el) {{
      el.addEventListener('click', function() {{
        try {{ gtag('event', 'click_post', {{ 'event_category': 'engagement', 'event_label': 'post_card', 'post_title': this.textContent.trim().substring(0, 50) }}); }} catch(e) {{}}
      }});
    }});
    document.querySelectorAll('.amp-badge').forEach(function(el) {{
      el.addEventListener('click', function() {{
        try {{ gtag('event', 'click_amp', {{ 'event_category': 'engagement', 'event_label': 'amp_version' }}); }} catch(e) {{}}
      }});
    }});
    document.querySelectorAll('[data-admitad-id]').forEach(function(el) {{
      el.addEventListener('click', function() {{
        try {{ gtag('event', 'click_admitad', {{ 'event_category': 'affiliate', 'event_label': 'partner_link' }}); }} catch(e) {{}}
      }});
    }});
    document.querySelectorAll('.shop-product-card a, .shop-widget a').forEach(function(el) {{
      el.addEventListener('click', function() {{
        try {{ gtag('event', 'click_product', {{ 'event_category': 'shop', 'event_label': 'product_card' }}); }} catch(e) {{}}
      }});
    }});
  }});
</script>"""


# =============================================================================
# Sitemap generators
# =============================================================================

def generate_sitemap_index(
    total_post_sitemaps: int,
    total_product_sitemaps: int,
    has_archive: bool = True,
) -> str:
    """Generate sitemap-index.xml content.

    Args:
        total_post_sitemaps: Number of post sitemap files (sitemap-posts-N.xml).
        total_product_sitemaps: Number of product sitemap files (sitemap-products-N.xml).
        has_archive: Whether archive sitemap should be included.

    Returns:
        XML string for sitemap-index.xml.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    entries = []

    # Static sitemap
    entries.append(
        f"<sitemap>\n<loc>{SITE_URL}/sitemap.xml</loc>\n<lastmod>{now}</lastmod>\n</sitemap>"
    )

    # Paginated post sitemaps
    for i in range(1, total_post_sitemaps + 1):
        entries.append(
            f"<sitemap>\n<loc>{SITE_URL}/sitemap-posts-{i}.xml</loc>\n<lastmod>{now}</lastmod>\n</sitemap>"
        )

    # Language sitemaps
    entries.append(
        f"<sitemap>\n<loc>{SITE_URL}/sitemap-ru.xml</loc>\n<lastmod>{now}</lastmod>\n</sitemap>"
    )
    entries.append(
        f"<sitemap>\n<loc>{SITE_URL}/sitemap-en.xml</loc>\n<lastmod>{now}</lastmod>\n</sitemap>"
    )

    # AMP sitemap
    entries.append(
        f"<sitemap>\n<loc>{SITE_URL}/sitemap-amp.xml</loc>\n<lastmod>{now}</lastmod>\n</sitemap>"
    )

    # News sitemap
    entries.append(
        f"<sitemap>\n<loc>{SITE_URL}/sitemap-news.xml</loc>\n<lastmod>{now}</lastmod>\n</sitemap>"
    )

    # Tags sitemap
    entries.append(
        f"<sitemap>\n<loc>{SITE_URL}/sitemap-tags.xml</loc>\n<lastmod>{now}</lastmod>\n</sitemap>"
    )

    # Archive sitemap — DISABLED (archive feature removed)

    # Product sitemaps
    for pi in range(1, min(total_product_sitemaps + 1, 11)):
        entries.append(
            f"<sitemap>\n<loc>{SITE_URL}/sitemap-products-{pi}.xml</loc>\n<lastmod>{now}</lastmod>\n</sitemap>"
        )

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(entries)
        + "\n</sitemapindex>"
    )


def _static_url_entry(
    ru_path: str,
    en_path: str,
    changefreq: str = "monthly",
    priority: str = "0.5",
    lastmod: Optional[str] = None,
) -> str:
    """Build a pair of <url> entries (ru + en) with full hreflang alternates.

    Args:
        ru_path: Russian path, e.g. "/contacts".
        en_path: English path, e.g. "/en/contacts".
        changefreq: Change frequency value.
        priority: Priority value.
        lastmod: Last modification date (YYYY-MM-DD). Defaults to today.

    Returns:
        Two <url> XML blocks (ru then en) separated by a newline.
    """
    if lastmod is None:
        lastmod = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    ru_url = f"{SITE_URL}{ru_path}"
    en_url = f"{SITE_URL}{en_path}"

    return (
        f"<url>\n"
        f"<loc>{ru_url}</loc>\n"
        f"<lastmod>{lastmod}</lastmod>\n"
        f"<changefreq>{changefreq}</changefreq>\n"
        f"<priority>{priority}</priority>\n"
        f'<xhtml:link rel="alternate" hreflang="ru" href="{ru_url}"/>\n'
        f'<xhtml:link rel="alternate" hreflang="en" href="{en_url}"/>\n'
        f'<xhtml:link rel="alternate" hreflang="x-default" href="{ru_url}"/>\n'
        f"</url>\n"
        f"<url>\n"
        f"<loc>{en_url}</loc>\n"
        f"<lastmod>{lastmod}</lastmod>\n"
        f"<changefreq>{changefreq}</changefreq>\n"
        f"<priority>{priority}</priority>\n"
        f'<xhtml:link rel="alternate" hreflang="ru" href="{ru_url}"/>\n'
        f'<xhtml:link rel="alternate" hreflang="en" href="{en_url}"/>\n'
        f'<xhtml:link rel="alternate" hreflang="x-default" href="{ru_url}"/>\n'
        f"</url>"
    )


def generate_static_sitemap(lang: str = "ru") -> str:
    """Generate sitemap.xml with ALL static pages.

    Includes: homepage, articles listing, archive listing, shop, contacts,
    privacy, ads category pages, and rss.xml.

    Every URL has full xhtml:link alternates for ru, en, and x-default.

    Returns:
        XML string for sitemap.xml.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    urls = []

    # ── Homepage (ru + en) ──
    ru_home = f"{SITE_URL}/"
    en_home = f"{SITE_URL}/en/"
    urls.append(
        f"<url>\n"
        f"<loc>{ru_home}</loc>\n"
        f"<lastmod>{now}</lastmod>\n"
        f"<changefreq>hourly</changefreq>\n"
        f"<priority>1.0</priority>\n"
        f'<xhtml:link rel="alternate" hreflang="ru" href="{ru_home}"/>\n'
        f'<xhtml:link rel="alternate" hreflang="en" href="{en_home}"/>\n'
        f'<xhtml:link rel="alternate" hreflang="x-default" href="{ru_home}"/>\n'
        f'<xhtml:link rel="amphtml" href="{SITE_URL}/amp/"/>\n'
        f"</url>"
    )
    urls.append(
        f"<url>\n"
        f"<loc>{en_home}</loc>\n"
        f"<lastmod>{now}</lastmod>\n"
        f"<changefreq>hourly</changefreq>\n"
        f"<priority>1.0</priority>\n"
        f'<xhtml:link rel="alternate" hreflang="ru" href="{ru_home}"/>\n'
        f'<xhtml:link rel="alternate" hreflang="en" href="{en_home}"/>\n'
        f'<xhtml:link rel="alternate" hreflang="x-default" href="{ru_home}"/>\n'
        f'<xhtml:link rel="amphtml" href="{SITE_URL}/en/amp/"/>\n'
        f"</url>"
    )

    # ── Articles listing ──
    urls.append(_static_url_entry("/articles", "/en/articles", "weekly", "0.8", now))

    # ── Archive listing — DISABLED (archive feature removed) ──

    # ── Shop ──
    urls.append(_static_url_entry(SHOP_PATH, SHOP_PATH_EN, "daily", "0.9", now))

    # ── Contacts ──
    urls.append(_static_url_entry(CONTACTS_PATH, f"/en{CONTACTS_PATH}", "monthly", "0.5", now))

    # ── Privacy ──
    urls.append(_static_url_entry(PRIVACY_PATH, f"/en{PRIVACY_PATH}", "monthly", "0.4", now))

    # ── Ads category pages (all PRODUCT_CATEGORIES) ──
    for cat_key in PRODUCT_CATEGORIES:
        urls.append(_static_url_entry(f"/ads/{cat_key}", f"/en/ads/{cat_key}", "weekly", "0.6", now))

    # ── RSS feed ──
    urls.append(
        f"<url>\n"
        f"<loc>{SITE_URL}/rss.xml</loc>\n"
        f"<lastmod>{now}</lastmod>\n"
        f"<changefreq>hourly</changefreq>\n"
        f"<priority>0.6</priority>\n"
        f"</url>"
    )

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
        'xmlns:xhtml="http://www.w3.org/1999/xhtml" '
        'xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">\n'
        + "\n".join(urls)
        + "\n</urlset>"
    )


def generate_posts_sitemap(posts: list, page_num: int, lang: str = "ru") -> str:
    """Generate sitemap-posts-N.xml for a batch of posts (max 1000 per file).

    Args:
        posts: List of post dicts for this page (already sliced).
        page_num: Page number (1-based).
        lang: Language code.

    Returns:
        XML string for sitemap-posts-N.xml.
    """
    if not posts:
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
            'xmlns:xhtml="http://www.w3.org/1999/xhtml" '
            'xmlns:image="http://www.google.com/schemas/sitemap-image/1.1"></urlset>'
        )

    urls = []
    for post in posts:
        post_id = post.get("id", "")
        post_url = post.get("postUrl") or _post_url(post_id, "ru")
        post_url_en = post.get("postUrlEn") or _post_url(post_id, "en")
        amp_url = post.get("ampUrl") or _amp_url(post_id, "ru")
        amp_url_en = post.get("ampUrlEn") or _amp_url(post_id, "en")

        # Date
        try:
            post_date = datetime.fromisoformat(str(post.get("date", ""))).strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            post_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Image tag
        image_tag = ""
        media = post.get("media", [])
        if isinstance(media, list) and len(media) > 0:
            first_media = media[0]
            if isinstance(first_media, dict) and first_media.get("type") == "photo":
                img_url = first_media.get("directUrl") or first_media.get("url", "")
                if img_url:
                    image_tag = f"\n<image:image><image:loc>{escape_xml(img_url)}</image:loc></image:image>"

        # Russian URL entry
        urls.append(
            f"<url>\n"
            f"<loc>{escape_xml(post_url)}</loc>\n"
            f"<lastmod>{post_date}</lastmod>\n"
            f"<changefreq>weekly</changefreq>\n"
            f"<priority>0.8</priority>\n"
            f'<xhtml:link rel="amphtml" href="{escape_xml(amp_url)}"/>\n'
            f'<xhtml:link rel="alternate" hreflang="en" href="{escape_xml(post_url_en)}"/>{image_tag}\n'
            f"</url>\n"
            f"<url>\n"
            f"<loc>{escape_xml(post_url_en)}</loc>\n"
            f"<lastmod>{post_date}</lastmod>\n"
            f"<changefreq>weekly</changefreq>\n"
            f"<priority>0.8</priority>\n"
            f'<xhtml:link rel="amphtml" href="{escape_xml(amp_url_en)}"/>\n'
            f'<xhtml:link rel="alternate" hreflang="ru" href="{escape_xml(post_url)}"/>{image_tag}\n'
            f"</url>"
        )

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
        'xmlns:xhtml="http://www.w3.org/1999/xhtml" '
        'xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">\n'
        + "\n".join(urls)
        + "\n</urlset>"
    )


def generate_language_sitemap(posts: list, lang: str = "ru") -> str:
    """Generate sitemap-ru.xml or sitemap-en.xml.

    Includes homepage, articles listing, posts, and articles.

    Args:
        posts: List of post dicts.
        lang: Language code ('ru' or 'en').

    Returns:
        XML string for language-specific sitemap.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    sitemap_posts = posts[:MAX_POSTS_SITEMAP]

    urls = []

    # Homepage
    homepage_url = f"{SITE_URL}/" if lang == "ru" else f"{SITE_URL}/en/"
    amp_home_url = f"{SITE_URL}/amp/" if lang == "ru" else f"{SITE_URL}/en/amp/"
    urls.append(
        f"<url>\n"
        f"<loc>{homepage_url}</loc>\n"
        f"<lastmod>{now}</lastmod>\n"
        f"<changefreq>hourly</changefreq>\n"
        f"<priority>1.0</priority>\n"
        f'<xhtml:link rel="amphtml" href="{amp_home_url}"/>\n'
        f"</url>"
    )

    # Articles listing
    articles_url = f"{SITE_URL}/articles/" if lang == "ru" else f"{SITE_URL}/en/articles/"
    urls.append(
        f"<url>\n"
        f"<loc>{articles_url}</loc>\n"
        f"<lastmod>{now}</lastmod>\n"
        f"<changefreq>daily</changefreq>\n"
        f"<priority>0.8</priority>\n"
        f"</url>"
    )

    # Post URLs
    for post in sitemap_posts:
        post_id = post.get("id", "")
        post_url = post.get("postUrl" if lang == "ru" else "postUrlEn") or _post_url(post_id, lang)
        amp_url = post.get("ampUrl" if lang == "ru" else "ampUrlEn") or _amp_url(post_id, lang)

        try:
            post_date = datetime.fromisoformat(str(post.get("date", ""))).strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            post_date = now

        # Image tag
        image_tag = ""
        media = post.get("media", [])
        if isinstance(media, list) and len(media) > 0:
            first_media = media[0]
            if isinstance(first_media, dict) and first_media.get("type") == "photo":
                img_url = first_media.get("directUrl") or first_media.get("url", "")
                if img_url:
                    image_tag = f"\n<image:image><image:loc>{escape_xml(img_url)}</image:loc></image:image>"

        urls.append(
            f"<url>\n"
            f"<loc>{escape_xml(post_url)}</loc>\n"
            f"<lastmod>{post_date}</lastmod>\n"
            f"<changefreq>weekly</changefreq>\n"
            f"<priority>0.7</priority>\n"
            f'<xhtml:link rel="amphtml" href="{escape_xml(amp_url)}"/>{image_tag}\n'
            f"</url>"
        )

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
        'xmlns:xhtml="http://www.w3.org/1999/xhtml" '
        'xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">\n'
        + "\n".join(urls)
        + "\n</urlset>"
    )


def generate_news_sitemap(posts: list, lang: str = "ru") -> str:
    """Generate sitemap-news.xml (posts from last 48 hours).

    Args:
        posts: List of post dicts.
        lang: Language code.

    Returns:
        XML string for sitemap-news.xml.
    """
    now = datetime.now(timezone.utc)
    two_days_ago = now - timedelta(hours=48)

    recent_posts = []
    for post in posts:
        try:
            post_date = datetime.fromisoformat(str(post.get("date", "")))
            if post_date.tzinfo is None:
                post_date = post_date.replace(tzinfo=timezone.utc)
            if post_date >= two_days_ago:
                recent_posts.append(post)
        except (ValueError, TypeError):
            continue

    urls = []
    for post in recent_posts:
        try:
            post_date = datetime.fromisoformat(str(post.get("date", "")))
            if post_date.tzinfo is None:
                post_date = post_date.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            post_date = now

        post_url = post.get("postUrl") or _post_url(post.get("id", ""), "ru")
        urls.append(
            f"<url>\n"
            f"<loc>{escape_xml(post_url)}</loc>\n"
            f"<news:news>\n"
            f"<news:publication>\n"
            f"<news:name>{escape_xml(SITE_AUTHOR)}</news:name>\n"
            f"<news:language>ru</news:language>\n"
            f"</news:publication>\n"
            f"<news:publication_date>{post_date.isoformat()}</news:publication_date>\n"
            f"<news:title>{escape_xml(post.get('title', ''))}</news:title>\n"
            f"<news:keywords>{escape_xml(', '.join(NEWS_KEYWORDS[:20]))}</news:keywords>\n"
            f"</news:news>\n"
            f"</url>"
        )

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
        'xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">\n'
        + "\n".join(urls)
        + "\n</urlset>"
    )


def generate_amp_sitemap(posts: list, lang: str = "ru") -> str:
    """Generate sitemap-amp.xml.

    Includes AMP homepage URLs and AMP post URLs.

    Args:
        posts: List of post dicts.
        lang: Language code.

    Returns:
        XML string for sitemap-amp.xml.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    sitemap_posts = posts[:MAX_POSTS_SITEMAP]

    urls = []

    # AMP homepages
    urls.append(
        f"<url>\n"
        f"<loc>{SITE_URL}/amp/</loc>\n"
        f"<lastmod>{now}</lastmod>\n"
        f"<changefreq>hourly</changefreq>\n"
        f"<priority>1.0</priority>\n"
        f"</url>"
    )
    urls.append(
        f"<url>\n"
        f"<loc>{SITE_URL}/en/amp/</loc>\n"
        f"<lastmod>{now}</lastmod>\n"
        f"<changefreq>hourly</changefreq>\n"
        f"<priority>1.0</priority>\n"
        f"</url>"
    )

    # AMP post URLs
    for post in sitemap_posts:
        post_id = post.get("id", "")
        amp_url = post.get("ampUrl") or _amp_url(post_id, "ru")
        amp_url_en = post.get("ampUrlEn") or _amp_url(post_id, "en")

        try:
            post_date = datetime.fromisoformat(str(post.get("date", ""))).strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            post_date = now

        urls.append(
            f"<url>\n"
            f"<loc>{escape_xml(amp_url)}</loc>\n"
            f"<lastmod>{post_date}</lastmod>\n"
            f"<changefreq>weekly</changefreq>\n"
            f"<priority>0.8</priority>\n"
            f"</url>"
        )
        urls.append(
            f"<url>\n"
            f"<loc>{escape_xml(amp_url_en)}</loc>\n"
            f"<lastmod>{post_date}</lastmod>\n"
            f"<changefreq>weekly</changefreq>\n"
            f"<priority>0.8</priority>\n"
            f"</url>"
        )

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls)
        + "\n</urlset>"
    )


def generate_tags_sitemap(hashtag_index: dict, lang: str = "ru") -> str:
    """Generate sitemap-tags.xml.

    Filters tags with < TAG_MIN_POSTS_FOR_SITEMAP posts to prevent
    thin-content tag pages from being indexed.

    Args:
        hashtag_index: Dict mapping tag -> post IDs or tag -> {posts: [...], count: N}.
        lang: Language code.

    Returns:
        XML string for sitemap-tags.xml.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Build tag -> post count map, filter mandatory hashtags
    mandatory_set = {"автоновости", "autonews", "carreviews", "globalautonews",
                     "тестдрайв", "автообзоры", "actualitésauto", "autonachrichten",
                     "汽车新闻", "noticiasdeautos", "أخبارالسيارات", "evnews", "carindustry"}

    tag_post_counts: Dict[str, int] = {}
    tag_last_dates: Dict[str, str] = {}

    for tag_key, tag_data in (hashtag_index or {}).items():
        clean_tag = re.sub(r"^#+", "", str(tag_key)).lower()
        if clean_tag in mandatory_set:
            continue

        if isinstance(tag_data, dict):
            post_ids = tag_data.get("posts", tag_data.get("post_ids", []))
            count = tag_data.get("count", len(post_ids) if isinstance(post_ids, list) else 0)
        elif isinstance(tag_data, list):
            post_ids = tag_data
            count = len(post_ids)
        else:
            continue

        tag_post_counts[clean_tag] = count

        # Try to find newest post date
        last_date = now
        if isinstance(post_ids, list) and len(post_ids) > 0:
            last_date = now  # Fallback
        tag_last_dates[clean_tag] = last_date

    # Filter by minimum posts
    urls = []
    for tag, count in tag_post_counts.items():
        if count < TAG_MIN_POSTS_FOR_SITEMAP:
            continue

        tag_encoded = url_quote(tag)
        lastmod = tag_last_dates.get(tag, now)

        urls.append(
            f"<url>\n"
            f"<loc>{SITE_URL}/tag/{tag_encoded}</loc>\n"
            f"<lastmod>{lastmod}</lastmod>\n"
            f"<changefreq>weekly</changefreq>\n"
            f"<priority>0.4</priority>\n"
            f'<xhtml:link rel="alternate" hreflang="en" href="{SITE_URL}/en/tag/{tag_encoded}"/>\n'
            f"</url>\n"
            f"<url>\n"
            f"<loc>{SITE_URL}/en/tag/{tag_encoded}</loc>\n"
            f"<lastmod>{lastmod}</lastmod>\n"
            f"<changefreq>weekly</changefreq>\n"
            f"<priority>0.4</priority>\n"
            f'<xhtml:link rel="alternate" hreflang="ru" href="{SITE_URL}/tag/{tag_encoded}"/>\n'
            f"</url>"
        )

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
        'xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
        + "\n".join(urls)
        + "\n</urlset>"
    )


def generate_products_sitemap(products: list, page_num: int) -> str:
    """Generate sitemap-products-N.xml.

    Args:
        products: List of product dicts for this page (already sliced).
        page_num: Page number (1-based).

    Returns:
        XML string for sitemap-products-N.xml.
    """
    if not products:
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
            'xmlns:xhtml="http://www.w3.org/1999/xhtml" '
            'xmlns:image="http://www.google.com/schemas/sitemap-image/1.1"></urlset>'
        )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    urls = []
    for product in products:
        product_id = product.get("id", "")
        product_url = f"{SITE_URL}/shop/{product_id}"
        product_url_en = f"{SITE_URL}/en/shop/{product_id}"

        image_tag = ""
        if product.get("image"):
            image_tag = f"\n<image:image><image:loc>{escape_xml(product['image'])}</image:loc></image:image>"

        urls.append(
            f"<url>\n"
            f"<loc>{escape_xml(product_url)}</loc>\n"
            f"<lastmod>{now}</lastmod>\n"
            f"<changefreq>daily</changefreq>\n"
            f"<priority>0.7</priority>\n"
            f'<xhtml:link rel="alternate" hreflang="ru" href="{escape_xml(product_url)}"/>\n'
            f'<xhtml:link rel="alternate" hreflang="en" href="{escape_xml(product_url_en)}"/>\n'
            f'<xhtml:link rel="alternate" hreflang="x-default" href="{escape_xml(product_url)}"/>{image_tag}\n'
            f"</url>\n"
            f"<url>\n"
            f"<loc>{escape_xml(product_url_en)}</loc>\n"
            f"<lastmod>{now}</lastmod>\n"
            f"<changefreq>daily</changefreq>\n"
            f"<priority>0.7</priority>\n"
            f'<xhtml:link rel="alternate" hreflang="ru" href="{escape_xml(product_url)}"/>\n'
            f'<xhtml:link rel="alternate" hreflang="en" href="{escape_xml(product_url_en)}"/>\n'
            f'<xhtml:link rel="alternate" hreflang="x-default" href="{escape_xml(product_url)}"/>{image_tag}\n'
            f"</url>"
        )

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
        'xmlns:xhtml="http://www.w3.org/1999/xhtml" '
        'xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">\n'
        + "\n".join(urls)
        + "\n</urlset>"
    )


def generate_archive_sitemap(posts: Optional[list] = None) -> str:
    """Generate sitemap-archive.xml with individual archive post URLs.

    Includes the archive listing pages (ru + en) and every individual
    /archive/post/{id} URL (ru + en) for all posts in the dataset,
    up to MAX_POSTS_SITEMAP entries.

    Args:
        posts: List of post dicts (same data used for post sitemaps).
            If None or empty, only the listing pages are included.

    Returns:
        XML string for sitemap-archive.xml.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    urls: List[str] = []

    # ── Archive listing page (ru) ──
    urls.append(
        f"<url>\n"
        f"  <loc>{SITE_URL}/archive</loc>\n"
        f"  <lastmod>{now}</lastmod>\n"
        f"  <changefreq>daily</changefreq>\n"
        f"  <priority>0.7</priority>\n"
        f'  <xhtml:link rel="alternate" hreflang="ru" href="{SITE_URL}/archive"/>\n'
        f'  <xhtml:link rel="alternate" hreflang="en" href="{SITE_URL}/en/archive"/>\n'
        f'  <xhtml:link rel="alternate" hreflang="x-default" href="{SITE_URL}/archive"/>\n'
        f"</url>"
    )

    # ── Archive listing page (en) ──
    urls.append(
        f"<url>\n"
        f"  <loc>{SITE_URL}/en/archive</loc>\n"
        f"  <lastmod>{now}</lastmod>\n"
        f"  <changefreq>daily</changefreq>\n"
        f"  <priority>0.7</priority>\n"
        f'  <xhtml:link rel="alternate" hreflang="ru" href="{SITE_URL}/archive"/>\n'
        f'  <xhtml:link rel="alternate" hreflang="en" href="{SITE_URL}/en/archive"/>\n'
        f'  <xhtml:link rel="alternate" hreflang="x-default" href="{SITE_URL}/archive"/>\n'
        f"</url>"
    )

    # ── Individual archive post pages ──
    if posts:
        archive_posts = posts[:MAX_POSTS_SITEMAP]
        for post in archive_posts:
            post_id = post.get("id", "")
            if not post_id:
                continue

            # Date
            try:
                post_date = datetime.fromisoformat(str(post.get("date", ""))).strftime("%Y-%m-%d")
            except (ValueError, TypeError):
                post_date = now

            ru_url = f"{SITE_URL}/archive/post/{post_id}"
            en_url = f"{SITE_URL}/en/archive/post/{post_id}"

            # Russian entry
            urls.append(
                f"<url>\n"
                f"  <loc>{ru_url}</loc>\n"
                f"  <lastmod>{post_date}</lastmod>\n"
                f"  <changefreq>monthly</changefreq>\n"
                f"  <priority>0.5</priority>\n"
                f'  <xhtml:link rel="alternate" hreflang="ru" href="{ru_url}"/>\n'
                f'  <xhtml:link rel="alternate" hreflang="en" href="{en_url}"/>\n'
                f'  <xhtml:link rel="alternate" hreflang="x-default" href="{ru_url}"/>\n'
                f"</url>"
            )

            # English entry
            urls.append(
                f"<url>\n"
                f"  <loc>{en_url}</loc>\n"
                f"  <lastmod>{post_date}</lastmod>\n"
                f"  <changefreq>monthly</changefreq>\n"
                f"  <priority>0.5</priority>\n"
                f'  <xhtml:link rel="alternate" hreflang="ru" href="{ru_url}"/>\n'
                f'  <xhtml:link rel="alternate" hreflang="en" href="{en_url}"/>\n'
                f'  <xhtml:link rel="alternate" hreflang="x-default" href="{ru_url}"/>\n'
                f"</url>"
            )

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
        'xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
        + "\n".join(urls)
        + "\n</urlset>"
    )


# =============================================================================
# robots.txt
# =============================================================================

def generate_robots_txt() -> str:
    """Generate robots.txt content.

    Matches the Worker v27.0-AUDITED output exactly.
    """
    return (
        f"# robots.txt for {SITE_URL}\n"
        f"# Updated: 2026-05-22 | v27.0-AUDITED\n"
        f"\n"
        f"# === General ===\n"
        f"User-agent: *\n"
        f"Allow: /\n"
        f"Allow: /ads/\n"
        f"Allow: /shop/\n"
        f"Allow: /shop/category/\n"
        f"Disallow: /api/\n"
        f"Disallow: /archive/\n"
        f"Disallow: /m/\n"
        f"Crawl-delay: 1\n"
        f"\n"
        f"# === Google ===\n"
        f"User-agent: Googlebot\n"
        f"Allow: /\n"
        f"Disallow: /api/\n"
        f"\n"
        f"# === Bing ===\n"
        f"User-agent: Bingbot\n"
        f"Allow: /\n"
        f"Disallow: /api/\n"
        f"Crawl-delay: 0\n"
        f"\n"
        f"# === Yandex ===\n"
        f"User-agent: Yandex\n"
        f"Allow: /\n"
        f"Disallow: /api/\n"
        f"Disallow: /m/\n"
        f"Crawl-delay: 0\n"
        f"Clean-param: page /\n"
        f"Clean-param: ysclid&yclid&_openstat&utm_source&utm_medium&utm_campaign&utm_content&utm_term&fbclid&gclid /\n"
        f"\n"
        f"# === Petalbot (Huawei) ===\n"
        f"User-agent: PetalBot\n"
        f"Allow: /\n"
        f"Disallow: /api/\n"
        f"Crawl-delay: 0\n"
        f"\n"
        f"# === Baidu ===\n"
        f"User-agent: Baiduspider\n"
        f"Allow: /\n"
        f"Disallow: /api/\n"
        f"Crawl-delay: 0\n"
        f"\n"
        f"# === Yahoo ===\n"
        f"User-agent: Slurp\n"
        f"Allow: /\n"
        f"Disallow: /api/\n"
        f"Crawl-delay: 0\n"
        f"\n"
        f"# === AI Crawlers - Limited Access ===\n"
        f"User-agent: GPTBot\n"
        f"Allow: /\n"
        f"Disallow: /api/\n"
        f"Crawl-delay: 10\n"
        f"\n"
        f"User-agent: ChatGPT-User\n"
        f"Allow: /\n"
        f"Disallow: /api/\n"
        f"\n"
        f"User-agent: CCBot\n"
        f"Allow: /\n"
        f"Disallow: /api/\n"
        f"Crawl-delay: 10\n"
        f"\n"
        f"User-agent: Google-Extended\n"
        f"Allow: /\n"
        f"Disallow: /api/\n"
        f"\n"
        f"User-agent: Applebot-Extended\n"
        f"Disallow: /\n"
        f"\n"
        f"User-agent: Bytespider\n"
        f"Disallow: /\n"
        f"\n"
        f"# === Sitemaps ===\n"
        f"Sitemap: {SITE_URL}/sitemap-index.xml\n"
        f"Sitemap: {SITE_URL}/sitemap.xml\n"
        f"Sitemap: {SITE_URL}/sitemap-news.xml\n"
    )


# =============================================================================
# manifest.json
# =============================================================================

def generate_manifest_json(lang: str = "ru") -> str:
    """Generate manifest.json for PWA.

    Matches the Worker's generateManifest function.

    Args:
        lang: Language code.

    Returns:
        JSON string for manifest.json.
    """
    manifest = {
        "name": SITE_NAME_RU if lang == "ru" else SITE_NAME_EN,
        "short_name": SITE_AUTHOR,
        "description": "Автомобильные новости" if lang == "ru" else "Automotive news",
        "start_url": "/" if lang == "ru" else "/en/",
        "display": "standalone",
        "background_color": "#F4F4F5",
        "theme_color": "#2481CC",
        "icons": [
            {
                "src": "/logo.jpg",
                "sizes": "640x640",
                "type": "image/jpeg",
            }
        ],
    }
    return json.dumps(manifest, ensure_ascii=False, indent=2)


# =============================================================================
# RSS feed
# =============================================================================

def _format_post_text_for_rss(text: str) -> str:
    """Format post text for RSS: escape HTML entities.

    Args:
        text: Raw post text.

    Returns:
        HTML-escaped text suitable for RSS content.
    """
    if not text or not isinstance(text, str):
        return ""
    return escape_html(text)


def generate_rss_feed(posts: list, articles: list, lang: str = "ru") -> str:
    """Generate RSS 2.0 feed with Media RSS extensions.

    Matches the Worker's generateRSSFeed function.

    Args:
        posts: List of post dicts.
        articles: List of article dicts.
        lang: Language code.

    Returns:
        RSS XML string.
    """
    now = datetime.now(timezone.utc)
    current_year = _get_current_year()

    rss_posts = posts[:MAX_POSTS_RSS]
    rss_articles = articles[:20] if articles else []

    # Generate post items
    post_items = []
    for post in rss_posts:
        raw_text = post.get("text", "")
        raw_text_with_tags = post.get("textWithHashtags") or raw_text
        description_text = _format_post_text_for_rss(raw_text) or "SOCHIAUTOPARTS Post"
        content_text = _format_post_text_for_rss(raw_text_with_tags) or "SOCHIAUTOPARTS Post"
        description_cdata = f"<![CDATA[{description_text}]]>"
        content_encoded = f"<![CDATA[{content_text}]]>"

        media_elements = ""
        enclosure_tags = ""

        media = post.get("media", [])
        if isinstance(media, list) and len(media) > 0:
            first_media = media[0]
            if isinstance(first_media, dict):
                media_url = escape_xml(first_media.get("directUrl", ""))
                media_title = escape_xml(post.get("title", ""))

                if first_media.get("type") == "photo":
                    width = first_media.get("width", 800)
                    height = first_media.get("height", 600)
                    media_elements = (
                        f'<media:content url="{media_url}" type="image/jpeg" medium="image" width="{width}" height="{height}">\n'
                        f'<media:title type="plain">{media_title}</media:title>\n'
                        f'<media:credit>{SITE_AUTHOR}</media:credit>\n'
                        f'</media:content>\n'
                        f'<media:thumbnail url="{media_url}" width="{width}" height="{height}"/>'
                    )
                    enclosure_tags = f'<enclosure url="{media_url}" type="image/jpeg" />'

                elif first_media.get("type") == "video":
                    poster_url = escape_xml(_get_poster_for_post(post))
                    width = first_media.get("width", 1280)
                    height = first_media.get("height", 720)
                    telegram_link = escape_xml(post.get("telegramLink", ""))
                    media_elements = (
                        f'<media:content url="{media_url}" type="video/mp4" medium="video" width="{width}" height="{height}">\n'
                        f'<media:title type="plain">{media_title}</media:title>\n'
                        f'<media:thumbnail url="{poster_url}" width="{width}" height="{height}"/>\n'
                        f'<media:credit>{SITE_AUTHOR}</media:credit>\n'
                        f'<media:player url="{telegram_link}"/>\n'
                        f'</media:content>'
                    )
                    enclosure_tags = f'<enclosure url="{media_url}" type="video/mp4" />'

        # Category tags
        keywords = post.get("keywords", [])
        if isinstance(keywords, list):
            category_tags = "".join(
                f"<category>{escape_xml(kw)}</category>" for kw in keywords[:5]
            )
        else:
            category_tags = ""

        post_url = escape_xml(post.get("postUrl") or _post_url(post.get("id", ""), lang))
        try:
            pub_date = datetime.fromisoformat(str(post.get("date", ""))).strftime("%a, %d %b %Y %H:%M:%S +0000")
        except (ValueError, TypeError):
            pub_date = now.strftime("%a, %d %b %Y %H:%M:%S +0000")

        source_url = f"{SITE_URL}/rss.xml" if lang == "ru" else f"{SITE_URL}/en/rss.xml"
        channel_title = SITE_NAME_RU if lang == "ru" else SITE_NAME_EN

        post_items.append(
            f"<item>\n"
            f"<title>{escape_xml(post.get('title', ''))}</title>\n"
            f"<link>{post_url}</link>\n"
            f'<guid isPermaLink="true">{post_url}</guid>\n'
            f"<pubDate>{pub_date}</pubDate>\n"
            f"<description>{description_cdata}</description>\n"
            f"<content:encoded>{content_encoded}</content:encoded>\n"
            f"<author>{SITE_AUTHOR}</author>\n"
            f'<source url="{source_url}">{escape_xml(channel_title)}</source>\n'
            f"{category_tags}\n"
            f"{media_elements + chr(10) if media_elements else ''}"
            f"{enclosure_tags + chr(10) if enclosure_tags else ''}"
            f"</item>"
        )

    # Generate article items
    article_items = []
    for article in rss_articles:
        article_url = _article_url(article.get("id", ""), lang)
        article_description = article.get("plainDescription") or article.get("title", "")
        description_cdata = f"<![CDATA[{article_description}]]>"

        media_elements = ""
        enclosure_tags = ""
        if article.get("thumbnail"):
            media_url = escape_xml(article["thumbnail"])
            _article_title = article.get("title", "")
            media_elements = (
                f'<media:content url="{media_url}" type="image/jpeg" medium="image">\n'
                f'<media:title type="plain">{escape_xml(_article_title)}</media:title>\n'
                f"<media:credit>{SITE_AUTHOR}</media:credit>\n"
                f"</media:content>\n"
                f'<media:thumbnail url="{media_url}"/>'
            )
            enclosure_tags = f'<enclosure url="{media_url}" type="image/jpeg"/>'

        try:
            pub_date = datetime.fromisoformat(str(article.get("date", ""))).strftime("%a, %d %b %Y %H:%M:%S +0000")
        except (ValueError, TypeError):
            pub_date = now.strftime("%a, %d %b %Y %H:%M:%S +0000")

        source_url = f"{SITE_URL}/rss.xml" if lang == "ru" else f"{SITE_URL}/en/rss.xml"
        channel_title = SITE_NAME_RU if lang == "ru" else SITE_NAME_EN
        category_label = "Статья" if lang == "ru" else "Article"

        article_items.append(
            f"<item>\n"
            f"<title>{escape_xml(article.get('title', ''))}</title>\n"
            f"<link>{escape_xml(article_url)}</link>\n"
            f'<guid isPermaLink="true">{escape_xml(article_url)}</guid>\n'
            f"<pubDate>{pub_date}</pubDate>\n"
            f"<description>{description_cdata}</description>\n"
            f"<author>{SITE_AUTHOR}</author>\n"
            f'<source url="{source_url}">{escape_xml(channel_title)}</source>\n'
            f"<category>{category_label}</category>\n"
            f"{media_elements + chr(10) if media_elements else ''}"
            f"{enclosure_tags + chr(10) if enclosure_tags else ''}"
            f"</item>"
        )

    # Combine items
    all_items = "\n".join(post_items + article_items)

    # Channel metadata
    channel_title = SITE_NAME_RU if lang == "ru" else SITE_NAME_EN
    channel_description = (
        f"Мировые автоновости, обзоры и тест-драйвы от SOCHIAUTOPARTS. "
        f"{len(rss_posts)} публикаций и {len(rss_articles)} статей в архиве."
        if lang == "ru"
        else f"Global automotive news, reviews and test drives by SOCHIAUTOPARTS. "
        f"{len(rss_posts)} posts and {len(rss_articles)} articles in archive."
    )
    rss_url = f"{SITE_URL}/rss.xml" if lang == "ru" else f"{SITE_URL}/en/rss.xml"

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" '
        'xmlns:media="http://search.yahoo.com/mrss/" '
        'xmlns:content="http://purl.org/rss/1.0/modules/content/" '
        'xmlns:atom="http://www.w3.org/2005/Atom" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:sy="http://purl.org/rss/1.0/modules/syndication/">\n'
        "<channel>\n"
        f"<title>{escape_xml(channel_title)}</title>\n"
        f"<link>{SITE_URL}</link>\n"
        f"<description>{escape_xml(channel_description)}</description>\n"
        f"<language>{lang}</language>\n"
        f"<lastBuildDate>{now.strftime('%a, %d %b %Y %H:%M:%S +0000')}</lastBuildDate>\n"
        f"<pubDate>{now.strftime('%a, %d %b %Y %H:%M:%S +0000')}</pubDate>\n"
        f"<ttl>60</ttl>\n"
        f"<generator>SOCHIAUTOPARTS Static Site Generator v1.0</generator>\n"
        f"<managingEditor>info@sochiautoparts.ru ({SITE_AUTHOR})</managingEditor>\n"
        f"<webMaster>info@sochiautoparts.ru ({SITE_AUTHOR})</webMaster>\n"
        f"<image>\n"
        f"<url>{LOGO_EXTERNAL_URL}</url>\n"
        f"<title>{escape_xml(channel_title)}</title>\n"
        f"<link>{SITE_URL}</link>\n"
        f"<width>{LOGO_WIDTH}</width>\n"
        f"<height>{LOGO_HEIGHT}</height>\n"
        f"</image>\n"
        f"<copyright>&#169; {current_year} {SITE_AUTHOR}. All rights reserved.</copyright>\n"
        f"<category>Autos</category>\n"
        f'<atom:link href="{escape_xml(rss_url)}" rel="self" type="application/rss+xml"/>\n'
        f"<sy:updatePeriod>hourly</sy:updatePeriod>\n"
        f"<sy:updateFrequency>1</sy:updateFrequency>\n"
        f"{all_items}\n"
        f"</channel>\n"
        f"</rss>"
    )


# =============================================================================
# Cookie consent HTML
# =============================================================================

def generate_cookie_consent_html(lang: str = "ru") -> str:
    """Generate cookie consent banner HTML + inline JS.

    Matches the Worker's cookie consent HTML on product/shop/archive pages.

    Args:
        lang: Language code.

    Returns:
        HTML string for the cookie consent banner.
    """
    privacy_url = _bp(f"/{PRIVACY_PATH.lstrip('/')}") if lang == "ru" else _bp(f"/en{PRIVACY_PATH}")

    if lang == "ru":
        text = f'Мы используем cookies для улучшения работы сайта. <a href="{privacy_url}">Подробнее</a>'
        accept = "Принять"
        decline = "Отклонить"
    else:
        text = f'We use cookies to improve site performance. <a href="{privacy_url}">Learn more</a>'
        accept = "Accept"
        decline = "Decline"

    accept_onclick = "localStorage.setItem('cookie_consent','accepted');document.getElementById('cookieConsent').classList.remove('active');"
    decline_onclick = "localStorage.setItem('cookie_consent','declined');document.getElementById('cookieConsent').classList.remove('active');"
    return (
        f'<div class="cookie-consent" id="cookieConsent">\n'
        f'<div class="cookie-consent-content">\n'
        f'<p class="cookie-consent-text">{text}</p>\n'
        f'<div class="cookie-consent-actions">\n'
        f'<button class="cookie-btn cookie-btn-accept" onclick="{accept_onclick}">{accept}</button>\n'
        f'<button class="cookie-btn cookie-btn-decline" onclick="{decline_onclick}">{decline}</button>\n'
        f'</div>\n</div>\n</div>'
    )


# =============================================================================
# Client scripts
# =============================================================================

def get_common_client_scripts(lang: str = "ru") -> str:
    """Generate common client-side JavaScript.

    Includes:
    - Theme toggle (light/dark)
    - Language switcher
    - Mobile menu toggle
    - Cookie consent logic
    - Search functionality

    Matches the Worker's getCommonClientScripts function.

    Args:
        lang: Language code.

    Returns:
        HTML <script> tag with all client-side JavaScript.
    """
    privacy_url = _bp(f"/{PRIVACY_PATH.lstrip('/')}") if lang == "ru" else _bp(f"/en{PRIVACY_PATH}")

    if lang == "ru":
        consent_text = "Мы используем файлы cookie для аналитики и улучшения работы сайта. Продолжая использование, вы соглашаетесь с нашей"
        consent_link = "Политикой конфиденциальности"
        accept_btn = "Принять"
        decline_btn = "Отклонить"
        no_results = "Ничего не найдено"
        search_error = "Ошибка поиска"
    else:
        consent_text = "We use cookies for analytics and to improve your experience. By continuing, you agree to our"
        consent_link = "Privacy Policy"
        accept_btn = "Accept"
        decline_btn = "Decline"
        no_results = "No results found"
        search_error = "Search error"

    return f"""
<script>
(function() {{
  var savedTheme = localStorage.getItem("theme") || "dark";
  document.documentElement.setAttribute("data-theme", savedTheme);
  function updateThemeButtons(theme) {{
    document.querySelectorAll(".theme-btn").forEach(function(btn) {{
      btn.classList.remove("active");
      if (btn.dataset.theme === theme) btn.classList.add("active");
    }});
  }}
  updateThemeButtons(savedTheme);
  document.querySelectorAll(".theme-btn").forEach(function(btn) {{
    btn.addEventListener("click", function() {{
      var theme = this.dataset.theme;
      document.documentElement.setAttribute("data-theme", theme);
      localStorage.setItem("theme", theme);
      updateThemeButtons(theme);
    }});
  }});
  var mobileMenuBtn = document.getElementById("mobileMenuBtn");
  var mainNav = document.getElementById("mainNav");
  if (mobileMenuBtn && mainNav) {{
    mobileMenuBtn.addEventListener("click", function() {{
      var isOpen = mainNav.classList.toggle("open");
      mobileMenuBtn.textContent = isOpen ? "✕" : "☰";
      mobileMenuBtn.setAttribute("aria-expanded", isOpen);
    }});
    document.addEventListener("click", function(e) {{
      if (!e.target.closest(".site-header")) {{
        mainNav.classList.remove("open");
        mobileMenuBtn.textContent = "☰";
        mobileMenuBtn.setAttribute("aria-expanded", "false");
      }}
    }});
  }}
  function initCookieConsent() {{
    var consent = localStorage.getItem('cookie_consent');
    if (consent) return;
    var banner = document.createElement('div');
    banner.className = 'cookie-consent active';
    banner.innerHTML = '<div class="cookie-consent-content">' +
      '<div class="cookie-consent-text">{consent_text} <a href="{privacy_url}" target="_blank">{consent_link}</a>.</div>' +
      '<div class="cookie-consent-actions">' +
      '<button class="cookie-btn cookie-btn-accept" id="cookieAccept">{accept_btn}</button>' +
      '<button class="cookie-btn cookie-btn-decline" id="cookieDecline">{decline_btn}</button>' +
      '</div></div>';
    document.body.appendChild(banner);
    document.getElementById('cookieAccept').addEventListener('click', function() {{
      localStorage.setItem('cookie_consent', 'accepted');
      banner.classList.remove('active');
      setTimeout(function() {{ banner.remove(); }}, 300);
    }});
    document.getElementById('cookieDecline').addEventListener('click', function() {{
      localStorage.setItem('cookie_consent', 'declined');
      banner.classList.remove('active');
      setTimeout(function() {{ banner.remove(); }}, 300);
    }});
  }}
  if (document.readyState === 'loading') {{
    document.addEventListener('DOMContentLoaded', initCookieConsent);
  }} else {{
    initCookieConsent();
  }}
  var searchInput = document.getElementById("searchInput");
  var searchBtn = document.getElementById("searchBtn");
  var searchResults = document.getElementById("searchResults");
  var searchTimeout = null;
  function escapeHTML(str) {{
    if (!str) return "";
    return str.replace(/[&<>"']/g, function(m) {{ return {{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}}[m]; }});
  }}
  function performSearch(query) {{
    if (!query || query.trim().length < 2) {{
      if (searchResults) searchResults.classList.remove("active");
      return;
    }}
    var currentLang = "{lang}";
    var basePath = "{BASE_PATH}";
    if (!window._searchIndex) {{
      var idxUrl = basePath + "/search-index.json";
      fetch(idxUrl).then(function(r) {{ return r.json(); }}).then(function(data) {{
        window._searchIndex = data;
        doSearch(query, currentLang, basePath);
      }}).catch(function(err) {{
        console.error("Search index load error:", err);
        if (searchResults) {{
          searchResults.innerHTML = '<div class="search-no-results">{search_error}</div>';
          searchResults.classList.add("active");
        }}
      }});
    }} else {{
      doSearch(query, currentLang, basePath);
    }}
  }}
  function doSearch(query, currentLang, basePath) {{
    var tokens = query.toLowerCase().split(/\\s+/).filter(function(t) {{ return t.length >= 2; }});
    if (tokens.length === 0) {{
      if (searchResults) searchResults.classList.remove("active");
      return;
    }}
    var idx = window._searchIndex;
    var inverted = idx.i || {{}};
    var titles = idx.t || {{}};
    var scoreMap = {{}};
    for (var ti = 0; ti < tokens.length; ti++) {{
      var ids = inverted[tokens[ti]];
      if (ids) {{
        for (var k = 0; k < ids.length; k++) {{
          var pid = ids[k];
          scoreMap[pid] = (scoreMap[pid] || 0) + 1;
        }}
      }}
    }}
    var sorted = Object.keys(scoreMap).sort(function(a, b) {{ return scoreMap[b] - scoreMap[a]; }}).slice(0, 20);
    if (sorted.length > 0) {{
      var html = "";
      sorted.forEach(function(pid) {{
        var postUrl = currentLang === "en" ? (basePath + "/en/post/" + pid) : (basePath + "/post/" + pid);
        var title = titles[pid] || titles[String(pid)] || "";
        html += '<a href="' + postUrl + '" class="search-result-item">';
        html += '<div class="search-result-title">' + escapeHTML(title) + '</div>';
        html += '</a>';
      }});
      if (searchResults) {{
        searchResults.innerHTML = html;
        searchResults.classList.add("active");
      }}
    }} else {{
      if (searchResults) {{
        searchResults.innerHTML = '<div class="search-no-results">{no_results}</div>';
        searchResults.classList.add("active");
      }}
    }}
  }}
  if (searchInput) {{
    searchInput.addEventListener("input", function() {{
      clearTimeout(searchTimeout);
      searchTimeout = setTimeout(function() {{
        performSearch(searchInput.value);
      }}, 300);
    }});
    searchInput.addEventListener("keydown", function(e) {{
      if (e.key === "Enter") {{
        e.preventDefault();
        performSearch(searchInput.value);
      }}
    }});
  }}
  if (searchBtn) {{
    searchBtn.addEventListener("click", function() {{
      if (searchInput) performSearch(searchInput.value);
    }});
  }}
  document.addEventListener("click", function(e) {{
    if (searchResults && !e.target.closest(".search-container")) {{
      searchResults.classList.remove("active");
    }}
  }});
  // Language switcher
  var langSelect = document.getElementById("langSelect");
  if (langSelect) {{
    langSelect.addEventListener("change", function() {{
      var selectedLang = this.value;
      var currentPath = window.location.pathname;
      var newPath;
      if (selectedLang === "en") {{
        if (currentPath.startsWith("/en")) {{
          newPath = currentPath;
        }} else {{
          newPath = "/en" + currentPath;
        }}
      }} else {{
        newPath = currentPath.replace(/^\\/en/, "") || "/";
      }}
      window.location.href = newPath;
    }});
  }}
  // Video click-to-play handler
  document.addEventListener("click", function(e) {{
    var thumb = e.target.closest(".video-thumbnail");
    if (thumb) {{
      var src = thumb.getAttribute("data-video-src");
      var type = thumb.getAttribute("data-video-type") || "video/mp4";
      if (src) {{
        var container = thumb.closest(".video-container");
        if (container) {{
          container.innerHTML = '<video src="' + src + '" controls autoplay playsinline referrerpolicy="no-referrer" style="width:100%;height:100%;object-fit:contain"><source src="' + src + '" type="' + type + '"></video>';
        }}
      }}
    }}
  }});
  // Matrix background animation — matching original Worker v27.0
  var matrixCanvas = document.getElementById("matrix-bg");
  if (matrixCanvas) {{
    var prefReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (prefReducedMotion || (navigator.hardwareConcurrency && navigator.hardwareConcurrency <= 2)) {{
      matrixCanvas.style.display = "none";
    }} else {{
      var mctx = matrixCanvas.getContext("2d");
      matrixCanvas.width = window.innerWidth;
      matrixCanvas.height = window.innerHeight;
      var matrixKeywords = ['#автозапчасти','#сочи','#запчастисочи','#авто','#автоновости','#autonews','#cars','#sochi','#автомобиль','#машина','#двигатель','#тормоза','#подвеска','#масло','#фильтр','#шиномонтаж','#кузов','#электрика','#рейтинг','#обзор'];
      var cols = Math.floor(matrixCanvas.width / 22);
      var drops = [];
      for (var mi = 0; mi < cols; mi++) {{ drops[mi] = Math.random() * -100; }}
      function drawMatrix() {{
        mctx.fillStyle = "rgba(15, 17, 21, 0.05)";
        mctx.fillRect(0, 0, matrixCanvas.width, matrixCanvas.height);
        for (var mj = 0; mj < drops.length; mj++) {{
          var t = matrixKeywords[Math.floor(Math.random() * matrixKeywords.length)];
          var r = Math.random();
          if (r > 0.95) {{
            mctx.shadowBlur = 30;
            mctx.shadowColor = "#FFFFFF";
            mctx.fillStyle = "#FFFFFF";
            mctx.font = "bold 18px monospace";
          }} else if (r > 0.8) {{
            mctx.shadowBlur = 20;
            mctx.shadowColor = "#CCCCCC";
            mctx.fillStyle = "#E0E0E0";
            mctx.font = "bold 16px monospace";
          }} else {{
            mctx.shadowBlur = 6;
            mctx.shadowColor = "#666666";
            mctx.fillStyle = "#707070";
            mctx.font = "12px monospace";
          }}
          mctx.fillText(t, mj * 22, drops[mj] * 22);
          mctx.shadowBlur = 0;
          if (drops[mj] * 22 > matrixCanvas.height && Math.random() > 0.97) {{
            drops[mj] = 0;
          }}
          drops[mj] += 0.25 + Math.random() * 0.3;
        }}
      }}
      setInterval(drawMatrix, 50);
      window.addEventListener("resize", function() {{
        matrixCanvas.width = window.innerWidth;
        matrixCanvas.height = window.innerHeight;
        cols = Math.floor(matrixCanvas.width / 22);
        drops = [];
        for (var ri = 0; ri < cols; ri++) {{ drops[ri] = Math.random() * -100; }}
      }});
    }}
  }}
}})();
</script>"""


# =============================================================================
# Module-level test / demo
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("SOCHIAUTOPARTS SEO Module — Standalone Test")
    print("=" * 60)

    # Test escape_html
    print("\n--- escape_html ---")
    print(escape_html('<script>alert("XSS")</script>'))
    print(escape_html("Tom & Jerry's \"cartoon\""))

    # Test escape_xml
    print("\n--- escape_xml ---")
    print(escape_xml('<tag attr="val">&data</tag>'))

    # Test meta tags
    print("\n--- generate_meta_tags ---")
    meta = generate_meta_tags(
        title="Тестовая страница | SOCHIAUTOPARTS",
        description="Описание тестовой страницы",
        url="https://sochiautoparts.ru/test",
        lang="ru",
    )
    print(meta[:500])

    # Test hreflang links
    print("\n--- generate_hreflang_links ---")
    print(generate_hreflang_links("/post/123"))
    print(generate_hreflang_links("/tag/автозапчасти"))
    print(generate_hreflang_links("/"))

    # Test WebSite schema
    print("\n--- generate_web_site_schema ---")
    print(generate_web_site_schema("ru"))

    # Test FAQ schema
    print("\n--- generate_faq_schema ---")
    print(generate_faq_schema("ru"))

    # Test breadcrumb schema
    print("\n--- generate_breadcrumb_schema ---")
    print(generate_breadcrumb_schema([
        {"name": "Главная", "url": "https://sochiautoparts.ru/"},
        {"name": "Магазин", "url": "https://sochiautoparts.ru/shop"},
    ]))

    # Test verification meta tags
    print("\n--- generate_verification_meta_tags ---")
    print(generate_verification_meta_tags())

    # Test GA4 script
    print("\n--- generate_ga4_script ---")
    print(generate_ga4_script()[:300])

    # Test robots.txt
    print("\n--- generate_robots_txt ---")
    print(generate_robots_txt()[:500])

    # Test manifest.json
    print("\n--- generate_manifest_json ---")
    print(generate_manifest_json("ru"))

    # Test sitemap index
    print("\n--- generate_sitemap_index ---")
    print(generate_sitemap_index(5, 3)[:500])

    # Test static sitemap
    print("\n--- generate_static_sitemap ---")
    print(generate_static_sitemap()[:500])

    # Test cookie consent
    print("\n--- generate_cookie_consent_html ---")
    print(generate_cookie_consent_html("ru")[:300])

    print("\n" + "=" * 60)
    print("SEO module test complete.")
