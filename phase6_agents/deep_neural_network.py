import json
import numpy as np
import torch
import torch.nn as nn
from sklearn.feature_extraction.text import HashingVectorizer
import logging
from pathlib import Path

MODELS_DIR = Path(__file__).resolve().parent.parent / "phase3_baselines" / "models"


class ResidualBlock(nn.Module):
    def __init__(self, hidden_size, dropout_prob):
        super().__init__()
        self.block = nn.Sequential(
            nn.Linear(hidden_size, hidden_size),
            nn.LayerNorm(hidden_size),
            nn.ReLU(),
            nn.Dropout(dropout_prob),
            nn.Linear(hidden_size, hidden_size),
            nn.LayerNorm(hidden_size),
        )
        self.relu = nn.ReLU()

    def forward(self, x):
        return self.relu(self.block(x) + x)


class DeepNeuralNetwork(nn.Module):
    def __init__(self, input_size, num_layers=10, hidden_size=4096, dropout_prob=0.2):
        super().__init__()
        self.input_layer = nn.Sequential(
            nn.Linear(input_size, hidden_size),
            nn.LayerNorm(hidden_size),
            nn.ReLU(),
            nn.Dropout(dropout_prob),
        )
        self.residual_blocks = nn.ModuleList(
            [ResidualBlock(hidden_size, dropout_prob) for _ in range(num_layers - 2)]
        )
        self.output_layer = nn.Linear(hidden_size, 1)

    def forward(self, x):
        x = self.input_layer(x)
        for block in self.residual_blocks:
            x = block(x)
        return self.output_layer(x)


class DeepNeuralNetworkInference:
    def __init__(self):
        self.vectorizer = None
        self.model = None
        self.device = None
        self.y_mean = 0.0
        self.y_std = 1.0

        np.random.seed(42)
        torch.manual_seed(42)

    def setup(self):
        params = self._load_params()
        n_features = params.get("n_features", 3000)
        hidden_size = params.get("hidden_size", 512)
        num_layers = params.get("num_layers", 5)
        dropout_prob = params.get("dropout_prob", 0.4)
        self.vectorizer = HashingVectorizer(n_features=n_features, stop_words=None, binary=True)
        self.model = DeepNeuralNetwork(n_features, num_layers=num_layers, hidden_size=hidden_size, dropout_prob=dropout_prob)

        if torch.cuda.is_available():
            self.device = torch.device("cuda")
        elif torch.backends.mps.is_available():
            self.device = torch.device("mps")
        else:
            self.device = torch.device("cpu")

        logging.info(f"Neural Network using {self.device}")
        self.model.to(self.device)

    def _load_params(self) -> dict:
        params_path = str(MODELS_DIR / "dnn_params.json")
        try:
            with open(params_path) as f:
                return json.load(f)
        except FileNotFoundError:
            logging.warning("dnn_params.json not found, using defaults")
            return {}

    def load(self, path=None):
        path = path or str(MODELS_DIR / "deep_neural_network.pth")
        self.model.load_state_dict(torch.load(path, map_location=self.device))
        self.model.to(self.device)

        params = self._load_params()
        self.y_mean = params.get("Y_MEAN", 0.0)
        self.y_std = params.get("Y_STD", 1.0)

    def inference(self, text):
        self.model.eval()
        with torch.no_grad():
            vector = self.vectorizer.transform([text])
            vector = torch.FloatTensor(vector.toarray()).to(self.device)
            pred = self.model(vector)[0]
            result = torch.exp(pred * self.y_std + self.y_mean) - 1
            result = result.item()
        return max(0, result)
