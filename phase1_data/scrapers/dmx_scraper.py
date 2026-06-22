import logging
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from shared.vn_utils import extract_price_vnd
from shared.config import SCRAPE_DELAY
from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)

CATEGORY_URLS = {
    "TV": "https://www.dienmayxanh.com/tivi",
    "Tu_lanh": "https://www.dienmayxanh.com/tu-lanh",
    "May_giat": "https://www.dienmayxanh.com/may-giat",
    "May_lanh": "https://www.dienmayxanh.com/may-lanh",
    "Nha_bep": [
        "https://www.dienmayxanh.com/lo-vi-song",
        "https://www.dienmayxanh.com/noi-com-dien",
    ],
}


class DMXScraper(BaseScraper):
    source = "dienmayxanh.com"
    base_url = "https://www.dienmayxanh.com"

    def _expand_all_products(self, page) -> str:
        """Click 'Xem thêm' repeatedly until all products are loaded."""
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
                logger.debug(f"[DMX] Click error: {e}")
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
            logger.debug(f"[DMX] Error parsing product: {e}")

    def _fetch_detail(self, item: dict):
        """Fetch product detail page for description and specs."""
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
            "div.parameter li, ul.parameter__list li"
        )
        for row in spec_rows[:20]:
            cols = row.select("span, p")
            if len(cols) >= 2:
                key = cols[0].get_text(strip=True)
                val = cols[1].get_text(strip=True)
                if key and val:
                    specs[key] = val
        if specs:
            item["specs"] = specs

    def scrape_category_pw(self, page, category: str, url: str):
        logger.info(f"[DMX] Scraping category: {category} from {url}")

        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2000)

        html = self._expand_all_products(page)
        soup = BeautifulSoup(html, "html.parser")

        product_items = soup.select("ul.listproduct > li")
        logger.info(f"[DMX] Found {len(product_items)} products in {category} (after expanding)")

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

            for category, urls in CATEGORY_URLS.items():
                if isinstance(urls, str):
                    urls = [urls]
                for url in urls:
                    try:
                        self.scrape_category_pw(page, category, url)
                    except Exception as e:
                        logger.error(f"[DMX] Failed {category} ({url}): {e}")

            browser.close()

        logger.info(f"[DMX] Listing scrape done: {len(self.items)} items total")

        if fetch_details:
            logger.info(f"[DMX] Fetching detail pages for {len(self.items)} items...")
            for i, item in enumerate(self.items):
                self._fetch_detail(item)
                if (i + 1) % 50 == 0:
                    logger.info(f"[DMX] Detail progress: {i + 1}/{len(self.items)}")

        return self.items
