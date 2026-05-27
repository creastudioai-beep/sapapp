"""
Main entry point for the SochiAutoParts static site generator.

Orchestrates the entire build process:
    1. Parse command-line arguments
    2. (Optional) Fetch/update Telegram archive via --fetch-archive / --full-archive
    3. Load all data from the pipeline (GitHub raw JSON with local caching)
    4. Generate all HTML pages (bilingual: Russian and English)
    5. Print a build summary with file counts and statistics

NOTE: Archive pages are generated as static HTML by the Python generator
using pipeline data. The Cloudflare Worker proxies these pages and adds
region-based affiliate filtering on top.

Usage:
    python -m site_generator [options]

Options:
    --output-dir DIR       Output directory (default: output)
    --data-dir DIR         Data cache directory (default: data)
    --force-refresh        Force refresh data from pipeline (ignore cache)
    --fetch-archive        Run incremental Telegram archive update, then build
    --full-archive         Run full Telegram archive fetch, then build
    --no-pages             Skip page generation (only fetch data)
    --no-sitemaps          Skip sitemap generation
    --no-rss               Skip RSS generation
    --lang ru,en           Languages to generate (default: ru,en)
    --verbose              Verbose output
"""

import argparse
import logging
import os
import shutil
import sys
import time
from datetime import datetime, timezone
from typing import Optional

# ---------------------------------------------------------------------------
# Ensure the site_generator package directory is on sys.path so that
# sibling modules (config, data_loader, …) can be imported when running
# via ``python -m site_generator.main`` from the project root.
# ---------------------------------------------------------------------------

_PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
if _PACKAGE_DIR not in sys.path:
    sys.path.insert(0, _PACKAGE_DIR)

# Parent of the package dir (project root) is also useful for relative paths
_PROJECT_ROOT = os.path.dirname(_PACKAGE_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from .config import (
    CHANNEL_USERNAME,
    GENERATOR_NAME,
    GENERATOR_VERSION,
    OUTPUT_DIR as DEFAULT_OUTPUT_DIR,
    SITE_NAME_RU,
    SITE_NAME_EN,
    SITE_URL,
    SUPPORTED_LANGUAGES,
)
from .data_loader import load_data
from .html_generator import generate_all_pages

# telegram_fetcher is imported lazily inside main() only when --fetch-archive / --full-archive is used.
# This prevents import errors if telegram_fetcher dependencies are missing.


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger = logging.getLogger("site_generator")
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(name)s] %(levelname)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)


# ===========================================================================
# Argument parsing
# ===========================================================================


def parse_args(argv: Optional[list] = None) -> argparse.Namespace:
    """Parse command-line arguments for the site generator.

    Args:
        argv: Optional list of argument strings (defaults to sys.argv[1:]).

    Returns:
        Parsed argparse.Namespace object with all options.
    """
    parser = argparse.ArgumentParser(
        prog="site_generator.main",
        description=(
            f"{GENERATOR_NAME} v{GENERATOR_VERSION} — "
            "Generates a complete static website for sochiautoparts.ru "
            "from pipeline data. Archive pages are handled dynamically "
            "by the Cloudflare Worker."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python -m site_generator.main\n"
            "  python -m site_generator.main --force-refresh --verbose\n"
            "  python -m site_generator.main --lang ru --output-dir /tmp/site\n"
        ),
    )

    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        metavar="DIR",
        help=f"Output directory for generated HTML files (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--data-dir",
        default="data",
        metavar="DIR",
        help="Data cache directory for pipeline JSON files (default: data)",
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Force refresh data from pipeline (ignore local cache)",
    )
    parser.add_argument(
        "--no-pages",
        action="store_true",
        help="Skip HTML page generation (only fetch/cache data)",
    )
    parser.add_argument(
        "--no-sitemaps",
        action="store_true",
        help="Skip sitemap XML generation",
    )
    parser.add_argument(
        "--no-rss",
        action="store_true",
        help="Skip RSS feed generation",
    )
    parser.add_argument(
        "--lang",
        default="ru,en",
        metavar="LANGS",
        help=(
            "Comma-separated list of languages to generate "
            "(default: ru,en). Supported: ru, en."
        ),
    )
    parser.add_argument(
        "--fetch-archive",
        action="store_true",
        help=(
            "Run incremental Telegram archive update (fetch new posts only), "
            "then generate site. Used by GitHub Actions on scheduled builds."
        ),
    )
    parser.add_argument(
        "--full-archive",
        action="store_true",
        help=(
            "Run full Telegram archive fetch (all posts from scratch), "
            "then generate site. Used by GitHub Actions on manual trigger."
        ),
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose (DEBUG-level) output",
    )

    args = parser.parse_args(argv)

    # Parse and validate language list
    requested_langs = [lang.strip().lower() for lang in args.lang.split(",")]
    valid_langs = []
    for lang in requested_langs:
        if lang in SUPPORTED_LANGUAGES:
            valid_langs.append(lang)
        else:
            logger.warning("Unsupported language '%s' ignored (supported: %s)", lang, SUPPORTED_LANGUAGES)
    if not valid_langs:
        logger.error("No valid languages specified. Using defaults: ru, en")
        valid_langs = ["ru", "en"]
    args.langs = valid_langs

    return args


