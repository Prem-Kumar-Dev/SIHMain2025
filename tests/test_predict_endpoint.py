import json
from httpx import AsyncClient
import pytest

from src.api import app


@pytest.mark.asyncio
async def test_predict_smoke():
    payload = {
        "sections": [
            {"id": "S1", "headway_seconds": 120, "traverse_seconds": 100},
            {"id": "S2", "headway_seconds": 120, "traverse_seconds": 120},
        ],
        "trains": [
            {
                "id": "A",
                "priority": 1,
                "planned_departure": 0,
                "route_sections": ["S1", "S2"],
                "current_delay_minutes": 2,
            },
            {
                "id": "B",
                "priority": 2,
                "planned_departure": 30,
                "route_sections": ["S1"],
                "current_delay_minutes": 0,
            },
        ],
    }
    async with AsyncClient(app=app, base_url="http://test") as ac:
        r = await ac.post("/predict", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert "predicted_delay_minutes" in data
        assert set(data["predicted_delay_minutes"].keys()) == {"A", "B"}
        assert all(v >= 0 for v in data["predicted_delay_minutes"].values())
        assert "predicted_conflicts" in data
        # With S1 shared and close planned departures plus predictions, conflicts likely >= 0
        assert isinstance(data["predicted_conflicts"], list)
