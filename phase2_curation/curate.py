"""
Full curation pipeline: load raw data, parse, dedup, split, save/push.

    cd PIRVN && uv run phase2_curation/curate.py
"""
import sys
import json
import random
import logging
from pathlib import Path
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.config import RAW_DATA_DIR, CURATED_DATA_DIR, HF_DATASET_NAME
from shared.vn_utils import fuzzy_title_key
from phase2_curation.parser import parse

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("curate")


def load_raw_items() -> list[dict]:
    augmented = RAW_DATA_DIR / "all_items_augmented.json"
    fallback = RAW_DATA_DIR / "all_items.json"
    path = augmented if augmented.exists() else fallback
    logger.info(f"Loading from {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def deduplicate(items):
    from statistics import mean

    # Group by fuzzy title key — cross-site duplicates get averaged price
    title_groups = {}
    seen_full = set()
    for item in tqdm(items, desc="Deduplicating"):
        if item.full in seen_full:
            continue
        seen_full.add(item.full)

        key = fuzzy_title_key(item.title)
        if key not in title_groups:
            title_groups[key] = []
        title_groups[key].append(item)

    unique = []
    multi_source_count = 0
    for key, group in title_groups.items():
        best = group[0]
        if len(group) > 1:
            best.price = mean([it.price for it in group])
            sources = set(it.source for it in group if it.source)
            if len(sources) > 1:
                best.source = ", ".join(sorted(sources))
                multi_source_count += 1
            # Keep longest description
            longest = max(group, key=lambda it: len(it.full))
            if len(longest.full) > len(best.full):
                best.full = longest.full
        unique.append(best)

    logger.info(f"Dedup: {len(items)} -> {len(unique)} ({multi_source_count} cross-site averages)")
    return unique


def curate():
    raw = load_raw_items()
    logger.info(f"Loaded {len(raw)} raw items")

    items = [parse(r) for r in tqdm(raw, desc="Parsing")]
    items = [it for it in items if it is not None]
    logger.info(f"Parsed {len(items)} valid items")

    random.seed(42)
    random.shuffle(items)
    items = deduplicate(items)
    logger.info(f"After dedup: {len(items)} items")

    for i, item in enumerate(items):
        item.id = i
        item.make_prompt(item.full)

    # Split: 80% train, 5% val, 15% test
    n = len(items)
    train_end = int(n * 0.80)
    val_end = int(n * 0.85)

    train = items[:train_end]
    val = items[train_end:val_end]
    test = items[val_end:]
    logger.info(f"Split: train={len(train)}, val={len(val)}, test={len(test)}")

    # Save locally
    CURATED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    for name, split in [("train", train), ("val", val), ("test", test)]:
        path = CURATED_DATA_DIR / f"{name}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump([it.model_dump() for it in split], f, ensure_ascii=False, indent=2)
        logger.info(f"Saved {name}: {len(split)} items to {path}")

    # Push to HuggingFace (optional — requires HF_TOKEN)
    try:
        from phase2_curation.items import Item as ItemCls
        ItemCls.push_to_hub(HF_DATASET_NAME, train, val, test)
        logger.info(f"Pushed to HuggingFace: {HF_DATASET_NAME}")
    except Exception as e:
        logger.warning(f"HuggingFace push failed (set HF_TOKEN in .env): {e}")

    return train, val, test


if __name__ == "__main__":
    curate()
