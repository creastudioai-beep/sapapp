"""
Configuration module for the SochiAutoParts static site generator.

Replicates the CONFIG object from the original Cloudflare Worker for sochiautoparts.ru.
All values are module-level constants for easy import and use throughout the generator.

Usage:
    from config import SITE_URL, CHANNEL_USERNAME, PRODUCT_CATEGORIES, ...
"""

# =============================================================================
# SITE CORE
# =============================================================================

SITE_URL: str = "https://sochiautoparts.ru"
SITE_NAME_RU: str = "SOCHIAUTOPARTS"
SITE_NAME_EN: str = "SOCHIAUTOPARTS"
SITE_DESCRIPTION_RU: str = (
    "Мировые автоновости, экспертные обзоры и тест-драйвы на SOCHIAUTOPARTS. "
    "Тренды глобального автопрома 2026. Электромобили, новые модели, технологии и аналитика рынка."
)
SITE_DESCRIPTION_EN: str = (
    "Global automotive news, expert reviews and test drives on SOCHIAUTOPARTS. "
    "Worldwide auto industry trends 2026. EVs, new models, technology and market analysis."
)
SITE_LANGUAGE_RU: str = "ru"
SITE_LANGUAGE_EN: str = "en"

# =============================================================================
# TELEGRAM CHANNEL
# =============================================================================

CHANNEL_USERNAME: str = "sochiautoparts"
CHANNEL_ID: str = "1001479468835"
CHANNEL_URL: str = f"https://t.me/{CHANNEL_USERNAME}"
CHANNEL_JOIN_URL: str = f"https://t.me/{CHANNEL_USERNAME}"

# =============================================================================
# PIPELINE DATA URLs
# Raw GitHub URLs from the creastudioai-beep/Main1 repository
# =============================================================================

PIPELINE_BASE_URL: str = (
    "https://raw.githubusercontent.com/creastudioai-beep/Main1/main"
)

# Posts data
POSTS_JSON_URL: str = f"{PIPELINE_BASE_URL}/posts.json"
POSTS_INDEX_URL: str = f"{PIPELINE_BASE_URL}/posts_index.json"

# Articles data
ARTICLES_JSON_URL: str = f"{PIPELINE_BASE_URL}/articles.json"
ARTICLES_INDEX_URL: str = f"{PIPELINE_BASE_URL}/articles_index.json"

# Tags data
TAGS_JSON_URL: str = f"{PIPELINE_BASE_URL}/tags.json"
POPULAR_TAGS_JSON_URL: str = f"{PIPELINE_BASE_URL}/popular_tags.json"

# Search index
SEARCH_INDEX_URL: str = f"{PIPELINE_BASE_URL}/search_index.json"

# Archive data (paginated)
ARCHIVE_INDEX_URL: str = f"{PIPELINE_BASE_URL}/archive_index.json"

# Products / shop data
PRODUCTS_JSON_URL: str = "https://raw.githubusercontent.com/creastudioai-beep/zap.online/main/products.json"
PRODUCTS_INDEX_URL: str = f"{PIPELINE_BASE_URL}/products_index.json"

# Categories data
CATEGORIES_JSON_URL: str = f"{PIPELINE_BASE_URL}/categories.json"

# Sitemap data
SITEMAP_DATA_URL: str = f"{PIPELINE_BASE_URL}/sitemap_data.json"

# RSS feed data
RSS_DATA_URL: str = f"{PIPELINE_BASE_URL}/rss_data.json"

# =============================================================================
# PAGINATION
# =============================================================================

POSTS_PER_PAGE: int = 30
MAX_POSTS: int = 10000
ARTICLES_PER_PAGE: int = 30

# =============================================================================
# POPULAR TAGS
# =============================================================================

POPULAR_TAGS_LIMIT: int = 50
POPULAR_TAGS_MIN_COUNT: int = 2

# =============================================================================
# SEARCH SETTINGS
# =============================================================================

SEARCH_MIN_QUERY_LENGTH: int = 2
SEARCH_MAX_RESULTS: int = 50
SEARCH_RESULTS_PER_PAGE: int = 20
SEARCH_CACHE_TTL: int = 3600  # seconds

# =============================================================================
# PRODUCT CATEGORIES
# Bilingual dictionary: key -> {ru: str, en: str}
# =============================================================================

