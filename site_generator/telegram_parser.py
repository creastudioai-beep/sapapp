#!/usr/bin/env python3
"""
Telegram Web Parser for SochiAutoParts.

Scrapes the public web preview of a Telegram channel (t.me/s/{channel})
using requests + BeautifulSoup, with support for:

  --full       : Full archive scan (up to PARSE_LIMIT=15000 posts, daily)
  --recent     : Update only the latest N posts (default 50)

Features:
  - Pagination via ?before=<post_id> parameter
  - Random User-Agent rotation and jitter delay for anti-detection
  - Tenacity-based retry with exponential backoff
  - Incremental updates: merge new/updated posts into existing cache
  - Paginated JSON storage (50 posts per file) for efficient access
  - Atomic file writes to prevent corruption
  - FNV-1a media hash mapping for URL shortening

Usage:
  python telegram_parser.py --full          # Full daily parse (up to 15000)
  python telegram_parser.py --recent 50     # Hourly update of latest 50 posts

Based on reference implementation: https://github.com/creastudioai-beep/sap
"""

import argparse
import json
import logging
import os
import random
import re
import shutil
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

# =============================================================================
# Configuration
# =============================================================================

CHANNEL_USERNAME: str = os.environ.get("CHANNEL_USERNAME", "sochiautoparts")
BASE_URL: str = f"https://t.me/s/{CHANNEL_USERNAME}"

PARSE_LIMIT: int = int(os.environ.get("PARSE_LIMIT", "15000"))  # Max posts for --full (matches MAX_POSTS in config)
RECENT_LIMIT: int = int(os.environ.get("RECENT_LIMIT", "50"))    # Max posts for --recent
POSTS_PER_FILE: int = 50  # Posts per paginated JSON file

MAX_RETRIES: int = int(os.environ.get("MAX_RETRIES", "5"))
REQUEST_DELAY_MIN: float = float(os.environ.get("REQUEST_DELAY_MIN", "0.8"))
REQUEST_DELAY_MAX: float = float(os.environ.get("REQUEST_DELAY_MAX", "1.5"))

# Output directories
DATA_DIR: str = os.environ.get("DATA_DIR", "data/telegram_posts")
LOG_FILE: str = os.environ.get("LOG_FILE", "data/telegram_posts/parser.log")

# User agents for rotation
USER_AGENTS: List[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]

# =============================================================================
# Logging
# =============================================================================

