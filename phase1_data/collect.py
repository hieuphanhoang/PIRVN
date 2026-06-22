"""
Orchestrates all scrapers. Run with:
    cd PIRVN && uv run phase1_data/collect.py              # all sites
    cd PIRVN && uv run phase1_data/collect.py gearvn       # one site
    cd PIRVN && uv run phase1_data/collect.py gearvn tgdd  # multiple sites
    cd PIRVN && uv run phase1_data/collect.py --list        # show available names
    cd PIRVN && uv run phase1_data/collect.py --merge       # merge all per-site JSONs into all_items.json
"""
import sys
import json
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.config import RAW_DATA_DIR
from phase1_data.scrapers.tgdd_scraper import TGDDScraper
from phase1_data.scrapers.dmx_scraper import DMXScraper
from phase1_data.scrapers.gearvn_scraper import GearVNScraper
from phase1_data.scrapers.cellphones_scraper import CellphonesScraper
from phase1_data.scrapers.tinhocngoisao_scraper import TinhocNgoisaoScraper
from phase1_data.scrapers.nguyencongpc_scraper import NguyenCongPCScraper
from phase1_data.scrapers.fptshop_scraper import FPTShopScraper
from phase1_data.scrapers.viettelstore_scraper import ViettelStoreScraper
from phase1_data.scrapers.dienmaycholon_scraper import DienMayChoLonScraper
from phase1_data.scrapers.memoryzone_scraper import MemoryZoneScraper
from phase1_data.scrapers.didongviet_scraper import DiDongVietScraper
from phase1_data.scrapers.clickbuy_scraper import ClickBuyScraper

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(name)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("collect")

SCRAPER_REGISTRY = {
    "tgdd":         TGDDScraper,
    "dmx":          DMXScraper,
    "gearvn":       GearVNScraper,
    "cellphones":   CellphonesScraper,
    "tinhocngoisao": TinhocNgoisaoScraper,
    "nguyencongpc": NguyenCongPCScraper,
    "fptshop":      FPTShopScraper,
    "viettelstore": ViettelStoreScraper,
    "dienmaycholon": DienMayChoLonScraper,
    "memoryzone":   MemoryZoneScraper,
    "didongviet":   DiDongVietScraper,
    "clickbuy":     ClickBuyScraper,
}


def run_scrapers(names: list[str] | None = None):
    """Run selected scrapers (or all if names is None). Each saves its own JSON."""
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

    if names is None:
        names = list(SCRAPER_REGISTRY.keys())

    total_items = 0
    for name in names:
        cls = SCRAPER_REGISTRY.get(name)
        if not cls:
            logger.error(f"Unknown scraper: '{name}'. Use --list to see available names.")
            continue
        scraper = cls()
        try:
            logger.info(f"Starting {scraper.source}...")
            scraper.scrape()
            scraper.save()
            logger.info(f"  -> {scraper.source}: {len(scraper.items)} items")
            total_items += len(scraper.items)
        except Exception as e:
            logger.error(f"  -> {scraper.source} FAILED: {e}", exc_info=True)

    logger.info(f"Done. {total_items} items from {len(names)} scraper(s)")
    return total_items


def merge_all():
    """Merge all per-site JSON files in raw_data/ into all_items.json."""
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    all_items = []

    for cls in SCRAPER_REGISTRY.values():
        source_file = RAW_DATA_DIR / f"{cls.source.replace('.', '_')}.json"
        if source_file.exists():
            with open(source_file, "r", encoding="utf-8") as f:
                items = json.load(f)
            all_items.extend(items)
            logger.info(f"  {source_file.name}: {len(items)} items")
        else:
            logger.warning(f"  {source_file.name}: NOT FOUND (run scraper first)")

    combined_path = RAW_DATA_DIR / "all_items.json"
    with open(combined_path, "w", encoding="utf-8") as f:
        json.dump(all_items, f, ensure_ascii=False, indent=2)

    logger.info(f"Merged: {len(all_items)} items -> {combined_path}")
    return all_items


if __name__ == "__main__":
    args = sys.argv[1:]

    if "--list" in args:
        print("Available scrapers:")
        for name, cls in SCRAPER_REGISTRY.items():
            print(f"  {name:16s}  {cls.source}")
        sys.exit(0)

    if "--merge" in args:
        merge_all()
        sys.exit(0)

    if args:
        run_scrapers(args)
    else:
        run_scrapers()
        merge_all()
