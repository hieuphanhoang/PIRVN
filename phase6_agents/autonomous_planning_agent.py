import os
import sys
import json
from pathlib import Path
from typing import Optional, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from phase6_agents.agent import Agent
from phase6_agents.deals import Deal, Opportunity
from phase6_agents.scanner_agent import ScannerAgent
from phase6_agents.ensemble_agent import EnsembleAgent
from shared.config import DEAL_THRESHOLD, get_anthropic_client


class AutonomousPlanningAgent(Agent):
    name = "Autonomous Planning Agent"
    color = Agent.GREEN

    def __init__(self, collection):
        self.log("Autonomous Planning Agent is initializing")
        self.scanner = ScannerAgent()
        self.ensemble = EnsembleAgent(collection)
        self.memory = None
        self.opportunity = None

        client, provider, _ = get_anthropic_client()
        if client:
            self.client = client
            self.model = os.getenv("FRONTIER_MODEL", "claude-sonnet" if provider == "foundry" else "claude-sonnet-4-6")
            self.provider = provider
        else:
            raise RuntimeError(
                "Autonomous Planning Agent requires Claude API (Foundry or Anthropic). "
                "Set ANTHROPIC_FOUNDRY_API_KEY or ANTHROPIC_API_KEY, and ensure USE_LOCAL_MODELS is not set."
            )

        self.log(f"Autonomous Planning Agent is ready (model: {self.model}, provider: {self.provider})")

    def scan_the_internet_for_bargains(self) -> str:
        self.log("Autonomous Planning Agent is calling scanner")
        results = self.scanner.scan(memory=self.memory)
        return results.model_dump_json() if results else "No deals found"

    def estimate_true_value(self, description: str) -> str:
        self.log("Autonomous Planning Agent is estimating value via Ensemble")
        estimate = self.ensemble.price(description)
        return f"The estimated true value of this product is {estimate:,.0f} VND"

    def report_deal(self, description: str, deal_price: float,
                    estimated_true_value: float, url: str) -> str:
        if self.opportunity:
            self.log("Autonomous Planning Agent: ignoring duplicate report")
        else:
            self.log(f"Autonomous Planning Agent found deal: {description[:60]}...")
            deal = Deal(product_description=description, price=deal_price, url=url)
            discount = estimated_true_value - deal_price
            self.opportunity = Opportunity(deal=deal, estimate=estimated_true_value, discount=discount)
        return "Deal reported successfully"

    tools = [
        {
            "name": "scan_the_internet_for_bargains",
            "description": "Returns top bargains scraped from Vietnamese e-commerce sites with prices in VND",
            "input_schema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "name": "estimate_true_value",
            "description": "Given a product description, estimate how much it is actually worth in VND",
            "input_schema": {
                "type": "object",
                "properties": {
                    "description": {"type": "string", "description": "The product description to estimate"},
                },
                "required": ["description"],
            },
        },
        {
            "name": "report_deal",
            "description": "Report the single most compelling deal where the price is much lower than the estimated true value. Only call once with the best deal.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "description": {"type": "string", "description": "The product description"},
                    "deal_price": {"type": "number", "description": "The deal price in VND"},
                    "estimated_true_value": {"type": "number", "description": "The estimated value in VND"},
                    "url": {"type": "string", "description": "The URL of the deal"},
                },
                "required": ["description", "deal_price", "estimated_true_value", "url"],
            },
        },
    ]

    tool_handlers = {
        "scan_the_internet_for_bargains": lambda self, **_: self.scan_the_internet_for_bargains(),
        "estimate_true_value": lambda self, **kw: self.estimate_true_value(kw["description"]),
        "report_deal": lambda self, **kw: self.report_deal(
            kw["description"], kw["deal_price"], kw["estimated_true_value"], kw["url"]
        ),
    }

    SYSTEM = (
        "You find great deals on Vietnamese e-commerce sites using your tools. "
        "First scan for deals, then estimate the true value of each, "
        "then report the single best deal where the discount is largest."
    )
    USER = (
        "Scan the internet for bargain deals on Vietnamese sites. "
        "For each deal, estimate its true value in VND. "
        "Then pick the single most compelling deal where the price is much lower "
        "than the estimated true value, and report it. Then reply OK."
    )

    def handle_tool_use(self, response):
        results = []
        for block in response.content:
            if block.type == "tool_use":
                handler = self.tool_handlers.get(block.name)
                if handler:
                    result = handler(self, **block.input)
                else:
                    result = f"Unknown tool: {block.name}"
                self.log(f"Tool {block.name} -> {result[:100]}...")
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })
        return results

    def plan(self, memory: list = []) -> Optional[Opportunity]:
        self.log("Autonomous Planning Agent is kicking off a run")
        self.memory = memory
        self.opportunity = None

        messages = [{"role": "user", "content": self.USER}]

        max_iterations = 15
        for i in range(max_iterations):
            self.log(f"Autonomous Planning Agent iteration {i + 1}")
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=self.SYSTEM,
                tools=self.tools,
                messages=messages,
            )

            if response.stop_reason == "end_turn":
                reply = next((b.text for b in response.content if b.type == "text"), "")
                self.log(f"Autonomous Planning Agent completed: {reply[:100]}")
                break

            if response.stop_reason == "tool_use":
                tool_results = self.handle_tool_use(response)
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})
            else:
                self.log(f"Unexpected stop_reason: {response.stop_reason}")
                break

        return self.opportunity