PRODUCT_CATEGORIES: dict[str, dict[str, str]] = {
    "engine": {
        "ru": "Двигатель",
        "en": "Engine",
    },
    "transmission": {
        "ru": "Трансмиссия",
        "en": "Transmission",
    },
    "brakes": {
        "ru": "Тормозная система",
        "en": "Brakes",
    },
    "suspension": {
        "ru": "Подвеска",
        "en": "Suspension",
    },
    "electrical": {
        "ru": "Электрооборудование",
        "en": "Electrical",
    },
    "body": {
        "ru": "Кузов",
        "en": "Body",
    },
    "interior": {
        "ru": "Салон",
        "en": "Interior",
    },
    "cooling": {
        "ru": "Система охлаждения",
        "en": "Cooling System",
    },
    "exhaust": {
        "ru": "Выхлопная система",
        "en": "Exhaust System",
    },
    "steering": {
        "ru": "Рулевое управление",
        "en": "Steering",
    },
    "fuel": {
        "ru": "Топливная система",
        "en": "Fuel System",
    },
    "filters": {
        "ru": "Фильтры",
        "en": "Filters",
    },
    "lighting": {
        "ru": "Освещение",
        "en": "Lighting",
    },
    "clutch": {
        "ru": "Сцепление",
        "en": "Clutch",
    },
    "wheels": {
        "ru": "Колёса и шины",
        "en": "Wheels & Tires",
    },
}

# =============================================================================
# COLORS
# =============================================================================

COLORS: dict[str, str] = {
    "primary": "#2481CC",         # Blue (matching live site)
    "primary_dark": "#1D6FAD",
    "primary_light": "#E6F3FF",
    "secondary": "#2AABEE",       # Light blue
    "secondary_light": "#58A6FF",
    "accent": "#0088cc",          # Telegram blue
    "background": "#FFFFFF",
    "surface": "#F4F4F5",
    "text_primary": "#000000",
    "text_secondary": "#707579",
    "text_on_primary": "#FFFFFF",
    "divider": "#DADCE0",
    "error": "#D32F2F",
    "success": "#388E3C",
    "warning": "#F57C00",
    "info": "#1976D2",
    "header_bg": "#FFFFFF",
    "header_text": "#000000",
    "footer_bg": "#FFFFFF",
    "footer_text": "#707579",
    "card_bg": "#FFFFFF",
    "card_border": "#E8E8E8",
    "tag_bg": "#E6F3FF",
    "tag_text": "#2481CC",
}

# =============================================================================
# SEO SETTINGS
# =============================================================================

SEO_TITLE_TEMPLATE_RU: str = "{title} | SOCHIAUTOPARTS"
SEO_TITLE_TEMPLATE_EN: str = "{title} | SOCHIAUTOPARTS"
SEO_DEFAULT_TITLE_RU: str = "SOCHIAUTOPARTS - Мировые автоновости, обзоры и тест-драйвы"
SEO_DEFAULT_TITLE_EN: str = "SOCHIAUTOPARTS - Global Automotive News, Reviews & Test Drives"
SEO_DEFAULT_DESCRIPTION_RU: str = SITE_DESCRIPTION_RU
SEO_DEFAULT_DESCRIPTION_EN: str = SITE_DESCRIPTION_EN
SEO_OG_IMAGE: str = f"{SITE_URL}/og-image.png"
SEO_OG_TYPE: str = "website"
SEO_TWITTER_CARD: str = "summary_large_image"
SEO_CANONICAL_OVERRIDE: str | None = None  # Set to override canonical URL
SEO_ROBOTS_DEFAULT: str = "index, follow, max-image-preview:large"
SEO_NOINDEX_PATTERNS: list[str] = [
    "/search?",
    "/page/",
    "/api/",
]

# =============================================================================
# GOOGLE ANALYTICS
# =============================================================================

GA4_MEASUREMENT_ID: str = "G-2GZ7FKV6CK"
GA_ENABLED: bool = True

# =============================================================================
# LOGO
# =============================================================================

