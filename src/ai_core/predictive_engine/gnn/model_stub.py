from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class GNNDelayPredictor:
    """Model stub for a GNN-based predictor.

    This is a placeholder to keep API stable; returns empty dict or zeros.
    Replace with a real PyTorch/PyG implementation and weight loading.
    """
    model_path: str | None = None

    def predict_minutes(self, graph: Dict[str, Any], train_idx: Dict[str, int]) -> Dict[str, float]:
        # Trivial output matching the number of trains
        out: Dict[str, float] = {}
        for tid in train_idx.keys():
            out[tid] = 0.0
        return out
