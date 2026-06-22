"""
TinhocNgoiSao scraper using Sapo/Haravan products.json API.
Same pattern as Shopify — /collections/{slug}/products.json returns JSON.
Sapo limits to 50 products per page.
"""
import logging
import time
from bs4 import BeautifulSoup
from shared.config import SCRAPE_DELAY
from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)

COLLECTIONS = [
    # PC Components
    ("VGA", "card-man-hinh"),
    ("CPU", "cpu-bo-vi-xu-ly"),
    ("Mainboard", "bo-mach-chu"),
    ("RAM", "bo-nho-ram"),
    ("Luu_tru", "o-cung-ssd"),
    ("Luu_tru", "o-cung-hdd"),
    # Monitors
    ("Man_hinh", "man-hinh-may-tinh"),
    # Laptops
    ("Laptop", "laptop"),
    # Peripherals & networking
    ("Phu_kien", "phu-kien"),
    ("Phu_kien", "thiet-bi-mang"),
]

PRODUCTS_PER_PAGE = 50
MAX_PAGES = 20


def html_to_text(html: str) -> str:
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text(separator=" ", strip=True)[:2000]


class TinhocNgoisaoScraper(BaseScraper):
    source = "tinhocngoisao.com"
    base_url = "https://tinhocngoisao.com"

    def __init__(self):
        super().__init__()
        self._seen_handles = set()

    def scrape_collection(self, category: str, slug: str):
        logger.info(f"[THNS] Scraping collection: {slug} -> {category}")
        page = 1

        while page <= MAX_PAGES:
            url = f"{self.base_url}/collections/{slug}/products.json?limit={PRODUCTS_PER_PAGE}&page={page}"
            time.sleep(SCRAPE_DELAY)

            try:
                resp = self.session.get(url, timeout=30)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.warning(f"[THNS] API error on page {page}: {e}")
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

                price = int(float(variants[0].get("price", 0)))
                vendor = p.get("vendor", "")
                product_url = f"{self.base_url}/products/{handle}"
                description = html_to_text(p.get("body_html", ""))

                self.add_item(
                    title=title,
                    description=description,
                    price=price,
                    category=category,
                    url=product_url,
                    brand=vendor,
                    specs={},
                )
                new_count += 1

            logger.info(f"[THNS] {slug} page {page}: {new_count} new products (total: {len(self.items)})")
            page += 1

    def scrape(self) -> list[dict]:
        for category, slug in COLLECTIONS:
            self.scrape_collection(category, slug)
        return self.items
