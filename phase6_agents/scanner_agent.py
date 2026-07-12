import os
import re
import sys
import json
from pathlib import Path
from typing import Optional, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from phase6_agents.agent import Agent
from phase6_agents.deals import ScrapedDeal, DealSelection, Deal
from shared.config import OLLAMA_BASE_URL, SCANNER_TOP_K, get_anthropic_client

SCANNER_OLLAMA_MODEL = os.getenv("SCANNER_OLLAMA_MODEL", "llama3.2")


class ScannerAgent(Agent):
    name = "Scanner Agent"
    color = Agent.CYAN

    SYSTEM_PROMPT = """You identify and summarize the 5 most detailed deals from a list, by selecting deals that have the most detailed, high quality description and the most clear price in VND.
    Respond strictly in JSON with no explanation, using this format:
    {"deals": [{"product_description": "...", "price": 15990000, "url": "..."}]}
    The price should be in VND. If the price isn't clear, do not include that deal.
    Focus on thorough product descriptions, not deal terms."""

    USER_PROMPT_PREFIX = """Respond with the 5 most promising deals from this list. Select those with the most detailed product descriptions and clear prices in VND.
    Rephrase descriptions to summarize the product itself, not the deal terms.

    Deals:

    """

    def __init__(self):
        self.log("Scanner Agent is initializing")

        client, provider, _ = get_anthropic_client()
        if client:
            self.anthropic_client = client
            self.model = os.getenv("SCANNER_MODEL", "claude-sonnet" if provider == "foundry" else "claude-sonnet-4-6")
            self.provider = provider
        else:
            self.anthropic_client = None
            self.model = f"ollama/{SCANNER_OLLAMA_MODEL}"
            self.provider = "ollama"

        self.log(f"Scanner Agent is ready (model: {self.model}, provider: {self.provider})")

    def fetch_deals(self, memory) -> List[ScrapedDeal]:
        self.log("Scanner Agent is fetching deals from Vietnamese sources")
        urls = [opp.deal.url for opp in memory]
        scraped = ScrapedDeal.fetch()
        result = [s for s in scraped if s.url not in urls]
        self.log(f"Scanner Agent received {len(result)} new deals")
        return result

    MAX_DEALS_FOUNDRY = 100
    MAX_DEALS_OLLAMA = 15
    MAX_RETRIES = 3

    def _call_foundry(self, user_prompt: str) -> str:
        import time
        for attempt in range(self.MAX_RETRIES):
            try:
                response = self.anthropic_client.messages.create(
                    model=self.model,
                    max_tokens=2048,
                    system=self.SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": user_prompt}],
                    timeout=60.0,
                )
                return response.content[0].text
            except Exception as e:
                self.log(f"Scanner attempt {attempt+1}/{self.MAX_RETRIES} failed: {e}")
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)
        return None

    def _call_ollama(self, user_prompt: str) -> str:
        from litellm import completion
        response = completion(
            model=f"ollama/{SCANNER_OLLAMA_MODEL}",
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            api_base=OLLAMA_BASE_URL,
        )
        return response.choices[0].message.content

    def _call_llm(self, user_prompt: str) -> str:
        if self.provider in ("foundry", "anthropic"):
            result = self._call_foundry(user_prompt)
            if result is not None:
                return result
            self.log(f"Foundry failed, falling back to Ollama ({SCANNER_OLLAMA_MODEL})")
            return self._call_ollama(user_prompt)
        else:
            return self._call_ollama(user_prompt)

    def _parse_json(self, content: str) -> Optional[DealSelection]:
        content = content.strip()
        if "<think>" in content:
            content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        # Fix common LLM JSON issues: trailing commas, truncated output
        content = re.sub(r",\s*}", "}", content)
        content = re.sub(r",\s*]", "]", content)
        # If JSON is truncated mid-object, try to close it
        if content.count("{") > content.count("}"):
            content = content.rsplit(",", 1)[0] + "]}"
        data = json.loads(content)
        if "deals" in data:
            data["deals"] = [
                d for d in data["deals"]
                if d.get("price") and d.get("product_description")
            ]
            for d in data["deals"]:
                if not d.get("url") or d["url"] == "...":
                    d["url"] = "https://websosanh.vn"
        result = DealSelection(**data)
        return result

    def scan(self, memory: list = []) -> Optional[DealSelection]:
        scraped = self.fetch_deals(memory)
        if not scraped:
            return None

        max_deals = self.MAX_DEALS_FOUNDRY if self.provider in ("foundry", "anthropic") else self.MAX_DEALS_OLLAMA
        if len(scraped) > max_deals:
            import random
            total = len(scraped)
            scraped = random.sample(scraped, max_deals)
            self.log(f"Sampled {max_deals} deals from {total} to fit LLM context")

        user_prompt = self.USER_PROMPT_PREFIX
        user_prompt += "\n\n".join(s.describe() for s in scraped)
        user_prompt += f"\n\nInclude exactly {SCANNER_TOP_K} deals, no more."

        self.log(f"Scanner Agent is calling {self.model} for deal selection")
        try:
            content = self._call_llm(user_prompt)
            result = self._parse_json(content)
            self.log(f"Scanner Agent selected {len(result.deals)} deals")
            return result
        except Exception as e:
            self.log(f"Scanner Agent parsing failed: {e}")
            if content:
                self.log(f"Raw LLM response (first 200 chars): {content[:200]}")
            return None
