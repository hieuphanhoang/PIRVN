"""
Prepare training data in JSONL chat format for QLoRA fine-tuning.

    cd PIRVN && uv run phase4_finetune/prepare_data.py
"""
import sys
import json
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.config import CURATED_DATA_DIR

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("prepare_data")

SYSTEM_MESSAGE = (
    "You are a Vietnamese product price estimator. "
    "Given a product description, predict its price in VND. "
    "Respond with only the number, no explanation."
)

OUTPUT_DIR = Path(__file__).parent


def item_to_messages(item: dict) -> dict:
    user_content = f"San pham nay gia bao nhieu (VND)?\n\n{item['full']}"
    assistant_content = str(round(item["price"]))
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_MESSAGE},
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": assistant_content},
        ]
    }


def prepare():
    for split in ["train", "val", "test"]:
        input_path = CURATED_DATA_DIR / f"{split}.json"
        output_path = OUTPUT_DIR / f"{split}.jsonl"

        with open(input_path, "r", encoding="utf-8") as f:
            items = json.load(f)

        with open(output_path, "w", encoding="utf-8") as f:
            for item in items:
                msg = item_to_messages(item)
                f.write(json.dumps(msg, ensure_ascii=False) + "\n")

        logger.info(f"{split}: {len(items)} examples -> {output_path}")


if __name__ == "__main__":
    prepare()
