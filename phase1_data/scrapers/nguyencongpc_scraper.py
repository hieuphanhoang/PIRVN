"""
NguyenCongPC scraper — SPA with Playwright.
nguyencongpc.vn uses a JS-rendered SPA with pagination (?page=N).

Selectors (verified 2026-06-19):
  - Product card: .product-item
  - Title: .product-title
  - Price: .product-market-price (original), .product-price (sale)
  - Link: a[href] inside .product-item
  - Pagination: ?page=N (30 items/page)
"""
import logging
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from shared.vn_utils import extract_price_vnd
from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)

CATEGORY_URLS = {
    "Laptop": "https://nguyencongpc.vn/laptop",
    "VGA": "https://nguyencongpc.vn/vga-card-man-hinh",
    "CPU": "https://nguyencongpc.vn/cpu-bo-vi-xu-ly",
    "Mainboard": "https://nguyencongpc.vn/mainboard-bo-mach-chu",
    "RAM": "https://nguyencongpc.vn/ram",
    "Luu_tru": [
        "https://nguyencongpc.vn/o-cung-ssd",
        "https://nguyencongpc.vn/o-cung-hdd",
    ],
    "Nguon_Case": [
        "https://nguyencongpc.vn/psu-nguon-may-tinh",
        "https://nguyencongpc.vn/case-vo-may-tinh",
    ],
    "Tan_nhiet": "https://nguyencongpc.vn/tan-nhiet",
    "Man_hinh": "https://nguyencongpc.vn/man-hinh-may-tinh",
    "Ban_phim": "https://nguyencongpc.vn/ban-phim",
    "Chuot": "https://nguyencongpc.vn/chuot-mouse",
    "Am_thanh": [
        "https://nguyencongpc.vn/tai-nghe",
        "https://nguyencongpc.vn/loa",
    ],
}

MAX_PAGES = 20


class NguyenCongPCScraper(BaseScraper):
    source = "nguyencongpc.vn"
    base_url = "https://nguyencongpc.vn"

    def _parse_product(self, el, category: str):
        try:
            title_el = el.select_one(".product-title")
            if not title_el:
                return
            title = title_el.get_text(strip=True)
            if not title:
                return

            link_el = el.select_one("a[href]")
            href = ""
            if link_el and link_el.get("href"):
                href = link_el["href"]
                if not href.startswith("http"):
                    href = self.base_url + href

            price_el = el.select_one(".product-price, .product-market-price")
            if not price_el:
                return
            price = extract_price_vnd(price_el.get_text())
            if not price:
                return

            self.add_item(
                title=title,
                description="",
                price=price,
                category=category,
                url=href,
                specs={},
            )
        except Exception as e:
            logger.debug(f"[NCPC] Error parsing product: {e}")

    def scrape_category_pw(self, page, category: str, url: str):
        logger.info(f"[NCPC] Scraping category: {category} from {url}")

        for page_num in range(1, MAX_PAGES + 1):
            page_url = url if page_num == 1 else f"{url}?page={page_num}"
            try:
                page.goto(page_url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(2500)
            except Exception as e:
                logger.warning(f"[NCPC] Failed to load {page_url}: {e}")
                break

            soup = BeautifulSoup(page.content(), "html.parser")
            products = soup.select(".product-item")

            if not products:
                break

            before = len(self.items)
            for el in products:
                self._parse_product(el, category)

            added = len(self.items) - before
            logger.info(f"[NCPC] {url} page {page_num}: {added} products (total: {len(self.items)})")

            if len(products) < 20:
                break

    def scrape(self) -> list[dict]:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            ctx = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                locale="vi-VN",
            )
            page = ctx.new_page()

            for category, urls in CATEGORY_URLS.items():
                if isinstance(urls, str):
                    urls = [urls]
                for url in urls:
                    try:
                        self.scrape_category_pw(page, category, url)
                    except Exception as e:
                        logger.error(f"[NCPC] Failed {category} ({url}): {e}")

            browser.close()

        logger.info(f"[NCPC] Done: {len(self.items)} items total")
        return self.items