# ===========================================================================
# Post-generation cleanup helpers
# ===========================================================================


def _remove_sitemaps(output_dir: str) -> int:
    """Remove all generated sitemap XML files from the output directory.

    Args:
        output_dir: Root output directory.

    Returns:
        Number of sitemap files removed.
    """
    removed = 0
    sitemap_patterns = [
        "sitemap.xml",
        "sitemap-index.xml",
        "sitemap-ru.xml",
        "sitemap-en.xml",
        "sitemap-amp.xml",
        "sitemap-news.xml",
        "sitemap-tags.xml",
        "sitemap-archive.xml",
    ]

    for filename in sitemap_patterns:
        filepath = os.path.join(output_dir, filename)
        if os.path.isfile(filepath):
            os.remove(filepath)
            removed += 1
            logger.debug("Removed sitemap: %s", filepath)

    # Remove paginated sitemap files (sitemap-posts-N.xml, sitemap-products-N.xml)
    for entry in os.listdir(output_dir):
        if entry.startswith("sitemap-posts-") or entry.startswith("sitemap-products-"):
            filepath = os.path.join(output_dir, entry)
            if os.path.isfile(filepath):
                os.remove(filepath)
                removed += 1
                logger.debug("Removed sitemap: %s", filepath)

    return removed


def _remove_rss(output_dir: str) -> int:
    """Remove all generated RSS feed files from the output directory.

    Args:
        output_dir: Root output directory.

    Returns:
        Number of RSS files removed.
    """
    removed = 0
    rss_paths = [
        os.path.join(output_dir, "feed.xml"),
        os.path.join(output_dir, "en", "feed.xml"),
    ]

    for filepath in rss_paths:
        if os.path.isfile(filepath):
            os.remove(filepath)
            removed += 1
            logger.debug("Removed RSS feed: %s", filepath)

    return removed


def _remove_language(output_dir: str, lang: str) -> int:
    """Remove all generated files for a specific language that is not requested.

    Args:
        output_dir: Root output directory.
        lang: Language code to remove ("en" or "ru").

    Returns:
        Number of top-level items removed.
    """
    if lang == "en":
        en_dir = os.path.join(output_dir, "en")
        if os.path.isdir(en_dir):
            shutil.rmtree(en_dir)
            logger.debug("Removed English language directory: %s", en_dir)
            return 1
    return 0


# ===========================================================================
# Build summary
# ===========================================================================


