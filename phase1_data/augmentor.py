"""
AI-powered data augmentation using Ollama (local LLM).
Enriches thin product descriptions using title + specs.

    cd PIRVN && uv run phase1_data/augmentor.py
"""
import sys
import json
import logging
from pathlib import Path
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.config import RAW_DATA_DIR, OLLAMA_BASE_URL, MIN_DESCRIPTION_LENGTH

# Use llama3.2 (3B) for augmentation — 6x faster than qwen3:4b on CPU
OLLAMA_MODEL = "llama3.2"
from litellm import completion

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("augmentor")

SYSTEM_PROMPT = """Write a short Vietnamese product description (2-3 sentences). Include key specs and use cases. Respond only with the description, nothing else."""


def augment_item(item: dict) -> dict:
    if item.get("description") and len(item["description"]) >= MIN_DESCRIPTION_LENGTH:
        return item

    specs_text = ""
    if item.get("specs"):
        specs_text = "\n".join(f"- {k}: {v}" for k, v in item["specs"].items())

    user_prompt = f"""Write a Vietnamese product description for:
Title: {item['title']}
Brand: {item.get('brand', 'N/A')}
Category: {item.get('category', 'N/A')}
Price: {item['price']:,.0f} VND
Specs:
{specs_text or 'N/A'}"""

    try:
        response = completion(
            model=f"ollama/{OLLAMA_MODEL}",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            api_base=OLLAMA_BASE_URL,
            max_tokens=150,
            temperature=0.3,
        )
        generated = response.choices[0].message.content.strip()
        if generated and len(generated) > 30:
            item["description"] = generated
            item["augmented"] = True
    except Exception as e:
        logger.debug(f"Augmentation failed for {item['title']}: {e}")

    return item


SAVE_EVERY = 50


def run_augmentation(input_path: Path | None = None, output_path: Path | None = None):
    input_path = input_path or RAW_DATA_DIR / "all_items.json"
    output_path = output_path or RAW_DATA_DIR / "all_items_augmented.json"

    with open(input_path, "r", encoding="utf-8") as f:
        items = json.load(f)
    logger.info(f"Loaded {len(items)} items from {input_path.name}")

    # Resume: carry over augmented descriptions from previous run
    if output_path.exists():
        with open(output_path, "r", encoding="utf-8") as f:
            old_items = json.load(f)
        old_desc = {}
        for it in old_items:
            if it.get("augmented") and it.get("description"):
                old_desc[it["title"]] = it["description"]
        carried = 0
        for it in items:
            if not it.get("description") or len(it.get("description", "")) < MIN_DESCRIPTION_LENGTH:
                if it["title"] in old_desc:
                    it["description"] = old_desc[it["title"]]
                    it["augmented"] = True
                    carried += 1
        if carried:
            logger.info(f"Resumed {carried} augmented descriptions from previous run")

    thin = [i for i in items if not i.get("description") or len(i.get("description", "")) < MIN_DESCRIPTION_LENGTH]
    logger.info(f"Total items: {len(items)}, thin descriptions to augment: {len(thin)}")

    augmented_count = 0
    for idx, item in enumerate(tqdm(thin, desc="Augmenting"), 1):
        augment_item(item)
        if item.get("augmented"):
            augmented_count += 1

        # Auto-save every SAVE_EVERY items to avoid losing progress on interrupt
        if idx % SAVE_EVERY == 0:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(items, f, ensure_ascii=False, indent=2)
            logger.info(f"  Auto-saved at {idx}/{len(thin)} ({augmented_count} augmented)")

    logger.info(f"Augmented {augmented_count}/{len(thin)} items")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

    logger.info(f"Saved to {output_path}")


if __name__ == "__main__":
    run_augmentation()
