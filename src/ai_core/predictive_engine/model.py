from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List

from .feature_engineering import TrainFeature


@dataclass
class BaselineDelayRegressor:
    """A trivial baseline regressor until GNN is implemented.

    Predicts delay minutes as a linear combination of a few features with
    hand-tuned weights. Replace later with a trained model.
    """
    w_priority: float = -0.2
    w_density: float = 1.5
    w_current: float = 1.0
    bias: float = 0.0

    def predict(self, feats: List[TrainFeature]) -> Dict[str, float]:
        out: Dict[str, float] = {}
        for tf in feats:
            f = tf.features
            pred = (
                self.bias
                + self.w_current * f.get("current_delay_minutes", 0.0)
                + self.w_density * f.get("traffic_density_in_section", 0.0)
                + self.w_priority * f.get("priority", 1.0)
            )
            out[tf.train_id] = max(0.0, float(pred))
        return out
