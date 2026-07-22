import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.config import OLLAMA_BASE_URL, get_anthropic_client

PREPROCESSOR_OLLAMA_MODEL = os.getenv("PREPROCESSOR_MODEL", "llama3.2")

SYSTEM_PROMPT = """Tao mo ta ngan gon ve san pham. Chi tra loi theo dinh dang sau. Khong bao gom ma san pham.
Title: Tieu de ngan gon chinh xac
Category: Vi du Dien tu, Laptop, Dien thoai
Brand: Ten thuong hieu
Description: 1 cau mo ta san pham
Details: 1 cau ve tinh nang noi bat"""


class Preprocessor:
    def __init__(self):
        client, provider, _ = get_anthropic_client()
        if client:
            self.anthropic_client = client
            self.model_name = os.getenv("PREPROCESSOR_MODEL", "claude-sonnet" if provider == "foundry" else "claude-sonnet-4-6")
            self.provider = provider
        else:
            self.anthropic_client = None
            self.model_name = f"ollama/{PREPROCESSOR_OLLAMA_MODEL}"
            self.provider = "ollama"
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    def preprocess(self, text: str) -> str:
        if self.provider in ("foundry", "anthropic"):
            response = self.anthropic_client.messages.create(
                model=self.model_name,
                max_tokens=500,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": text}],
            )
            self.total_input_tokens += response.usage.input_tokens
            self.total_output_tokens += response.usage.output_tokens
            return response.content[0].text
        else:
            from litellm import completion
            response = completion(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ],
                api_base=OLLAMA_BASE_URL,
            )
            self.total_input_tokens += response.usage.prompt_tokens
            self.total_output_tokens += response.usage.completion_tokens
            return response.choices[0].message.content
