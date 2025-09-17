import httpx
import pytest
from src.api import app
from httpx import ASGITransport


@pytest.mark.asyncio
async def test_schedule_returns_lateness_map():
    transport = ASGITransport(app=app)
    payload = {
        "sections": [
            {"id": "S1", "headway_seconds": 0, "traverse_seconds": 10}
        ],
        "trains": [
            {"id": "A", "priority": 1, "planned_departure": 0, "route_sections": ["S1"], "due_time": 5},
            {"id": "B", "priority": 1, "planned_departure": 0, "route_sections": ["S1"], "due_time": 100}
        ]
    }
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        r = await client.post("/schedule", json=payload, params={"solver": "milp"})
        assert r.status_code == 200
        data = r.json()
        assert "lateness_by_train" in data
        # Train A has tighter due_time; expect non-negative integer value present
        la = data["lateness_by_train"].get("A")
        assert la is not None and isinstance(la, int) and la >= 0
