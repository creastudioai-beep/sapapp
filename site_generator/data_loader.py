"""
Data loader module for the SochiAutoParts static site generator.

Loads all data needed for site generation from LOCAL data files only.
No remote pipeline URLs are used — all data comes from the local
``data/`` directory:

    - Posts:     data/telegram_posts/  (from telegram_parser.py)
    - Products:  data/products.json    (and data/products/ directory)
    - Admitad:   data/admitad_ads.json

Features:
    - Reads local JSON files for products and Admitad programs
    - Loads posts from the telegram_parser output directory
    - Builds auxiliary data structures on the fly: postMap, productMap,
      categoryMap, hashtagIndex, searchIndex, popularTags, relatedPosts
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
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import quote as url_quote


# ---------------------------------------------------------------------------
# Surrogate character sanitization
# ---------------------------------------------------------------------------

def _sanitize_surrogates(obj):
    """Recursively remove UTF-16 surrogate characters from data structures.

    Local JSON files may contain stray surrogate code points
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
# Local file paths (relative to data_dir)
# ---------------------------------------------------------------------------

# Cyrillic-to-Latin transliteration table for slug generation
_CYRILLIC_TO_LATIN = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
}


def _generate_slug(title: str, post_id: int) -> str:
    """Generate a URL-safe slug from a post title.

    Transliterates Russian characters to Latin, removes special characters,
    and appends the post ID for uniqueness. Avoids duplicate ID patterns
    like "post-87923-87923" when the title itself contains the post ID.

    Args:
        title: Post title text.
        post_id: Numeric post ID for uniqueness.

    Returns:
        URL-safe slug string (e.g., "toyota-corolla-2024-87923").
    """
    if not title:
        return str(post_id)

    # Lowercase
    slug = title.lower().strip()

    # Transliterate Cyrillic to Latin
    result = []
    for char in slug:
        if char in _CYRILLIC_TO_LATIN:
            result.append(_CYRILLIC_TO_LATIN[char])
        elif char in _CYRILLIC_TO_LATIN.values():
            result.append(char)
        elif char.isalnum() and ord(char) < 128:
            result.append(char)
        elif char in (' ', '-', '_', '/'):
            result.append('-')
        # Skip other characters (emoji, special symbols, etc.)

    slug = ''.join(result)

    # Clean up: remove consecutive hyphens, leading/trailing hyphens
    slug = re.sub(r'-+', '-', slug).strip('-')

    # Remove leading/trailing whitespace
    slug = slug.strip()

    # If slug is empty after cleaning, use post_id
    if not slug:
        return str(post_id)

    # Check if slug already ends with the post ID (e.g. "post-87923")
    # to avoid duplication like "post-87923-87923"
    post_id_str = str(post_id)
    if slug.endswith(f"-{post_id_str}") or slug == post_id_str:
        return slug

    # Append post ID for guaranteed uniqueness
    return f"{slug}-{post_id}"


_PRODUCTS_FILENAME = "products.json"
_ADMITAD_FILENAME = "admitad_ads.json"

# Product field mapping (compressed keys -> readable names)
_PRODUCT_KEY_MAP = {
    "n": "name", "p": "price", "o": "old_price", "c": "currency",
    "u": "url", "i": "image", "v": "vendor", "d": "description",
    "f": "feed_id", "fn": "feed_name", "fc": "feed_color", "fi": "feed_icon",
    "cat": "category_id", "a": "available", "sn": "short_note",
    "m": "model", "tp": "type", "id": "id",
}


# ===========================================================================
# Core local file helpers
# ===========================================================================