def print_build_summary(output_dir: str, elapsed_seconds: float = 0.0) -> None:
    """Print a detailed build summary with file counts and statistics.

    Args:
        output_dir: Root output directory to scan.
        elapsed_seconds: Total build time in seconds.
    """
    # Count files by extension and by directory
    total_files = 0
    total_size = 0
    extension_counts: dict[str, int] = {}
    directory_counts: dict[str, int] = {}

    for root, _dirs, files in os.walk(output_dir):
        for filename in files:
            filepath = os.path.join(root, filename)
            total_files += 1
            try:
                total_size += os.path.getsize(filepath)
            except OSError:
                pass

            # Count by extension
            _, ext = os.path.splitext(filename)
            ext = ext.lower() if ext else "(no ext)"
            extension_counts[ext] = extension_counts.get(ext, 0) + 1

            # Count by top-level directory
            rel_path = os.path.relpath(root, output_dir)
            top_dir = rel_path.split(os.sep)[0] if rel_path != "." else "(root)"
            directory_counts[top_dir] = directory_counts.get(top_dir, 0) + 1

    # Format elapsed time
    if elapsed_seconds >= 60:
        mins = int(elapsed_seconds // 60)
        secs = elapsed_seconds % 60
        time_str = f"{mins}m {secs:.1f}s"
    else:
        time_str = f"{elapsed_seconds:.1f}s"

    # Format total size
    if total_size >= 1024 * 1024:
        size_str = f"{total_size / (1024 * 1024):.1f} MB"
    elif total_size >= 1024:
        size_str = f"{total_size / 1024:.1f} KB"
    else:
        size_str = f"{total_size} bytes"

    # Print summary
    print()
    print("=" * 60)
    print(f"  {GENERATOR_NAME} v{GENERATOR_VERSION} — Build Summary")
    print("=" * 60)
    print(f"  Output directory:  {os.path.abspath(output_dir)}")
    print(f"  Total files:       {total_files}")
    print(f"  Total size:        {size_str}")
    print(f"  Build time:        {time_str}")
    print()

    # File types breakdown
    if extension_counts:
        print("  Files by type:")
        for ext, count in sorted(extension_counts.items(), key=lambda x: -x[1]):
            print(f"    {ext:<12} {count:>6}")
        print()

    # Directory breakdown
    if directory_counts:
        print("  Files by section:")
        for dir_name, count in sorted(directory_counts.items(), key=lambda x: -x[1]):
            print(f"    {dir_name:<20} {count:>6}")
        print()

    print("  Note: Archive feature disabled — pages not generated")
    print(f"  Built at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 60)
    print()


# ===========================================================================
# Main entry point
# ===========================================================================


def main(argv: Optional[list] = None) -> None:
    """Main entry point for the static site generator.

    Orchestrates the entire build process:
        1. Parse command-line arguments
        2. Load all data from the pipeline
        3. Generate all HTML pages
        4. Post-generation cleanup (sitemaps, RSS, language filtering)
        5. Print a build summary

    Args:
        argv: Optional list of argument strings (defaults to sys.argv[1:]).
    """
    start_time = time.time()

    # ------------------------------------------------------------------
    # Step 0: Parse arguments
    # ------------------------------------------------------------------
    args = parse_args(argv)

    # Configure logging verbosity
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        for name in ("data_loader", "html_generator", "seo"):
            logging.getLogger(name).setLevel(logging.DEBUG)
        logger.debug("Verbose mode enabled")

    logger.info(
        "%s v%s starting…",
        GENERATOR_NAME,
        GENERATOR_VERSION,
    )
    logger.debug("Arguments: %s", vars(args))

    # ------------------------------------------------------------------
    # Step 0b: Telegram archive fetch
    # ------------------------------------------------------------------
    if args.full_archive or args.fetch_archive:
        try:
            from .telegram_fetcher import fetch_all_posts
            archive_data_dir = os.path.join(args.data_dir, "telegram_archive")
            channel = CHANNEL_USERNAME
            if args.full_archive:
                logger.info("Starting full Telegram archive fetch for @%s", channel)
                print(f"  Running full Telegram archive fetch for @{channel} (up to 100000 posts)…")
                fetch_all_posts(channel, archive_data_dir, max_posts=100000, force_full=True)
            else:
                logger.info("Starting incremental Telegram archive update for @%s", channel)
                print(f"  Running incremental Telegram archive update for @{channel} (last 50 posts)…")
                fetch_all_posts(channel, archive_data_dir, max_posts=50, force_full=False)
        except Exception as exc:
            logger.error("Telegram fetch failed: %s", exc)
            print(f"  WARNING: Telegram fetch failed: {exc}")
            # Continue with build even if fetch fails

    # ------------------------------------------------------------------
    # Step 1: Load pipeline data
    # ------------------------------------------------------------------
    print()
    print("Loading pipeline data…")
    data = load_data(args.data_dir, force_refresh=args.force_refresh)

    posts_count = len(data.get("posts", []))
    articles_count = len(data.get("articles", []))
    products_count = len(data.get("products", []))
    admitad_count = len(data.get("admitad_programs", []))

    print(f"  Posts:           {posts_count}")
    print(f"  Articles:        {articles_count}")
    print(f"  Products:        {products_count}")
    print(f"  Admitad programs:{admitad_count}")

    # ------------------------------------------------------------------
    # Step 2: Generate all pages
    # ------------------------------------------------------------------
    if not args.no_pages:
        print()
        print("Generating pages…")
        logger.info(
            "Generating pages into %s",
            args.output_dir,
        )

        try:
            generate_all_pages(data, args.output_dir)
            logger.info("Page generation complete")
        except Exception as exc:
            logger.error("Page generation failed: %s", exc)
            print(f"  ERROR: Page generation failed: {exc}")
            # Try to generate at least a minimal site even if full generation fails
            try:
                import shutil
                os.makedirs(args.output_dir, exist_ok=True)
                # Create a minimal index.html so the build doesn't produce 0 pages
                minimal_html = '<!DOCTYPE html><html><head><meta charset="UTF-8"><title>SOCHIAUTOPARTS</title></head><body><h1>SOCHIAUTOPARTS</h1><p>Site is being rebuilt. Please check back soon.</p></body></html>'
                with open(os.path.join(args.output_dir, 'index.html'), 'w', encoding='utf-8') as f:
                    f.write(minimal_html)
                with open(os.path.join(args.output_dir, '404.html'), 'w', encoding='utf-8') as f:
                    f.write(minimal_html)
                logger.info("Created minimal fallback pages")
            except Exception as fallback_exc:
                logger.error("Fallback page generation also failed: %s", fallback_exc)
            raise

        # ----------------------------------------------------------
        # Step 2a: Post-generation cleanup based on flags
        # ----------------------------------------------------------

        # Remove sitemaps if --no-sitemaps
        if args.no_sitemaps:
            removed = _remove_sitemaps(args.output_dir)
            if removed > 0:
                logger.info("Removed %d sitemap file(s) (--no-sitemaps)", removed)
                print(f"  Removed {removed} sitemap file(s)")

        # Remove RSS feeds if --no-rss
        if args.no_rss:
            removed = _remove_rss(args.output_dir)
            if removed > 0:
                logger.info("Removed %d RSS feed file(s) (--no-rss)", removed)
                print(f"  Removed {removed} RSS feed file(s)")

        # Remove language-specific files if not all languages are requested
        if set(args.langs) != set(SUPPORTED_LANGUAGES):
            for lang in SUPPORTED_LANGUAGES:
                if lang not in args.langs:
                    removed = _remove_language(args.output_dir, lang)
                    if removed > 0:
                        logger.info(
                            "Removed %s language files (--lang %s)",
                            lang,
                            ",".join(args.langs),
                        )
                        print(f"  Removed {lang} language files")
    else:
        print()
        print("Skipping page generation (--no-pages)")
        logger.info("Page generation skipped (--no-pages)")

    # ------------------------------------------------------------------
    # Step 3: Print build summary
    # ------------------------------------------------------------------
    elapsed = time.time() - start_time
    print_build_summary(args.output_dir, elapsed_seconds=elapsed)

    logger.info(
        "Build complete in %.1f seconds — %d posts, %d articles, %d products",
        elapsed,
        posts_count,
        articles_count,
        products_count,
    )


# ===========================================================================
# __main__ support
# ===========================================================================

if __name__ == "__main__":
    main()
