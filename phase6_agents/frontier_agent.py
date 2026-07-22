import os
import re
import sys
import requests
from pathlib import Path
from typing import List, Dict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from phase6_agents.agent import Agent
from shared.config import EMBEDDING_MODEL, OLLAMA_BASE_URL, RAG_SIMILAR_K, get_anthropic_client

FRONTIER_OLLAMA_MODEL = os.getenv("FRONTIER_OLLAMA_MODEL", "llama3.2")


class FrontierAgent(Agent):
    name = "Frontier Agent"
    color = Agent.BLUE

    def __init__(self, collection):
        self.log("Initializing Frontier Agent")
        self.collection = collection

        client, provider, _ = get_anthropic_client()
        if client:
            self.anthropic_client = client
            self.model = os.getenv("FRONTIER_MODEL", "claude-sonnet" if provider == "foundry" else "claude-sonnet-4-6")
            self.provider = provider
        else:
            self.anthropic_client = None
            openai_key = os.getenv("OPENAI_API_KEY", "")
            if openai_key and openai_key != "ollama" and not openai_key.startswith("sk-your"):
                self.model = os.getenv("FRONTIER_MODEL", "gpt-4.1-mini")
                self.provider = "openai"
            else:
                self.model = FRONTIER_OLLAMA_MODEL
                self.provider = "ollama"

        self.log(f"Frontier Agent is ready (model: {self.model}, provider: {self.provider})")

    def make_context(self, similars: List[str], prices: List[float]) -> str:
        message = "De tham khao, day la mot so san pham tuong tu voi gia cua chung:\n\n"
        for doc, price in zip(similars, prices):
            message += f"San pham tuong tu:\n{doc[:300]}\nGia: {price:,.0f} VND\n\n"
        return message

    def messages_for(self, description: str, similars: List[str], prices: List[float]) -> List[Dict[str, str]]:
        message = f"Estimate the price of this product in VND. Respond with only the number.\n\n{description}\n\n"
        message += self.make_context(similars, prices)
        return [{"role": "user", "content": message}]

    def _embed(self, text: str) -> list[float]:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/embed",
            json={"model": EMBEDDING_MODEL, "input": [text]},
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["embeddings"][0]

    def find_similars(self, description: str):
        self.log("Frontier Agent is searching ChromaDB for similar products")
        vector = self._embed(description)
        results = self.collection.query(
            query_embeddings=[vector],
            n_results=RAG_SIMILAR_K,
        )
        documents = results["documents"][0]
        prices = [m["price"] for m in results["metadatas"][0]]
        self.log(f"Frontier Agent found {len(documents)} similar products")
        return documents, prices

    def get_price(self, s) -> float:
        s = str(s).replace(",", "").replace(".", "").replace(" ", "")
        s = s.replace("VND", "").replace("₫", "").replace("đ", "")
        match = re.search(r"\d+", s)
        return float(match.group()) if match else 0.0

    def price(self, description: str) -> float:
        documents, prices = self.find_similars(description)
        self.log(f"Frontier Agent calling {self.model} with RAG context ({self.provider})")
        msgs = self.messages_for(description, documents, prices)
        system_prompt = "You are a price estimator. Output ONLY a single integer number in VND. No text, no explanation."

        if self.provider in ("foundry", "anthropic"):
            response = self.anthropic_client.messages.create(
                model=self.model,
                max_tokens=50,
                system=system_prompt,
                messages=msgs,
            )
            reply = response.content[0].text
        elif self.provider == "openai":
            from openai import OpenAI
            client = OpenAI()
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": system_prompt}] + msgs,
                seed=42,
            )
            reply = response.choices[0].message.content
        else:
            resp = requests.post(f"{OLLAMA_BASE_URL}/api/chat", json={
                "model": self.model,
                "messages": [{"role": "system", "content": system_prompt}] + msgs,
                "stream": False,
                "options": {"num_predict": 30},
            }, timeout=300)
            reply = resp.json().get("message", {}).get("content", "")

        result = self.get_price(reply)
        self.log(f"Frontier Agent completed - predicting {result:,.0f} VND")
        return result