def _load_local_json(filepath: str) -> Optional[Any]:
    """Load and parse a local JSON file.

    Reads a JSON file from the local filesystem and returns the parsed
    data. Returns None if the file does not exist, cannot be read, or
    contains invalid JSON.

    Args:
        filepath: Absolute or relative path to the JSON file.

    Returns:
        Parsed JSON data (dict, list, etc.) or None on error.
    """
    if not os.path.isfile(filepath):
        logger.debug("Local file not found: %s", filepath)
        return None

    try:
        with open(filepath, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        logger.debug("Loaded local file: %s", filepath)
        return data
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("Invalid JSON in %s: %s", filepath, exc)
        return None
    except OSError as exc:
        logger.warning("Cannot read file %s: %s", filepath, exc)
        return None


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
    :func:`_generate_product_id` based on name, vendor, feed_id, and
    list index. The ID format ``{feed_id}-{idx}`` matches the Worker
    API so that static product pages are found at the same URL path.

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
            feed_id = str(product.get("feed_id", ""))
            pid = _generate_product_id(name, vendor, idx, feed_id)
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


def _generate_product_id(name: str, vendor: str, idx: int, feed_id: str = "") -> str:
    """Generate unique product ID matching Worker API format.

    When feed_id is available, uses ``{feed_id}-{idx}`` format which
    matches the Worker's getProducts() ID generation. This ensures
    that static HTML pages at /shop/{id}/index.html have the same
    ID as the Worker API returns, so product links always resolve.

    Falls back to ``{idx}_{hash_prefix}`` when no feed_id is given.

    Args:
        name: Product name.
        vendor: Product vendor/brand.
        idx: Index of the product in the list.
        feed_id: The feed/supplier ID (e.g. "25860"). When provided,
            generates ``{feed_id}-{idx}`` matching the Worker API.

    Returns:
        A unique string identifier for the product.
    """
    if feed_id:
        return f"{feed_id}-{idx}"
    # Fallback: hash-based ID when no feed_id available
    raw = f"{name}|{vendor}|{idx}"
    hash_hex = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:8]
    return f"{idx}_{hash_hex}"


def _expand_product_keys(products: list) -> list:
    """Expand compressed product keys (n->name, p->price, etc.) to readable names.

    The products JSON may use abbreviated field names to
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
    """Parse Admitad data from local JSON format.

    The Admitad JSON may be:
    - A dict with 'programs' key containing the list of programs
    - A list of programs directly
    - Empty/default

    This function normalizes to a flat list of program dicts with
    standard keys (name, image, category, gotoLink, etc.).

    Args:
        raw_data: Raw Admitad data.

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
# Index builders (built on the fly from posts)
# ===========================================================================


def _build_hashtag_index(posts: list) -> dict:
    """Build hashtag index from posts.

    Iterates over all posts, collects their hashtags, and builds:
    - A dict mapping each tag to a list of post IDs
    - A tag counts dict for popularity ranking

    Args:
        posts: List of post dicts (each may have a ``hashtags`` field).

    Returns:
        Dict with keys:
            - "index": dict mapping tag (str) -> list of post IDs
            - "tagCounts": dict mapping tag (str) -> count (int)
    """
    index: dict[str, list] = {}
    tag_counts: dict[str, int] = {}

    for post in posts:
        if not isinstance(post, dict):
            continue

        post_id = post.get("id")
        if post_id is None:
            continue

        hashtags = post.get("hashtags", [])
        if not isinstance(hashtags, list):
            continue

        for tag in hashtags:
            tag_str = str(tag).strip()
            if not tag_str:
                continue

            # Store under the tag as-is (e.g. "#автозапчасти")
            if tag_str not in index:
                index[tag_str] = []
            index[tag_str].append(post_id)

            tag_counts[tag_str] = tag_counts.get(tag_str, 0) + 1

    return {"index": index, "tagCounts": tag_counts}


