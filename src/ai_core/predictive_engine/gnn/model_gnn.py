from __future__ import annotations
"""Prototype 'GNN' delay predictor.

Instead of a true graph neural network (which would require torch-geometric
installation) we implement a minimal MLP over the per-train feature matrix
produced by `graph_builder.build_hetero_graph`. The class maintains the same
public API expected by the rest of the system so we can later swap the body
with a hetero GNN without touching callers.

Checkpoint format (JSON + torch weights if available):
  ckpt = {
      'state_dict': <model weights>,
      'meta': { 'feature_names': [...], 'hidden': 64 }
  }

If `model_path` is None or load fails we fall back to randomly initialised
weights (still deterministic forward thanks to torch default seed unless the
caller seeds differently). Predictions are non-negative minutes.
"""
from dataclasses import dataclass
from typing import Dict, Any, List

try:  # Attempt light import of torch only
    import torch  # type: ignore
    from torch import nn  # type: ignore
except Exception:  # pragma: no cover
    torch = None  # type: ignore
    nn = None  # type: ignore


class _TrainFeatureMLP(nn.Module):  # type: ignore[misc]
    def __init__(self, in_dim: int, hidden: int = 64):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_dim, hidden),
            nn.ReLU(),
            nn.Linear(hidden, hidden),
            nn.ReLU(),
            nn.Linear(hidden, 1),
        )

    def forward(self, x):  # x: [N, F]
        return self.net(x).squeeze(-1)


@dataclass
class HetGNNDelayPredictor:
    model_path: str | None = None
    hidden: int = 64

    def __post_init__(self):
        self._available = torch is not None and nn is not None
        self._feature_names: List[str] | None = None
        self._model: Any | None = None
        if not self._available:
            return
        # Attempt lazy load of checkpoint
        if self.model_path:
            try:
                ckpt = torch.load(self.model_path, map_location="cpu")  # type: ignore
                meta = ckpt.get("meta", {}) if isinstance(ckpt, dict) else {}
                self._feature_names = list(meta.get("feature_names") or [])
                self.hidden = int(meta.get("hidden", self.hidden))
                # instantiate
                if "state_dict" in ckpt:
                    # We'll infer in_dim later when we first see a graph if absent
                    self._state_dict = ckpt["state_dict"]  # type: ignore[attr-defined]
            except Exception:
                pass

    def _ensure_model(self, in_dim: int):
        if self._model is None and self._available:
            self._model = _TrainFeatureMLP(in_dim, hidden=self.hidden)  # type: ignore
            # Load weights if shape matches
            state_dict = getattr(self, "_state_dict", None)
            if state_dict:
                try:
                    self._model.load_state_dict(state_dict, strict=False)
                except Exception:
                    pass
            self._model.eval()

    def predict_minutes(self, graph: Dict[str, Any], train_idx: Dict[str, int]) -> Dict[str, float]:
        if not self._available:
            raise RuntimeError("torch not available; install torch to use GNN path")
        feats = graph.get("x") or []
        if not feats:
            return {tid: 0.0 for tid in train_idx.keys()}
        in_dim = len(feats[0])
        self._ensure_model(in_dim)
        with torch.no_grad():  # type: ignore
            x = torch.tensor(feats, dtype=torch.float32)  # type: ignore
            y = self._model(x)  # type: ignore
            y = torch.clamp(y, min=0.0)
            vals = y.cpu().numpy().tolist()
        # Map back using ordering (train_idx maintained insertion order from builder)
        ordered_tids = list(train_idx.keys())
        return {ordered_tids[i]: float(vals[i]) for i in range(min(len(ordered_tids), len(vals)))}
