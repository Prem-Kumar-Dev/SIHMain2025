import pytest
from httpx import AsyncClient

from src.api import app


@pytest.mark.asyncio
@pytest.mark.parametrize("model", ["baseline", "mlp", "gnn", "auto", None])
async def test_predict_accepts_model_selector(model):
    payload = {
        "sections": [
            {"id": "S1", "headway_seconds": 120, "traverse_seconds": 100},
            {"id": "S2", "headway_seconds": 120, "traverse_seconds": 120},
        ],
        "trains": [
            {"id": "A", "priority": 1, "planned_departure": 0, "route_sections": ["S1", "S2"]},
            {"id": "B", "priority": 2, "planned_departure": 30, "route_sections": ["S1"]},
        ],
    }
    params = {"model": model} if model is not None else None
    async with AsyncClient(app=app, base_url="http://test") as ac:
        r = await ac.post("/predict", json=payload, params=params)
        assert r.status_code == 200
        data = r.json()
        assert "predicted_delay_minutes" in data
        assert "predicted_conflicts" in data
        assert isinstance(data["predicted_conflicts"], list)
        # model_used should be present for visibility
        assert "model_used" in data