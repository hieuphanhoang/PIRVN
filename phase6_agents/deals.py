import re
import logging
from typing import List, Self
from pydantic import BaseModel, Field
from bs4 import BeautifulSoup
import requests
from tqdm import tqdm

logger = logging.getLogger(__name__)

WEBSOSANH_CATEGORIES = [
    ("laptop", 18),
    ("dien-thoai-smartphone", 82),
    ("tivi", 15),
    ("tu-lanh", 60),
    ("may-giat", 58),
    ("dieu-hoa-may-lanh", 51),
    ("linh-kien-may-tinh", 75),
    ("man-hinh-may-tinh", 143),
    ("loa", 157),
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
}


def parse_vnd_price(text: str) -> float:
    text = re.sub(r"[^\d]", "", text)
    return float(text) if text else 0.0


class ScrapedDeal:
    title: str
    summary: str
    url: str
    details: str
    features: str

    def __init__(self, title: str, price_text: str, url: str):
        self.title = title[:200]
        self.summary = price_text
        self.url = url
        self.price_raw = parse_vnd_price(price_text)
        self.details = ""
        self.features = ""

    def __repr__(self):
        return f"<{self.title}>"

    def describe(self):
        return (
            f"Title: {self.title}\n"
            f"Price: {self.price_raw:,.0f} VND\n"
            f"Details: {self.details.strip()}\n"
            f"URL: {self.url}"
        )

    @classmethod
    def _scrape_category(cls, slug: str, cat_id: int, max_products: int = 10) -> List[Self]:
        url = f"https://websosanh.vn/{slug}/cat-{cat_id}.htm"
        deals = []
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                logger.warning(f"websosanh.vn {slug} returned {resp.status_code}")
                return deals
            soup = BeautifulSoup(resp.text, "html.parser")
            for card in soup.select("div.product-single")[:max_products]:
                link_el = card.select_one("h2.product-single-name > a")
                price_el = card.select_one("div.product-single-price")
                if not link_el or not price_el:
                    continue
                title = link_el.get_text(strip=True)
                href = link_el.get("href", "")
                if href and not href.startswith("http"):
                    href = "https://websosanh.vn" + href
                price_text = price_el.get_text(strip=True)
                price_val = parse_vnd_price(price_text)
                if price_val < 500_000:
                    continue
                deals.append(cls(title, price_text, href))
        except Exception as e:
            logger.warning(f"Failed to scrape websosanh.vn/{slug}: {e}")
        return deals

    @classmethod
    def fetch(cls, show_progress: bool = False, max_per_category: int = 10) -> List[Self]:
        deals = []
        cat_iter = tqdm(WEBSOSANH_CATEGORIES, desc="Scraping") if show_progress else WEBSOSANH_CATEGORIES
        for slug, cat_id in cat_iter:
            category_deals = cls._scrape_category(slug, cat_id, max_per_category)
            deals.extend(category_deals)
        return deals


class Deal(BaseModel):
    product_description: str = Field(
        description="A clear summary of the product in 3-4 sentences focusing on the item itself, not the deal terms."
    )
    price: float = Field(
        description="The actual price in VND as advertised."
    )
    url: str = Field(description="The URL of the deal")


class DealSelection(BaseModel):
    deals: List[Deal] = Field(
        description="The 5 deals with the most detailed descriptions and clearest prices."
    )


class Opportunity(BaseModel):
    deal: Deal
    estimate: float
    discount: float
