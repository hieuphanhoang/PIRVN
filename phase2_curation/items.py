from pydantic import BaseModel
from datasets import Dataset, DatasetDict, load_dataset
from typing import Optional, Self

PREFIX = "Price is "
QUESTION = "San pham nay gia bao nhieu (VND)?"


class Item(BaseModel):
    title: str
    title_en: str = ""
    category: str
    price: float
    source: str = ""
    brand: str = ""
    full: str = ""
    weight: float = 0.0
    specs: dict = {}
    prompt: str = ""
    id: int = 0

    def make_prompt(self, text: str):
        self.prompt = f"{QUESTION}\n\n{text}\n\n{PREFIX}{round(self.price)}"

    def test_prompt(self) -> str:
        return self.prompt.split(PREFIX)[0] + PREFIX

    def __repr__(self) -> str:
        return f"<{self.title} = {self.price:,.0f} VND>"

    @staticmethod
    def _to_hf_row(item):
        d = item.model_dump()
        import json
        d["specs"] = json.dumps(d["specs"], ensure_ascii=False)
        return d

    @staticmethod
    def push_to_hub(dataset_name: str, train: list, val: list, test: list):
        DatasetDict({
            "train": Dataset.from_list([Item._to_hf_row(item) for item in train]),
            "validation": Dataset.from_list([Item._to_hf_row(item) for item in val]),
            "test": Dataset.from_list([Item._to_hf_row(item) for item in test]),
        }).push_to_hub(dataset_name)

    @classmethod
    def from_hub(cls, dataset_name: str) -> tuple[list, list, list]:
        import json
        ds = load_dataset(dataset_name)
        def _parse(row):
            d = dict(row)
            if isinstance(d.get("specs"), str):
                d["specs"] = json.loads(d["specs"])
            return cls.model_validate(d)
        return (
            [_parse(row) for row in ds["train"]],
            [_parse(row) for row in ds["validation"]],
            [_parse(row) for row in ds["test"]],
        )