LOGO_URL: str = f"{SITE_URL}/static/logo.png"
LOGO_SVG_URL: str = f"{SITE_URL}/static/logo.svg"
LOGO_FAVICON_URL: str = f"{SITE_URL}/static/favicon.ico"
LOGO_APPLE_TOUCH_URL: str = f"{SITE_URL}/static/apple-touch-icon.png"
LOGO_ICON_192: str = f"{SITE_URL}/static/android-chrome-192x192.png"
LOGO_ICON_512: str = f"{SITE_URL}/static/android-chrome-512x512.png"

# =============================================================================
# SOCIAL LINKS
# =============================================================================

SOCIAL_LINKS: dict[str, str] = {
    "telegram": f"https://t.me/{CHANNEL_USERNAME}",
    "instagram": "https://www.instagram.com/sochi_auto_parts/",
}

# =============================================================================
# ARCHIVE SETTINGS
# =============================================================================

ARCHIVE_POSTS_PER_PAGE: int = 50
MAX_ARCHIVE_PAGES: int = 1800  # 90K posts / 50 per page = 1800 pages
ARCHIVE_ENABLED: bool = False  # Archive pages removed — no longer generated

# NOTE: Archive pages are now generated as static HTML by the Python generator
# using pipeline data (posts.json). The Cloudflare Worker proxies these pages
# and adds region-based affiliate filtering on top.

# =============================================================================
# GITHUB PAGES OUTPUT
# =============================================================================

GITHUB_PAGES_URL: str = "https://creastudioai-beep.github.io/sapapp"
GITHUB_PAGES_BASE_PATH: str = "/sapapp"  # Subpath for GitHub Pages deployment

# BASE_PATH: Prefix for ALL relative URLs in generated HTML.
# Must be EMPTY ("") because the Cloudflare Worker proxies GitHub Pages
# at the root domain sochiautoparts.ru.  The Worker maps:
#   sochiautoparts.ru/path  →  creastudioai-beep.github.io/sapapp/path
# If BASE_PATH were "/sapapp", links in the HTML would point to
# /sapapp/path which the browser resolves to sochiautoparts.ru/sapapp/path,
# and the Worker would then fetch creastudioai-beep.github.io/sapapp/sapapp/path
# — a double-prefix 404.
BASE_PATH: str = ""

# =============================================================================
# GITHUB REPOSITORY CONFIG
# Repository that will host the static site
# =============================================================================

GITHUB_REPO: dict[str, str] = {
    "owner": "sochiautoparts",
    "name": "sochiautoparts.github.io",
    "branch": "main",
    "url": "https://github.com/sochiautoparts/sochiautoparts.github.io",
    "pages_url": "https://sochiautoparts.github.io",
    "api_url": "https://api.github.com/repos/sochiautoparts/sochiautoparts.github.io",
    "clone_url": "https://github.com/sochiautoparts/sochiautoparts.github.io.git",
}

# =============================================================================
# SHOP CONFIGURATION
# =============================================================================

SHOP_ZAP_ONLINE_URL: str = "https://sochiautoparts.zap-online.ru"
SHOP_CATALOG_URL: str = f"{SHOP_ZAP_ONLINE_URL}/catalog"
SHOP_CART_URL: str = f"{SHOP_ZAP_ONLINE_URL}/cart"
SHOP_SEARCH_URL: str = f"{SHOP_ZAP_ONLINE_URL}/search"
SHOP_API_URL: str = f"{SHOP_ZAP_ONLINE_URL}/api"

# Products data source (pipeline)
PRODUCTS_DATA_URL: str = PRODUCTS_JSON_URL
PRODUCTS_INDEX_DATA_URL: str = PRODUCTS_INDEX_URL

# Product display settings
PRODUCTS_PER_PAGE: int = 30
PRODUCTS_IMAGE_PLACEHOLDER: str = f"{SITE_URL}/static/product-placeholder.png"
PRODUCTS_DEFAULT_IMAGE: str = f"{SITE_URL}/static/no-image.png"
PRODUCTS_CURRENCY_RU: str = "руб."
PRODUCTS_CURRENCY_EN: str = "RUB"

# =============================================================================
# ADMITAD CONFIGURATION
# Affiliate marketing integration with 8 categories
# =============================================================================

