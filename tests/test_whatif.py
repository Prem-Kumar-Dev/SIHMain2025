import pytest
import httpx
from httpx import ASGITransport
from src.api import app

@pytest.mark.asyncio
async def test_whatif_endpoint_returns_gantt():
    transport = ASGITransport(app=app)
    payload = {
        "sections": [
            {"id": "S1", "headway_seconds": 60, "traverse_seconds": 100}
        ],
        "trains": [
            {"id": "A", "priority": 1, "planned_departure": 0, "route_sections": ["S1"]},
            {"id": "B", "priority": 2, "planned_departure": 10, "route_sections": ["S1"]}
        ]
    }
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        r = await client.post("/whatif", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert "gantt" in data and isinstance(data["gantt"], list)
        assert data["count"] == len(data["gantt"]) > 0
        # Validate required Gantt fields
        g = data["gantt"][0]
        for key in ("train", "section", "start", "end"):
            assert key in g
