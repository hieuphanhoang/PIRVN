 import sys
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from phase6_agents.agent import Agent
from phase6_agents.deals import Deal, Opportunity
from phase6_agents.scanner_agent import ScannerAgent
from phase6_agents.ensemble_agent import EnsembleAgent
from shared.config import DEAL_THRESHOLD


class PlanningAgent(Agent):
    name = "Planning Agent"
    color = Agent.GREEN

    def __init__(self, collection):
        self.log("Planning Agent is initializing")
        self.scanner = ScannerAgent()
        self.ensemble = EnsembleAgent(collection)
        self.log("Planning Agent is ready")

    def run(self, deal: Deal) -> Opportunity:
        self.log("Planning Agent is pricing a potential deal")
        estimate = self.ensemble.price(deal.product_description)
        discount = estimate - deal.price
        self.log(f"Planning Agent: price={deal.price:,.0f}, estimate={estimate:,.0f}, discount={discount:,.0f} VND")
        return Opportunity(deal=deal, estimate=estimate, discount=discount)

    def plan(self, memory: list = []) -> List[Opportunity]:
        self.log("Planning Agent is kicking off a daily run")
        selection = self.scanner.scan(memory=memory)
        if not selection:
            self.log("Planning Agent: no deals found")
            return []
        opportunities = [self.run(deal) for deal in selection.deals[:5]]
        good_deals = [opp for opp in opportunities if opp.discount > DEAL_THRESHOLD]
        good_deals.sort(key=lambda opp: opp.discount, reverse=True)
        self.log(f"Planning Agent: {len(good_deals)} deals above threshold out of {len(opportunities)}")
        # Results displayed in Gradio UI — no Telegram notification
        self.log("Planning Agent has completed a daily run")
        return good_deals
