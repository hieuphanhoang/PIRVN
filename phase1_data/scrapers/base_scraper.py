import json
import time
import logging
from pathlib import Path
from datetime import date
from abc import ABC, abstractmethod
import requests
from bs4 import BeautifulSoup

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from shared.config import SCRAPE_DELAY, SCRAPE_HEADERS, RAW_DATA_DIR, MIN_PRICE, MAX_PRICE
from shared.vn_utils import normalize_vietnamese, extract_brand, clean_title

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    source: str = ""
    base_url: str = ""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(SCRAPE_HEADERS)
        self.items = []

    def get_soup(self, url: str) -> BeautifulSoup | None:
        try:
            time.sleep(SCRAPE_DELAY)
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
            return BeautifulSoup(resp.content, "html.parser")
        except Exception as e:
            logger.warning(f"Failed to fetch {url}: {e}")
            return None

    def post_api(self, url: str, data: str | None = None) -> dict | None:
        try:
            time.sleep(SCRAPE_DELAY)
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "X-Requested-With": "XMLHttpRequest",
            }
            resp = self.session.post(url, data=data, headers=headers, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"POST failed {url}: {e}")
            return None

    def add_item(self, title: str, description: str, price: int, category: str,
                 url: str, brand: str = "", specs: dict | None = None):
        if not title or not price:
            return
        if price < MIN_PRICE or price > MAX_PRICE:
            return
        title = clean_title(title)
        description = normalize_vietnamese(description) if description else ""
        if not brand:
            brand = extract_brand(title)
        item = {
            "title": title,
            "description": description,
            "price": price,
            "category": category,
            "source": self.source,
            "url": url,
            "brand": brand,
            "specs": specs or {},
            "scraped_at": date.today().isoformat(),
        }
        self.items.append(item)

    @abstractmethod
    def scrape(self) -> list[dict]:
        pass

    def save(self) -> Path:
        RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
        output = RAW_DATA_DIR / f"{self.source.replace('.', '_')}.json"
        with open(output, "w", encoding="utf-8") as f:
            json.dump(self.items, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved {len(self.items)} items to {output}")
        return output

    def run(self) -> list[dict]:
        logger.info(f"Starting scrape of {self.source}")
        self.scrape()
        logger.info(f"Scraped {len(self.items)} items from {self.source}")
        self.save()
        return self.items
