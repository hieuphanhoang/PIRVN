from phase6_agents.agent import Agent
from phase6_agents.specialist_agent import SpecialistAgent
from phase6_agents.frontier_agent import FrontierAgent
from phase6_agents.neural_network_agent import NeuralNetworkAgent
from phase6_agents.preprocessor import Preprocessor
from shared.config import USE_LOCAL_MODELS


class EnsembleAgent(Agent):
    name = "Ensemble Agent"
    color = Agent.YELLOW

    if USE_LOCAL_MODELS:
        WEIGHT_FRONTIER = 0.0
        WEIGHT_SPECIALIST = 0.7
        WEIGHT_NEURAL = 0.3
    else:
        WEIGHT_FRONTIER = 0.8
        WEIGHT_SPECIALIST = 0.1
        WEIGHT_NEURAL = 0.1

    def __init__(self, collection):
        self.log("Initializing Ensemble Agent")
        self.specialist = SpecialistAgent()
        self.frontier = FrontierAgent(collection) if self.WEIGHT_FRONTIER > 0 else None
        self.neural_network = NeuralNetworkAgent()
        self.preprocessor = Preprocessor()
        if self.frontier is None:
            self.log("Ensemble Agent is ready (local mode — Frontier skipped)")
        else:
            self.log("Ensemble Agent is ready")

    def price(self, description: str) -> float:
        self.log("Running Ensemble Agent - preprocessing text")
        rewrite = self.preprocessor.preprocess(description)
        self.log(f"Pre-processed text using {self.preprocessor.model_name}")
        specialist = self.specialist.price(rewrite)
        frontier = self.frontier.price(rewrite) if self.frontier else 0.0
        neural_network = self.neural_network.price(rewrite)
        combined = (
            frontier * self.WEIGHT_FRONTIER
            + specialist * self.WEIGHT_SPECIALIST
            + neural_network * self.WEIGHT_NEURAL
        )
        self.log(f"Ensemble Agent: Frontier={frontier:,.0f}, Specialist={specialist:,.0f}, NN={neural_network:,.0f} -> Combined={combined:,.0f} VND")
        return combined
