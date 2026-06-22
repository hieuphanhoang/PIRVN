"""
Di Dong Viet scraper — Playwright-based.
didongviet.vn is a TPHCM (Q.3) phone/tablet retailer.
Server renders first 20 products, rest loaded via JS scroll.

Selectors (verified 2026-06-20):
  - Product card: a.product-card
  - Title: a[title] attribute or h3 text
  - Sale price: p.font-bold (containing "XX.XXX.XXX đ")
  - Original price: p with line-through style
  - Link: a.product-card[href]
  - Load more: <button> "Xem thêm N sản phẩm" (Ant Design ant-btn, rendered by Next.js client)
"""
import logging
from playwright.sync_api import sync_playwright
from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)

CATEGORY_URLS = {
    "Dien_thoai": "https://didongviet.vn/dien-thoai.html",
    "May_tinh_bang": "https://didongviet.vn/may-tinh-bang.html",
    "Laptop": "https://didongviet.vn/apple-macbook-imac.html",
    "Am_thanh": [
        "https://didongviet.vn/tai-nghe.html",
        "https://didongviet.vn/loa-bluetooth.html",
    ],
    "Phu_kien": "https://didongviet.vn/dong-ho-thong-minh.html",
}

MAX_SCROLLS = 20


class DiDongVietScraper(BaseScraper):
    source = "didongviet.vn"
    base_url = "https://didongviet.vn"

    def _extract_products_via_js(self, page, category: str):
        """Extract products using JS evaluation — more reliable than BeautifulSoup
        for Next.js/Tailwind sites where class names are dynamic."""
        products = page.evaluate("""
            (() => {
                const cards = document.querySelectorAll('a.product-card');
                return [...cards].map(card => {
                    const title = card.getAttribute('title') || '';
                    const href = card.getAttribute('href') || '';
                    // Price: find <p> with font-bold that contains 'đ'
                    let price = 0;
                    for (const p of card.querySelectorAll('p')) {
                        const cls = p.className || '';
                        const txt = p.textContent.trim();
                        if (cls.includes('font-bold') && txt.includes('đ') && txt.length < 25) {
                            const cleaned = txt.replace(/\\./g,'').replace(/,/g,'').replace(/\\s/g,'')
                                              .replace('₫','').replace('đ','');
                            const match = cleaned.match(/(\\d+)/);
                            if (match) price = parseInt(match[1]);
                            break;
                        }
                    }
                    return { title, href, price };
                });
            })()
        """)
        for p in products:
            if not p["title"] or len(p["title"]) < 5 or not p["price"]:
                continue
            href = p["href"]
            if href and not href.startswith("http"):
                href = self.base_url + href
            self.add_item(
                title=p["title"],
                description="",
                price=p["price"],
                category=category,
                url=href,
                specs={},
            )

    def _expand_products(self, page):
        """Click 'Xem thêm N sản phẩm' button (Ant Design) until all products loaded."""
        for i in range(MAX_SCROLLS):
            prev_count = page.evaluate("document.querySelectorAll('a.product-card').length")
            clicked = page.evaluate("""
                (() => {
                    const btns = document.querySelectorAll('button');
                    for (const btn of btns) {
                        const text = btn.textContent.trim();
                        if (text.includes('Xem thêm') && text.includes('sản phẩm')) {
                            btn.scrollIntoView();
                            btn.click();
                            return true;
                        }
                    }
                    return false;
                })()
            """)
            if not clicked:
                break
            page.wait_for_timeout(3000)
            new_count = page.evaluate("document.querySelectorAll('a.product-card').length")
            logger.info(f"[DDV] Click {i+1}: {prev_count} -> {new_count} products")
            if new_count == prev_count:
                break

    def scrape_category_pw(self, page, category: str, url: str):
        logger.info(f"[DDV] Scraping category: {category} from {url}")

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            # Wait for Next.js to hydrate and render prices (client-side only)
            page.wait_for_selector("a.product-card p.font-bold", timeout=15000)
            page.wait_for_timeout(2000)
        except Exception as e:
            logger.warning(f"[DDV] Failed to load or render {url}: {e}")
            return

        self._expand_products(page)

        card_count = page.evaluate("document.querySelectorAll('a.product-card').length")
        if not card_count:
            logger.warning(f"[DDV] No products found in {category}")
            return

        before = len(self.items)
        self._extract_products_via_js(page, category)
        added = len(self.items) - before
        logger.info(f"[DDV] {category}: {added} items from {card_count} cards (total: {len(self.items)})")

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
                        logger.error(f"[DDV] Failed {category} ({url}): {e}")

            browser.close()

        logger.info(f"[DDV] Done: {len(self.items)} items total")
        return self.items
