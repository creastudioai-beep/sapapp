"""
Data loader module for the SochiAutoParts static site generator.

Loads all data needed for site generation from the existing GitHub pipeline
(same data sources as the Cloudflare Worker). Fetches pre-computed JSON files
from the creastudioai-beep/Main1 repository, plus products from zap.online
and Admitad affiliate programs from the pr repository.

Features:
    - Fetches JSON data from GitHub raw URLs with timeout and retry logic
    - Caches data locally in a data/ directory (saves JSON after first fetch)
    - Uses cached data if less than 1 hour old (configurable)
    - Handles missing/failed downloads gracefully (partial data is used)
    - Builds auxiliary data structures: postMap, productMap, categoryMap
    - Sorts posts by date (newest first) and validates dates

Usage:
    from data_loader import load_data, get_post_by_id, search_posts

    data = load_data()
    post = get_post_by_id(data, 123)
    results = search_posts(data, 'тормозные колодки')
"""

import hashlib
import html
import json
import logging
import math
import os
import re
import time
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import quote as url_quote

import requests


# ---------------------------------------------------------------------------
# Surrogate character sanitization
# ---------------------------------------------------------------------------

def _sanitize_surrogates(obj):
    """Recursively remove UTF-16 surrogate characters from data structures.

    Pipeline JSON from GitHub may contain stray surrogate code points
    (U+D800..U+DFFF) which are invalid in UTF-8 and cause
    UnicodeEncodeError when written with ``json.dump(ensure_ascii=False)``.
    This function walks dicts and lists and replaces any string containing
    surrogates with a cleaned version.

    Args:
        obj: Any JSON-serializable object (dict, list, str, int, float, None).

    Returns:
        The same structure with all surrogate characters removed from strings.
    """
    if isinstance(obj, str):
        # Encode with surrogatepass then decode ignoring errors to strip surrogates
        try:
            obj.encode('utf-8')
            return obj  # No surrogates
        except UnicodeEncodeError:
            # Remove surrogates by encoding with surrogatepass and replacing
            return obj.encode('utf-8', errors='surrogatepass').decode('utf-8', errors='replace')
    elif isinstance(obj, dict):
        return {_sanitize_surrogates(k): _sanitize_surrogates(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_sanitize_surrogates(item) for item in obj]
    return obj

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger = logging.getLogger("data_loader")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("[%(name)s] %(levelname)s: %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# URL Configuration
# ---------------------------------------------------------------------------

PIPELINE_BASE_URL = (
    "https://raw.githubusercontent.com/creastudioai-beep/Main1/main/data/output"
)

PRODUCTS_URL = (
    "https://raw.githubusercontent.com/creastudioai-beep/zap.online/main/products.json"
)

ADMITAD_URL = (
    "https://raw.githubusercontent.com/creastudioai-beep/pr/main/data/admitad_ads.json"
)

# Product field mapping (compressed keys -> readable names)
_PRODUCT_KEY_MAP = {
    "n": "name", "p": "price", "o": "old_price", "c": "currency",
    "u": "url", "i": "image", "v": "vendor", "d": "description",
    "f": "feed_id", "fn": "feed_name", "fc": "feed_color", "fi": "feed_icon",
    "cat": "category_id", "a": "available", "sn": "short_note",
    "m": "model", "tp": "type", "id": "id",
}
_DATA_SOURCES = {
    "posts":           ("posts.json",           f"{PIPELINE_BASE_URL}/posts.json"),
    "articles":        ("articles.json",        f"{PIPELINE_BASE_URL}/articles.json"),
    "seo_posts":       ("seo-posts.json",       f"{PIPELINE_BASE_URL}/seo-posts.json"),
    "seo_articles":    ("seo-articles.json",    f"{PIPELINE_BASE_URL}/seo-articles.json"),
    "schema_posts":    ("schema-posts.json",    f"{PIPELINE_BASE_URL}/schema-posts.json"),
    "schema_articles": ("schema-articles.json", f"{PIPELINE_BASE_URL}/schema-articles.json"),
    "search_index":    ("search-index.json",    f"{PIPELINE_BASE_URL}/search-index.json"),
    "hashtag_index":   ("hashtag-index.json",   f"{PIPELINE_BASE_URL}/hashtag-index.json"),
    "popular_tags":    ("popular-tags.json",    f"{PIPELINE_BASE_URL}/popular-tags.json"),
    "related_posts":   ("related-posts.json",   f"{PIPELINE_BASE_URL}/related-posts.json"),
    "products":        ("products.json",        PRODUCTS_URL),
    "admitad_programs": ("admitad_ads.json",    ADMITAD_URL),
}

# ---------------------------------------------------------------------------
# Default request settings
# ---------------------------------------------------------------------------

_DEFAULT_TIMEOUT = 30       # seconds
_DEFAULT_RETRIES = 3
_DEFAULT_RETRY_DELAY = 1.0  # seconds (base delay, exponentially backed off)
_DEFAULT_CACHE_MAX_AGE = 3600  # 1 hour in seconds


# ===========================================================================
# Core fetch / cache helpers
# ===========================================================================


def _fetch_json(url: str, timeout: int = _DEFAULT_TIMEOUT, retries: int = _DEFAULT_RETRIES) -> Optional[dict]:
    """Fetch JSON from URL with retry logic.

    Uses exponential backoff between retries. Returns parsed JSON on success
    or ``None`` if all retries are exhausted.

    Args:
        url: The URL to fetch.
        timeout: Request timeout in seconds.
        retries: Maximum number of retry attempts.

    Returns:
        Parsed JSON as dict/list, or None on failure.
    """
    last_exc: Optional[Exception] = None

    for attempt in range(1, retries + 1):
        try:
            logger.debug("Fetching %s (attempt %d/%d)", url, attempt, retries)
            resp = requests.get(url, timeout=timeout, headers={
                "User-Agent": "SochiAutoParts-SiteGenerator/1.0",
                "Accept": "application/json",
            })
            resp.raise_for_status()
            data = resp.json()
            logger.debug("Successfully fetched %s (%d bytes)", url, len(resp.content))
            return data
        except requests.exceptions.Timeout as exc:
            last_exc = exc
            logger.warning("Timeout fetching %s (attempt %d/%d): %s", url, attempt, retries, exc)
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "N/A"
            last_exc = exc
            # Don't retry 404s – the resource simply doesn't exist
            if status == 404:
                logger.warning("Resource not found (404): %s", url)
                return None
            logger.warning("HTTP %s fetching %s (attempt %d/%d): %s", status, url, attempt, retries, exc)
        except requests.exceptions.ConnectionError as exc:
            last_exc = exc
            logger.warning("Connection error fetching %s (attempt %d/%d): %s", url, attempt, retries, exc)
        except (json.JSONDecodeError, ValueError) as exc:
            last_exc = exc
            logger.error("Invalid JSON from %s: %s", url, exc)
            return None  # No point retrying bad JSON
        except Exception as exc:
            last_exc = exc
            logger.warning("Unexpected error fetching %s (attempt %d/%d): %s", url, attempt, retries, exc)

        # Exponential backoff before next retry
        if attempt < retries:
            delay = _DEFAULT_RETRY_DELAY * (2 ** (attempt - 1))
            logger.debug("Retrying in %.1f seconds...", delay)
            time.sleep(delay)

    logger.error("All %d retries exhausted for %s: %s", retries, url, last_exc)
    return None


def _load_from_cache(data_dir: str, filename: str, max_age: int = _DEFAULT_CACHE_MAX_AGE) -> Optional[dict]:
    """Load from local cache if fresh enough.

    Checks if a cached file exists and its modification time is within
    ``max_age`` seconds of the current time. If so, parses and returns
    the JSON content.

    Args:
        data_dir: Directory containing cached files.
        filename: Name of the cache file.
        max_age: Maximum age in seconds for the cache to be considered fresh.

    Returns:
        Parsed JSON data if cache is fresh, otherwise None.
    """
    filepath = os.path.join(data_dir, filename)
    if not os.path.isfile(filepath):
        return None

    try:
        mtime = os.path.getmtime(filepath)
        age = time.time() - mtime
        if age > max_age:
            logger.debug("Cache expired for %s (age=%.0fs, max_age=%ds)", filepath, age, max_age)
            return None

        with open(filepath, "r", encoding="utf-8") as fh:
            data = json.load(fh)

        logger.debug("Loaded from cache: %s (age=%.0fs)", filepath, age)
        return data
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("Corrupt cache file %s, will re-fetch: %s", filepath, exc)
        return None
    except OSError as exc:
        logger.warning("Cannot read cache file %s: %s", filepath, exc)
        return None


def _save_to_cache(data_dir: str, filename: str, data: Any) -> None:
    """Save to local cache.

    Creates the ``data_dir`` directory if it doesn't exist, then writes
    the data as pretty-printed JSON. Sanitizes any UTF-16 surrogate
    characters before writing to prevent UnicodeEncodeError.

    Args:
        data_dir: Directory to store the cache file.
        filename: Name of the cache file.
        data: JSON-serializable data to cache.
    """
    try:
        os.makedirs(data_dir, exist_ok=True)
        filepath = os.path.join(data_dir, filename)

        # Sanitize surrogate characters that may be present in pipeline data
        clean_data = _sanitize_surrogates(data)

        # Use ensure_ascii=True as a safety net to avoid UnicodeEncodeError
        # from stray surrogate characters that _sanitize_surrogates might miss.
        # This produces ASCII-safe JSON with \uXXXX escapes but is bulletproof.
        with open(filepath, "w", encoding="utf-8") as fh:
            json.dump(clean_data, fh, ensure_ascii=True, indent=2)

        logger.debug("Saved to cache: %s", filepath)
    except (OSError, UnicodeEncodeError) as exc:
        logger.warning("Cannot write cache file %s/%s: %s", data_dir, filename, exc)


# ===========================================================================
# Data structure builders
# ===========================================================================


def _build_post_map(posts: list) -> dict:
    """Build post_id -> post dict for O(1) lookups.

    Each post is expected to have an ``id`` field (int). The resulting
    dictionary maps that id to the full post dict.

    Args:
        posts: List of post dicts.

    Returns:
        Dict mapping post id (int) to post dict.
    """
    post_map: dict[int, dict] = {}
    for post in posts:
        post_id = post.get("id")
        if post_id is not None:
            try:
                post_map[int(post_id)] = post
            except (ValueError, TypeError):
                logger.warning("Skipping post with non-integer id: %s", post_id)
    return post_map


def _build_product_map(products: list) -> dict:
    """Build product_id -> product dict.

    If a product doesn't have an ``id`` field, one is generated using
    :func:`_generate_product_id` based on name, vendor, and list index.

    Args:
        products: List of product dicts.

    Returns:
        Dict mapping product id (str) to product dict.
    """
    product_map: dict[str, dict] = {}
    for idx, product in enumerate(products):
        pid = product.get("id")
        if not pid:
            name = product.get("name", "")
            vendor = product.get("vendor", product.get("brand", ""))
            pid = _generate_product_id(name, vendor, idx)
            product["id"] = pid
        product_map[str(pid)] = product
    return product_map


def _build_category_map(products: list) -> dict:
    """Build category_slug -> list of products dict.

    Products are grouped by their ``category`` field. Products without
    a category are placed under an ``"uncategorized"`` key.

    Args:
        products: List of product dicts.

    Returns:
        Dict mapping category slug (str) to list of product dicts.
    """
    category_map: dict[str, list] = {}
    for product in products:
        category = product.get("category", "uncategorized") or "uncategorized"
        # Normalize category to a slug-like key
        slug = str(category).lower().strip().replace(" ", "-")
        if slug not in category_map:
            category_map[slug] = []
        category_map[slug].append(product)
    return category_map


def _generate_product_id(name: str, vendor: str, idx: int) -> str:
    """Generate unique product ID (idx_hash format to prevent collisions).

    Format: ``{idx}_{hash_prefix}`` where hash_prefix is the first 8
    characters of the SHA-256 digest of ``name|vendor|idx``.

    Args:
        name: Product name.
        vendor: Product vendor/brand.
        idx: Index of the product in the list.

    Returns:
        A unique string identifier for the product.
    """
    raw = f"{name}|{vendor}|{idx}"
    hash_hex = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:8]
    return f"{idx}_{hash_hex}"


def _expand_product_keys(products: list) -> list:
    """Expand compressed product keys (n->name, p->price, etc.) to readable names.

    The products JSON from the pipeline uses abbreviated field names to
    reduce file size. This function expands them to full names that the
    rest of the generator expects.

    Args:
        products: List of product dicts with compressed keys.

    Returns:
        List of product dicts with expanded keys.
    """
    if not products:
        return []

    expanded = []
    for product in products:
        if not isinstance(product, dict):
            continue

        # Check if keys are already expanded (e.g. 'name' exists)
        if "name" in product or "n" not in product:
            expanded.append(product)
            continue

        new_product = {}
        for key, value in product.items():
            readable_key = _PRODUCT_KEY_MAP.get(key, key)
            new_product[readable_key] = value

        # Ensure 'available' is a boolean
        if "available" in new_product:
            new_product["available"] = bool(new_product["available"])

        expanded.append(new_product)

    return expanded


def _parse_admitad_data(raw_data) -> list:
    """Parse Admitad data from the pipeline JSON format.

    The Admitad JSON may be:
    - A dict with 'programs' key containing the list of programs
    - A list of programs directly
    - Empty/default

    This function normalizes to a flat list of program dicts with
    standard keys (name, image, category, gotoLink, etc.).

    Args:
        raw_data: Raw Admitad data from the pipeline.

    Returns:
        List of Admitad program dicts.
    """
    if not raw_data:
        return []

    # If it's already a list, return as-is
    if isinstance(raw_data, list):
        return raw_data

    # If it's a dict with 'programs' key, extract the programs
    if isinstance(raw_data, dict):
        programs = raw_data.get("programs", [])
        if isinstance(programs, list):
            # Normalize each program's keys
            normalized = []
            for prog in programs:
                if not isinstance(prog, dict):
                    continue

                # Map 'goto_link' -> 'affiliateUrl' for template compatibility
                if "goto_link" in prog and "affiliateUrl" not in prog:
                    prog["affiliateUrl"] = prog["goto_link"]
                elif "gotoLink" not in prog and "goto_link" in prog:
                    prog["gotoLink"] = prog["goto_link"]

                # Map 'category' -> 'jsonCategory' for template compatibility
                # NOTE: jsonCategory may exist but be None/null in the data,
                # so check for falsy value, not just key existence
                if "category" in prog and not prog.get("jsonCategory"):
                    prog["jsonCategory"] = prog["category"]

                # Map 'allowed_regions' -> 'regions'
                if "allowed_regions" in prog and "regions" not in prog:
                    prog["regions"] = prog["allowed_regions"]

                # Map 'advertiser_legal_info' stays as-is (templates check for it)

                normalized.append(prog)

            return normalized

    return []


# ===========================================================================
# Date validation & sorting
# ===========================================================================


def _parse_date(date_str: str) -> Optional[datetime]:
    """Parse a date string in common formats.

    Supports ISO-8601, Unix timestamps (as string), and common Russian
    date formats.

    Args:
        date_str: Date string to parse.

    Returns:
        A datetime object if parsing succeeds, otherwise None.
    """
    if not date_str:
        return None

    # Try ISO format first (most common from pipeline)
    for fmt in (
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d.%m.%Y",
        "%d.%m.%Y %H:%M",
        "%d.%m.%Y %H:%M:%S",
    ):
        try:
            return datetime.strptime(str(date_str).strip(), fmt)
        except (ValueError, TypeError):
            continue

    # Try as Unix timestamp (int or float)
    try:
        ts = float(date_str)
        if ts > 1_000_000:  # Reasonable Unix timestamp range
            return datetime.fromtimestamp(ts, tz=timezone.utc)
    except (ValueError, TypeError, OSError):
        pass

    return None


def _load_telegram_archive(archive_dir: str) -> list:
    """Load all posts from the Telegram archive directory.

    The telegram_fetcher stores posts as paginated JSON files:
        data/telegram_archive/page_1.json, page_2.json, ...
        data/telegram_archive/meta.json

    This function reads all pages and returns a single list of post dicts.
    Falls back to an empty list if the directory doesn't exist or is empty.

    Args:
        archive_dir: Path to the telegram_archive directory.

    Returns:
        List of post dicts from the Telegram archive.
    """
    import glob as _glob

    if not os.path.isdir(archive_dir):
        return []

    # Read meta to get total pages count
    meta_path = os.path.join(archive_dir, "meta.json")
    pages_count = 0
    if os.path.isfile(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            pages_count = meta.get("pages_count", 0)
        except (json.JSONDecodeError, OSError):
            pass

    # If no meta, discover pages by globbing
    if pages_count == 0:
        page_files = sorted(
            _glob.glob(os.path.join(archive_dir, "page_*.json")),
            key=lambda p: int(re.search(r"page_(\d+)", p).group(1)) if re.search(r"page_(\d+)", p) else 0,
        )
        pages_count = len(page_files)

    all_posts = []
    for page_num in range(1, pages_count + 1):
        page_path = os.path.join(archive_dir, f"page_{page_num}.json")
        if not os.path.isfile(page_path):
            continue
        try:
            with open(page_path, "r", encoding="utf-8") as f:
                page_posts = json.load(f)
            if isinstance(page_posts, list):
                # Normalize each post to have expected fields
                for post in page_posts:
                    if not isinstance(post, dict):
                        continue
                    post.setdefault("id", 0)
                    post.setdefault("title", "")
                    post.setdefault("text", "")
                    post.setdefault("media", [])
                    post.setdefault("hashtags", [])
                    # Convert legacy field names from telegram_fetcher
                    if not post.get("media") and (post.get("photos") or post.get("videos")):
                        media_list = []
                        for photo_url in post.get("photos", []):
                            media_list.append({"type": "photo", "directUrl": photo_url, "url": photo_url})
                        for video_url in post.get("videos", []):
                            media_item = {"type": "video", "directUrl": video_url, "url": video_url}
                            if post.get("video_thumbnails") and len(post["video_thumbnails"]) > 0:
                                media_item["poster"] = post["video_thumbnails"][0]
                            media_list.append(media_item)
                        post["media"] = media_list
                    # Extract hashtags from text if not present (including Arabic)
                    # Broad Unicode coverage: \w (letters/digits/_), Arabic basic + Supplement + Extended-A
                    if not post.get("hashtags") and post.get("text"):
                        hashtags = re.findall(r"#([\w\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]+)", post["text"], re.UNICODE)
                        if hashtags:
                            post["hashtags"] = ["#" + h for h in hashtags]
                    # Generate title from text if not present
                    if not post.get("title") and post.get("text"):
                        first_line = post["text"].split("\n")[0].strip()
                        post["title"] = first_line[:100] if first_line else f"Пост {post.get('id', '')}"
                    all_posts.append(post)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to read archive page %s: %s", page_path, e)
            continue

    return all_posts


def _sort_posts_by_date(posts: list) -> list:
    """Sort posts by date, newest first.

    Posts with unparseable dates are placed at the end.

    Args:
        posts: List of post dicts (each may have a ``date`` field).

    Returns:
        New list sorted by date descending.
    """
    def _sort_key(post: dict) -> float:
        date_str = post.get("date") or post.get("created_at") or post.get("pub_date") or ""
        dt = _parse_date(str(date_str))
        if dt is None:
            return 0.0  # Push undated posts to the end
        return dt.timestamp()

    return sorted(posts, key=_sort_key, reverse=True)


def _validate_and_normalize_posts(posts: list) -> list:
    """Validate post dates and ensure required fields exist.

    Adds missing ``date`` field as empty string if absent. Normalizes
    date strings to a consistent ISO format where possible.

    Args:
        posts: List of post dicts.

    Returns:
        List of validated and normalized post dicts.
    """
    validated = []
    for post in posts:
        if not isinstance(post, dict):
            continue

        # Ensure date field exists
        date_val = post.get("date") or post.get("created_at") or post.get("pub_date") or ""
        if "date" not in post:
            post["date"] = str(date_val)

        # Normalize the date to ISO format if parseable
        if date_val:
            dt = _parse_date(str(date_val))
            if dt is not None:
                post["date"] = dt.strftime("%Y-%m-%dT%H:%M:%S")
            # else: leave as-is

        # Ensure essential fields exist (with defaults)
        post.setdefault("id", 0)
        post.setdefault("title", "")
        post.setdefault("text", "")
        post.setdefault("media", [])
        post.setdefault("hashtags", [])

        validated.append(post)

    return validated


# ===========================================================================
# Main data loading
# ===========================================================================


def load_data(data_dir: str = "data", force_refresh: bool = False) -> dict:
    """Load all data from GitHub pipeline URLs with local caching.

    Fetches pre-computed JSON files from the creastudioai-beep repositories.
    On the first run, downloads are saved to the ``data_dir`` cache directory.
    On subsequent runs, cached data is used if less than 1 hour old.

    Missing or failed downloads are handled gracefully — partial data is
    returned with empty defaults so the generator can still run.

    Args:
        data_dir: Local directory for cached JSON files. Defaults to ``"data"``.
        force_refresh: If True, bypass cache and re-download all data.

    Returns:
        Dict with keys:
            - posts: list of post dicts (sorted by date, newest first)
            - articles: list of article dicts
            - seo_posts: dict of SEO metadata per post
            - seo_articles: dict of SEO metadata per article
            - schema_posts: dict of Schema.org JSON-LD per post
            - schema_articles: dict of Schema.org JSON-LD per article
            - search_index: dict of tokenized search index
            - hashtag_index: dict of tag -> post IDs mapping + tag counts
            - popular_tags: list of top tags sorted by frequency
            - related_posts: dict of post_id -> related post IDs
            - products: list of product dicts
            - admitad_programs: list of Admitad affiliate programs
            - post_map: dict of post_id -> post
            - product_map: dict of product_id -> product
            - category_map: dict of category_slug -> list of products
    """
    result: dict[str, Any] = {}

    for key, (filename, url) in _DATA_SOURCES.items():
        data = None

        # Step 1: Try cache (unless force_refresh)
        if not force_refresh:
            cached = _load_from_cache(data_dir, filename)
            if cached is not None:
                data = cached
                logger.info("Loaded %s from cache", key)

        # Step 2: Fetch from remote if cache miss or force_refresh
        if data is None:
            data = _fetch_json(url)
            if data is not None:
                _save_to_cache(data_dir, filename, data)
                logger.info("Fetched and cached %s", key)
            else:
                # Try stale cache as last resort
                stale = _load_from_cache(data_dir, filename, max_age=999999999)
                if stale is not None:
                    data = stale
                    logger.warning("Using stale cache for %s (remote fetch failed)", key)
                else:
                    logger.error("No data available for %s — using empty default", key)

        # Step 3: Assign with sensible defaults
        if data is None:
            # Provide empty defaults based on expected type
            if key in ("posts", "articles", "popular_tags", "products", "admitad_programs"):
                result[key] = []
            else:
                result[key] = {}
        else:
            result[key] = data

    # ------------------------------------------------------------------
    # Telegram archive data — merge with pipeline posts
    # ------------------------------------------------------------------
    archive_dir = os.path.join(data_dir, "telegram_archive")
    telegram_posts = _load_telegram_archive(archive_dir)
    if telegram_posts:
        logger.info("Loaded %d posts from telegram archive at %s", len(telegram_posts), archive_dir)
        # Validate and normalize telegram posts
        telegram_posts = _validate_and_normalize_posts(telegram_posts)
        # Merge: telegram posts take priority over pipeline posts (dedup by ID)
        existing_ids = set()
        for post in result["posts"]:
            pid = post.get("id")
            if pid is not None:
                existing_ids.add(str(pid))
        # Add telegram posts that don't overlap with pipeline
        new_from_telegram = []
        for post in telegram_posts:
            pid = str(post.get("id", ""))
            if pid and pid not in existing_ids:
                new_from_telegram.append(post)
                existing_ids.add(pid)
        if new_from_telegram:
            result["posts"].extend(new_from_telegram)
            logger.info("Merged %d new posts from telegram archive (deduped)", len(new_from_telegram))
    result["archive_posts"] = telegram_posts
    result["archive_post_map"] = {}

    # ------------------------------------------------------------------
    # Post-processing
    # ------------------------------------------------------------------

    # Validate and normalize posts
    result["posts"] = _validate_and_normalize_posts(result["posts"])

    # Sort posts by date (newest first)
    result["posts"] = _sort_posts_by_date(result["posts"])
    logger.info("Loaded %d posts (sorted by date, newest first)", len(result["posts"]))

    # Expand compressed product keys to readable names
    result["products"] = _expand_product_keys(result["products"])
    logger.info("Expanded %d products from compressed keys", len(result["products"]))

    # Parse Admitad data (may be a dict with 'programs' key, or a list)
    result["admitad_programs"] = _parse_admitad_data(result["admitad_programs"])
    logger.info("Parsed %d Admitad programs", len(result["admitad_programs"]))

    # Build post_map for O(1) lookups
    result["post_map"] = _build_post_map(result["posts"])
    logger.info("Built post_map with %d entries", len(result["post_map"]))

    # Build product_map for O(1) lookups
    result["product_map"] = _build_product_map(result["products"])
    logger.info("Built product_map with %d entries", len(result["product_map"]))

    # Build category_map for category-based lookups
    result["category_map"] = _build_category_map(result["products"])
    logger.info("Built category_map with %d categories", len(result["category_map"]))

    # Ensure seo/schema structures are dict even if they came as lists
    for key in ("seo_posts", "seo_articles", "schema_posts", "schema_articles",
                "search_index", "hashtag_index", "related_posts"):
        if isinstance(result.get(key), list):
            # Convert list to dict if possible (e.g. list of objects with 'id')
            try:
                result[key] = {item["id"]: item for item in result[key] if isinstance(item, dict) and "id" in item}
            except (TypeError, KeyError):
                pass  # Keep as-is

    # Unwrap nested hashtag_index structure: pipeline sends {"index": {tag: [ids]}, "tagCounts": {tag: count}}
    # Normalize to just the "index" part for easier downstream use
    hi_raw = result.get("hashtag_index", {})
    if isinstance(hi_raw, dict) and "index" in hi_raw:
        # Store both the full structure and the unwrapped index for convenience
        result["hashtag_index_full"] = hi_raw
        result["hashtag_index"] = hi_raw["index"]
        logger.info("Unwrapped hashtag_index: %d tags (from nested structure)", len(hi_raw["index"]))

    logger.info(
        "Data loading complete: %d posts, %d articles, %d products, %d admitad programs",
        len(result["posts"]),
        len(result.get("articles", [])),
        len(result.get("products", [])),
        len(result.get("admitad_programs", [])),
    )

    return result


# ===========================================================================
# Query helper functions
# ===========================================================================


def get_post_by_id(data: dict, post_id: int) -> Optional[dict]:
    """Get post by ID from loaded data.

    Uses the pre-built ``post_map`` for O(1) lookup.

    Args:
        data: The data dict returned by :func:`load_data`.
        post_id: The post ID to look up.

    Returns:
        The post dict if found, otherwise None.
    """
    post_map = data.get("post_map", {})
    try:
        return post_map[int(post_id)]
    except (KeyError, ValueError, TypeError):
        return None


def get_posts_by_tag(data: dict, tag: str, page: int = 1, per_page: int = 30) -> tuple:
    """Get posts by tag. Returns (posts, total, total_pages).

    Uses the ``hashtag_index`` to find post IDs for a given tag, then
    resolves them via ``post_map`` and applies pagination.

    Args:
        data: The data dict returned by :func:`load_data`.
        tag: The hashtag to filter by (with or without leading ``#``).
        page: Page number (1-based). Defaults to 1.
        per_page: Number of posts per page. Defaults to 30.

    Returns:
        Tuple of (list of post dicts, total count, total pages).
    """
    # hashtag_index is now unwrapped by load_data() automatically
    hashtag_index = data.get("hashtag_index", {})
    # Safety: still check for nested structure in case data was loaded differently
    if isinstance(hashtag_index, dict) and "index" in hashtag_index:
        hashtag_index = hashtag_index["index"]
    post_map = data.get("post_map", {})

    # Normalize tag: ensure it starts with # for lookup, but try both
    normalized_tag = tag if tag.startswith("#") else f"#{tag}"
    lookup_tag = normalized_tag.lstrip("#").lower()

    # Try various key formats in the hashtag index
    tag_data = None
    for candidate in (normalized_tag, normalized_tag.lower(), tag, lookup_tag, f"#{lookup_tag}"):
        if candidate in hashtag_index:
            tag_data = hashtag_index[candidate]
            break

    if tag_data is None:
        return [], 0, 0

    # Extract post IDs – the index may store them under "posts", "post_ids", or be a list directly
    if isinstance(tag_data, dict):
        post_ids = tag_data.get("posts", tag_data.get("post_ids", []))
    elif isinstance(tag_data, list):
        post_ids = tag_data
    else:
        return [], 0, 0

    # Resolve post IDs to actual post dicts
    matched_posts = []
    for pid in post_ids:
        try:
            post = post_map.get(int(pid))
            if post is not None:
                matched_posts.append(post)
        except (ValueError, TypeError):
            continue

    # Sort by date (newest first)
    matched_posts = _sort_posts_by_date(matched_posts)

    total = len(matched_posts)
    total_pages = max(1, math.ceil(total / per_page))

    # Paginate
    start = (page - 1) * per_page
    end = start + per_page
    page_posts = matched_posts[start:end]

    return page_posts, total, total_pages


def get_related_posts(data: dict, post_id: int, limit: int = 12) -> list:
    """Get related posts for a given post ID.

    Looks up the ``related_posts`` index for the given post ID and resolves
    the returned IDs to actual post dicts.

    Args:
        data: The data dict returned by :func:`load_data`.
        post_id: The post ID to find related posts for.
        limit: Maximum number of related posts to return. Defaults to 12.

    Returns:
        List of related post dicts (up to ``limit`` items).
    """
    related_index = data.get("related_posts", {})
    post_map = data.get("post_map", {})

    # Look up related post IDs – key may be int or string
    related_ids = None
    for key_candidate in (post_id, str(post_id)):
        if key_candidate in related_index:
            related_ids = related_index[key_candidate]
            break

    if related_ids is None:
        return []

    # Resolve to actual posts
    results = []
    for rid in related_ids[:limit]:
        try:
            post = post_map.get(int(rid))
            if post is not None:
                results.append(post)
        except (ValueError, TypeError):
            continue

    return results


def search_posts(data: dict, query: str, limit: int = 200) -> list:
    """Search posts by query using the pre-computed search index.

    Tokenizes the query, looks up each token in ``search_index``, computes
    a relevance score based on the number of matching tokens and their
    frequency, and returns the top results.

    Args:
        data: The data dict returned by :func:`load_data`.
        query: The search query string.
        limit: Maximum number of results. Defaults to 200.

    Returns:
        List of post dicts sorted by relevance (best match first).
    """
    search_index = data.get("search_index", {})
    post_map = data.get("post_map", {})

    if not query or not search_index:
        return []

    # Tokenize query: lowercase, split on non-word chars, remove short tokens
    tokens = re.findall(r"[a-zA-Zа-яА-ЯёЁ0-9]+", query.lower())
    tokens = [t for t in tokens if len(t) >= 2]

    if not tokens:
        return []

    # Score each post by number of matching tokens
    post_scores: dict[int, int] = {}

    for token in tokens:
        # The search index maps token -> list of post IDs or token -> {post_id: count}
        token_data = search_index.get(token)
        if token_data is None:
            continue

        if isinstance(token_data, dict):
            # token -> {post_id: frequency/count}
            for pid_str, count in token_data.items():
                try:
                    pid = int(pid_str)
                    score = count if isinstance(count, int) else 1
                    post_scores[pid] = post_scores.get(pid, 0) + score
                except (ValueError, TypeError):
                    continue
        elif isinstance(token_data, list):
            # token -> [post_id, post_id, ...]
            for pid in token_data:
                try:
                    pid = int(pid)
                    post_scores[pid] = post_scores.get(pid, 0) + 1
                except (ValueError, TypeError):
                    continue

    if not post_scores:
        return []

    # Sort by score descending, then by date
    sorted_ids = sorted(
        post_scores.keys(),
        key=lambda pid: (-post_scores[pid], pid),
    )

    # Resolve to post dicts
    results = []
    for pid in sorted_ids[:limit]:
        post = post_map.get(pid)
        if post is not None:
            # Attach relevance score for potential downstream use
            post_copy = dict(post)
            post_copy["_search_score"] = post_scores[pid]
            results.append(post_copy)

    return results


def format_post_text(text: str, lang: str = "ru") -> str:
    """Format post text: convert URLs to links, hashtags to links, escape HTML.

    - Escapes all HTML entities in the text body to prevent XSS.
    - Converts ``https://...`` and ``http://...`` URLs into clickable links.
    - Converts ``@username`` Telegram mentions into clickable links.
    - Converts ``#hashtag`` patterns into clickable links pointing to
      ``/tag/hashtag``.
    - Preserves line breaks by converting newlines to ``<br>`` tags.

    Args:
        text: Raw post text.
        lang: Language code (for URL path prefix).

    Returns:
        HTML-formatted string with escaped entities, linkified URLs, and hashtag links.
    """
    if not text:
        return ""

    # Step 1: Escape HTML entities
    safe = html.escape(str(text))

    # Step 2: Convert URLs to clickable links (before hashtag processing)
    prefix = "/en/" if lang == "en" else "/"
    def _url_link(match: re.Match) -> str:
        url = match.group(0)
        escaped_url = html.escape(url)
        # Shorten display URL if too long
        display = escaped_url
        if len(display) > 60:
            display = display[:57] + "..."
        return f'<a href="{escaped_url}" target="_blank" rel="nofollow noopener noreferrer">{display}</a>'

    safe = re.sub(
        r"https?://[^\s<>\"]+",
        _url_link,
        safe,
    )

    # Step 3: Convert @username to Telegram links
    def _mention_link(match: re.Match) -> str:
        username = match.group(1)
        escaped_name = html.escape(username)
        return f'<a href="https://t.me/{escaped_name}" target="_blank" rel="nofollow noopener noreferrer">@{escaped_name}</a>'

    safe = re.sub(
        r"@([a-zA-Z0-9_]{5,32})",
        _mention_link,
        safe,
    )

    # Step 4: Convert hashtags to links
    # Match #word patterns (Cyrillic, Latin, Arabic, numbers, underscores)
    # Broad Unicode coverage: \w (letters/digits/_), Arabic basic + Supplement + Extended-A
    def _hashtag_link(match: re.Match) -> str:
        hashtag = match.group(0)       # e.g. "#автозапчасти" or "#أخبارالسيارات"
        tag_name = match.group(1)      # e.g. "автозапчасти" or "أخبارالسيارات"
        escaped_hashtag = html.escape(hashtag)
        # URL-encode the tag name for the href and add .html extension
        # so GitHub Pages can find the tag page file on disk.
        encoded_tag = url_quote(tag_name)
        return f'<a href="{prefix}tag/{encoded_tag}.html" class="hashtag-link">{escaped_hashtag}</a>'

    safe = re.sub(
        r"#([\w\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]+)",
        _hashtag_link,
        safe,
        flags=re.UNICODE,
    )

    # Step 5: Convert newlines to <br>
    safe = safe.replace("\n", "<br>\n")

    return safe


def extract_first_image(post: dict) -> Optional[str]:
    """Extract first image URL from post for thumbnail/OG.

    Checks the ``media`` field (which may be a list of objects or strings),
    then falls back to ``image``, ``thumbnail``, ``photo``, and ``media_url``
    fields.

    Args:
        post: Post dict.

    Returns:
        URL string of the first image if found, otherwise None.
    """
    if not isinstance(post, dict):
        return None

    # Check media list first
    media = post.get("media", [])
    if isinstance(media, list):
        for item in media:
            if isinstance(item, str):
                # Simple URL string
                if _looks_like_image_url(item):
                    return item
            elif isinstance(item, dict):
                # Object with type/url fields
                media_type = str(item.get("type", "")).lower()
                url = item.get("url") or item.get("src") or item.get("link") or ""
                if url and (media_type in ("photo", "image", "img", "") or _looks_like_image_url(url)):
                    return url

    # Fallback: check various single-image fields
    for field in ("image", "thumbnail", "photo", "media_url", "og_image", "preview"):
        val = post.get(field)
        if val and isinstance(val, str) and _looks_like_image_url(val):
            return val

    # Last resort: check text for embedded image URLs
    text = post.get("text", "")
    if isinstance(text, str):
        url_match = re.search(r"https?://\S+\.(?:jpg|jpeg|png|gif|webp|svg)(?:\?\S*)?", text, re.IGNORECASE)
        if url_match:
            return url_match.group(0)

    return None


def _looks_like_image_url(url: str) -> bool:
    """Check if a URL looks like it points to an image.

    Args:
        url: URL string to check.

    Returns:
        True if the URL appears to be an image URL.
    """
    if not url or not isinstance(url, str):
        return False
    lower = url.lower().split("?")[0]  # Strip query params
    return any(lower.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".avif"))


def get_popular_tags(data: dict, limit: int = 12) -> list:
    """Get popular tags.

    Returns the top tags sorted by frequency from the pre-computed
    ``popular_tags`` list. Each item is expected to be a dict with
    ``tag`` and ``count`` keys (or ``name`` and ``count``).

    Args:
        data: The data dict returned by :func:`load_data`.
        limit: Maximum number of tags to return. Defaults to 12.

    Returns:
        List of tag dicts, each with ``tag`` and ``count`` keys.
    """
    popular_tags = data.get("popular_tags", [])

    if isinstance(popular_tags, list):
        # Normalize tag items to consistent format
        normalized = []
        for item in popular_tags:
            if isinstance(item, dict):
                tag_name = item.get("tag") or item.get("name") or item.get("hashtag", "")
                count = item.get("count", 0)
                normalized.append({"tag": str(tag_name), "count": int(count)})
            elif isinstance(item, str):
                normalized.append({"tag": item, "count": 0})
        return normalized[:limit]

    elif isinstance(popular_tags, dict):
        # Convert dict format {tag: count, ...} to list
        normalized = [
            {"tag": str(tag), "count": int(count)}
            for tag, count in popular_tags.items()
        ]
        normalized.sort(key=lambda x: x["count"], reverse=True)
        return normalized[:limit]

    return []


def get_admitad_programs(data: dict, category: str = None, region: str = None) -> list:
    """Get Admitad programs, optionally filtered by category and region.

    Each program in ``admitad_programs`` is expected to be a dict with
    fields like ``name``, ``category``/``jsonCategory``, ``regions``/``allowed_regions``,
    ``affiliateUrl``/``gotoLink``, etc.

    Region matching checks both ``regions`` (list of country codes) and
    ``allowed_regions`` (list). The special value "RU" matches programs
    that target Russian users.

    Args:
        data: The data dict returned by :func:`load_data`.
        category: Optional category string to filter by (case-insensitive
            substring match against the program's ``category`` or ``jsonCategory`` field).
        region: Optional region/country code to filter by (case-insensitive
            match against the program's ``regions`` or ``allowed_regions`` list).
            If None, returns programs available in Russia ("RU") or worldwide.

    Returns:
        List of matching Admitad program dicts.
    """
    programs = data.get("admitad_programs", [])

    if not isinstance(programs, list):
        return []

    # If no filters, return programs relevant to RU audience (RU + WW/global)
    if category is None and region is None:
        # Filter to programs that target RU or are worldwide
        relevant = []
        for program in programs:
            if not isinstance(program, dict):
                continue
            regions_val = program.get("regions", program.get("allowed_regions", []))
            if isinstance(regions_val, list):
                # Include if RU in regions or if regions contains many countries (worldwide)
                if "RU" in regions_val or len(regions_val) > 50 or len(regions_val) == 0:
                    relevant.append(program)
            elif isinstance(regions_val, str):
                if "RU" in regions_val.upper() or "WW" in regions_val.upper():
                    relevant.append(program)
            else:
                # No region info - include it
                relevant.append(program)
        return relevant

    results = []
    for program in programs:
        if not isinstance(program, dict):
            continue

        # Category filter
        if category is not None:
            prog_category = str(program.get("category", program.get("jsonCategory", ""))).lower()
            if category.lower() not in prog_category:
                continue

        # Region filter
        if region is not None:
            regions_val = program.get("regions", program.get("allowed_regions", ""))
            if isinstance(regions_val, list):
                region_str = " ".join(str(r) for r in regions_val).upper()
            else:
                region_str = str(regions_val).upper()
            if region.upper() not in region_str and len(regions_val) <= 50:
                continue

        results.append(program)

    return results


# ===========================================================================
# Convenience: Quick data reload
# ===========================================================================


def refresh_data(data_dir: str = "data") -> dict:
    """Force a full refresh of all data, ignoring cache.

    Shortcut for ``load_data(data_dir, force_refresh=True)``.

    Args:
        data_dir: Local directory for cached JSON files.

    Returns:
        Fresh data dict.
    """
    return load_data(data_dir=data_dir, force_refresh=True)


# ===========================================================================
# Module-level test / demo
# ===========================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    print("=" * 60)
    print("SochiAutoParts Data Loader — Standalone Test")
    print("=" * 60)

    data = load_data()

    print(f"\nPosts:        {len(data['posts'])}")
    print(f"Articles:     {len(data['articles'])}")
    print(f"Products:     {len(data['products'])}")
    print(f"Admitad:      {len(data['admitad_programs'])}")
    print(f"Post Map:     {len(data['post_map'])} entries")
    print(f"Product Map:  {len(data['product_map'])} entries")
    print(f"Category Map: {len(data['category_map'])} categories")

    # Show first 5 popular tags
    tags = get_popular_tags(data, limit=5)
    print(f"\nTop 5 tags:   {tags}")

    # Test search
    results = search_posts(data, "тормозные колодки", limit=5)
    print(f"\nSearch 'тормозные колодки': {len(results)} results")
    for r in results[:3]:
        print(f"  - [{r.get('id')}] {r.get('title', '(no title)')[:60]}  (score={r.get('_search_score', 0)})")

    # Test get_post_by_id
    if data["posts"]:
        first_post = data["posts"][0]
        pid = first_post.get("id")
        found = get_post_by_id(data, pid)
        print(f"\nget_post_by_id({pid}): {'OK' if found else 'NOT FOUND'}")

    # Test extract_first_image
    if data["posts"]:
        img = extract_first_image(data["posts"][0])
        print(f"First image of first post: {img[:80] if img else 'None'}...")

    # Test get_posts_by_tag
    if tags:
        test_tag = tags[0]["tag"]
        tag_posts, total, pages = get_posts_by_tag(data, test_tag, page=1, per_page=5)
        print(f"\nPosts by tag '{test_tag}': {total} total, {pages} pages, showing {len(tag_posts)}")

    print("\n" + "=" * 60)
    print("Data loader test complete.")
