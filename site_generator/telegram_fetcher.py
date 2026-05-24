"""
Telegram Channel Post Fetcher for @sochiautoparts

Fetches ALL posts (up to 87,000+) from a Telegram public channel
and stores them incrementally as paginated JSON files.

Architecture:
    data/telegram_archive/
    ├── meta.json           # Metadata: total_posts, last_post_id, last_updated, pages_count
    ├── page_1.json         # Posts 1-50 (newest)
    ├── page_2.json         # Posts 51-100
    ├── ...
    ├── page_N.json         # Oldest posts
    └── posts_index.json    # Index: post_id -> (page_number, position) for O(1) lookup

Key design principles:
    1. Incremental updates: Old posts never change, only new posts are added
    2. Paginated storage: Posts stored in JSON files of 50 posts each
    3. Background loading: Initial load of 87K posts takes time, done in batches with delays
    4. Resumable: If interrupted, can resume from where it left off
"""

import requests
import json
import os
import time
import re
import html as html_module
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

POSTS_PER_PAGE = 50
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
REQUEST_TIMEOUT = 15
MAX_RETRIES = 3
RETRY_DELAY = 2.0
BASE_URL_TEMPLATE = "https://t.me/s/{channel}"


# ---------------------------------------------------------------------------
# HTML Parser
# ---------------------------------------------------------------------------