def setup_logging() -> logging.Logger:
    """Setup rotating file + console logger."""
    log_dir = os.path.dirname(LOG_FILE)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    logger = logging.getLogger("telegram_parser")
    logger.setLevel(logging.INFO)

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(ch)

    # File handler with rotation
    try:
        from logging.handlers import RotatingFileHandler
        fh = RotatingFileHandler(
            LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        fh.setLevel(logging.INFO)
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logger.addHandler(fh)
    except Exception as e:
        logger.warning(f"Could not setup file logging: {e}")

    return logger


logger = setup_logging()


# =============================================================================
# FNV-1a Hash (for media URL shortening)
# =============================================================================

def fnv1a_32(data: str) -> int:
    """FNV-1a 32-bit hash."""
    h = 0x811C9DC5
    for byte in data.encode("utf-8"):
        h ^= byte
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h


def hash_to_base36(num: int) -> str:
    """Convert integer to base36 string."""
    if num == 0:
        return "0"
    chars = "0123456789abcdefghijklmnopqrstuvwxyz"
    result = ""
    while num > 0:
        result = chars[num % 36] + result
        num //= 36
    return result


def media_hash(url: str) -> str:
    """Generate short hash key for a media URL."""
    return hash_to_base36(fnv1a_32(url))


# =============================================================================
# Atomic file write
# =============================================================================

def atomic_write(filepath: str, data: str) -> None:
    """Write data to file atomically using temp file + rename."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=os.path.dirname(filepath), suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
        shutil.move(tmp_path, filepath)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


# =============================================================================
# Session setup
# =============================================================================

def create_session() -> requests.Session:
    """Create a requests session with browser-like headers."""
    session = requests.Session()
    session.headers.update({
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    })
    return session


# =============================================================================
# Fetch page with retry
# =============================================================================

@retry(
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type((requests.RequestException, requests.Timeout)),
    reraise=True,
)
def fetch_page(session: requests.Session, url: str) -> str:
    """Fetch a single page from Telegram web preview."""
    ua = random.choice(USER_AGENTS)
    session.headers["User-Agent"] = ua

    response = session.get(url, timeout=30)

    if len(response.content) < 500:
        raise ValueError(
            f"Suspiciously small response ({len(response.content)} bytes) — "
            f"possible ban or captcha from Telegram"
        )

    return response.text


# =============================================================================
# Parse a single post from HTML
# =============================================================================

def parse_post(wrap_element) -> Optional[Dict[str, Any]]:
    """Parse a single Telegram post from its HTML wrapper element.

    Returns a dict with: id, date, text, photo_urls, video_urls, links, views
    """
    try:
        # Post ID from data-post attribute (e.g. "sochiautoparts/87911")
        msg_div = wrap_element.find("div", class_="tgme_widget_message")
        if not msg_div:
            return None

        data_post = msg_div.get("data-post", "")
        if not data_post:
            return None

        # Extract numeric ID
        parts = data_post.split("/")
        post_id = parts[-1] if len(parts) >= 2 else data_post

        # Date
        time_elem = wrap_element.find("time")
        date_str = ""
        if time_elem and time_elem.get("datetime"):
            date_str = time_elem["datetime"]

        # Text content
        text_div = wrap_element.find("div", class_="tgme_widget_message_text")
        text = ""
        if text_div:
            # Replace <br> with newlines before extracting text
            for br in text_div.find_all("br"):
                br.replace_with("\n")
            text = text_div.get_text(separator="\n", strip=True)

        # Photos
        photo_urls = []
        photo_wraps = wrap_element.find_all("a", class_="tgme_widget_message_photo_wrap")
        for pw in photo_wraps:
            style = pw.get("style", "")
            url_match = re.search(r"url\(['\"]?(.+?)['\"]?\)", style)
            if url_match:
                photo_urls.append(url_match.group(1))

        # Videos (with thumbnails)
        video_urls = []
        video_thumbnails = []
        video_wraps = wrap_element.find_all("div", class_="tgme_widget_message_video_wrap")
        for vw in video_wraps:
            video_elem = vw.find("video")
            if video_elem and video_elem.get("src"):
                video_urls.append(video_elem["src"])
                # Extract poster attribute from video element
                poster = video_elem.get("poster", "")
                if poster:
                    video_thumbnails.append(poster)
            else:
                source_elem = vw.find("source")
                if source_elem and source_elem.get("src"):
                    video_urls.append(source_elem["src"])
            # Also try to extract thumbnail from background-image style
            # Telegram web preview uses: style="background-image:url('...')"
            if not video_thumbnails or len(video_thumbnails) < len(video_urls):
                style = vw.get("style", "")
                thumb_match = re.search(r"background-image\s*:\s*url\(['\"]?(.+?)['\"]?\)", style)
                if thumb_match:
                    idx = len(video_urls) - 1
                    if idx >= len(video_thumbnails):
                        video_thumbnails.append(thumb_match.group(1))
                    elif not video_thumbnails[idx]:
                        video_thumbnails[idx] = thumb_match.group(1)
            # Also check for <img> inside the video wrapper (Telegram sometimes uses img as poster)
            if not video_thumbnails or len(video_thumbnails) < len(video_urls):
                img_elem = vw.find("img")
                if img_elem and img_elem.get("src"):
                    idx = len(video_urls) - 1
                    if idx >= len(video_thumbnails):
                        video_thumbnails.append(img_elem["src"])

        # Views
        views = None
        views_elem = wrap_element.find("span", class_="tgme_widget_message_views")
        if views_elem:
            views_text = views_elem.get_text(strip=True)
            views = parse_views(views_text)

        # Links
        links = []
        if text_div:
            for a_tag in text_div.find_all("a", href=True):
                href = a_tag["href"]
                if href.startswith("http") and "t.me/" not in href:
                    links.append(href)
        # Also check link previews
        link_preview = wrap_element.find("a", class_="tgme_widget_message_link_preview")
        if link_preview and link_preview.get("href"):
            href = link_preview["href"]
            if href.startswith("http") and "t.me/" not in href:
                links.append(href)

        return {
            "id": post_id,
            "date": date_str,
            "text": text,
            "photo_urls": photo_urls,
            "video_urls": video_urls,
            "video_thumbnails": video_thumbnails,
            "links": links,
            "views": views,
        }

    except Exception as e:
        logger.error(f"Error parsing post: {e}")
        return None


def parse_views(views_text: str) -> Optional[int]:
    """Parse view count text like '1.2K' or '15.3M' into integer."""
    if not views_text:
        return None
    views_text = views_text.strip().replace(",", "").replace(" ", "")
    try:
        multiplier = 1
        if views_text.upper().endswith("K"):
            multiplier = 1000
            views_text = views_text[:-1]
        elif views_text.upper().endswith("M"):
            multiplier = 1_000_000
            views_text = views_text[:-1]
        return int(float(views_text) * multiplier)
    except (ValueError, TypeError):
        return None


# =============================================================================
# Full parse: collect up to PARSE_LIMIT posts
# =============================================================================

def parse_full(session: requests.Session, limit: int = PARSE_LIMIT) -> List[Dict]:
    """Full parse: scrape all posts up to limit."""
    logger.info(f"Starting FULL parse with limit={limit}")

    all_posts: Dict[str, Dict] = {}  # id -> post (dedup)
    next_url = BASE_URL
    page_count = 0

    while len(all_posts) < limit:
        page_count += 1
        logger.info(
            f"Fetching page {page_count} — collected {len(all_posts)} posts — "
            f"URL: {next_url}"
        )

        try:
            html = fetch_page(session, next_url)
        except Exception as e:
            if len(all_posts) > 0:
                logger.warning(f"Fetch failed after {len(all_posts)} posts collected: {e}")
                break
            else:
                logger.error(f"Fetch failed on first page: {e}")
                raise

        soup = BeautifulSoup(html, "html.parser")

        # Find all post wrappers
        wraps = soup.find_all("div", class_="tgme_widget_message_wrap")
        if not wraps:
            logger.info("No more posts found on page")
            break

        new_count = 0
        for wrap in wraps:
            post = parse_post(wrap)
            if post and post["id"] not in all_posts:
                all_posts[post["id"]] = post
                new_count += 1

        logger.info(f"Page {page_count}: found {len(wraps)} elements, {new_count} new posts")

        # Find "Load more" button for pagination
        load_more = soup.find("a", class_="tme_messages_more")
        if not load_more or not load_more.get("href"):
            logger.info("No 'Load more' button found — reached end of channel")
            break

        from urllib.parse import urljoin
        next_url = urljoin("https://t.me", load_more["href"])

        # Jitter delay between page fetches
        delay = random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX)
        time.sleep(delay)

    posts_list = list(all_posts.values())
    logger.info(f"FULL parse complete: {len(posts_list)} posts across {page_count} pages")
    return posts_list


# =============================================================================
# Recent parse: collect only the latest N posts
# =============================================================================

def parse_recent(session: requests.Session, limit: int = RECENT_LIMIT) -> List[Dict]:
    """Recent parse: scrape only the latest N posts from the first page(s)."""
    logger.info(f"Starting RECENT parse with limit={limit}")

    all_posts: Dict[str, Dict] = {}
    next_url = BASE_URL
    page_count = 0
    max_pages = (limit // 20) + 3  # ~20 posts per page, with buffer

    while len(all_posts) < limit and page_count < max_pages:
        page_count += 1
        logger.info(f"Fetching recent page {page_count} — collected {len(all_posts)} posts")

        try:
            html = fetch_page(session, next_url)
        except Exception as e:
            logger.warning(f"Fetch failed: {e}")
            break

        soup = BeautifulSoup(html, "html.parser")
        wraps = soup.find_all("div", class_="tgme_widget_message_wrap")
        if not wraps:
            break

        for wrap in wraps:
            post = parse_post(wrap)
            if post and post["id"] not in all_posts:
                all_posts[post["id"]] = post

        if len(all_posts) >= limit:
            break

        # Try to load more if we haven't reached the limit yet
        load_more = soup.find("a", class_="tme_messages_more")
        if not load_more or not load_more.get("href"):
            break

        from urllib.parse import urljoin
        next_url = urljoin("https://t.me", load_more["href"])

        delay = random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX)
        time.sleep(delay)

    # Sort by ID descending and take top N
    posts_list = sorted(all_posts.values(), key=lambda p: int(p["id"]) if p["id"].isdigit() else 0, reverse=True)
    posts_list = posts_list[:limit]

    logger.info(f"RECENT parse complete: {len(posts_list)} posts")
    return posts_list


# =============================================================================
# Storage: save posts to paginated JSON files
# =============================================================================

def save_posts(posts: List[Dict], data_dir: str = DATA_DIR, merge: bool = True) -> None:
    """Save posts to paginated JSON files with optional merge into existing data.

    Args:
        posts: List of post dicts to save
        data_dir: Directory for output files
        merge: If True, merge with existing posts (incremental update)
    """
    os.makedirs(data_dir, exist_ok=True)

    # Load existing posts if merging
    existing_posts: Dict[str, Dict] = {}
    if merge:
        existing_posts = load_all_posts(data_dir)
        logger.info(f"Loaded {len(existing_posts)} existing posts for merge")

    # Merge: new posts update existing, new IDs are added
    for post in posts:
        pid = str(post.get("id", ""))
        if pid:
            existing_posts[pid] = post

    logger.info(f"After merge: {len(existing_posts)} total posts")

    # Sort by post ID descending
    sorted_posts = sorted(
        existing_posts.values(),
        key=lambda p: int(p.get("id", "0")) if str(p.get("id", "0")).isdigit() else 0,
        reverse=True,
    )

    # Paginate into files
    total_pages = (len(sorted_posts) + POSTS_PER_FILE - 1) // POSTS_PER_FILE

    for page_num in range(1, total_pages + 1):
        start = (page_num - 1) * POSTS_PER_FILE
        end = start + POSTS_PER_FILE
        page_posts = sorted_posts[start:end]

        filepath = os.path.join(data_dir, f"page_{page_num}.json")
        atomic_write(filepath, json.dumps(page_posts, ensure_ascii=False, indent=2))

    # Write meta.json
    meta = {
        "total_posts": len(sorted_posts),
        "pages_count": total_pages,
        "posts_per_page": POSTS_PER_FILE,
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "channel": CHANNEL_USERNAME,
        "parse_limit": PARSE_LIMIT,
    }
    atomic_write(os.path.join(data_dir, "meta.json"), json.dumps(meta, ensure_ascii=False, indent=2))

    # Save latest 10 posts
    latest = sorted_posts[:10]
    atomic_write(
        os.path.join(data_dir, "latest_posts.json"),
        json.dumps(latest, ensure_ascii=False, indent=2),
    )

    # Build and save media map (FNV-1a hash -> URL)
    media_map = {}
    for post in sorted_posts:
        for url in post.get("photo_urls", []):
            media_map[media_hash(url)] = url
        for url in post.get("video_urls", []):
            media_map[media_hash(url)] = url

    atomic_write(
        os.path.join(data_dir, "media_map.json"),
        json.dumps(media_map, ensure_ascii=False, indent=2),
    )

    # Cleanup old page files that are no longer needed
    for fname in os.listdir(data_dir):
        if fname.startswith("page_") and fname.endswith(".json"):
            try:
                page_num = int(fname.replace("page_", "").replace(".json", ""))
                if page_num > total_pages:
                    os.remove(os.path.join(data_dir, fname))
                    logger.info(f"Removed old page file: {fname}")
            except ValueError:
                pass

    logger.info(f"Saved {len(sorted_posts)} posts to {total_pages} pages in {data_dir}")


def load_all_posts(data_dir: str) -> Dict[str, Dict]:
    """Load all existing posts from paginated JSON files."""
    posts: Dict[str, Dict] = {}
    meta_path = os.path.join(data_dir, "meta.json")

    if not os.path.exists(meta_path):
        return posts

    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        total_pages = meta.get("pages_count", 0)
    except Exception:
        # Fallback: scan directory for page files
        total_pages = 0
        for fname in os.listdir(data_dir):
            if fname.startswith("page_") and fname.endswith(".json"):
                try:
                    pn = int(fname.replace("page_", "").replace(".json", ""))
                    total_pages = max(total_pages, pn)
                except ValueError:
                    pass

    for page_num in range(1, total_pages + 1):
        filepath = os.path.join(data_dir, f"page_{page_num}.json")
        if not os.path.exists(filepath):
            continue
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                page_posts = json.load(f)
            for post in page_posts:
                pid = str(post.get("id", ""))
                if pid:
                    posts[pid] = post
        except Exception as e:
            logger.warning(f"Error loading {filepath}: {e}")

    return posts


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Telegram Web Parser for SochiAutoParts")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--full", action="store_true", help="Full archive parse (up to PARSE_LIMIT)")
    group.add_argument("--recent", type=int, nargs="?", const=RECENT_LIMIT,
                       help="Parse only the latest N posts (default: 50)")
    parser.add_argument("--data-dir", default=DATA_DIR, help="Output data directory")
    parser.add_argument("--limit", type=int, default=PARSE_LIMIT, help="Max posts for --full mode")

    args = parser.parse_args()

    start_time = time.time()
    session = create_session()

    try:
        if args.full:
            posts = parse_full(session, limit=args.limit)
            save_posts(posts, data_dir=args.data_dir, merge=True)
        elif args.recent is not None:
            posts = parse_recent(session, limit=args.recent)
            save_posts(posts, data_dir=args.data_dir, merge=True)
    except Exception as e:
        logger.error(f"Parse failed: {e}")
        sys.exit(1)

    elapsed = time.time() - start_time
    logger.info(f"Parser finished in {elapsed:.1f} seconds")


if __name__ == "__main__":
    main()
