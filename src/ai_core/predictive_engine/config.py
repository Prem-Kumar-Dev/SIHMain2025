from __future__ import annotations
import os
from dataclasses import dataclass
from dotenv import load_dotenv

# Load .env early (no error if missing)
load_dotenv()


@dataclass(frozen=True)
class PredictiveConfig:
    railradar_base: str = os.getenv("RAILRADAR_API_BASE", "https://railradar.in/api/v1")
    railradar_key: str | None = os.getenv("RAILRADAR_API_KEY")
    # Future: weather provider
    weather_key: str | None = os.getenv("WEATHER_API_KEY")
    # Optional GNN model path
    model_path: str | None = os.getenv("PREDICTIVE_MODEL_PATH")
    # Model selection: 'auto' | 'baseline' | 'mlp' | 'gnn'
    model_kind: str = os.getenv("PREDICTIVE_MODEL_KIND", "auto").lower()

    @property
    def is_live_enabled(self) -> bool:
        return bool(self.railradar_key)
