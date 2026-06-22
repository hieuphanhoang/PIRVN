"""
MemoryZone scraper — Sapo/Bizweb JSON API (no Playwright needed).
memoryzone.com.vn uses Bizweb platform with /collections/{slug}/products.json endpoint.
Same pattern as GearVN and TinhocNgoiSao.

Verified 2026-06-20:
  - API: /collections/all/products.json?limit=250&page=N
  - ~1,100 products total (pages 1-5)
  - Fields: name, price, vendor, product_type, summary (specs HTML), content
  - Categories via product_type: RAM, SSD, VGA, CPU, Màn hình, Laptop, etc.
  - TPHCM (Q.Tân Bình)
"""
import logging
import time
from bs4 import BeautifulSoup
from shared.config import SCRAPE_DELAY
from shared.vn_utils import standardize_category
from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)

PRODUCTS_PER_PAGE = 250
MAX_PAGES = 10

PRODUCT_TYPE_TO_CATEGORY = {
    "RAM": "RAM",
    "RAM Server": "RAM",
    "Ổ cứng SSD": "Luu_tru",
    "Ổ cứng HDD": "Luu_tru",
    "Ổ cứng HDD di động": "Luu_tru",
    "Ổ cứng di động SSD": "Luu_tru",
    "CPU": "CPU",
    "Linh kiện PC": "Phu_kien",
    "Màn hình": "Man_hinh",
    "Laptop": "Laptop",
    "Bàn phím": "Ban_phim",
    "Chuột máy tính": "Chuot",
    "Bàn di chuột": "Chuot",
    "Tai nghe": "Am_thanh",
    "Thiết bị mạng": "Phu_kien",
    "Mini PC": "Phu_kien",
    "Ghế": "Phu_kien",
    "NAS": "Luu_tru",
}


def html_to_text(html: str) -> str:
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text(separator=" ", strip=True)[:2000]


class MemoryZoneScraper(BaseScraper):
    source = "memoryzone.com.vn"
    base_url = "https://memoryzone.com.vn"

    def __init__(self):
        super().__init__()
        self._seen_aliases = set()

    def scrape(self) -> list[dict]:
        logger.info(f"[MZ] Scraping all products via JSON API")
        page = 1

        while page <= MAX_PAGES:
            url = f"{self.base_url}/collections/all/products.json?limit={PRODUCTS_PER_PAGE}&page={page}"
            time.sleep(SCRAPE_DELAY)

            try:
                resp = self.session.get(url, timeout=30)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.warning(f"[MZ] API error on page {page}: {e}")
                break

            products = data.get("products", [])
            if not products:
                break

            new_count = 0
            for p in products:
                alias = p.get("alias", "")
                if alias in self._seen_aliases:
                    continue
                self._seen_aliases.add(alias)

                title = p.get("name", "")
                if not title:
                    continue

                price = p.get("price", 0)
                if isinstance(price, str):
                    price = float(price)
                price = int(price)
                if price <= 0:
                    variants = p.get("variants", [])
                    for v in variants:
                        vp = v.get("price", 0)
                        if isinstance(vp, str):
                            vp = float(vp)
                        if int(vp) > 0:
                            price = int(vp)
                            break
                if price <= 0:
                    continue

                vendor = p.get("vendor", "")
                product_type = p.get("product_type", "")
                product_url = f"{self.base_url}/{alias}" if alias else ""
                description = html_to_text(p.get("summary", "") or p.get("content", ""))

                category = PRODUCT_TYPE_TO_CATEGORY.get(product_type, "")
                if not category:
                    category = standardize_category(product_type or "unknown", self.source, title=title)

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

            logger.info(f"[MZ] Page {page}: {new_count} new products (total: {len(self.items)})")

            if len(products) < PRODUCTS_PER_PAGE:
                break
            page += 1

        logger.info(f"[MZ] Done: {len(self.items)} items total")
        return self.items
