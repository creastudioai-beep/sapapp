#!/usr/bin/env python3
"""
Product page generator for SochiAutoParts.

Generates individual HTML pages for each product from products.json.
Each product gets its own page at /product/{slug}/index.html with:
  - Full product details (name, description, price, old price, images)
  - Store/brand information
  - Regional ad blocks (via placeholder for Worker injection)
  - Related products from the same category
  - SEO metadata (Schema.org Product, OpenGraph, Twitter Card)
  - Breadcrumb navigation

Products data source: https://github.com/creastudioai-beep/zap.online/blob/main/products.json
"""

import html as _html_module
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote as url_quote

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from site_generator.config import (
    SITE_URL,
    SITE_NAME_RU,
    SITE_NAME_EN,
    BASE_PATH,
    GA4_MEASUREMENT_ID,
    PRODUCTS_CURRENCY_RU,
    PRODUCTS_CURRENCY_EN,
    FEATURE_DARK_MODE,
    FEATURE_ANALYTICS,
)
from site_generator.templates import (
    escape_html,
    render_header,
    render_footer,
    render_fab,
    render_matrix_bg,
    render_ad_blocks,
    render_ad_category_buttons,
    _bp,
    _lang_path,
    _lang_base,
)


# =============================================================================
# Product category mapping (from products.json cat ID to display name)
# =============================================================================

PRODUCT_CATEGORY_NAMES: Dict[int, Dict[str, str]] = {
    1: {"ru": "Масла и смазки", "en": "Oils & Lubricants"},
    2: {"ru": "Моторное масло", "en": "Motor Oil"},
    3: {"ru": "Трансмиссионное масло", "en": "Transmission Oil"},
    4: {"ru": "Автожидкости", "en": "Auto Fluids"},
    5: {"ru": "Чернитель шин", "en": "Tire Black"},
    6: {"ru": "Спецпредложения", "en": "Special Offers"},
    7: {"ru": "Каталог запчастей", "en": "Parts Catalog"},
    8: {"ru": "Аксессуары", "en": "Accessories"},
    9: {"ru": "Инструменты", "en": "Tools"},
    10: {"ru": "Преобразователь ржавчины", "en": "Rust Converter"},
    11: {"ru": "Антигравий", "en": "Anti-Gravel"},
    12: {"ru": "Распродажа", "en": "Clearance"},
}

# Store display info (fallback when product lacks store fields)
STORE_INFO: Dict[int, Dict[str, str]] = {
    26554: {"name": "Лукойл Shop", "color": "#e21a1c", "icon": "🛢️"},
    25860: {"name": "GlobalDrive.ru", "color": "#9c27b0", "icon": "🚤"},
}


# =============================================================================
# Helper: slug generation
# =============================================================================

def product_slug(product: Dict) -> str:
    """Generate URL-safe slug for a product.

    Uses product ID to ensure uniqueness and avoid encoding issues.
    Format: {id}-{sanitized-name}
    """
    pid = product.get("id") or product.get("f") or ""
    name = product.get("n") or product.get("name") or ""
    # Sanitize name: keep alphanumeric + hyphens, limit length
    slug_name = re.sub(r"[^\w\-]", "-", name.lower())[:60].strip("-")
    slug_name = re.sub(r"-+", "-", slug_name)
    if slug_name:
        return f"{pid}-{slug_name}"
    return str(pid)


# =============================================================================
# Expand compressed product keys
# =============================================================================

def expand_product(p: Dict) -> Dict:
    """Expand compressed product keys (n->name, p->price, etc.) to full names."""
    store_info = STORE_INFO.get(p.get("f", 0), {})
    return {
        "id": p.get("f") or p.get("id"),
        "name": p.get("n") or p.get("name", ""),
        "price": p.get("p") or p.get("price", 0),
        "old_price": p.get("o") or p.get("old_price", 0),
        "currency": p.get("c") or p.get("currency", "RUB"),
        "url": p.get("u") or p.get("url", "#"),
        "image": p.get("i") or p.get("image", ""),
        "vendor": p.get("v") or p.get("vendor", ""),
        "description": p.get("d") or p.get("description", ""),
        "feed_id": p.get("f") or p.get("feed_id", ""),
        "feed_name": p.get("fn") or p.get("feed_name") or store_info.get("name", ""),
        "feed_color": p.get("fc") or p.get("feed_color") or store_info.get("color", ""),
        "feed_icon": p.get("fi") or p.get("feed_icon") or store_info.get("icon", ""),
        "category_id": p.get("cat") or p.get("category_id", 0),
        "available": p.get("a", True) if p.get("a") is not None else p.get("available", True),
        "short_note": p.get("sn") or p.get("short_note", ""),
        "model": p.get("m") or p.get("model", ""),
        "type": p.get("tp") or p.get("type", ""),
    }


