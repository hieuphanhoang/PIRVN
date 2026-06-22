"""
FPT Shop scraper — Next.js SPA with Playwright.
fptshop.com.vn uses a Next.js frontend.

Selectors (expected structure):
  - Product card: .product-card, .fs-product-card, div[class*="ProductCard"]
  - Title: h3, .product-name, a[title]
  - Price: .product-price, .price, span[class*="price"]
  - Link: a[href] within product card
  - Pagination: page buttons or infinite scroll

NOTE: Selectors need verification on first run — FPT Shop updates frontend frequently.
      Run with LOG_LEVEL=DEBUG to see parsing details if yield is low.
"""
import logging
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from shared.vn_utils import extract_price_vnd
from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)

CATEGORY_URLS = {
    "Dien_thoai": "https://fptshop.com.vn/dien-thoai",
    "Laptop": "https://fptshop.com.vn/may-tinh-xach-tay",
    "May_tinh_bang": "https://fptshop.com.vn/may-tinh-bang",
    "TV": "https://fptshop.com.vn/tivi",
    "Tu_lanh": "https://fptshop.com.vn/tu-lanh",
    "May_giat": "https://fptshop.com.vn/may-giat",
    "May_lanh": "https://fptshop.com.vn/may-lanh",
    "Am_thanh": [
        "https://fptshop.com.vn/tai-nghe",
        "https://fptshop.com.vn/loa",
    ],
    "Nha_bep": [
        "https://fptshop.com.vn/lo-vi-song",
        "https://fptshop.com.vn/noi-com-dien",
    ],
}

PRODUCT_CARD_SELECTORS = [
    ".product-card",
    ".fs-product-card",
    "div[class*='ProductCard']",
    ".cdt-product",
    ".card-product",
]

TITLE_SELECTORS = [
    "h3",
    ".product-name",
    ".product-title",
    "a[title]",
    "[class*='product-name']",
    "[class*='ProductName']",
]

PRICE_SELECTORS = [
    ".product-price",
    ".price",
    "[class*='progress-price']",
    "[class*='Price']",
    "span[class*='price']",
]

MAX_SCROLLS = 20


class FPTShopScraper(BaseScraper):
    source = "fptshop.com.vn"
    base_url = "https://fptshop.com.vn"

    def _find_products(self, soup: BeautifulSoup) -> list:
        """Try multiple selectors to find product containers."""
        for sel in PRODUCT_CARD_SELECTORS:
            products = soup.select(sel)
            if products:
                logger.debug(f"[FPT] Found {len(products)} products with selector: {sel}")
                return products
        return []

    def _extract_title(self, el) -> str:
        for sel in TITLE_SELECTORS:
            title_el = el.select_one(sel)
            if title_el:
                if title_el.get("title"):
                    return title_el["title"].strip()
                text = title_el.get_text(strip=True)
                if text and len(text) > 5:
                    return text
        return ""

    def _extract_price(self, el) -> int | None:
        for sel in PRICE_SELECTORS:
            price_el = el.select_one(sel)
            if price_el:
                price = extract_price_vnd(price_el.get_text())
                if price:
                    return price
        return None

    def _extract_link(self, el) -> str:
        link_el = el.select_one("a[href]")
        if link_el and link_el.get("href"):
            href = link_el["href"]
            if not href.startswith("http"):
                href = self.base_url + href
            return href
        return ""

    def _parse_product(self, el, category: str):
        try:
            title = self._extract_title(el)
            if not title:
                return
            price = self._extract_price(el)
            if not price:
                return
            url = self._extract_link(el)

            self.add_item(
                title=title,
                description="",
                price=price,
                category=category,
                url=url,
                specs={},
            )
        except Exception as e:
            logger.debug(f"[FPT] Error parsing product: {e}")

    def _load_all_products(self, page) -> str:
        """Try clicking 'Xem thêm' or scroll to load all products."""
        load_more_sels = [
            "a.btn-load-more",
            "button.btn-load-more",
            "[class*='load-more']",
            "[class*='LoadMore']",
            "a:has-text('Xem thêm')",
        ]
        for _ in range(MAX_SCROLLS):
            clicked = False
            for sel in load_more_sels:
                try:
                    btn = page.query_selector(sel)
                    if btn and btn.is_visible():
                        btn.scroll_into_view_if_needed()
                        btn.click()
                        page.wait_for_timeout(2000)
                        clicked = True
                        break
                except Exception:
                    continue
            if not clicked:
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(1500)
                break
        return page.content()

    def scrape_category_pw(self, page, category: str, url: str):
        logger.info(f"[FPT] Scraping category: {category} from {url}")

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)
        except Exception as e:
            logger.warning(f"[FPT] Failed to load {url}: {e}")
            return

        html = self._load_all_products(page)
        soup = BeautifulSoup(html, "html.parser")
        products = self._find_products(soup)

        if not products:
            logger.warning(f"[FPT] No products found in {category} — selectors may need update")
            return

        for el in products:
            self._parse_product(el, category)

        logger.info(f"[FPT] {category}: {len(products)} products found (total: {len(self.items)})")

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
                        logger.error(f"[FPT] Failed {category} ({url}): {e}")

            browser.close()

        logger.info(f"[FPT] Done: {len(self.items)} items total")
        return self.items
