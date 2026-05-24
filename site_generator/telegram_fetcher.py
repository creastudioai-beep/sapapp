#!/usr/bin/env python3
"""
Site Generator for Telegram Channel Archive
============================================

Generates a static HTML site from Telegram channel posts.
Fetches posts via public Telegram preview page (t.me/s/...),
stores them incrementally in JSON, and builds HTML pages.
"""

import os
import sys
import json
import time
import re
import argparse
import html
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import requests

# ------------------------------
# Constants
# ------------------------------
POSTS_PER_PAGE = 50           # posts per JSON page & per HTML page
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
REQUEST_TIMEOUT = 15
MAX_RETRIES = 3
RETRY_DELAY = 2.0
BASE_URL_TEMPLATE = "https://t.me/s/{channel}"

# ------------------------------
# Telegram Fetcher (robust)
# ------------------------------

class TelegramPostParser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.posts: List[Dict] = []
        self.next_before_id: Optional[int] = None
        self._current = None
        self._in_wrap = False
        self._in_text = False
        self._text_chunks = []
        self._views_text = ""
        self._in_views = False
        self._style_buffer = ""

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = attrs.get("class", "")
        if tag == "div" and "data-before" in attrs:
            try:
                self.next_before_id = int(attrs["data-before"])
            except:
                pass

        if tag == "div" and classes.startswith("tgme_widget_message_wrap"):
            if self._current and self._current.get("id"):
                self._finalize_post()
            self._current = {
                "id": None, "text": "", "photos": [], "videos": [],
                "video_thumbnails": [], "date": "", "views": 0,
            }
            self._in_wrap = True
            data_post = attrs.get("data-post", "")
            if "/" in data_post:
                try:
                    self._current["id"] = int(data_post.split("/")[-1])
                except:
                    pass

        if not self._in_wrap or not self._current:
            return

        # Text block
        if "tgme_widget_message_text" in classes:
            self._in_text = True
            self._text_chunks = []

        # Photo / video thumbnail via background-image
        if "tgme_widget_message_photo_wrap" in classes or "tgme_widget_message_roundvideo" in classes:
            style = attrs.get("style", "")
            urls = re.findall(r"url\(['\"]([^'\"]+)['\"]\)", style)
            for u in urls:
                if "twemoji" not in u and "emoji" not in u:
                    if "roundvideo" in classes:
                        self._current["video_thumbnails"].append(u)
                    else:
                        self._current["photos"].append(u)

        if tag == "video":
            src = attrs.get("src")
            if src:
                self._current["videos"].append(src)
            poster = attrs.get("poster")
            if poster:
                self._current["video_thumbnails"].append(poster)

        if tag == "source" and self._current.get("videos") is not None:
            src = attrs.get("src")
            if src:
                self._current["videos"].append(src)

        if "tgme_widget_message_views" in classes:
            self._in_views = True
            self._views_text = ""

        if tag == "time":
            dt = attrs.get("datetime")
            if dt and not self._current["date"]:
                self._current["date"] = dt

    def handle_data(self, data):
        if self._in_text and self._current:
            self._text_chunks.append(data)
        if self._in_views:
            self._views_text += data

    def handle_entityref(self, name):
        char = html.unescape(f"&{name};")
        if self._in_text:
            self._text_chunks.append(char)
        if self._in_views:
            self._views_text += char

    def handle_charref(self, name):
        char = html.unescape(f"&#{name};")
        if self._in_text:
            self._text_chunks.append(char)
        if self._in_views:
            self._views_text += char

    def handle_endtag(self, tag):
        if self._in_wrap and tag == "div":
            # heuristic: end of wrap? we'll rely on next wrap or finalize
            pass
        if self._in_text and tag == "div":
            self._in_text = False
            if self._current:
                raw = "".join(self._text_chunks).strip()
                raw = re.sub(r"[^\S\n]+", " ", raw)
                self._current["text"] = raw
        if self._in_views and tag == "span":
            self._in_views = False
            self._parse_views()

    def _parse_views(self):
        t = self._views_text.strip().replace(",", "").replace(" ", "")
        if not t:
            return
        try:
            if t.upper().endswith("K"):
                val = float(t[:-1]) * 1000
            elif t.upper().endswith("M"):
                val = float(t[:-1]) * 1000000
            else:
                val = float(t)
            self._current["views"] = int(val)
        except:
            pass

    def _finalize_post(self):
        if self._current and self._current.get("id"):
            self.posts.append(self._current)
        self._current = None
        self._in_wrap = False

    def close(self):
        if self._current and self._current.get("id"):
            self._finalize_post()
        super().close()


