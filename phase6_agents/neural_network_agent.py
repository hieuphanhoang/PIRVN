from phase6_agents.agent import Agent
from phase6_agents.deep_neural_network import DeepNeuralNetworkInference


class NeuralNetworkAgent(Agent):
    name = "Neural Network Agent"
    color = Agent.MAGENTA

    def __init__(self):
        self.log("Neural Network Agent is initializing")
        self.neural_network = DeepNeuralNetworkInference()
        self.neural_network.setup()
        self.neural_network.load()
        self.log("Neural Network Agent is ready")

    def price(self, description: str) -> float:
        self.log("Neural Network Agent is predicting")
        result = self.neural_network.inference(description)
        self.log(f"Neural Network Agent completed - predicting {result:,.0f} VND")
        return result
