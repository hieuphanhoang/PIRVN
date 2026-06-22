"""
Dien May Cho Lon scraper — Playwright-based.
dienmaycholon.com is a TPHCM appliance retailer using Vue.js.

Selectors (verified 2026-06-20):
  - Product card: .product (contains .product_block_img + .product_block_desc)
  - Title: .name_pro or .product_block_desc a
  - Sale price: .price_sale (text like "35.990.000 đ" or "Rẻ hơn: 15.490.000 đ")
  - Original price: .price_market
  - Link: a[href] inside .product_block_desc
  - Load more: <button> inside div.see_more_cat ("Xem thêm sản phẩm")
    Vue.js loads more products on click. SSR only gives ~15/category.

Category counts: dien-thoai ~179, tivi ~109, tu-lanh ~84, may-giat ~88, etc.
"""
import logging
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from shared.vn_utils import extract_price_vnd
from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)

CATEGORY_URLS = {
    "Dien_thoai": "https://dienmaycholon.com/dien-thoai-di-dong",
    "Laptop": "https://dienmaycholon.com/laptop-macbook",
    "May_tinh_bang": "https://dienmaycholon.com/may-tinh-bang",
    "TV": "https://dienmaycholon.com/tivi",
    "Tu_lanh": "https://dienmaycholon.com/tu-lanh",
    "May_giat": "https://dienmaycholon.com/may-giat",
    "May_lanh": "https://dienmaycholon.com/may-lanh",
    "Am_thanh": [
        "https://dienmaycholon.com/tai-nghe",
        "https://dienmaycholon.com/loa",
    ],
    "Nha_bep": [
        "https://dienmaycholon.com/lo-vi-song",
        "https://dienmaycholon.com/noi-com-dien",
    ],
    "Phu_kien": "https://dienmaycholon.com/may-loc-nuoc",
}

MAX_CLICKS = 20


class DienMayChoLonScraper(BaseScraper):
    source = "dienmaycholon.com"
    base_url = "https://dienmaycholon.com"

    def _parse_product(self, el, category: str):
        try:
            title = ""
            name_el = el.select_one(".name_pro")
            if name_el:
                title = name_el.get_text(strip=True)
            if not title:
                link_el = el.select_one(".product_block_desc a")
                if link_el:
                    title = link_el.get_text(strip=True)
            if not title or len(title) < 5:
                return

            price_el = el.select_one(".price_sale")
            if not price_el:
                return
            price = extract_price_vnd(price_el.get_text())
            if not price:
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
            logger.debug(f"[DMCL] Error parsing product: {e}")

    def _expand_products(self, page):
        """Click 'Xem thêm sản phẩm' button in div.see_more_cat until all loaded."""
        for i in range(MAX_CLICKS):
            prev_count = page.evaluate("document.querySelectorAll('.product').length")
            clicked = page.evaluate("""
                (() => {
                    const btn = document.querySelector('.see_more_cat button');
                    if (btn && btn.offsetParent !== null) {
                        btn.scrollIntoView();
                        btn.click();
                        return true;
                    }
                    return false;
                })()
            """)
            if not clicked:
                break
            page.wait_for_timeout(2500)
            new_count = page.evaluate("document.querySelectorAll('.product').length")
            logger.info(f"[DMCL] Click {i+1}: {prev_count} -> {new_count} products")
            if new_count == prev_count:
                break

    def scrape_category_pw(self, page, category: str, url: str):
        logger.info(f"[DMCL] Scraping category: {category} from {url}")

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)
        except Exception as e:
            logger.warning(f"[DMCL] Failed to load {url}: {e}")
            return

        self._expand_products(page)

        html = page.content()
        soup = BeautifulSoup(html, "html.parser")
        products = soup.select(".product")

        if not products:
            logger.warning(f"[DMCL] No products found in {category}")
            return

        before = len(self.items)
        for el in products:
            self._parse_product(el, category)

        added = len(self.items) - before
        logger.info(f"[DMCL] {category}: {added} items from {len(products)} cards (total: {len(self.items)})")

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
                        logger.error(f"[DMCL] Failed {category} ({url}): {e}")

            browser.close()

        logger.info(f"[DMCL] Done: {len(self.items)} items total")
        return self.items
