import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.config import MIN_PRICE, MAX_PRICE, MIN_DESCRIPTION_LENGTH, MAX_TEXT_LENGTH
from shared.vn_utils import normalize_vietnamese, clean_title, extract_brand, standardize_category
from phase2_curation.items import Item


def build_full_text(raw: dict) -> str:
    parts = [raw["title"]]
    if raw.get("description"):
        parts.append(raw["description"][:2000])
    if raw.get("specs"):
        specs = raw["specs"]
        if isinstance(specs, str):
            specs = json.loads(specs)
        specs_text = ", ".join(f"{k}: {v}" for k, v in specs.items())
        parts.append(specs_text)
    return normalize_vietnamese("\n".join(parts))[:MAX_TEXT_LENGTH]


def parse(raw: dict) -> Item | None:
    try:
        price = float(raw.get("price", 0))
    except (ValueError, TypeError):
        return None

    if not (MIN_PRICE <= price <= MAX_PRICE):
        return None

    title = clean_title(raw.get("title", ""))
    if not title:
        return None

    full = build_full_text(raw)
    if len(full) < MIN_DESCRIPTION_LENGTH:
        return None

    category = standardize_category(
        raw.get("category", ""),
        raw.get("source", ""),
        title=title,
    )
    brand = raw.get("brand", "") or extract_brand(title)

    return Item(
        title=title,
        category=category,
        price=price,
        source=raw.get("source", ""),
        brand=brand,
        full=full,
        specs=raw.get("specs", {}),
    )
