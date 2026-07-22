"""
Build ChromaDB vector store from curated product data.
Uses qwen3-embedding via Ollama for Vietnamese product embeddings.

    cd PIRVN && uv run phase5_rag/build_vectorstore.py
"""
import sys
import json
import logging
import requests
from pathlib import Path
from itertools import islice

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.config import CURATED_DATA_DIR, VECTORSTORE_DIR, EMBEDDING_MODEL, OLLAMA_BASE_URL

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("vectorstore")

BATCH_SIZE = 10


def batched(iterable, n):
    it = iter(iterable)
    while True:
        batch = list(islice(it, n))
        if not batch:
            return
        yield batch


def embed_texts(texts: list[str]) -> list[list[float]]:
    resp = requests.post(
        f"{OLLAMA_BASE_URL}/api/embed",
        json={"model": EMBEDDING_MODEL, "input": texts},
        timeout=300,
    )
    resp.raise_for_status()
    return resp.json()["embeddings"]


def build():
    import chromadb

    db_path = str(VECTORSTORE_DIR)
    logger.info(f"Creating ChromaDB at {db_path}")
    client = chromadb.PersistentClient(path=db_path)
    collection = client.get_or_create_collection("vn_products")

    existing = collection.count()
    if existing > 0:
        logger.info(f"Collection already has {existing} items. Clearing...")
        client.delete_collection("vn_products")
        collection = client.create_collection("vn_products")

    train_path = CURATED_DATA_DIR / "train.json"
    logger.info(f"Loading training data from {train_path}")
    with open(train_path, "r", encoding="utf-8") as f:
        items = json.load(f)
    logger.info(f"Loaded {len(items)} items")
    logger.info(f"Embedding with {EMBEDDING_MODEL} via Ollama (batch_size={BATCH_SIZE})")

    total_added = 0
    for batch in batched(items, BATCH_SIZE):
        texts = [item["full"][:500] for item in batch]
        ids = [str(item.get("id", i + total_added)) for i, item in enumerate(batch)]
        metadatas = [
            {
                "price": item["price"],
                "category": item.get("category", ""),
                "source": item.get("source", ""),
                "brand": item.get("brand", ""),
                "title": item.get("title", "")[:200],
            }
            for item in batch
        ]

        embeddings = embed_texts(texts)
        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )
        total_added += len(batch)
        logger.info(f"  Added {total_added}/{len(items)} items...")

    logger.info(f"Done. Total items in vectorstore: {collection.count()}")


if __name__ == "__main__":
    build()