def _build_search_index(posts: list) -> dict:
    """Build a simple tokenized search index from posts.

    Tokenizes each post's text and title into lowercase word tokens,
    then maps each token to a dict of {post_id: frequency} for relevance
    scoring.

    Args:
        posts: List of post dicts (each may have ``text`` and ``title`` fields).

    Returns:
        Dict mapping token (str) -> {post_id (int): count (int)}.
    """
    search_index: dict[str, dict[int, int]] = {}

    for post in posts:
        if not isinstance(post, dict):
            continue

        post_id = post.get("id")
        if post_id is None:
            continue

        # Combine text and title for tokenization
        text = str(post.get("text", "")) + " " + str(post.get("title", ""))

        # Tokenize: split on non-word chars, keep tokens of length >= 2
        tokens = re.findall(r"[a-zA-Zа-яА-ЯёЁ0-9]+", text.lower())
        tokens = [t for t in tokens if len(t) >= 2]

        # Count token occurrences in this post
        token_counts = Counter(tokens)

        for token, count in token_counts.items():
            if token not in search_index:
                search_index[token] = {}
            search_index[token][post_id] = search_index[token].get(post_id, 0) + count

    return search_index


def _build_popular_tags(hashtag_index_data: dict, limit: int = 200) -> list:
    """Build popular tags list from hashtag index data.

    Sorts tags by their count (frequency) in descending order and
    returns a list of dicts with ``tag`` and ``count`` keys.

    Args:
        hashtag_index_data: The hashtag index dict (with "tagCounts" key).
        limit: Maximum number of tags to return.

    Returns:
        List of dicts: [{"tag": "#автозапчасти", "count": 42}, ...]
    """
    tag_counts = hashtag_index_data.get("tagCounts", {})
    sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)
    return [{"tag": tag, "count": count} for tag, count in sorted_tags[:limit]]


def _build_related_posts(posts: list) -> dict:
    """Build related posts index based on shared hashtags.

    For each post, finds other posts that share at least one hashtag.
    Related posts are sorted by the number of shared hashtags (most
    related first), limited to 20 per post.

    Args:
        posts: List of post dicts (each with ``hashtags`` field).

    Returns:
        Dict mapping post_id (int) -> list of related post IDs.
    """
    # Build tag -> [post_ids] reverse index
    tag_to_posts: dict[str, list] = {}
    for post in posts:
        if not isinstance(post, dict):
            continue
        post_id = post.get("id")
        if post_id is None:
            continue
        for tag in post.get("hashtags", []):
            tag_str = str(tag).strip()
            if tag_str:
                if tag_str not in tag_to_posts:
                    tag_to_posts[tag_str] = []
                tag_to_posts[tag_str].append(post_id)

    # For each post, find related posts by shared tags
    related: dict[int, list] = {}
    for post in posts:
        if not isinstance(post, dict):
            continue
        post_id = post.get("id")
        if post_id is None:
            continue

        shared_counts: dict[int, int] = {}
        for tag in post.get("hashtags", []):
            tag_str = str(tag).strip()
            if tag_str in tag_to_posts:
                for other_id in tag_to_posts[tag_str]:
                    if other_id != post_id:
                        shared_counts[other_id] = shared_counts.get(other_id, 0) + 1

        # Sort by number of shared tags, keep top 20
        sorted_related = sorted(shared_counts.items(), key=lambda x: x[1], reverse=True)
        related[post_id] = [pid for pid, _ in sorted_related[:20]]

    return related


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

    # Try ISO format first (most common)
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


