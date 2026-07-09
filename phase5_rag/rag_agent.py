"""
RAG-augmented pricing agent. Can be used standalone for testing or imported by phase6 agents.
Uses qwen3-embedding via Ollama for query encoding.
"""
import sys
import requests
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.config import VECTORSTORE_DIR, EMBEDDING_MODEL, OLLAMA_BASE_URL, RAG_SIMILAR_K


def embed_query(text: str) -> list[float]:
    resp = requests.post(
        f"{OLLAMA_BASE_URL}/api/embed",
        json={"model": EMBEDDING_MODEL, "input": [text]},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["embeddings"][0]


class RAGPricer:
    def __init__(self, collection=None):
        import chromadb

        if collection:
            self.collection = collection
        else:
            client = chromadb.PersistentClient(path=str(VECTORSTORE_DIR))
            self.collection = client.get_or_create_collection("vn_products")

    def find_similars(self, description: str, n_results: int = RAG_SIMILAR_K):
        vector = embed_query(description)
        results = self.collection.query(
            query_embeddings=[vector],
            n_results=n_results,
        )
        documents = results["documents"][0]
        prices = [m["price"] for m in results["metadatas"][0]]
        return documents, prices

    def make_context(self, similars: List[str], prices: List[float]) -> str:
        message = "De tham khao, day la mot so san pham tuong tu:\n\n"
        for doc, price in zip(similars, prices):
            message += f"San pham tuong tu:\n{doc[:300]}\nGia: {price:,.0f} VND\n\n"
        return message


if __name__ == "__main__":
    rag = RAGPricer()
    test_desc = "Laptop ASUS VivoBook 15, man hinh 15.6 inch Full HD, Intel Core i5, RAM 16GB, SSD 512GB"
    docs, prices = rag.find_similars(test_desc)
    print(f"Found {len(docs)} similar products:")
    for doc, price in zip(docs, prices):
        print(f"  {price:>12,.0f} VND - {doc[:80]}...")
