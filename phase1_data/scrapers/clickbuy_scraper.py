"""
ClickBuy scraper — Playwright-based.
clickbuy.com.vn is a TPHCM (Q.3, Q.Tân Bình) phone/laptop retailer.

Selectors (verified 2026-06-20 via curl):
  - Product card: .list-products__item
  - Title: strong.title_name
  - Sale price: ins.new-price[data-price] (attribute = integer VND, no parsing needed)
  - Original price: del.old-price[data-price]
  - Link: a[href] inside card
  - Load more: a.btn-show-more.button__show-more-product ("Xem thêm 283 sản phẩm")

Product counts: dien-thoai ~303, laptop ~81, macbook ~45, tai-nghe ~27, loa ~18
"""
import logging
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)

CATEGORY_URLS = {
    "Dien_thoai": "https://clickbuy.com.vn/dien-thoai",
    "Laptop": [
        "https://clickbuy.com.vn/laptop",
        "https://clickbuy.com.vn/macbook",
    ],
    "Am_thanh": [
        "https://clickbuy.com.vn/tai-nghe",
        "https://clickbuy.com.vn/loa",
    ],
}

MAX_CLICKS = 20


class ClickBuyScraper(BaseScraper):
    source = "clickbuy.com.vn"
    base_url = "https://clickbuy.com.vn"

    def _parse_product(self, el, category: str):
        try:
            title_el = el.select_one("strong.title_name")
            if not title_el:
                return
            title = title_el.get_text(strip=True)
            if not title or len(title) < 5:
                return

            # Sale price from data-price attribute (integer VND, no parsing needed)
            price_el = el.select_one("ins.new-price[data-price]")
            if not price_el:
                return
            try:
                price = int(price_el["data-price"])
            except (ValueError, KeyError):
                return

            link_el = el.select_one("a[href]")
            href = ""
            if link_el and link_el.get("href"):
                href = link_el["href"]
                if not href.startswith("http"):
                    href = self.base_url + href

            self.add_item(
                title=title,
                description="",
                price=price,
                category=category,
                url=href,
                specs={},
            )
        except Exception as e:
            logger.debug(f"[CB] Error parsing product: {e}")

    def _expand_products(self, page) -> str:
        """Click 'Xem thêm N sản phẩm' button until all products loaded."""
        for i in range(MAX_CLICKS):
            prev_count = page.evaluate("document.querySelectorAll('.list-products__item').length")
            try:
                btn = page.query_selector("a.button__show-more-product")
                if not btn or not btn.is_visible():
                    break
                btn.scroll_into_view_if_needed()
                btn.click()
                page.wait_for_timeout(2000)
                new_count = page.evaluate("document.querySelectorAll('.list-products__item').length")
                logger.info(f"[CB] Click {i+1}: {prev_count} -> {new_count} products")
                if new_count == prev_count:
                    break
            except Exception as e:
                logger.debug(f"[CB] Expand click failed: {e}")
                break
        return page.content()

    def scrape_category_pw(self, page, category: str, url: str):
        logger.info(f"[CB] Scraping category: {category} from {url}")

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)
        except Exception as e:
            logger.warning(f"[CB] Failed to load {url}: {e}")
            return

        html = self._expand_products(page)
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select(".list-products__item")

        if not cards:
            logger.warning(f"[CB] No products found in {category}")
            return

        before = len(self.items)
        for card in cards:
            self._parse_product(card, category)

        added = len(self.items) - before
        logger.info(f"[CB] {category}: {added} items from {len(cards)} cards (total: {len(self.items)})")

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
                        logger.error(f"[CB] Failed {category} ({url}): {e}")

            browser.close()

        logger.info(f"[CB] Done: {len(self.items)} items total")
        return self.items