def _normalize_cached_posts(raw_posts: list) -> list:
    """Normalize posts from cached_posts.json format.

    The cached_posts.json format uses:
        - id: "channel/post_number" (e.g. "sochiautoparts/87923")
        - photo_urls: list of image URLs
        - video_urls: list of video URLs
        - text: post text
        - date: ISO date string
        - links: list of URLs found in the post
        - views: view count

    This function converts to the internal format:
        - id: integer (extracted from "channel/NNNN" string)
        - media: list of {"type": "photo"|"video", "directUrl": "...", "url": "..."}
        - title: generated from first line of text
        - hashtags: extracted from text
    """
    normalized = []
    for post in raw_posts:
        if not isinstance(post, dict):
            continue

        # Extract numeric post ID from "channel/NNNN" format
        raw_id = post.get("id", "")
        if isinstance(raw_id, str) and "/" in raw_id:
            try:
                post_id = int(raw_id.split("/")[-1])
            except (ValueError, IndexError):
                post_id = abs(hash(raw_id)) % 1000000
        elif isinstance(raw_id, (int, float)):
            post_id = int(raw_id)
        else:
            post_id = abs(hash(str(raw_id))) % 1000000

        # Build media list from photo_urls and video_urls
        media_list = []
        for photo_url in post.get("photo_urls", []):
            if isinstance(photo_url, str) and photo_url:
                media_list.append({"type": "photo", "directUrl": photo_url, "url": photo_url})
        for video_url in post.get("video_urls", []):
            if isinstance(video_url, str) and video_url:
                media_item = {"type": "video", "directUrl": video_url, "url": video_url}
                media_list.append(media_item)

        # Extract text and generate title
        text = post.get("text", "") or ""
        title = ""
        if text:
            first_line = text.split("\n")[0].strip()
            # Strip URLs from title
            first_line = re.sub(r"https?://\S+", "", first_line).strip()
            title = first_line[:100] if first_line else f"Пост {post_id}"

        # Extract hashtags from text (broad Unicode coverage)
        hashtags = []
        if text:
            hashtag_matches = re.findall(r"#([\w\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]+)", text, re.UNICODE)
            hashtags = ["#" + h for h in hashtag_matches]

        # Build the normalized post
        normalized_post = {
            "id": post_id,
            "slug": _generate_slug(title, post_id),
            "title": title,
            "text": text,
            "textWithHashtags": text,  # Keep original text with hashtags
            "date": post.get("date", ""),
            "media": media_list,
            "hashtags": hashtags,
            "views": post.get("views", 0),
            "links": post.get("links", []),
        }

        normalized.append(normalized_post)

    return normalized


def _normalize_telegram_media(posts: list) -> list:
    """Normalize media fields from telegram parser output.

    The telegram parser uses `photo_urls` and `video_urls` fields,
    while the rest of the generator expects a `media` list with items
    like {"type": "photo", "directUrl": "..."} or {"type": "video", "directUrl": "..."}.

    This function converts:
    - `photo_urls` -> media items with type "photo"
    - `video_urls` -> media items with type "video"
    - `video_thumbnails` -> poster field on video media items

    If a post already has a `media` field with content, it is left as-is.

    Args:
        posts: List of post dicts from telegram parser.

    Returns:
        List of post dicts with normalized media fields.
    """
    for post in posts:
        if not isinstance(post, dict):
            continue

        # Skip if media already exists and is populated
        existing_media = post.get("media", [])
        if isinstance(existing_media, list) and len(existing_media) > 0:
            continue

        photo_urls = post.get("photo_urls", [])
        video_urls = post.get("video_urls", [])
        video_thumbnails = post.get("video_thumbnails", [])

        if not photo_urls and not video_urls:
            # Also check legacy field names from telegram_fetcher
            photo_urls = post.get("photos", [])
            video_urls = post.get("videos", [])
            video_thumbnails = post.get("video_thumbnails", [])

        if not photo_urls and not video_urls:
            continue

        media_list = []
        for photo_url in photo_urls:
            if isinstance(photo_url, str) and photo_url:
                media_list.append({"type": "photo", "directUrl": photo_url, "url": photo_url})

        for idx, video_url in enumerate(video_urls):
            if isinstance(video_url, str) and video_url:
                media_item = {"type": "video", "directUrl": video_url, "url": video_url}
                # Attach poster/thumbnail if available
                if video_thumbnails and idx < len(video_thumbnails):
                    thumb = video_thumbnails[idx]
                    if isinstance(thumb, str) and thumb:
                        media_item["poster"] = thumb
                elif video_thumbnails and len(video_thumbnails) > 0:
                    # Use first thumbnail for all videos
                    media_item["poster"] = video_thumbnails[0]
                media_list.append(media_item)

        if media_list:
            post["media"] = media_list

    return posts


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