# Admitad programs are loaded dynamically from the pipeline JSON:
# https://raw.githubusercontent.com/creastudioai-beep/pr/main/admitad_ads.json
# No static ADMITAD_CONFIG — all partner data comes from the pipeline.
ADMITAD_CONFIG: dict[str, dict[str, str]] = {
    "autoparts": {
        "ru": "Автозапчасти",
        "en": "Auto Parts",
        "url": "https://ujhjj.com/g/on8kt46xpp3c08bd9d2c648980e865/",
        "logo": "https://cdn.admitad-connect.com/public/images/brands/autoparts.png",
        "icon": "🔧",
    },
    "autoinsurance": {
        "ru": "Автострахование",
        "en": "Car Insurance",
        "url": "https://ujhjj.com/g/on8kt46xpp3c08bd9d2c648980e865/",
        "logo": "",
        "icon": "🛡️",
    },
    "tires": {
        "ru": "Шины и диски",
        "en": "Tires & Wheels",
        "url": "https://ujhjj.com/g/on8kt46xpp3c08bd9d2c648980e865/",
        "logo": "",
        "icon": "🛞",
    },
    "checkauto": {
        "ru": "Проверка авто",
        "en": "Car Check",
        "url": "https://ujhjj.com/g/on8kt46xpp3c08bd9d2c648980e865/",
        "logo": "",
        "icon": "🔍",
    },
    "autorent": {
        "ru": "Прокат авто",
        "en": "Car Rental",
        "url": "https://ujhjj.com/g/on8kt46xpp3c08bd9d2c648980e865/",
        "logo": "",
        "icon": "🚗",
    },
    "tools": {
        "ru": "Инструменты",
        "en": "Tools",
        "url": "https://ujhjj.com/g/on8kt46xpp3c08bd9d2c648980e865/",
        "logo": "",
        "icon": "🧰",
    },
    "coupons": {
        "ru": "Купоны и скидки",
        "en": "Coupons & Deals",
        "url": "https://ujhjj.com/g/on8kt46xpp3c08bd9d2c648980e865/",
        "logo": "",
        "icon": "🏷️",
    },
}

# =============================================================================
# NEWS KEYWORDS
# Used for classifying and tagging posts as news
# =============================================================================

NEWS_KEYWORDS: list[str] = [
    "акция",
    "скидка",
    "распродажа",
    "новинка",
    "поступление",
    "в наличии",
    "под заказ",
    "доставка",
    "срочная доставка",
    "аналог",
    "замена",
    "оригинал",
    "неоригинал",
    "б/у",
    "контрактный",
    "разборка",
    "капремонт",
    "диагностика",
    "то",
    "техобслуживание",
    "масло",
    "фильтр",
    "тормозные колодки",
    "диск",
    "амортизатор",
    "свеча",
    "ремень",
    "ролик",
    "помпа",
    "радиатор",
    "стартер",
    "генератор",
    "компрессор",
    "форсунка",
    "турбина",
    "катушка",
    "датчик",
    "поворотник",
    "фара",
    "зеркало",
    "бампер",
    "крыло",
    "капот",
    "дверь",
    "стекло",
    "салон",
    "сиденье",
    "руль",
    "приборная панель",
    "головное устройство",
    "сигнализация",
    "видеорегистратор",
    "парктроник",
    "камера заднего вида",
]

# =============================================================================
# MANDATORY HASHTAGS
# Every post must include these hashtags
# =============================================================================

MANDATORY_HASHTAGS: list[str] = [
    "#сочиавтозапчасти",
    "#автозапчасти",
    "#сочи",
    "#запчастисочи",
]

# =============================================================================
# VERIFICATION META TAGS
# For webmaster tools and platform verification
# =============================================================================

VERIFICATION_META_TAGS: dict[str, str] = {
    "verify-admitad": "3c08bd9d2c",
    "takprodam-verification": "cf451bd9-e5de-413f-990b-147d25c657e2",
}

# =============================================================================
# BUILD / GENERATOR SETTINGS
# =============================================================================

OUTPUT_DIR: str = "output"  # Relative to project root
STATIC_DIR: str = "static"  # Source static files
TEMPLATES_DIR: str = "site_generator/templates"  # Jinja2 / HTML templates

# Cache settings
CACHE_DIR: str = "data/cache"
CACHE_TTL: int = 3600  # Default cache TTL in seconds
CACHE_ENABLED: bool = True

