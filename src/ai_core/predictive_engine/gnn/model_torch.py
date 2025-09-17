from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Any

try:
    import torch
    import torch.nn as nn
except Exception:  # pragma: no cover - torch may be optional in some envs
    torch = None
    nn = None


class DelayMLP(nn.Module):  # type: ignore[misc]
    def __init__(self, in_dim: int, hidden: int = 64):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_dim, hidden),
            nn.ReLU(),
            nn.Linear(hidden, hidden),
            nn.ReLU(),
            nn.Linear(hidden, 1),
        )

    def forward(self, x):  # x: [N, in_dim]
        return self.net(x).squeeze(-1)  # [N]


@dataclass
class TorchModelState:
    feature_order: List[str]
    feature_mean: List[float]
    feature_std: List[float]
    hidden: int


class TorchDelayPredictor:
    """Feature-based Torch MLP predictor producing delay minutes per train.

    Expects a checkpoint saved by the companion trainer with keys:
      - 'state_dict': model weights
      - 'meta': { feature_order, feature_mean, feature_std, hidden }
    """

    def __init__(self, model_path: str):
        if torch is None:
            raise RuntimeError("torch not available")
        ckpt = torch.load(model_path, map_location="cpu")
        meta = ckpt.get("meta") or {}
        self.state = TorchModelState(
            feature_order=list(meta.get("feature_order") or []),
            feature_mean=list(meta.get("feature_mean") or []),
            feature_std=list(meta.get("feature_std") or []),
            hidden=int(meta.get("hidden") or 64),
        )
        in_dim = len(self.state.feature_order)
        self.model = DelayMLP(in_dim=in_dim, hidden=self.state.hidden)
        self.model.load_state_dict(ckpt.get("state_dict", {}))
        self.model.eval()

    def _vectorize(self, feature_map: Dict[str, float]) -> List[float]:
        vec = []
        for i, k in enumerate(self.state.feature_order):
            v = float(feature_map.get(k, 0.0))
            # standardize
            mu = self.state.feature_mean[i] if i < len(self.state.feature_mean) else 0.0
            sd = self.state.feature_std[i] if i < len(self.state.feature_std) and self.state.feature_std[i] > 1e-6 else 1.0
            vec.append((v - mu) / sd)
        return vec

    def predict_minutes(self, features: List[Any]) -> Dict[str, float]:
        """features: list of TrainFeature objects from feature_engineering.build_features_from_state"""
        if not features:
            return {}
        X = [self._vectorize(tf.features) for tf in features]
        with torch.no_grad():
            x = torch.tensor(X, dtype=torch.float32)
            y = self.model(x)  # minutes (as trained)
            y = torch.clamp(y, min=0.0)
            vals = y.cpu().numpy().tolist()
        return {features[i].train_id: float(vals[i]) for i in range(len(features))}
