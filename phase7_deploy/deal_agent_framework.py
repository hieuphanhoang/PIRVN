import os
import sys
import json
import logging
from typing import List
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
import chromadb
import numpy as np

from shared.config import VECTORSTORE_DIR, CATEGORIES, CATEGORY_COLORS
from phase6_agents.planning_agent import PlanningAgent
from phase6_agents.deals import Opportunity

load_dotenv(override=True)

BG_BLUE = "\033[44m"
WHITE = "\033[37m"
RESET = "\033[0m"


def init_logging():
    root = logging.getLogger()
    if root.handlers:
        return
    root.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "[%(asctime)s] [PIRVN] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    root.addHandler(handler)


class DealAgentFramework:
    DB = str(VECTORSTORE_DIR)
    MEMORY_FILENAME = str(Path(__file__).parent / "memory.json")

    def __init__(self):
        init_logging()
        client = chromadb.PersistentClient(path=self.DB)
        self.memory = self.read_memory()
        self.collection = client.get_or_create_collection("vn_products")
        self.planner = None

    def init_agents_as_needed(self):
        if not self.planner:
            self.log("Initializing PIRVN Agent Framework")
            self.planner = PlanningAgent(self.collection)
            self.log("Agent Framework is ready")

    def read_memory(self) -> List[Opportunity]:
        if os.path.exists(self.MEMORY_FILENAME):
            with open(self.MEMORY_FILENAME, "r", encoding="utf-8") as f:
                data = json.load(f)
            return [Opportunity(**item) for item in data]
        return []

    def write_memory(self) -> None:
        data = [opp.model_dump() for opp in self.memory]
        with open(self.MEMORY_FILENAME, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @classmethod
    def reset_memory(cls) -> None:
        path = str(Path(__file__).parent / "memory.json")
        data = []
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        truncated = data[:2]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(truncated, f, ensure_ascii=False, indent=2)

    def log(self, message: str):
        text = BG_BLUE + WHITE + "[Agent Framework] " + message + RESET
        logging.info(text)

    def run(self) -> List[Opportunity]:
        self.init_agents_as_needed()
        logging.info("Kicking off Planning Agent (daily run)")
        results = self.planner.plan(memory=self.memory)
        logging.info(f"Planning Agent returned {len(results)} deals")
        if results:
            self.memory.extend(results)
            self.write_memory()
        return self.memory

    @classmethod
    def get_plot_data(cls, max_datapoints=800):
        from sklearn.manifold import TSNE

        client = chromadb.PersistentClient(path=cls.DB)
        collection = client.get_or_create_collection("vn_products")
        result = collection.get(
            include=["embeddings", "documents", "metadatas"],
            limit=max_datapoints,
        )
        vectors = np.array(result["embeddings"])
        documents = result["documents"]
        categories = [m.get("category", "Phu_kien") for m in result["metadatas"]]

        colors = []
        for cat in categories:
            if cat in CATEGORIES:
                colors.append(CATEGORY_COLORS[CATEGORIES.index(cat)])
            else:
                colors.append("gray")

        tsne = TSNE(n_components=3, random_state=42, n_jobs=-1)
        reduced = tsne.fit_transform(vectors)
        return documents, reduced, colors


if __name__ == "__main__":
    DealAgentFramework().run()
