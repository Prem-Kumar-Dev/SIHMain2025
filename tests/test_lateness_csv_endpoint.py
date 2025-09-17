import httpx
import pytest
from httpx import ASGITransport
from src.api import app


@pytest.mark.asyncio
async def test_download_lateness_csv_endpoint():
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
        # Create a scenario and run it to persist a run
        r = await client.post("/scenarios", json={"name": "csv-late", "payload": payload})
        assert r.status_code == 200
        sid = r.json()["id"]
        r = await client.post(f"/scenarios/{sid}/run", params={"solver": "milp", "otp_tolerance": 300})
        assert r.status_code == 200
        rid = r.json()["run_id"]
        # Download CSV
        rcsv = await client.get(f"/runs/{rid}/lateness.csv")
        assert rcsv.status_code == 200
        assert rcsv.headers.get("content-type", "").startswith("text/csv")
        assert "train_id,lateness_s" in rcsv.text