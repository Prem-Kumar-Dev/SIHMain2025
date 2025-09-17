import pytest
from httpx import AsyncClient
from src.api import app


@pytest.mark.asyncio
async def test_resolve_smoke():
    state = {
        "sections": [
            {"id": "S1", "headway_seconds": 120, "traverse_seconds": 100},
            {"id": "S2", "headway_seconds": 120, "traverse_seconds": 120},
        ],
        "trains": [
            {"id": "A", "priority": 1, "planned_departure": 0, "route_sections": ["S1", "S2"], "due_time": 300},
            {"id": "B", "priority": 2, "planned_departure": 30, "route_sections": ["S1"], "due_time": 200},
        ],
    }
    body = {
        "state": state,
        "predicted_conflicts": [{"section_id": "S1", "trains": ["A", "B"]}],
    }
    async with AsyncClient(app=app, base_url="http://test") as ac:
        r = await ac.post("/resolve", json=body)
        assert r.status_code == 200
        data = r.json()
        assert "kpis" in data and "schedule" in data
        assert isinstance(data["schedule"], list)