def _normalize_blog_posts(raw_posts: list) -> list:
    """Normalize blog posts from blog_posts.json (Blogger format).

    The blog_posts.json format uses:
        - id: "tag:blogger.com,1999:blog-XXX.post-YYY" (Blogger post ID)
        - title: post title
        - slug: URL-friendly slug from Blogger
        - content_html: HTML content of the post
        - content_text: plain text content
        - published: ISO date string
        - updated: ISO date string
        - thumbnail: thumbnail image URL
        - images: list of image URLs
        - description: short description/excerpt
        - tags: list of tags
        - categories: list of categories
        - author: dict with name and url
        - seo: dict with headline, description, etc.
        - json_ld: Schema.org JSON-LD dict

    This function converts to the internal articles format:
        - id: string (slug for URL)
        - slug: URL-friendly slug
        - title: post title
        - content: HTML content
        - text: plain text content
        - date: ISO date string (published)
        - media: list of {"type": "photo", "directUrl": "...", "url": "..."}
        - thumbnail: thumbnail URL
        - description: short description
        - hashtags: list of tags (from tags/categories)
        - author: author name
    """
    normalized = []
    for post in raw_posts:
        if not isinstance(post, dict):
            continue

        # Use slug as ID for URL routing
        slug = post.get("slug", "")
        if not slug:
            # Generate slug from title
            title = post.get("title", "")
            slug = _generate_slug(title, abs(hash(title)) % 100000)

        # Build media list from images
        media_list = []
        thumbnail = post.get("thumbnail", "")
        # Add thumbnail as first image if available
        if thumbnail and isinstance(thumbnail, str):
            media_list.append({"type": "photo", "directUrl": thumbnail, "url": thumbnail})
        # Add other images
        for img_url in post.get("images", []):
            if isinstance(img_url, str) and img_url != thumbnail:
                media_list.append({"type": "photo", "directUrl": img_url, "url": img_url})

        # Extract hashtags from tags and categories
        hashtags = []
        for tag in post.get("tags", []):
            tag_str = str(tag).strip()
            if tag_str and not tag_str.startswith("#"):
                hashtags.append(f"#{tag_str}")
            elif tag_str:
                hashtags.append(tag_str)
        for cat in post.get("categories", []):
            cat_str = str(cat).strip()
            if cat_str and not cat_str.startswith("#"):
                hashtags.append(f"#{cat_str}")
            elif cat_str:
                hashtags.append(cat_str)

        # Get author name
        author_data = post.get("author", {})
        author_name = ""
        if isinstance(author_data, dict):
            author_name = author_data.get("name", "")
        elif isinstance(author_data, str):
            author_name = author_data

        # Get description
        description = post.get("description", "") or post.get("content_text", "")[:200] or ""

        # Build the normalized article
        normalized_article = {
            "id": slug,  # Use slug as the article ID for URL routing
            "slug": slug,
            "title": post.get("title", ""),
            "content": post.get("content_html", ""),
            "text": post.get("content_text", ""),
            "textWithHashtags": post.get("content_text", ""),
            "date": post.get("published", ""),
            "updated": post.get("updated", ""),
            "media": media_list,
            "thumbnail": thumbnail,
            "description": description,
            "hashtags": hashtags,
            "author": author_name,
            "url": post.get("url", ""),
            "original_url": post.get("original_url", ""),
            "seo": post.get("seo", {}),
            "json_ld": post.get("json_ld", {}),
            "word_count": post.get("word_count", 0),
            "image_count": post.get("image_count", 0),
        }

        normalized.append(normalized_article)

    return normalized


