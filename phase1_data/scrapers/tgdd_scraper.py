import logging
import time
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from shared.vn_utils import extract_price_vnd
from shared.config import SCRAPE_DELAY
from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)

CATEGORY_URLS = {
    "Dien_thoai": "https://www.thegioididong.com/dtdd",
    "Laptop": "https://www.thegioididong.com/laptop",
    "May_tinh_bang": "https://www.thegioididong.com/may-tinh-bang",
    "Am_thanh": "https://www.thegioididong.com/loa",
}


class TGDDScraper(BaseScraper):
    source = "thegioididong.com"
    base_url = "https://www.thegioididong.com"

    def _expand_all_products(self, page) -> str:
        """Click 'Xem thêm' repeatedly until all products are loaded, return full HTML."""
        while True:
            btn = page.query_selector(".view-more a")
            if not btn or not btn.is_visible():
                break
            try:
                btn.scroll_into_view_if_needed()
                btn.click()
                page.wait_for_timeout(1500)
            except PWTimeout:
                break
            except Exception as e:
                logger.debug(f"[TGDD] Click error: {e}")
                break
        return page.content()

    def _parse_product_li(self, li_tag, category: str):
        try:
            link_el = li_tag.select_one("a")
            if not link_el or not link_el.get("href"):
                return

            href = link_el["href"]
            if not href.startswith("http"):
                href = self.base_url + href

            # Clean title from p.product-title or img alt (not <a> text which has promo tags)
            title_el = li_tag.select_one("p.product-title")
            img_el = li_tag.select_one("img.thumb")
            title = ""
            if title_el:
                title = title_el.get_text(strip=True)
            elif img_el and img_el.get("alt"):
                title = img_el["alt"]
            if not title:
                return

            price_el = li_tag.select_one("strong.price, span.price, div.price")
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
            logger.debug(f"[TGDD] Error parsing product: {e}")

    def _fetch_detail(self, item: dict):
        """Fetch product detail page for description and specs (uses requests session)."""
        detail_soup = self.get_soup(item["url"])
        if not detail_soup:
            return
        desc_el = detail_soup.select_one(
            "div.text-content, div.article-detail, div.box-content"
        )
        if desc_el:
            item["description"] = desc_el.get_text(separator=" ", strip=True)[:2000]

        specs = {}
        spec_rows = detail_soup.select(
            "div.parameter li, ul.parameter__list li, table.specifi tr"
        )
        for row in spec_rows[:20]:
            cols = row.select("span, td, p")
            if len(cols) >= 2:
                key = cols[0].get_text(strip=True)
                val = cols[1].get_text(strip=True)
                if key and val:
                    specs[key] = val
        if specs:
            item["specs"] = specs

    def scrape_category_pw(self, page, category: str, url: str):
        logger.info(f"[TGDD] Scraping category: {category} from {url}")

        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2000)

        # Expand all products
        html = self._expand_all_products(page)
        soup = BeautifulSoup(html, "html.parser")

        product_items = soup.select("ul.listproduct > li")
        logger.info(f"[TGDD] Found {len(product_items)} products in {category} (after expanding)")

        for li in product_items:
            self._parse_product_li(li, category)

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
                    logger.error(f"[TGDD] Failed category {category}: {e}")

            browser.close()

        logger.info(f"[TGDD] Listing scrape done: {len(self.items)} items total")

        if fetch_details:
            logger.info(f"[TGDD] Fetching detail pages for {len(self.items)} items...")
            for i, item in enumerate(self.items):
                self._fetch_detail(item)
                if (i + 1) % 50 == 0:
                    logger.info(f"[TGDD] Detail progress: {i + 1}/{len(self.items)}")

        return self.items
