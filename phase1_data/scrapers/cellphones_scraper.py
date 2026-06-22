import logging
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from shared.vn_utils import extract_price_vnd
from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)

CATEGORY_URLS = {
    "Dien_thoai": "https://cellphones.com.vn/mobile.html",
    "Laptop": "https://cellphones.com.vn/laptop.html",
    "May_tinh_bang": "https://cellphones.com.vn/tablet.html",
}


class CellphonesScraper(BaseScraper):
    source = "cellphones.com.vn"
    base_url = "https://cellphones.com.vn"

    def _expand_all_products(self, page) -> str:
        """Click 'Xem thêm' repeatedly until all products are loaded."""
        while True:
            btn = page.query_selector("a.button__show-more-product")
            if not btn or not btn.is_visible():
                break
            try:
                btn.scroll_into_view_if_needed()
                btn.click()
                page.wait_for_timeout(1500)
            except PWTimeout:
                break
            except Exception as e:
                logger.debug(f"[CellphoneS] Click error: {e}")
                break
        return page.content()

    def _parse_product(self, prod_tag, category: str):
        try:
            link_el = prod_tag.select_one("a[href]")
            if not link_el:
                return

            href = link_el["href"]
            if not href.startswith("http"):
                href = self.base_url + href

            name_el = prod_tag.select_one(".product__name")
            title = name_el.get_text(strip=True) if name_el else ""
            if not title:
                return

            price_el = prod_tag.select_one(".product__price--show")
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
            logger.debug(f"[CellphoneS] Error parsing product: {e}")

    def scrape_category_pw(self, page, category: str, url: str):
        logger.info(f"[CellphoneS] Scraping category: {category} from {url}")

        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2000)

        html = self._expand_all_products(page)
        soup = BeautifulSoup(html, "html.parser")

        products = soup.select("div.product-item")
        logger.info(f"[CellphoneS] Found {len(products)} products in {category} (after expanding)")

        for prod in products:
            self._parse_product(prod, category)

    def scrape(self, fetch_details: bool = False) -> list[dict]:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            ctx = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                locale="vi-VN",
            )
            page = ctx.new_page()

            for category, url in CATEGORY_URLS.items():
                try:
                    self.scrape_category_pw(page, category, url)
                except Exception as e:
                    logger.error(f"[CellphoneS] Failed category {category}: {e}")

            browser.close()

        logger.info(f"[CellphoneS] Listing done: {len(self.items)} items total")
        return self.items