# Concurrency
MAX_CONCURRENT_FETCHES: int = 5
FETCH_TIMEOUT: int = 30  # seconds
FETCH_RETRY_COUNT: int = 3
FETCH_RETRY_DELAY: float = 1.0  # seconds

# =============================================================================
# LOCALE / I18N
# =============================================================================

SUPPORTED_LANGUAGES: list[str] = ["ru", "en"]
DEFAULT_LANGUAGE: str = "ru"
LANGUAGE_NAMES: dict[str, str] = {
    "ru": "Русский",
    "en": "English",
}
LANGUAGE_PATHS: dict[str, str] = {
    "ru": "",       # Russian at root
    "en": "/en",    # English at /en subpath
}

# =============================================================================
# DATE / TIME FORMATS
# =============================================================================

DATE_FORMAT_RU: str = "%d.%m.%Y"
DATE_FORMAT_EN: str = "%Y-%m-%d"
DATETIME_FORMAT_RU: str = "%d.%m.%Y %H:%M"
DATETIME_FORMAT_EN: str = "%Y-%m-%d %H:%M"
TIMEZONE: str = "Europe/Moscow"  # MSK (UTC+3)

# =============================================================================
# SITEMAP SETTINGS
# =============================================================================

SITEMAP_ENABLED: bool = True
SITEMAP_FILENAME: str = "sitemap.xml"
SITEMAP_CHANGEFREQ_POSTS: str = "daily"
SITEMAP_CHANGEFREQ_ARTICLES: str = "weekly"
SITEMAP_CHANGEFREQ_STATIC: str = "monthly"
SITEMAP_PRIORITY_HOME: float = 1.0
SITEMAP_PRIORITY_POST: float = 0.8
SITEMAP_PRIORITY_ARTICLE: float = 0.7
SITEMAP_PRIORITY_TAG: float = 0.5
SITEMAP_PRIORITY_CATEGORY: float = 0.6
SITEMAP_MAX_URLS: int = 50000

# =============================================================================
# RSS FEED SETTINGS
# =============================================================================

RSS_ENABLED: bool = True
RSS_FILENAME: str = "feed.xml"
RSS_TITLE_RU: str = "SOCHIAUTOPARTS — Лента новостей"
RSS_TITLE_EN: str = "SOCHIAUTOPARTS — News Feed"
RSS_DESCRIPTION_RU: str = SITE_DESCRIPTION_RU
RSS_DESCRIPTION_EN: str = SITE_DESCRIPTION_EN
RSS_LANGUAGE: str = "ru"
RSS_ITEM_COUNT: int = 50
RSS_TTL: int = 60  # minutes

# =============================================================================
# MANIFEST / PWA
# =============================================================================

PWA_ENABLED: bool = True
PWA_MANIFEST_NAME_RU: str = "SOCHIAUTOPARTS"
PWA_MANIFEST_NAME_EN: str = "SOCHIAUTOPARTS"
PWA_MANIFEST_SHORT_NAME_RU: str = "SAP"
PWA_MANIFEST_SHORT_NAME_EN: str = "SAP"
PWA_MANIFEST_THEME_COLOR: str = COLORS["primary"]
PWA_MANIFEST_BG_COLOR: str = COLORS["background"]
PWA_MANIFEST_DISPLAY: str = "standalone"

# =============================================================================
# SECURITY HEADERS
# =============================================================================

SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "SAMEORIGIN",
    "X-XSS-Protection": "1; mode=block",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}

# =============================================================================
# BREADCRUMB SETTINGS
# =============================================================================

BREADCRUMB_HOME_RU: str = "Главная"
BREADCRUMB_HOME_EN: str = "Home"
BREADCRUMB_NEWS_RU: str = "Новости"
BREADCRUMB_NEWS_EN: str = "News"
BREADCRUMB_ARTICLES_RU: str = "Статьи"
BREADCRUMB_ARTICLES_EN: str = "Articles"
BREADCRUMB_CATALOG_RU: str = "Каталог"
BREADCRUMB_CATALOG_EN: str = "Catalog"
BREADCRUMB_ARCHIVE_RU: str = "Архив"
BREADCRUMB_ARCHIVE_EN: str = "Archive"
BREADCRUMB_SEARCH_RU: str = "Поиск"
BREADCRUMB_SEARCH_EN: str = "Search"