def fetch_telegram_page(channel: str, before_id: Optional[int] = None) -> Tuple[List[Dict], Optional[int]]:
    url = BASE_URL_TEMPLATE.format(channel=channel)
    params = {"before": before_id} if before_id else {}
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = session.get(url, params=params, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            break
        except Exception as e:
            if attempt == MAX_RETRIES:
                raise RuntimeError(f"Failed after {MAX_RETRIES} attempts: {e}")
            time.sleep(RETRY_DELAY * attempt)
    parser = TelegramPostParser()
    parser.feed(resp.text)
    parser.close()
    return parser.posts, parser.next_before_id


# ------------------------------
# JSON archive helpers
# ------------------------------
def ensure_dir(path):
    Path(path).mkdir(parents=True, exist_ok=True)

def load_meta(data_dir):
    p = os.path.join(data_dir, "meta.json")
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_meta(data_dir, meta):
    ensure_dir(data_dir)
    with open(os.path.join(data_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

def load_page(data_dir, page_num):
    p = os.path.join(data_dir, f"page_{page_num}.json")
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_page(data_dir, page_num, posts):
    ensure_dir(data_dir)
    with open(os.path.join(data_dir, f"page_{page_num}.json"), "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)

def rebuild_index(data_dir, meta):
    pages = meta.get("pages_count", 0)
    index = {}
    for pn in range(1, pages + 1):
        posts = load_page(data_dir, pn)
        for pos, post in enumerate(posts):
            pid = post.get("id")
            if pid:
                index[str(pid)] = {"page": pn, "pos": pos}
    with open(os.path.join(data_dir, "posts_index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    return index

# ------------------------------
# Incremental update & re-pagination
# ------------------------------
def re_paginate(data_dir, new_posts, meta):
    """Insert new posts (newest first) and rewrite all pages."""
    pages = meta.get("pages_count", 0)
    all_posts = []
    for pn in range(1, pages + 1):
        all_posts.extend(load_page(data_dir, pn))
    all_posts = new_posts + all_posts
    # dedup by id (keep first = newest)
    seen = set()
    deduped = []
    for p in all_posts:
        pid = p.get("id")
        if pid and pid not in seen:
            seen.add(pid)
            deduped.append(p)
    all_posts = deduped

    new_pages = (len(all_posts) + POSTS_PER_PAGE - 1) // POSTS_PER_PAGE if all_posts else 0
    for pn in range(1, new_pages + 1):
        start = (pn - 1) * POSTS_PER_PAGE
        end = start + POSTS_PER_PAGE
        save_page(data_dir, pn, all_posts[start:end])
    # delete stale pages
    pn = new_pages + 1
    while os.path.exists(os.path.join(data_dir, f"page_{pn}.json")):
        os.remove(os.path.join(data_dir, f"page_{pn}.json"))
        pn += 1

    meta["total_posts"] = len(all_posts)
    meta["pages_count"] = new_pages
    if all_posts:
        meta["last_post_id"] = all_posts[0]["id"]
    meta["last_updated"] = datetime.utcnow().isoformat() + "Z"
    save_meta(data_dir, meta)
    rebuild_index(data_dir, meta)


def incremental_update(channel, data_dir):
    meta = load_meta(data_dir)
    if not meta:
        return full_fetch(channel, data_dir)
    last_id = meta.get("last_post_id")
    if not last_id:
        return full_fetch(channel, data_dir)
    print(f"Incremental update: last ID = {last_id}")
    posts, _ = fetch_telegram_page(channel)
    if not posts:
        return meta
    new_posts = [p for p in posts if p.get("id", 0) > last_id]
    # check further pages
    before = None
    if len(new_posts) == len(posts):
        oldest = min(p["id"] for p in posts)
        older, _ = fetch_telegram_page(channel, before_id=oldest)
        while older:
            older_new = [p for p in older if p.get("id", 0) > last_id]
            if not older_new:
                break
            new_posts.extend(older_new)
            # get next older page
            oldest_older = min(p["id"] for p in older)
            older, _ = fetch_telegram_page(channel, before_id=oldest_older)
            time.sleep(0.5)
    if not new_posts:
        print("No new posts.")
        meta["last_updated"] = datetime.utcnow().isoformat() + "Z"
        save_meta(data_dir, meta)
        return meta
    new_posts.sort(key=lambda x: x["id"], reverse=True)
    print(f"Found {len(new_posts)} new posts")
    re_paginate(data_dir, new_posts, meta)
    return load_meta(data_dir)


def full_fetch(channel, data_dir, max_posts=100000, batch_delay=0.5):
    print(f"Full fetch from @{channel} ...")
    ensure_dir(data_dir)
    # backup old
    if os.path.exists(os.path.join(data_dir, "meta.json")):
        bak = data_dir + "_backup_" + str(int(time.time()))
        os.rename(data_dir, bak)
        ensure_dir(data_dir)
    all_posts = []
    before = None
    page_counter = 1
    while len(all_posts) < max_posts:
        posts, next_before = fetch_telegram_page(channel, before)
        if not posts:
            break
        all_posts.extend(posts)
        if next_before is None:
            break
        before = next_before
        time.sleep(batch_delay)
        if len(all_posts) % 1000 < 50:
            print(f"Fetched {len(all_posts)} posts...")
    # split into pages
    num_pages = (len(all_posts) + POSTS_PER_PAGE - 1) // POSTS_PER_PAGE if all_posts else 0
    for pn in range(1, num_pages + 1):
        start = (pn - 1) * POSTS_PER_PAGE
        end = start + POSTS_PER_PAGE
        save_page(data_dir, pn, all_posts[start:end])
    meta = {
        "channel": channel,
        "total_posts": len(all_posts),
        "pages_count": num_pages,
        "last_post_id": all_posts[0]["id"] if all_posts else None,
        "last_updated": datetime.utcnow().isoformat() + "Z",
    }
    save_meta(data_dir, meta)
    rebuild_index(data_dir, meta)
    print(f"Full fetch done: {meta['total_posts']} posts, {num_pages} pages.")
    return meta

# ------------------------------
# HTML Site Generator
# ------------------------------
def render_post_html(post: Dict) -> str:
    """Convert one post dict to HTML fragment."""
    text = html.escape(post.get("text", ""))
    text = text.replace("\n", "<br>")
    photos = post.get("photos", [])
    videos = post.get("videos", [])
    thumbs = post.get("video_thumbnails", [])
    date_str = post.get("date", "")
    views = post.get("views", 0)

    media_html = ""
    for p in photos:
        media_html += f'<div class="post-photo"><img src="{html.escape(p)}" loading="lazy"></div>\n'
    for v in videos:
        media_html += f'<div class="post-video"><video controls preload="metadata" poster="{html.escape(thumbs[0]) if thumbs else ""}"><source src="{html.escape(v)}"></video></div>\n'

    return f"""
    <div class="post">
        <div class="post-header">
            <span class="post-id">Post #{post.get("id", "")}</span>
            <span class="post-date">{html.escape(date_str)}</span>
            <span class="post-views">👁️ {views}</span>
        </div>
        <div class="post-content">{text}</div>
        {media_html}
    </div>
    """

def generate_site(data_dir: str, output_dir: str):
    """Generate static HTML site from JSON archive."""
    meta = load_meta(data_dir)
    total_posts = meta.get("total_posts", 0)
    pages_count = meta.get("pages_count", 0)
    if not pages_count:
        print("No posts found. Run with --fetch-archive first.")
        return

    ensure_dir(output_dir)
    # copy static assets if any (optional)
    # generate index page (list of recent posts)
    recent_posts = []
    for pn in range(1, min(3, pages_count) + 1):
        page_posts = load_page(data_dir, pn)
        recent_posts.extend(page_posts[:10])  # first 10 from page1, then page2 etc.
    recent_posts = recent_posts[:20]

    # index.html
    index_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Telegram Archive: @{meta.get("channel", "")}</title>
    <style>
        body {{ font-family: sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
        .post {{ border: 1px solid #ddd; margin: 20px 0; padding: 15px; border-radius: 8px; }}
        .post-header {{ color: #666; margin-bottom: 10px; font-size: 0.9em; }}
        .post-id {{ font-weight: bold; }}
        .post-date {{ margin-left: 15px; }}
        .post-views {{ margin-left: 15px; }}
        .post-content {{ line-height: 1.5; }}
        .post-photo img {{ max-width: 100%; margin: 10px 0; }}
        .post-video video {{ max-width: 100%; }}
        .pagination {{ margin: 30px 0; text-align: center; }}
        .pagination a {{ margin: 0 5px; }}
    </style>
</head>
<body>
    <h1>📢 @{meta.get("channel", "")}</h1>
    <p>Total posts: {total_posts} | Last updated: {meta.get("last_updated", "")}</p>
    <h2>Latest posts</h2>
"""
    for post in recent_posts:
        index_content += render_post_html(post)
    # pagination links
    index_content += '<div class="pagination">'
    for i in range(1, min(pages_count, 10) + 1):
        index_content += f'<a href="page_{i}.html">{i}</a> '
    if pages_count > 10:
        index_content += '...'
    index_content += '</div></body></html>'
    with open(os.path.join(output_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_content)

    # generate individual page files (page_1.html, page_2.html, ...)
    for pn in range(1, pages_count + 1):
        posts = load_page(data_dir, pn)
        page_html = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>Page {pn} – @{meta.get("channel", "")}</title>
<style>
    body {{ font-family: sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
    .post {{ border: 1px solid #ddd; margin: 20px 0; padding: 15px; border-radius: 8px; }}
    .post-header {{ color: #666; margin-bottom: 10px; font-size: 0.9em; }}
    .post-content {{ line-height: 1.5; }}
    .post-photo img {{ max-width: 100%; margin: 10px 0; }}
    .post-video video {{ max-width: 100%; }}
    .pagination {{ margin: 30px 0; text-align: center; }}
</style>
</head>
<body>
    <h1>📄 Page {pn} of {pages_count}</h1>
    <p><a href="index.html">← Back to latest posts</a></p>
"""
        for post in posts:
            page_html += render_post_html(post)
        page_html += '<div class="pagination">'
        if pn > 1:
            page_html += f'<a href="page_{pn-1}.html">‹ Previous</a> '
        if pn < pages_count:
            page_html += f'<a href="page_{pn+1}.html">Next ›</a>'
        page_html += '</div></body></html>'
        with open(os.path.join(output_dir, f"page_{pn}.html"), "w", encoding="utf-8") as f:
            f.write(page_html)

    print(f"✅ Site generated in {output_dir}: {pages_count} pages, {total_posts} posts.")

# ------------------------------
# CLI entry point
# ------------------------------
def main():
    parser = argparse.ArgumentParser(description="Generate static site from Telegram channel")
    parser.add_argument("--fetch-archive", action="store_true", help="Fetch/update Telegram archive")
    parser.add_argument("--full", action="store_true", help="Full fetch (ignore existing archive)")
    parser.add_argument("--channel", default=os.environ.get("TELEGRAM_CHANNEL", "sochiautoparts"), help="Channel username")
    parser.add_argument("--data-dir", default="data/telegram_archive", help="JSON storage dir")
    parser.add_argument("--output-dir", default="output", help="HTML output dir")
    args = parser.parse_args()

    data_dir = os.path.abspath(args.data_dir)
    output_dir = os.path.abspath(args.output_dir)

    if args.fetch_archive:
        if args.full:
            full_fetch(args.channel, data_dir)
        else:
            incremental_update(args.channel, data_dir)

    # always generate site (even if fetch not requested)
    generate_site(data_dir, output_dir)

if __name__ == "__main__":
    main()
