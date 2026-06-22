"""
GearVN scraper using Shopify products.json API.
GearVN runs on Shopify — the standard /products.json endpoint returns
structured product data (title, price, body_html, vendor, tags).
No HTML parsing needed.
"""
import logging
import time
from bs4 import BeautifulSoup
from shared.config import SCRAPE_DELAY
from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)

# (PIRVN_category, shopify_collection_slug)
COLLECTIONS = [
    # Laptops
    ("Laptop", "laptop"),
    # PC Components
    ("VGA", "vga-card-man-hinh"),
    ("CPU", "cpu-bo-vi-xu-ly"),
    ("CPU", "cpu-amd-ryzen"),
    ("Mainboard", "mainboard-bo-mach-chu"),
    ("RAM", "ram-pc"),
    ("Luu_tru", "ssd-o-cung-the-ran"),
    ("Luu_tru", "hdd-o-cung-pc"),
    ("Nguon_Case", "psu-nguon-may-tinh"),
    ("Nguon_Case", "case-thung-may-tinh"),
    ("Tan_nhiet", "tan-nhiet-may-tinh"),
    # Monitors
    ("Man_hinh", "man-hinh"),
    # Peripherals
    ("Ban_phim", "ban-phim-may-tinh"),
    ("Chuot", "chuot-may-tinh"),
    # Audio
    ("Am_thanh", "tai-nghe-may-tinh"),
    ("Am_thanh", "loa"),
]

PRODUCTS_PER_PAGE = 250
MAX_PAGES = 20


def html_to_text(html: str) -> str:
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text(separator=" ", strip=True)[:2000]


class GearVNScraper(BaseScraper):
    source = "gearvn.vn"
    base_url = "https://gearvn.com"

    def __init__(self):
        super().__init__()
        self._seen_handles = set()

    def scrape_collection(self, category: str, slug: str):
        logger.info(f"[GearVN] Scraping collection: {slug} -> {category}")
        page = 1

        while page <= MAX_PAGES:
            url = f"{self.base_url}/collections/{slug}/products.json?limit={PRODUCTS_PER_PAGE}&page={page}"
            time.sleep(SCRAPE_DELAY)

            try:
                resp = self.session.get(url, timeout=30)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.warning(f"[GearVN] API error on page {page}: {e}")
                break

            products = data.get("products", [])
            if not products:
                break

            new_count = 0
            for p in products:
                handle = p.get("handle", "")
                if handle in self._seen_handles:
                    continue
                self._seen_handles.add(handle)

                title = p.get("title", "")
                variants = p.get("variants", [])
                if not variants:
                    continue

                price = int(variants[0].get("price", 0))
                vendor = p.get("vendor", "")
                product_url = f"{self.base_url}/products/{handle}"
                description = html_to_text(p.get("body_html", ""))
                tags = p.get("tags", [])

                specs = {}
                if isinstance(tags, list):
                    for tag in tags:
                        if ":" in tag:
                            k, v = tag.split(":", 1)
                            specs[k.strip()] = v.strip()

                self.add_item(
                    title=title,
                    description=description,
                    price=price,
                    category=category,
                    url=product_url,
                    brand=vendor,
                    specs=specs,
                )
                new_count += 1

            logger.info(f"[GearVN] {slug} page {page}: {new_count} new products (total: {len(self.items)})")
            page += 1

    def scrape(self) -> list[dict]:
        for category, slug in COLLECTIONS:
            self.scrape_collection(category, slug)
        return self.items