# =============================================================================
# Format price
# =============================================================================

def format_price(price: Any, currency: str = "RUB", lang: str = "ru") -> str:
    """Format price with currency symbol."""
    if not price or price == 0:
        return ""
    try:
        price_num = int(price)
        if currency == "KZT":
            symbol = "₸" if lang == "ru" else "KZT"
        else:
            symbol = "₽" if lang == "ru" else "RUB"
        return f"{price_num:,} {symbol}".replace(",", " ")
    except (ValueError, TypeError):
        return str(price)


# =============================================================================
# Generate product page HTML
# =============================================================================

def generate_product_page(
    product: Dict,
    related_products: List[Dict],
    admitad_programs: List[Dict],
    lang: str = "ru",
) -> str:
    """Generate complete HTML page for a single product.

    Args:
        product: Expanded product dict
        related_products: List of related products from same category
        admitad_programs: List of Admitad programs for ad blocks
        lang: Language code (ru/en)
    """
    is_ru = lang == "ru"
    slug = product_slug(product)

    # Meta information
    page_title = f"{product['name']} | SOCHIAUTOPARTS"
    page_description = product.get("description", "")[:200] or product["name"]  # meta description, keep short for SEO
    canonical_url = f"{SITE_URL}/product/{slug}/"

    # Category info
    cat_id = product.get("category_id", 0)
    cat_names = PRODUCT_CATEGORY_NAMES.get(cat_id, {"ru": "Автозапчасти", "en": "Auto Parts"})
    cat_name = cat_names.get(lang, cat_names["ru"])

    # Price display
    price_display = format_price(product.get("price", 0), product.get("currency", "RUB"), lang)
    old_price = product.get("old_price", 0)
    old_price_display = format_price(old_price, product.get("currency", "RUB"), lang) if old_price and old_price > product.get("price", 0) else ""

    # Discount calculation
    discount_html = ""
    if old_price and old_price > product.get("price", 0):
        try:
            discount_pct = int((1 - product["price"] / old_price) * 100)
            if discount_pct > 0:
                discount_label = f"-{discount_pct}%" if is_ru else f"-{discount_pct}%"
                discount_html = f'<span class="product-discount">{discount_label}</span>'
        except (ZeroDivisionError, TypeError):
            pass

    # Availability
    available = product.get("available", True)
    avail_class = "in-stock" if available else "out-of-stock"
    avail_text = "В наличии" if available and is_ru else ("In Stock" if available else ("Нет в наличии" if is_ru else "Out of Stock"))

    # Store badge
    feed_name = product.get("feed_name", "")
    feed_color = product.get("feed_color", "")
    feed_icon = product.get("feed_icon", "🛒")
    store_badge = ""
    if feed_name:
        store_badge = (
            f'<span class="product-store-badge" '
            f'style="background:{escape_html(feed_color)}20;color:{escape_html(feed_color)};border:1px solid {escape_html(feed_color)}40;">'
            f'{feed_icon} {escape_html(feed_name)}</span>'
        )

    # Breadcrumbs
    shop_label = "Магазин" if is_ru else "Shop"
    home_label = "Главная" if is_ru else "Home"
    breadcrumbs_html = (
        f'<nav class="breadcrumbs">'
        f'<a href="{_lang_base(lang)}">{home_label}</a> '
        f'<span>›</span> '
        f'<a href="{_lang_path(lang)}/shop">{shop_label}</a> '
        f'<span>›</span> '
        f'<a href="{_lang_path(lang)}/shop?cat={cat_id}">{escape_html(cat_name)}</a> '
        f'<span>›</span> '
        f'<span>{escape_html(product["name"][:50])}</span>'
        f'</nav>'
    )

    # Related products
    related_html = ""
    if related_products:
        related_label = "Похожие товары" if is_ru else "Similar Products"
        cards = ""
        for rp in related_products[:6]:
            rp_slug = product_slug(rp)
            rp_name = rp.get("name", "")
            if len(rp_name) > 60:
                rp_name = rp_name[:57] + "..."
            rp_price = format_price(rp.get("price", 0), rp.get("currency", "RUB"), lang)
            rp_image = rp.get("image", "") or "/logo.jpg"
            cards += (
                f'<a href="{_lang_path(lang)}/product/{rp_slug}/" class="related-product-card">'
                f'<div class="rp-image"><img src="{escape_html(rp_image)}" alt="{escape_html(rp_name)}" loading="lazy" referrerpolicy="no-referrer" onerror="this.src=\'/logo.jpg\'"></div>'
                f'<div class="rp-name">{escape_html(rp_name)}</div>'
                f'<div class="rp-price">{escape_html(rp_price)}</div>'
                f'</a>'
            )
        related_html = (
            f'<section class="related-products-section">'
            f'<h2>{related_label}</h2>'
            f'<div class="related-products-grid">{cards}</div>'
            f'</section>'
        )

    # Ad blocks with regional placeholder
    ad_blocks_html = render_ad_blocks(admitad_programs, lang=lang, max_blocks=4)

    # Schema.org Product JSON-LD
    schema_product = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": product["name"],
        "description": product.get("description", ""),
        "image": product.get("image", ""),
        "brand": {
            "@type": "Brand",
            "name": product.get("vendor", ""),
        },
        "offers": {
            "@type": "Offer",
            "url": canonical_url,
            "priceCurrency": product.get("currency", "RUB"),
            "price": product.get("price", 0),
            "availability": "https://schema.org/InStock" if available else "https://schema.org/OutOfStock",
            "seller": {
                "@type": "Organization",
                "name": product.get("feed_name", SITE_NAME_RU if is_ru else SITE_NAME_EN),
            },
        },
    }

    # Buy button — link directly to partner store (affiliate URL)
    buy_text = "Купить" if is_ru else "Buy Now"
    product_url = product.get("url", "")
    buy_url = product_url if product_url and product_url != "#" else f"/api/go/{url_quote(str(product.get('feed_id', '') or product.get('feedId', '')))}/{url_quote(str(product.get('id', '')))}"

    # Description (preserve line breaks)
    description_html = ""
    desc_text = product.get("description", "")
    if desc_text:
        description_html = escape_html(desc_text).replace("\n", "<br>\n")

    # Short note
    short_note_html = ""
    if product.get("short_note"):
        short_note_html = f'<div class="product-note">{escape_html(product["short_note"])}</div>'

    # Type/subcategory
    type_html = ""
    if product.get("type"):
        type_label = "Тип" if is_ru else "Type"
        type_html = f'<div class="product-meta-item"><strong>{type_label}:</strong> {escape_html(product["type"])}</div>'

    # Vendor
    vendor_html = ""
    if product.get("vendor"):
        vendor_label = "Бренд" if is_ru else "Brand"
        vendor_html = f'<div class="product-meta-item"><strong>{vendor_label}:</strong> {escape_html(product["vendor"])}</div>'

    # Model
    model_html = ""
    if product.get("model"):
        model_label = "Модель" if is_ru else "Model"
        model_html = f'<div class="product-meta-item"><strong>{model_label}:</strong> {escape_html(product["model"])}</div>'

    # Header & Footer
    header_html = render_header(lang=lang, active_page="shop")
    footer_html = render_footer(lang=lang)
    fab_html = render_fab(lang=lang)
    matrix_html = render_matrix_bg()

    # Full HTML page
    html = f"""<!DOCTYPE html>
<html lang="{lang}" data-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{escape_html(page_title)}</title>
<meta name="description" content="{escape_html(page_description)}">
<link rel="canonical" href="{canonical_url}">
<link rel="icon" href="/logo.jpg" type="image/jpeg" />
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Manrope:wght@400;500;600;700;800&display=swap" rel="stylesheet" />
<link rel="stylesheet" href="/style.css" />
<script>try{{var _t=localStorage.getItem('theme')||'dark';document.documentElement.setAttribute('data-theme',_t)}}catch(e){{}}</script>
<meta property="og:type" content="product" />
<meta property="og:title" content="{escape_html(page_title)}" />
<meta property="og:description" content="{escape_html(page_description)}" />
<meta property="og:image" content="{escape_html(product.get('image', ''))}" />
<meta property="og:url" content="{canonical_url}" />
<meta property="og:site_name" content="SOCHIAUTOPARTS" />
<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content="{escape_html(page_title)}" />
<meta name="twitter:description" content="{escape_html(page_description)}" />
<meta name="twitter:image" content="{escape_html(product.get('image', ''))}" />
<meta name="robots" content="index, follow" />
<script type="application/ld+json">{json.dumps(schema_product, ensure_ascii=False)}</script>
</head>
<body>
{matrix_html}
{header_html}
<main class="container">
{breadcrumbs_html}
<article class="product-page">
<div class="product-layout">
  <div class="product-image-section">
    <div class="product-main-image">
      <img src="{escape_html(product.get('image', '/logo.jpg'))}" alt="{escape_html(product['name'])}" loading="eager" referrerpolicy="no-referrer" onerror="this.src='/logo.jpg'" />
    </div>
  </div>
  <div class="product-info-section">
    <div class="product-category-line">{store_badge} <span class="product-cat-name">{escape_html(cat_name)}</span></div>
    <h1 class="product-title">{escape_html(product['name'])}</h1>
    <div class="product-price-block">
      <span class="product-price">{escape_html(price_display)}</span>
      {f'<span class="product-old-price">{escape_html(old_price_display)}</span>' if old_price_display else ''}
      {discount_html}
    </div>
    <div class="product-availability {avail_class}">{avail_text}</div>
    {short_note_html}
    <div class="product-meta">
      {vendor_html}
      {model_html}
      {type_html}
    </div>
    <div class="product-actions">
      <a href="{escape_html(buy_url)}" class="btn-buy" target="_blank" rel="nofollow noopener sponsored">{buy_text}</a>
    </div>
  </div>
</div>
<div class="product-description">
  <h2>{"Описание" if is_ru else "Description"}</h2>
  <div class="product-description-text">{description_html or ('Описание отсутствует' if is_ru else 'No description available')}</div>
</div>
</article>
<section class="product-ads">
  <h2>{"Рекомендуем" if is_ru else "Recommended"}</h2>
  {ad_blocks_html}
</section>
{related_html}
</main>
{footer_html}
{fab_html}
<script src="/scripts.js"></script>
<script src="/i18n.js"></script>
<style>
.product-page{{padding:1.5rem 0}}
.product-layout{{display:grid;grid-template-columns:1fr 1fr;gap:2rem;margin-bottom:2rem}}
@media(max-width:768px){{.product-layout{{grid-template-columns:1fr}}}}
.product-main-image img{{width:100%;height:auto;max-height:500px;object-fit:contain;border-radius:12px;background:var(--surface,#f4f4f5)}}
.product-category-line{{display:flex;align-items:center;gap:8px;margin-bottom:0.75rem;flex-wrap:wrap}}
.product-store-badge{{display:inline-flex;align-items:center;gap:4px;padding:2px 10px;border-radius:999px;font-size:0.8rem;font-weight:600}}
.product-cat-name{{color:var(--text-sec,#707579);font-size:0.9rem}}
.product-title{{font-size:1.5rem;font-weight:800;line-height:1.3;margin:0 0 1rem}}
.product-price-block{{display:flex;align-items:baseline;gap:12px;margin-bottom:0.75rem}}
.product-price{{font-size:1.8rem;font-weight:800;color:var(--primary,#2481CC)}}
.product-old-price{{font-size:1.1rem;text-decoration:line-through;color:var(--text-sec,#707579)}}
.product-discount{{background:#d32f2f;color:#fff;padding:2px 8px;border-radius:4px;font-size:0.85rem;font-weight:700}}
.product-availability{{font-size:0.9rem;font-weight:600;margin-bottom:0.5rem}}
.product-availability.in-stock{{color:#388e3c}}
.product-availability.out-of-stock{{color:#d32f2f}}
.product-note{{background:var(--surface,#f4f4f5);padding:0.75rem;border-radius:8px;font-size:0.85rem;color:var(--text-sec,#707579);margin-bottom:1rem}}
.product-meta{{margin-bottom:1.5rem}}
.product-meta-item{{font-size:0.9rem;margin-bottom:0.25rem;color:var(--text-sec,#707579)}}
.product-meta-item strong{{color:var(--text-main,#000)}}
.btn-buy{{display:inline-flex;align-items:center;gap:8px;padding:14px 32px;background:var(--primary,#2481CC);color:#fff;text-decoration:none;border-radius:999px;font-size:1.1rem;font-weight:700;transition:opacity .15s}}
.btn-buy:hover{{opacity:.85}}
.product-description{{margin-top:2rem;padding-top:2rem;border-top:1px solid var(--divider,#dadce0)}}
.product-description h2{{font-size:1.25rem;margin-bottom:1rem}}
.product-description-text{{line-height:1.7;color:var(--text-sec,#707579)}}
.product-ads{{margin-top:2rem;padding-top:2rem;border-top:1px solid var(--divider,#dadce0)}}
.product-ads h2{{font-size:1.25rem;margin-bottom:1rem}}
.related-products-section{{margin-top:2rem;padding-top:2rem;border-top:1px solid var(--divider,#dadce0)}}
.related-products-section h2{{font-size:1.25rem;margin-bottom:1rem}}
.related-products-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:1rem}}
.related-product-card{{display:block;text-decoration:none;color:inherit;border:1px solid var(--divider,#dadce0);border-radius:12px;overflow:hidden;transition:box-shadow .2s}}
.related-product-card:hover{{box-shadow:0 4px 12px rgba(0,0,0,.1)}}
.rp-image img{{width:100%;height:140px;object-fit:contain;background:var(--surface,#f4f4f5)}}
.rp-name{{padding:0.5rem;font-size:0.85rem;font-weight:600;line-height:1.3;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}}
.rp-price{{padding:0 0.5rem 0.5rem;font-size:0.9rem;font-weight:700;color:var(--primary,#2481CC)}}
[data-theme="dark"] .product-main-image img{{background:var(--surface,#1a1a2e)}}
</style>
</body>
</html>"""
    return html