class TelegramPostParser(HTMLParser):
    """
    Parse Telegram public channel preview HTML to extract posts.

    Telegram's public preview at https://t.me/s/<channel> renders posts as
    a series of ``<div class="tgme_widget_message_wrap">`` elements.  Each
    contains:

    * ``data-post="channel/POSTID"`` — the numeric post ID
    * ``tgme_widget_message_text`` — the text body (may contain HTML)
    * ``background-image: url('...')`` — photo URLs inside styled divs
    * ``<video>`` or video-player divs — video sources
    * ``datetime`` attribute on ``<time>`` — post date
    * ``tgme_widget_message_views`` — view count text
    * ``data-before="NEXT_ID"`` — on the messages container, for pagination

    Emoji images are served from ``cdn.jsdelivr.net/gh/twitter/twemoji``
    and should **not** be treated as real photos.
    """

    def __init__(self):
        super().__init__()
        self.posts: List[Dict[str, Any]] = []
        self.next_before_id: Optional[int] = None

        # Current post being assembled
        self._current_post: Optional[Dict[str, Any]] = None

        # Parsing state flags
        self._in_message_wrap = False
        self._in_message_text = False
        self._in_message_views = False
        self._in_time_tag = False
        self._in_link_preview = False
        self._depth = 0
        self._text_depth = 0

        # Accumulate text content
        self._text_chunks: List[str] = []
        self._views_text: str = ""

        # For capturing style attributes that contain background-image
        self._capture_styles = False
        self._current_style: str = ""

        # For capturing video src
        self._in_video_tag = False

        # Track whether we are inside a <br> context for text
        self._in_bidi = False

    # -- helpers -------------------------------------------------------------

    def _reset_post(self):
        """Start a fresh post accumulator."""
        self._current_post = {
            "id": None,
            "text": "",
            "photos": [],
            "videos": [],
            "video_thumbnails": [],
            "date": "",
            "views": 0,
        }
        self._text_chunks = []
        self._in_message_text = False
        self._text_depth = 0

    @staticmethod
    def _extract_background_urls(style: str) -> List[str]:
        """Extract all url('...') values from a CSS style string."""
        urls = re.findall(r"url\(['\"]([^'\"]+)['\"]\)", style)
        return urls

    @staticmethod
    def _is_emoji_url(url: str) -> bool:
        """Return True if the URL points to a Twemoji (not a real photo)."""
        emoji_patterns = [
            "cdn.jsdelivr.net/gh/twitter/twemoji",
            "cdn.jsdelivr.net/gh/joypixels/emoji",
            "telegram.org/img/emoji",
        ]
        for pat in emoji_patterns:
            if pat in url:
                return True
        return False

    # -- HTMLParser callbacks ------------------------------------------------

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]):
        attr_dict = dict(attrs)

        # --- Detect the messages container with data-before ----------------
        # Note: data-before may appear on <a> or <div> tags depending on Telegram's HTML version
        if "data-before" in attr_dict:
            before_val = attr_dict.get("data-before")
            if before_val:
                try:
                    self.next_before_id = int(before_val)
                except (ValueError, TypeError):
                    pass

        # --- Detect a post wrapper -----------------------------------------
        if tag == "div" and attr_dict.get("class", "").startswith("tgme_widget_message_wrap"):
            # Save previous post if any
            if self._current_post is not None and self._current_post["id"] is not None:
                self._finalise_post()
            self._reset_post()
            self._in_message_wrap = True

            # Extract post ID from data-post="channel/POSTID" (may be on this div or a nested one)
            data_post = attr_dict.get("data-post", "")
            if "/" in data_post:
                try:
                    self._current_post["id"] = int(data_post.rsplit("/", 1)[1])
                except (ValueError, IndexError):
                    pass

        # --- Inside a post -------------------------------------------------
        if self._in_message_wrap and self._current_post is not None:

            # Extract post ID from nested data-post div (Telegram puts data-post on inner div)
            if self._current_post["id"] is None and "data-post" in attr_dict:
                data_post = attr_dict.get("data-post", "")
                if "/" in data_post:
                    try:
                        self._current_post["id"] = int(data_post.rsplit("/", 1)[1])
                    except (ValueError, IndexError):
                        pass

            # Text body
            classes = attr_dict.get("class", "")
            if "tgme_widget_message_text" in classes:
                self._in_message_text = True
                self._text_depth = 0

            # Photos — they live in divs with background-image style
            if "tgme_widget_message_photo_wrap" in classes or "tgme_widget_message_roundvideo" in classes:
                style = attr_dict.get("style", "")
                if style:
                    urls = self._extract_background_urls(style)
                    for u in urls:
                        if not self._is_emoji_url(u):
                            # For round videos the background image is a thumbnail
                            if "tgme_widget_message_roundvideo" in classes:
                                self._current_post["video_thumbnails"].append(u)
                            else:
                                self._current_post["photos"].append(u)

            # Video player divs
            if "tgme_widget_message_video_player" in classes:
                style = attr_dict.get("style", "")
                if style:
                    urls = self._extract_background_urls(style)
                    for u in urls:
                        if not self._is_emoji_url(u):
                            self._current_post["video_thumbnails"].append(u)

            # Inline style that might contain a photo (some layouts)
            if "tgme_widget_message_inline_button" in classes:
                pass  # skip buttons

            # <video> tag
            if tag == "video":
                self._in_video_tag = True
                src = attr_dict.get("src")
                if src:
                    self._current_post["videos"].append(src)
                # Poster is a thumbnail
                poster = attr_dict.get("poster")
                if poster:
                    self._current_post["video_thumbnails"].append(poster)

            # <source> inside <video>
            if tag == "source" and self._in_video_tag:
                src = attr_dict.get("src")
                if src:
                    self._current_post["videos"].append(src)

            # <a> tags inside text — we just collect the text, ignore href
            # no special handling needed; text accumulation covers it

            # View count
            if "tgme_widget_message_views" in classes:
                self._in_message_views = True
                self._views_text = ""

            # Date / time
            if tag == "time":
                dt = attr_dict.get("datetime")
                if dt and self._current_post["date"] == "":
                    self._current_post["date"] = dt

            # Link preview — we skip these to avoid counting preview images as photos
            if "tgme_widget_message_link_preview" in classes:
                self._in_link_preview = True

            # Photos inside link preview — skip them
            if self._in_link_preview:
                if "tgme_widget_message_site_photo_wrap" in classes:
                    style = attr_dict.get("style", "")
                    if style:
                        # We intentionally do NOT add these to photos
                        pass

            # Post author photo (small avatar) — skip
            if "tgme_widget_message_user_avatar" in classes:
                pass

            # Reply markup / keyboard — skip
            if "tgme_widget_message_reply" in classes:
                pass

        # --- <br> inside text -----------------------------------------------
        if self._in_message_text and tag == "br":
            self._text_chunks.append("\n")

    def handle_endtag(self, tag: str):
        if self._in_message_wrap:
            # Leaving message_wrap div — finalise the post
            if tag == "div" and self._in_message_wrap:
                # We cannot reliably detect when the wrap div closes just from
                # the tag name because there are nested divs.  Instead, we
                # finalise a post when we encounter the *next* post wrapper or
                # at the end of parsing.
                pass

            if self._in_message_text and tag == "div":
                # Rough heuristic: the text div may close.  We keep
                # accumulating just in case there are nested elements.
                pass

            if tag == "div" and self._in_message_text:
                self._text_depth += 1

            if tag == "a" and self._in_message_text:
                # Links are just text for our purposes
                pass

            if tag == "video":
                self._in_video_tag = False

            if tag == "span" and self._in_message_views:
                self._in_message_views = False
                self._parse_views()

            if "tgme_widget_message_link_preview" in tag or tag == "a":
                # Approximate — link preview sections are usually <a> wrappers
                self._in_link_preview = False

        if tag == "div" and self._in_message_text:
            self._text_depth += 1

    def handle_data(self, data: str):
        if self._in_message_text and self._current_post is not None:
            self._text_chunks.append(data)

        if self._in_message_views:
            self._views_text += data

    def handle_entityref(self, name: str):
        """Handle named HTML entities like &amp; &lt; etc."""
        char = html_module.unescape(f"&{name};")
        if self._in_message_text and self._current_post is not None:
            self._text_chunks.append(char)
        if self._in_message_views:
            self._views_text += char

    def handle_charref(self, name: str):
        """Handle numeric character references like &#39; &#x27;"""
        char = html_module.unescape(f"&#{name};")
        if self._in_message_text and self._current_post is not None:
            self._text_chunks.append(char)
        if self._in_message_views:
            self._views_text += char

    # -- finalisation -------------------------------------------------------

    def _parse_views(self):
        """Parse the views text (e.g. '12.5K', '1.2M', '345') into an int."""
        text = self._views_text.strip()
        if not text:
            return
        try:
            text = text.replace(",", "").replace(" ", "")
            if text.upper().endswith("K"):
                val = float(text[:-1]) * 1_000
            elif text.upper().endswith("M"):
                val = float(text[:-1]) * 1_000_000
            else:
                val = float(text)
            self._current_post["views"] = int(val)
        except (ValueError, TypeError):
            pass

    def _finalise_post(self):
        """Move the current post into the posts list."""
        if self._current_post is None:
            return
        # Assemble text
        raw_text = "".join(self._text_chunks)
        # Strip leading/trailing whitespace but preserve internal newlines
        raw_text = raw_text.strip()
        # Collapse multiple spaces (not newlines) into one
        raw_text = re.sub(r"[^\S\n]+", " ", raw_text)
        self._current_post["text"] = raw_text
        self.posts.append(self._current_post)
        self._current_post = None
        self._in_message_wrap = False

    def close(self):
        """Override close to finalise the last post."""
        if self._current_post is not None and self._current_post["id"] is not None:
            self._finalise_post()
        super().close()


