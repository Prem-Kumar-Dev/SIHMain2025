from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Optional
import httpx

from .config import PredictiveConfig


@dataclass
class RailRadarClient:
    base_url: str
    api_key: Optional[str]

    @classmethod
    def from_config(cls, cfg: PredictiveConfig) -> "RailRadarClient":
        return cls(base_url=cfg.railradar_base, api_key=cfg.railradar_key)

    def _headers(self) -> Dict[str, str]:
        h = {"Accept": "application/json"}
        if self.api_key:
            h["x-api-key"] = self.api_key
        return h

    async def get_live_map(self) -> Dict[str, Any]:
        # GET /trains/live-map
        url = f"{self.base_url}/trains/live-map"
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(url, headers=self._headers())
            r.raise_for_status()
            return r.json()

    async def get_average_delay(self, train_number: str) -> Dict[str, Any]:
        # GET /trains/{trainNumber}/average-delay
        url = f"{self.base_url}/trains/{train_number}/average-delay"
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(url, headers=self._headers())
            r.raise_for_status()
            return r.json()

    async def get_schedule(self, train_number: str) -> Dict[str, Any]:
        # GET /trains/{trainNumber}/schedule
        url = f"{self.base_url}/trains/{train_number}/schedule"
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(url, headers=self._headers())
            r.raise_for_status()
            return r.json()
