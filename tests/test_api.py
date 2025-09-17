import httpx
import pytest
from src.api import app
from httpx import ASGITransport


@pytest.mark.asyncio
async def test_demo_endpoint():
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        r = await client.get("/demo")
        assert r.status_code == 200
        data = r.json()
        assert "kpis" in data and "schedule" in data
        assert isinstance(data["schedule"], list)
        assert len(data["schedule"]) >= 1

@pytest.mark.asyncio
async def test_schedule_endpoint_basic():
    transport = ASGITransport(app=app)
    payload = {
        "sections": [
            {"id": "S1", "headway_seconds": 120, "traverse_seconds": 100}
        ],
        "trains": [
            {"id": "A", "priority": 2, "planned_departure": 0, "route_sections": ["S1"]},
            {"id": "B", "priority": 1, "planned_departure": 0, "route_sections": ["S1"]}
        ]
    }
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        r = await client.post("/schedule", json=payload)
        assert r.status_code == 200
        data = r.json()
        items = data["schedule"]
        # Ensure non-overlap
        items = sorted(items, key=lambda x: x["entry"])
        for a, b in zip(items, items[1:]):
            assert a["exit"] <= b["entry"]