# =============================================================================
# Generate all product pages
# =============================================================================

def generate_all_product_pages(
    products_data: List[Dict],
    admitad_programs: List[Dict],
    output_dir: str = "output",
) -> int:
    """Generate individual HTML pages for all products.

    Returns the number of product pages generated.
    """
    if not products_data:
        print("[product_pages] No products data, skipping product page generation")
        return 0

    # Expand all products
    expanded = [expand_product(p) for p in products_data]

    # Index by category for related products
    by_category: Dict[int, List[Dict]] = {}
    for p in expanded:
        cat = p.get("category_id", 0)
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(p)

    count = 0
    for product in expanded:
        slug = product_slug(product)
        cat_id = product.get("category_id", 0)

        # Get related products (same category, excluding current)
        related = [
            rp for rp in by_category.get(cat_id, [])
            if rp.get("id") != product.get("id")
        ][:6]

        # Generate for both languages
        for lang in ("ru", "en"):
            html = generate_product_page(
                product=product,
                related_products=related,
                admitad_programs=admitad_programs,
                lang=lang,
            )

            # Write to output directory
            if lang == "ru":
                page_dir = os.path.join(output_dir, "product", slug)
            else:
                page_dir = os.path.join(output_dir, "en", "product", slug)

            os.makedirs(page_dir, exist_ok=True)
            filepath = os.path.join(page_dir, "index.html")

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(html)

        count += 1

        if count % 500 == 0:
            print(f"[product_pages] Generated {count}/{len(expanded)} product pages...")

    print(f"[product_pages] Generated {count} product pages (ru+en)")
    return count