def load_data(data_dir: str = "data", force_refresh: bool = False) -> dict:
    """Load all data from LOCAL files only.

    Reads data from the local ``data_dir`` directory:
    - Posts from telegram_parser output (data/telegram_posts/)
    - Products from data/products.json
    - Admitad from data/admitad_ads.json

    Builds auxiliary indexes (hashtag_index, search_index, popular_tags,
    related_posts) on the fly from the posts data.

    The ``force_refresh`` parameter is accepted for API compatibility
    but is not used since all data is local.

    Args:
        data_dir: Local directory containing data files. Defaults to ``"data"``.
        force_refresh: Ignored (kept for API compatibility).

    Returns:
        Dict with keys:
            - posts: list of post dicts (sorted by date, newest first)
            - articles: empty list (not used in local-only mode)
            - seo_posts: empty dict
            - seo_articles: empty dict
            - schema_posts: empty dict
            - schema_articles: empty dict
            - search_index: dict of tokenized search index (built from posts)
            - hashtag_index: dict of tag -> post IDs mapping
            - popular_tags: list of top tags sorted by frequency
            - related_posts: dict of post_id -> related post IDs
            - products: list of product dicts
            - admitad_programs: list of Admitad affiliate programs
            - post_map: dict of post_id -> post
            - product_map: dict of product_id -> product
            - category_map: dict of category_slug -> list of products
    """
    result: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Load posts from cached_posts.json (downloaded hourly by GitHub Actions)
    # ------------------------------------------------------------------
    cached_posts_path = os.path.join(data_dir, "cached_posts.json")
    all_posts = []

    if os.path.isfile(cached_posts_path):
        raw_posts = _load_local_json(cached_posts_path)
        if isinstance(raw_posts, list):
            all_posts = _normalize_cached_posts(raw_posts)
            logger.info("Loaded %d posts from %s", len(all_posts), cached_posts_path)
        else:
            logger.warning("cached_posts.json is not a list, trying telegram_posts directory")
    else:
        logger.warning("No cached_posts.json found at %s, trying telegram_posts directory", cached_posts_path)

    # Fallback: try loading from old telegram_posts directory
    if not all_posts:
        tg_posts_dir = os.path.join(data_dir, "telegram_posts")
        if os.path.isdir(tg_posts_dir):
            all_posts = _load_telegram_archive(tg_posts_dir)
            if all_posts:
                all_posts = _normalize_telegram_media(all_posts)
                logger.info("Fallback: loaded %d posts from telegram_posts/", len(all_posts))

    all_posts = _validate_and_normalize_posts(all_posts)
    result["posts"] = all_posts

    logger.info(
        "Loaded %d posts total",
        len(all_posts),
    )

    # ------------------------------------------------------------------
    # Load products from local file (products.json is the primary source)
    # ------------------------------------------------------------------
    products_path = os.path.join(data_dir, _PRODUCTS_FILENAME)
    products_data = _load_local_json(products_path)

    # If products.json doesn't exist, try loading from the paginated
    # data/products/ directory instead (used by the Worker API).
    # DO NOT load both — they contain the same data and would cause duplicates.
    if products_data is None:
        products_dir = os.path.join(data_dir, "products")
        if os.path.isdir(products_dir):
            import glob as _glob
            products_data = []
            for pfile in sorted(_glob.glob(os.path.join(products_dir, "page_*.json"))):
                extra = _load_local_json(pfile)
                if isinstance(extra, list):
                    products_data.extend(extra)

    if isinstance(products_data, list):
        result["products"] = products_data
    elif isinstance(products_data, dict):
        result["products"] = products_data.get("products", products_data.get("items", []))
    else:
        result["products"] = []
        logger.warning("No products data found at %s", products_path)

    logger.info("Loaded %d products", len(result["products"]))

    # ------------------------------------------------------------------
    # Load admitad from local file
    # ------------------------------------------------------------------
    admitad_path = os.path.join(data_dir, _ADMITAD_FILENAME)
    admitad_data = _load_local_json(admitad_path)

    if admitad_data is not None:
        result["admitad_programs"] = admitad_data
    else:
        result["admitad_programs"] = []
        logger.warning("No admitad data found at %s", admitad_path)

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

    # Build slug_map for slug-based lookups
    slug_map = {}
    for post in result["posts"]:
        slug = post.get("slug", "")
        if slug:
            slug_map[slug] = post
    result["slug_map"] = slug_map
    logger.info("Built slug_map with %d entries", len(slug_map))

    # ------------------------------------------------------------------
    # Build indexes on the fly from posts (no pipeline dependency)
    # ------------------------------------------------------------------

    # Build hashtag_index from posts
    hashtag_index_data = _build_hashtag_index(result["posts"])
    result["hashtag_index"] = hashtag_index_data["index"]
    result["hashtag_index_full"] = hashtag_index_data
    logger.info("Built hashtag_index: %d tags", len(hashtag_index_data["index"]))

    # Build popular_tags from hashtag counts
    result["popular_tags"] = _build_popular_tags(hashtag_index_data)
    logger.info("Built popular_tags: %d tags", len(result["popular_tags"]))

    # Build search_index from posts
    result["search_index"] = _build_search_index(result["posts"])
    logger.info("Built search_index: %d tokens", len(result["search_index"]))

    # Build related_posts from posts
    result["related_posts"] = _build_related_posts(result["posts"])
    logger.info("Built related_posts: %d entries", len(result["related_posts"]))

    # ------------------------------------------------------------------
    # Load blog articles from blog_posts.json (from Blogger via newblosap repo)
    # ------------------------------------------------------------------
    blog_posts_path = os.path.join(data_dir, "blog_posts.json")
    all_articles = []

    if os.path.isfile(blog_posts_path):
        raw_blog = _load_local_json(blog_posts_path)
        if isinstance(raw_blog, dict) and "posts" in raw_blog:
            all_articles = _normalize_blog_posts(raw_blog["posts"])
            logger.info("Loaded %d articles from %s", len(all_articles), blog_posts_path)
        elif isinstance(raw_blog, list):
            all_articles = _normalize_blog_posts(raw_blog)
            logger.info("Loaded %d articles from %s", len(all_articles), blog_posts_path)
        else:
            logger.warning("blog_posts.json format not recognized at %s", blog_posts_path)
    else:
        logger.info("No blog_posts.json found at %s — articles page will be empty", blog_posts_path)

    # Sort articles by date (newest first)
    all_articles = _sort_posts_by_date(all_articles)
    result["articles"] = all_articles
    logger.info("Loaded %d articles (sorted by date, newest first)", len(all_articles))

    # Build article_map for O(1) lookups
    article_map = {}
    for art in all_articles:
        art_slug = art.get("slug", "")
        art_id = art.get("id", "")
        if art_slug:
            article_map[art_slug] = art
        if art_id:
            article_map[str(art_id)] = art
    result["article_map"] = article_map

    # ------------------------------------------------------------------
    # Empty defaults for keys that were previously from pipeline
    # ------------------------------------------------------------------
    result["seo_posts"] = {}
    result["seo_articles"] = {}
    result["schema_posts"] = {}
    result["schema_articles"] = {}

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


def get_post_by_slug(data: dict, slug: str) -> Optional[dict]:
    """Get post by slug from loaded data.

    Args:
        data: The data dict returned by load_data().
        slug: The post slug to look up.

    Returns:
        The post dict if found, otherwise None.
    """
    slug_map = data.get("slug_map", {})
    return slug_map.get(slug)


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
    """Force a full refresh of all data.

    Shortcut for ``load_data(data_dir, force_refresh=True)``.
    Since all data is local, this simply re-reads the files.

    Args:
        data_dir: Local directory containing data files.

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
    print("SochiAutoParts Data Loader — Standalone Test (LOCAL ONLY)")
    print("=" * 60)

    data = load_data()

    print(f"\nPosts:        {len(data['posts'])}")
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