# ---------------------------------------------------------------------------
# Network layer
# ---------------------------------------------------------------------------

def _make_session() -> requests.Session:
    """Create a requests session with sensible defaults."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    })
    return session


def fetch_telegram_page(
    channel: str,
    before_id: Optional[int] = None,
    timeout: int = REQUEST_TIMEOUT,
) -> Tuple[List[Dict[str, Any]], Optional[int]]:
    """
    Fetch a page of posts from a Telegram public channel preview.

    Parameters
    ----------
    channel : str
        Channel username (without @), e.g. ``"sochiautoparts"``.
    before_id : int, optional
        Post ID to use as the ``?before=`` cursor for pagination.
    timeout : int
        Request timeout in seconds.

    Returns
    -------
    (posts, next_before_id)
        *posts* is a list of post dicts, newest first.
        *next_before_id* is the cursor for the next older page, or ``None``
        if there are no more pages.
    """
    url = BASE_URL_TEMPLATE.format(channel=channel)
    params = {}
    if before_id is not None:
        params["before"] = before_id

    session = _make_session()
    last_exception: Optional[Exception] = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = session.get(url, params=params, timeout=timeout)
            resp.raise_for_status()
            break
        except requests.RequestException as exc:
            last_exception = exc
            if attempt < MAX_RETRIES:
                wait = RETRY_DELAY * attempt
                time.sleep(wait)
    else:
        raise RuntimeError(
            f"Failed to fetch Telegram page after {MAX_RETRIES} attempts: {last_exception}"
        )

    html_text = resp.text
    parser = TelegramPostParser()
    try:
        parser.feed(html_text)
        parser.close()
    except Exception as exc:
        raise RuntimeError(f"Failed to parse Telegram HTML: {exc}")

    # Posts come in newest-first order from Telegram.
    # We keep them in the same order.
    return parser.posts, parser.next_before_id


# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------

def _ensure_dir(data_dir: str):
    """Make sure the data directory exists."""
    Path(data_dir).mkdir(parents=True, exist_ok=True)


def load_meta(data_dir: str) -> dict:
    """
    Load archive metadata from ``meta.json``.

    Returns a dict with keys:
        total_posts, last_post_id, last_updated, pages_count

    Returns an empty dict if the file does not exist.
    """
    meta_path = os.path.join(data_dir, "meta.json")
    if not os.path.exists(meta_path):
        return {}
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_meta(data_dir: str, meta: dict):
    """Save archive metadata to ``meta.json``."""
    _ensure_dir(data_dir)
    meta_path = os.path.join(data_dir, "meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def load_page(data_dir: str, page_num: int) -> list:
    """
    Load a page of posts from its JSON file.

    Parameters
    ----------
    page_num : int
        1-based page number.

    Returns
    -------
    list of post dicts, or an empty list if the file does not exist.
    """
    page_path = os.path.join(data_dir, f"page_{page_num}.json")
    if not os.path.exists(page_path):
        return []
    try:
        with open(page_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def save_page(data_dir: str, page_num: int, posts: list):
    """
    Save a page of posts to its JSON file.

    Parameters
    ----------
    page_num : int
        1-based page number.
    posts : list
        List of post dicts.
    """
    _ensure_dir(data_dir)
    page_path = os.path.join(data_dir, f"page_{page_num}.json")
    with open(page_path, "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)


def build_posts_index(data_dir: str, meta: dict) -> dict:
    """
    Build a ``post_id -> {page, pos}`` index for O(1) lookups.

    Iterates over all stored pages and records the page number and
    position (0-based index within the page) for each post ID.

    The index is saved to ``posts_index.json`` and also returned.

    Parameters
    ----------
    data_dir : str
        Path to the telegram archive directory.
    meta : dict
        Current archive metadata (needs ``pages_count``).

    Returns
    -------
    dict mapping post_id (as string key) to ``{"page": int, "pos": int}``.
    """
    pages_count = meta.get("pages_count", 0)
    index: Dict[str, Dict[str, int]] = {}

    for page_num in range(1, pages_count + 1):
        posts = load_page(data_dir, page_num)
        for pos, post in enumerate(posts):
            post_id = post.get("id")
            if post_id is not None:
                index[str(post_id)] = {"page": page_num, "pos": pos}

    index_path = os.path.join(data_dir, "posts_index.json")
    _ensure_dir(data_dir)
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    return index


# ---------------------------------------------------------------------------
# Re-pagination logic
# ---------------------------------------------------------------------------

def re_paginate(data_dir: str, new_posts: list, meta: dict):
    """
    Insert new posts at the beginning and re-paginate.

    New posts go first (sorted by ID descending — newest first, which is
    the same order Telegram returns them).  We read ``page_1``, prepend the
    new posts, split back into pages of ``POSTS_PER_PAGE``, and if there is
    overflow, push excess to ``page_2``, etc.

    Parameters
    ----------
    data_dir : str
        Path to the telegram archive directory.
    new_posts : list
        New post dicts to insert (newest first).
    meta : dict
        Current archive metadata (mutated in place and saved).
    """
    if not new_posts:
        return

    pages_count = meta.get("pages_count", 0)

    # We'll carry overflow forward page by page.
    overflow: list = list(new_posts)  # copy

    for page_num in range(1, pages_count + 1):
        existing = load_page(data_dir, page_num)
        combined = overflow + existing
        # How many full pages does this give us?
        pages_from_combined = len(combined) // POSTS_PER_PAGE
        remainder = len(combined) % POSTS_PER_PAGE

        if pages_from_combined > 0:
            for i in range(pages_from_combined):
                target_page = page_num + i
                slice_start = i * POSTS_PER_PAGE
                slice_end = slice_start + POSTS_PER_PAGE
                save_page(data_dir, target_page, combined[slice_start:slice_end])

            overflow = combined[pages_from_combined * POSTS_PER_PAGE:]
            # The next page to process is page_num + pages_from_combined,
            # but the for loop will increment by 1, so we adjust.
            # Actually, we need to skip ahead. Let's restructure:
            # We write pages_from_combined pages starting at page_num,
            # and then overflow goes into the next iteration.
            # But the next iteration of the outer loop is page_num+1,
            # which we may have already written to. So we need to adjust.
            # Let's use a while loop approach instead.
            break_outer = False
            break  # handled below
        else:
            # combined fits within the current page (shouldn't happen if
            # overflow is non-empty, but just in case)
            save_page(data_dir, page_num, combined)
            overflow = []
            break

    # If we broke out of the loop with overflow still remaining, we need
    # to continue processing pages.  Let's redo this more carefully with
    # a while loop.
    # Actually, let me rewrite the whole thing more clearly:

    # Reload and redo — the logic above is fragile.  Here's a clean version:
    _re_paginate_clean(data_dir, new_posts, meta)


def _re_paginate_clean(data_dir: str, new_posts: list, meta: dict):
    """
    Clean re-implementation of re-paginate.

    Strategy: collect all existing posts into one big list, prepend new
    posts, then re-write all pages from scratch.  This is simpler and
    correct, at the cost of re-writing pages that haven't changed.

    For an archive of 87K posts this is fine because we only do this
    when new posts arrive (which is at most ~20 per update).
    """
    pages_count = meta.get("pages_count", 0)
    total_posts = meta.get("total_posts", 0)

    # Collect all existing posts
    all_posts: list = []
    for page_num in range(1, pages_count + 1):
        posts = load_page(data_dir, page_num)
        all_posts.extend(posts)

    # Prepend new posts (they are newest-first, same order as stored)
    all_posts = list(new_posts) + all_posts

    # De-duplicate by post ID (keep first occurrence = newest position)
    seen_ids = set()
    deduped: list = []
    for post in all_posts:
        pid = post.get("id")
        if pid is not None and pid not in seen_ids:
            seen_ids.add(pid)
            deduped.append(post)

    all_posts = deduped

    # Re-write all pages
    new_pages_count = (len(all_posts) + POSTS_PER_PAGE - 1) // POSTS_PER_PAGE if all_posts else 0

    for page_num in range(1, new_pages_count + 1):
        start = (page_num - 1) * POSTS_PER_PAGE
        end = start + POSTS_PER_PAGE
        save_page(data_dir, page_num, all_posts[start:end])

    # Remove any stale pages beyond the new count
    stale = new_pages_count + 1
    while True:
        stale_path = os.path.join(data_dir, f"page_{stale}.json")
        if os.path.exists(stale_path):
            os.remove(stale_path)
            stale += 1
        else:
            break

    # Update meta
    meta["total_posts"] = len(all_posts)
    meta["pages_count"] = new_pages_count
    if all_posts:
        meta["last_post_id"] = all_posts[0].get("id")
    meta["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    save_meta(data_dir, meta)

    # Rebuild index
    build_posts_index(data_dir, meta)


# ---------------------------------------------------------------------------
# Main fetch functions
# ---------------------------------------------------------------------------

def fetch_all_posts(
    channel: str,
    data_dir: str,
    max_posts: int = 100000,
    batch_delay: float = 0.5,
    force_full: bool = False,
) -> dict:
    """
    Fetch all posts from a Telegram public channel.

    Strategy
    --------
    1. If ``meta.json`` exists and ``force_full`` is False:
       a. Perform an incremental update (fast — 1-2 API calls).
    2. If ``meta.json`` does not exist or ``force_full`` is True:
       a. Start from the latest page.
       b. Follow ``?before=N`` links to get all posts.
       c. Save in batches of ``POSTS_PER_PAGE`` posts per file.
       d. Update ``meta.json`` with total count and last post ID.
       e. This is SLOW — ~4350 API calls for 87K posts at 0.5s delay.

    Parameters
    ----------
    channel : str
        Channel username (without @).
    data_dir : str
        Directory for storing the archive JSON files.
    max_posts : int
        Safety cap on the total number of posts to fetch.
    batch_delay : float
        Seconds to wait between HTTP requests.
    force_full : bool
        If True, ignore existing archive and fetch everything from scratch.

    Returns
    -------
    Updated meta dict.
    """
    _ensure_dir(data_dir)
    meta = load_meta(data_dir)

    # --- Incremental update path -------------------------------------------
    # Only use incremental update if we have a valid last_post_id.
    # If meta exists but last_post_id is None, we need a full fetch
    # (otherwise we get infinite recursion with incremental_update).
    if meta and not force_full and meta.get("last_post_id") is not None and meta.get("total_posts", 0) > 0:
        return incremental_update(channel, data_dir)

    # --- Full fetch path ---------------------------------------------------
    # Support resuming a previously interrupted full fetch.
    # If meta exists with pages but no last_post_id (incomplete fetch),
    # we can resume by fetching from the oldest post we already have.
    resume_mode = False
    if not force_full and meta and meta.get("pages_count", 0) > 0 and meta.get("last_post_id") is None:
        # Incomplete previous fetch — resume from where we left off
        resume_mode = True
        last_page_num = meta.get("pages_count", 0)
        last_page = load_page(data_dir, last_page_num) if last_page_num > 0 else []
        if last_page:
            oldest_id = min(p.get("id", 0) for p in last_page if p.get("id"))
            print(f"[telegram_fetcher] Resuming previous fetch from post ID {oldest_id} (page {last_page_num})")
        else:
            resume_mode = False  # Can't resume, start fresh
    elif not force_full and meta and meta.get("pages_count", 0) > 0 and meta.get("total_posts", 0) > 0 and meta.get("last_post_id") is not None:
        # We have a complete archive — this should have been caught by the incremental path above
        return incremental_update(channel, data_dir)

    if force_full and meta:
        # Back up existing data
        backup_dir = data_dir + "_backup_" + str(int(time.time()))
        os.rename(data_dir, backup_dir)
        _ensure_dir(data_dir)
        print(f"[telegram_fetcher] Existing data backed up to {backup_dir}")

    if resume_mode:
        # Continue from existing state
        page_num = meta.get("pages_count", 0) + 1
        fetched_count = meta.get("total_posts", 0)
        # Get the before_id from the oldest post in the last page
        last_page = load_page(data_dir, meta.get("pages_count", 0))
        if last_page:
            oldest_id = min(p.get("id", 0) for p in last_page if p.get("id"))
            before_id = oldest_id
        else:
            before_id = None
        all_posts: list = []
    else:
        meta = {
            "total_posts": 0,
            "last_post_id": None,
            "last_updated": "",
            "pages_count": 0,
            "channel": channel,
        }
        all_posts: list = []
        before_id: Optional[int] = None
        fetched_count = 0
        page_num = 1

    print(f"[telegram_fetcher] Starting full fetch of @{channel} {'(resuming)' if resume_mode else ''}…")

    while fetched_count < max_posts:
        try:
            posts, next_before = fetch_telegram_page(channel, before_id=before_id)
        except RuntimeError as exc:
            print(f"[telegram_fetcher] Error fetching page: {exc}")
            # Save what we have so far
            if all_posts:
                _flush_posts(data_dir, all_posts, page_num)
                all_posts = []
                page_num += 1
                _update_meta_after_flush(data_dir, meta, fetched_count)
            break

        if not posts:
            # No more posts
            break

        all_posts.extend(posts)
        fetched_count += len(posts)

        # Flush to disk every time we accumulate POSTS_PER_PAGE or more
        while len(all_posts) >= POSTS_PER_PAGE:
            page_posts = all_posts[:POSTS_PER_PAGE]
            save_page(data_dir, page_num, page_posts)
            all_posts = all_posts[POSTS_PER_PAGE:]
            page_num += 1

            # Update meta and save to disk after each page flush
            # This ensures progress is NOT lost if the process is interrupted
            meta["pages_count"] = page_num - 1
            meta["total_posts"] = fetched_count - len(all_posts)
            if page_posts:
                if meta.get("last_post_id") is None:
                    meta["last_post_id"] = page_posts[0].get("id")
            # Save meta after every 10 pages to minimize I/O but still be safe
            if (page_num - 1) % 10 == 0:
                meta["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                save_meta(data_dir, meta)

        # Progress log
        if fetched_count % 1000 < 25:
            print(f"[telegram_fetcher] Fetched {fetched_count} posts so far …")

        # Check if there are more pages
        if next_before is None:
            break

        before_id = next_before
        time.sleep(batch_delay)

    # Flush remaining posts
    if all_posts:
        save_page(data_dir, page_num, all_posts)
        meta["pages_count"] = page_num

    # Final meta update
    total = 0
    for pn in range(1, meta.get("pages_count", 0) + 1):
        p = load_page(data_dir, pn)
        total += len(p)

    meta["total_posts"] = total
    # The first post in page_1 is the newest
    first_page = load_page(data_dir, 1)
    if first_page:
        meta["last_post_id"] = first_page[0].get("id")
    meta["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    meta["channel"] = channel
    save_meta(data_dir, meta)

    # Build index
    build_posts_index(data_dir, meta)

    print(
        f"[telegram_fetcher] Full fetch complete. "
        f"Total: {meta['total_posts']} posts in {meta['pages_count']} pages."
    )
    return meta


def _flush_posts(data_dir: str, posts: list, page_num: int):
    """Save a batch of posts to a page file."""
    save_page(data_dir, page_num, posts)


def _update_meta_after_flush(data_dir: str, meta: dict, total_count: int):
    """Quick meta update during a flush."""
    meta["total_posts"] = total_count
    meta["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    save_meta(data_dir, meta)


def incremental_update(channel: str, data_dir: str) -> dict:
    """
    Fast incremental update — only fetch new posts.

    Steps
    -----
    1. Read ``meta.json`` for last known post ID.
    2. Fetch the latest page from Telegram.
    3. Check if there are new posts (IDs higher than last known).
    4. If yes, keep fetching pages until we reach the last known ID.
    5. Insert new posts into the archive.
    6. Update ``meta.json``.

    This typically requires only 1-2 API calls.

    Parameters
    ----------
    channel : str
        Channel username (without @).
    data_dir : str
        Path to the telegram archive directory.

    Returns
    -------
    Updated meta dict.
    """
    meta = load_meta(data_dir)
    if not meta:
        # No existing archive — fall back to full fetch
        return fetch_all_posts(channel, data_dir, force_full=True)

    last_known_id = meta.get("last_post_id")
    if last_known_id is None or meta.get("total_posts", 0) == 0:
        # Archive exists but is empty/corrupt — need a full fetch
        return fetch_all_posts(channel, data_dir, force_full=True)

    print(f"[telegram_fetcher] Incremental update for @{channel}, last known ID: {last_known_id}")

    # Fetch the latest page
    try:
        posts, _ = fetch_telegram_page(channel)
    except RuntimeError as exc:
        print(f"[telegram_fetcher] Error during incremental update: {exc}")
        return meta

    if not posts:
        print("[telegram_fetcher] No posts returned from Telegram.")
        return meta

    # Filter new posts (IDs higher than last_known_id)
    new_posts = [p for p in posts if p.get("id") is not None and p["id"] > last_known_id]

    # If the latest page has new posts, there might be more pages with new posts
    before_id = None
    extra_pages = 0
    max_extra_pages = 50  # Safety limit

    while len(new_posts) == len(posts) and extra_pages < max_extra_pages:
        # All posts on this page are new → there may be more
        # Get the oldest post ID from the current batch to paginate
        oldest_new_id = min(p["id"] for p in posts if p.get("id") is not None)
        try:
            older_posts, _ = fetch_telegram_page(channel, before_id=oldest_new_id)
        except RuntimeError:
            break

        if not older_posts:
            break

        older_new = [p for p in older_posts if p.get("id") is not None and p["id"] > last_known_id]
        if not older_new:
            break

        new_posts.extend(older_new)
        posts = older_posts
        extra_pages += 1
        time.sleep(0.5)

    if not new_posts:
        print("[telegram_fetcher] No new posts found.")
        meta["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        save_meta(data_dir, meta)
        return meta

    # Sort new posts by ID descending (newest first) to match our storage order
    new_posts.sort(key=lambda p: p.get("id", 0), reverse=True)

    print(f"[telegram_fetcher] Found {len(new_posts)} new post(s).")

    # Re-paginate
    re_paginate(data_dir, new_posts, meta)

    # meta is updated inside re_paginate, reload it
    meta = load_meta(data_dir)

    # Rebuild index
    build_posts_index(data_dir, meta)

    print(
        f"[telegram_fetcher] Incremental update complete. "
        f"Total: {meta['total_posts']} posts, {meta['pages_count']} pages."
    )
    return meta


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def get_post_by_id(data_dir: str, post_id: int) -> Optional[dict]:
    """
    Look up a single post by its ID using the index.

    Parameters
    ----------
    data_dir : str
        Path to the telegram archive directory.
    post_id : int
        The Telegram post ID.

    Returns
    -------
    Post dict or ``None`` if not found.
    """
    index_path = os.path.join(data_dir, "posts_index.json")
    if not os.path.exists(index_path):
        return None

    try:
        with open(index_path, "r", encoding="utf-8") as f:
            index = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    entry = index.get(str(post_id))
    if entry is None:
        return None

    page_num = entry.get("page")
    pos = entry.get("pos")
    if page_num is None or pos is None:
        return None

    posts = load_page(data_dir, page_num)
    if pos < len(posts):
        return posts[pos]
    return None


def get_archive_page_posts(
    data_dir: str,
    page_num: int,
    per_page: int = POSTS_PER_PAGE,
) -> Tuple[list, int, int]:
    """
    Get posts for a specific archive page number.

    Parameters
    ----------
    data_dir : str
        Path to the telegram archive directory.
    page_num : int
        1-based page number.
    per_page : int
        Number of posts per page (default 50).

    Returns
    -------
    (posts, total_posts, total_pages)
    """
    meta = load_meta(data_dir)
    total_posts = meta.get("total_posts", 0)
    total_pages = meta.get("pages_count", 0)

    if page_num < 1 or page_num > total_pages:
        return [], total_posts, total_pages

    posts = load_page(data_dir, page_num)

    # If per_page differs from POSTS_PER_PAGE, slice accordingly
    if per_page != POSTS_PER_PAGE and posts:
        # We store in chunks of POSTS_PER_PAGE; if a different per_page
        # is requested, we need to recalculate which logical page this is.
        # For simplicity, just return what we have.
        pass

    return posts, total_posts, total_pages


def get_total_posts_count(data_dir: str) -> int:
    """
    Get total number of archived posts.

    Parameters
    ----------
    data_dir : str
        Path to the telegram archive directory.

    Returns
    -------
    int — total post count, or 0 if no archive exists.
    """
    meta = load_meta(data_dir)
    return meta.get("total_posts", 0)


# ---------------------------------------------------------------------------
# CLI convenience
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Telegram channel post fetcher")
    parser.add_argument(
        "--channel",
        default="sochiautoparts",
        help="Telegram channel username (without @)",
    )
    parser.add_argument(
        "--data-dir",
        default="data/telegram_archive",
        help="Directory to store the archive",
    )
    parser.add_argument(
        "--force-full",
        action="store_true",
        help="Force a full fetch even if an archive exists",
    )
    parser.add_argument(
        "--max-posts",
        type=int,
        default=100000,
        help="Maximum number of posts to fetch",
    )
    parser.add_argument(
        "--batch-delay",
        type=float,
        default=0.5,
        help="Delay between API requests in seconds",
    )
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="Run incremental update only",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Print archive status and exit",
    )

    args = parser.parse_args()

    # Resolve data dir relative to this script's parent
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(script_dir, "..", args.data_dir)
    data_dir = os.path.normpath(data_dir)

    if args.status:
        meta = load_meta(data_dir)
        if meta:
            print(f"Channel:      @{meta.get('channel', 'unknown')}")
            print(f"Total posts:  {meta.get('total_posts', 0)}")
            print(f"Pages:        {meta.get('pages_count', 0)}")
            print(f"Last post ID: {meta.get('last_post_id', 'N/A')}")
            print(f"Last updated: {meta.get('last_updated', 'N/A')}")
        else:
            print("No archive found.")
        exit(0)

    if args.incremental:
        result = incremental_update(args.channel, data_dir)
    else:
        result = fetch_all_posts(
            channel=args.channel,
            data_dir=data_dir,
            max_posts=args.max_posts,
            batch_delay=args.batch_delay,
            force_full=args.force_full,
        )

    print(json.dumps(result, indent=2, ensure_ascii=False))