# =============================================================================
# Generate product sitemap entries
# =============================================================================

def generate_product_sitemap_urls(
    products_data: List[Dict],
    site_url: str = SITE_URL,
) -> List[Dict]:
    """Generate sitemap URL entries for all product pages."""
    urls = []
    for p_raw in products_data:
        product = expand_product(p_raw)
        slug = product_slug(product)
        loc = f"{site_url}/product/{slug}/"
        urls.append({
            "loc": loc,
            "changefreq": "weekly",
            "priority": 0.6,
            "lastmod": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        })
    return urls


# =============================================================================
# Main (for standalone execution)
# =============================================================================

def main():
    """Standalone entry point: generate product pages from products.json."""
    import argparse
    parser = argparse.ArgumentParser(description="Generate product pages")
    parser.add_argument("--products", default="data/products.json", help="Path to products.json")
    parser.add_argument("--admitad", default="", help="Path to admitad_ads.json (optional)")
    parser.add_argument("--output", default="output", help="Output directory")
    args = parser.parse_args()

    # Load products
    print(f"Loading products from {args.products}...")
    with open(args.products, "r", encoding="utf-8") as f:
        products_data = json.load(f)
    print(f"Loaded {len(products_data)} products")

    # Load admitad programs (optional)
    admitad_programs = []
    if args.admitad and os.path.exists(args.admitad):
        with open(args.admitad, "r", encoding="utf-8") as f:
            data = json.load(f)
            admitad_programs = data.get("programs", [])
        print(f"Loaded {len(admitad_programs)} Admitad programs")

    # Generate pages
    count = generate_all_product_pages(products_data, admitad_programs, args.output)
    print(f"Done: {count} product pages generated")


if __name__ == "__main__":
    main()
