import os
import sys
import re
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from phase6_agents.agent import Agent
from shared.config import SPECIALIST_HF_SPACE

SPECIALIST_OLLAMA_MODEL = os.getenv("SPECIALIST_OLLAMA_MODEL", "pirvn-pricer")


class SpecialistAgent(Agent):
    name = "Specialist Agent"
    color = Agent.RED

    def __init__(self):
        self.log("Specialist Agent is initializing")
        self.hf_space_url = SPECIALIST_HF_SPACE
        if not self.hf_space_url:
            self.log(f"SPECIALIST_HF_SPACE not set - using Ollama model '{SPECIALIST_OLLAMA_MODEL}'")
            self.use_ollama = True
        else:
            self.use_ollama = False
        self.log("Specialist Agent is ready")

    def price_via_hf(self, description: str) -> float:
        self.log("Specialist Agent calling HuggingFace Spaces")
        try:
            resp = requests.post(
                f"{self.hf_space_url}/api/predict",
                json={"data": [description]},
                timeout=120,
            )
            resp.raise_for_status()
            result = resp.json()["data"][0]
            return float(result)
        except Exception as e:
            self.log(f"HF Spaces call failed: {e}")
            return 0.0

    def price_via_ollama(self, description: str) -> float:
        from litellm import completion
        from shared.config import OLLAMA_BASE_URL

        self.log(f"Specialist Agent calling Ollama model '{SPECIALIST_OLLAMA_MODEL}'")
        response = completion(
            model=f"ollama/{SPECIALIST_OLLAMA_MODEL}",
            messages=[
                {"role": "system", "content": "You are a Vietnamese product price estimator. Respond with only the price number in VND."},
                {"role": "user", "content": f"San pham nay gia bao nhieu (VND)?\n\n{description}"},
            ],
            api_base=OLLAMA_BASE_URL,
        )
        reply = response.choices[0].message.content
        reply = reply.replace(",", "").replace(".", "").replace(" ", "")
        match = re.search(r"\d+", reply)
        result = float(match.group()) if match else 0.0
        self.log(f"Specialist Agent completed - predicting {result:,.0f} VND")
        return result

    def price(self, description: str) -> float:
        if self.use_ollama:
            return self.price_via_ollama(description)
        return self.price_via_hf(description)
