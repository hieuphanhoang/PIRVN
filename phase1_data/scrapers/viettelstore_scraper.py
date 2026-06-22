"""
Viettel Store scraper — Playwright-based.
viettelstore.vn is server-rendered with JS lazy-loading.

Selectors (verified 2026-06-20):
  - Product card: .product-item (contains .product-info)
  - Title: .product-info h3, or a[title]
  - Price: .product-price, [class*='price']
  - Link: a[href] inside .product-item
  - Load more: <a href="javascript:void();">Xem thêm sản phẩm</a> (no class/id)
    Must use text selector: a:has-text('Xem thêm sản phẩm')

Page shows "158 sản phẩm" but only loads 25 at a time — need to click
"Xem thêm sản phẩm" repeatedly to load all.
"""
import logging
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from shared.vn_utils import extract_price_vnd
from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)

CATEGORY_URLS = {
    "Dien_thoai": "https://viettelstore.vn/dien-thoai",
    "Laptop": "https://viettelstore.vn/laptop",
    "May_tinh_bang": "https://viettelstore.vn/may-tinh-bang",
    "Am_thanh": [
        "https://viettelstore.vn/tai-nghe",
        "https://viettelstore.vn/loa-bluetooth",
    ],
    "Phu_kien": "https://viettelstore.vn/phu-kien",
}

MAX_CLICKS = 15


class ViettelStoreScraper(BaseScraper):
    source = "viettelstore.vn"
    base_url = "https://viettelstore.vn"

    def _parse_product(self, el, category: str):
        """Extract product data from data-* attributes on the <a> tag."""
        try:
            link = el.select_one("a[data-name][data-price]")
            if not link:
                return

            title = link.get("data-name", "").strip()
            if not title:
                return

            price_raw = link.get("data-price", "0")
            try:
                price = int(round(float(price_raw)))
            except (ValueError, TypeError):
                return

            href = link.get("href", "")
            if href and not href.startswith("http"):
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
            logger.debug(f"[VTS] Error parsing product: {e}")

    def _expand_products(self, page) -> str:
        """Click 'Xem thêm sản phẩm' until all products are loaded."""
        for i in range(MAX_CLICKS):
            prev_count = page.evaluate("document.querySelectorAll('.product-item').length")
            try:
                # Use JS click — Playwright CSS :has-text may not match <a href="javascript:void();">
                clicked = page.evaluate("""
                    (() => {
                        const btns = [...document.querySelectorAll('a')];
                        const btn = btns.find(a =>
                            a.textContent.trim().includes('Xem thêm sản phẩm') &&
                            a.href.includes('javascript')
                        );
                        if (btn && btn.offsetParent !== null) {
                            btn.click();
                            return true;
                        }
                        return false;
                    })()
                """)
                if not clicked:
                    break
                page.wait_for_timeout(2500)
                new_count = page.evaluate("document.querySelectorAll('.product-item').length")
                logger.info(f"[VTS] Click {i+1}: {prev_count} -> {new_count} products")
                if new_count == prev_count:
                    break
            except Exception as e:
                logger.debug(f"[VTS] Expand click failed: {e}")
                break
        return page.content()

    def scrape_category_pw(self, page, category: str, url: str):
        logger.info(f"[VTS] Scraping category: {category} from {url}")

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)
        except Exception as e:
            logger.warning(f"[VTS] Failed to load {url}: {e}")
            return

        html = self._expand_products(page)
        soup = BeautifulSoup(html, "html.parser")
        products = soup.select(".product-item")

        if not products:
            logger.warning(f"[VTS] No products found in {category}")
            return

        before = len(self.items)
        for el in products:
            self._parse_product(el, category)

        added = len(self.items) - before
        logger.info(f"[VTS] {category}: {added} items from {len(products)} cards (total: {len(self.items)})")

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
                        logger.error(f"[VTS] Failed {category} ({url}): {e}")

            browser.close()

        logger.info(f"[VTS] Done: {len(self.items)} items total")
        return self.items