# =============================================================================
# CONTACT INFORMATION
# =============================================================================

CONTACT_PHONE: str = ""
CONTACT_PHONE_HREF: str = ""
CONTACT_EMAIL: str = "pr@sochiautoparts.ru"
CONTACT_EMAIL_HREF: str = "mailto:pr@sochiautoparts.ru"
CONTACT_ADDRESS_RU: str = "г. Сочи, Краснодарский край, Россия"
CONTACT_ADDRESS_EN: str = "Sochi, Krasnodar Krai, Russia"
CONTACT_WORKING_HOURS_RU: str = "Круглосуточно (онлайн)"
CONTACT_WORKING_HOURS_EN: str = "24/7 (online)"

# =============================================================================
# FEATURE FLAGS
# =============================================================================

FEATURE_SHOP_ENABLED: bool = True
FEATURE_ARTICLES_ENABLED: bool = True
FEATURE_ARCHIVE_ENABLED: bool = False  # Archive pages removed from site
FEATURE_SEARCH_ENABLED: bool = True
FEATURE_RSS_ENABLED: bool = True
FEATURE_SITEMAP_ENABLED: bool = True
FEATURE_ADMITAD_ENABLED: bool = True
FEATURE_PWA_ENABLED: bool = True
FEATURE_DARK_MODE: bool = True
FEATURE_ANALYTICS: bool = True

# =============================================================================
# MISCELLANEOUS
# =============================================================================

GENERATOR_NAME: str = "SochiAutoParts Static Site Generator"
GENERATOR_VERSION: str = "1.0.0"
CURRENT_YEAR: int = 2026  # Updated at build time
COPYRIGHT_RU: str = f"© {CURRENT_YEAR} {SITE_NAME_RU}"
COPYRIGHT_EN: str = f"© {CURRENT_YEAR} {SITE_NAME_EN}"

# Maximum number of related posts to show
RELATED_POSTS_COUNT: int = 6

# Maximum number of recent posts to show in sidebar
RECENT_POSTS_COUNT: int = 10

# Image optimization
IMAGE_LAZY_LOADING: bool = True
IMAGE_QUALITY: int = 80
IMAGE_MAX_WIDTH: int = 1200
IMAGE_THUMBNAIL_WIDTH: int = 300
IMAGE_THUMBNAIL_HEIGHT: int = 200

# Excerpt / preview length
EXCERPT_LENGTH_RU: int = 200  # characters
EXCERPT_LENGTH_EN: int = 300  # characters

# API rate limiting
API_RATE_LIMIT_PER_MINUTE: int = 60

# =============================================================================
# CONVENIENCE: Combined CONFIG dict (mirrors the original Worker CONFIG object)
# =============================================================================

CONFIG: dict = {
    "site_url": SITE_URL,
    "site_name_ru": SITE_NAME_RU,
    "site_name_en": SITE_NAME_EN,
    "site_description_ru": SITE_DESCRIPTION_RU,
    "site_description_en": SITE_DESCRIPTION_EN,
    "channel_username": CHANNEL_USERNAME,
    "channel_id": CHANNEL_ID,
    "channel_url": CHANNEL_URL,
    "channel_join_url": CHANNEL_JOIN_URL,
    "pipeline_base_url": PIPELINE_BASE_URL,
    "posts_json_url": POSTS_JSON_URL,
    "posts_index_url": POSTS_INDEX_URL,
    "articles_json_url": ARTICLES_JSON_URL,
    "articles_index_url": ARTICLES_INDEX_URL,
    "tags_json_url": TAGS_JSON_URL,
    "popular_tags_json_url": POPULAR_TAGS_JSON_URL,
    "search_index_url": SEARCH_INDEX_URL,
    "archive_index_url": ARCHIVE_INDEX_URL,
    "products_json_url": PRODUCTS_JSON_URL,
    "products_index_url": PRODUCTS_INDEX_URL,
    "categories_json_url": CATEGORIES_JSON_URL,
    "sitemap_data_url": SITEMAP_DATA_URL,
    "rss_data_url": RSS_DATA_URL,
    "posts_per_page": POSTS_PER_PAGE,
    "max_posts": MAX_POSTS,
    "articles_per_page": ARTICLES_PER_PAGE,
    "popular_tags_limit": POPULAR_TAGS_LIMIT,
    "search_min_query_length": SEARCH_MIN_QUERY_LENGTH,
    "search_max_results": SEARCH_MAX_RESULTS,
    "product_categories": PRODUCT_CATEGORIES,
    "colors": COLORS,
    "ga4_measurement_id": GA4_MEASUREMENT_ID,
    "logo_url": LOGO_URL,
    "logo_svg_url": LOGO_SVG_URL,
    "logo_favicon_url": LOGO_FAVICON_URL,
    "social_links": SOCIAL_LINKS,
    "archive_posts_per_page": ARCHIVE_POSTS_PER_PAGE,
    "github_pages_url": GITHUB_PAGES_URL,
    "github_pages_base_path": GITHUB_PAGES_BASE_PATH,
    "base_path": BASE_PATH,
    "github_repo": GITHUB_REPO,
    "shop_zap_online_url": SHOP_ZAP_ONLINE_URL,
    "shop_catalog_url": SHOP_CATALOG_URL,
    "shop_cart_url": SHOP_CART_URL,
    "shop_search_url": SHOP_SEARCH_URL,
    "admitad_config": ADMITAD_CONFIG,
    "news_keywords": NEWS_KEYWORDS,
    "mandatory_hashtags": MANDATORY_HASHTAGS,
    "verification_meta_tags": VERIFICATION_META_TAGS,
    "output_dir": OUTPUT_DIR,
    "static_dir": STATIC_DIR,
    "templates_dir": TEMPLATES_DIR,
    "supported_languages": SUPPORTED_LANGUAGES,
    "default_language": DEFAULT_LANGUAGE,
    "seo_title_template_ru": SEO_TITLE_TEMPLATE_RU,
    "seo_title_template_en": SEO_TITLE_TEMPLATE_EN,
    "seo_default_title_ru": SEO_DEFAULT_TITLE_RU,
    "seo_default_title_en": SEO_DEFAULT_TITLE_EN,
    "seo_og_image": SEO_OG_IMAGE,
    "related_posts_count": RELATED_POSTS_COUNT,
    "recent_posts_count": RECENT_POSTS_COUNT,
    "excerpt_length_ru": EXCERPT_LENGTH_RU,
    "excerpt_length_en": EXCERPT_LENGTH_EN,
}


# =============================================================================
# VALIDATION (runs on import)
# =============================================================================

def _validate_config() -> None:
    """Basic validation of configuration values at import time."""
    if not SITE_URL.startswith("https://"):
        raise ValueError(f"SITE_URL must use HTTPS: {SITE_URL}")
    if not CHANNEL_USERNAME:
        raise ValueError("CHANNEL_USERNAME must not be empty")
    if not CHANNEL_ID:
        raise ValueError("CHANNEL_ID must not be empty")
    if POSTS_PER_PAGE < 1:
        raise ValueError(f"POSTS_PER_PAGE must be >= 1, got {POSTS_PER_PAGE}")
    if MAX_POSTS < POSTS_PER_PAGE:
        raise ValueError(f"MAX_POSTS ({MAX_POSTS}) must be >= POSTS_PER_PAGE ({POSTS_PER_PAGE})")
    if ARCHIVE_POSTS_PER_PAGE < 1:
        raise ValueError(f"ARCHIVE_POSTS_PER_PAGE must be >= 1, got {ARCHIVE_POSTS_PER_PAGE}")
    if len(PRODUCT_CATEGORIES) == 0:
        raise ValueError("PRODUCT_CATEGORIES must not be empty")
    for key, val in PRODUCT_CATEGORIES.items():
        if "ru" not in val or "en" not in val:
            raise ValueError(f"PRODUCT_CATEGORIES['{key}'] must have both 'ru' and 'en' keys")
    # ADMITAD_CONFIG can be empty — data comes from pipeline JSON at runtime
    # No validation needed for empty dict
    if len(NEWS_KEYWORDS) == 0:
        raise ValueError("NEWS_KEYWORDS must not be empty")
    if len(MANDATORY_HASHTAGS) == 0:
        raise ValueError("MANDATORY_HASHTAGS must not be empty")


# Run validation on import
_validate_config()
