import httpx
import pytest
from pathlib import Path

from httpx import ASGITransport

from src.api import app
from src.store.db import set_db_path, init_db


@pytest.mark.asyncio
async def test_persistence_flow(tmp_path):
    # Isolate DB to a temp file
    db_file = Path(tmp_path) / "unit.db"
    set_db_path(db_file)
    init_db()

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1) Create a scenario
        payload = {
            "name": "basic-s1",
            "payload": {
                "sections": [
                    {"id": "S1", "headway_seconds": 120, "traverse_seconds": 100}
                ],
                "trains": [
                    {"id": "T1", "priority": 1, "planned_departure": 0, "route_sections": ["S1"]},
                    {"id": "T2", "priority": 2, "planned_departure": 30, "route_sections": ["S1"]}
                ],
            },
        }
        r = await client.post("/scenarios", json=payload)
        assert r.status_code == 200
        sid = r.json().get("id")
        assert isinstance(sid, int)

        # 2) List scenarios and ensure our scenario is present
        r = await client.get("/scenarios")
        assert r.status_code == 200
        items = r.json().get("items")
        assert isinstance(items, list)
        assert any(it.get("id") == sid for it in items)

        # 3) Run saved scenario
        r = await client.post(f"/scenarios/{sid}/run")
        assert r.status_code == 200
        data = r.json()
        rid = data.get("run_id")
        assert isinstance(rid, int)
        kpis = data.get("kpis")
        assert isinstance(kpis, dict)
        assert kpis.get("total_trains") == 2

        # 4) Fetch run details
        r = await client.get(f"/runs/{rid}")
        assert r.status_code == 200
        run = r.json().get("run")
        assert isinstance(run, dict)
        assert isinstance(run.get("input_payload"), dict)
        assert isinstance(run.get("schedule"), list)
        assert isinstance(run.get("kpis"), dict)
        # Sanity checks on schedule items
        assert len(run["schedule"]) >= 1
        item0 = run["schedule"][0]
        for key in ("train_id", "section_id", "entry", "exit"):
            assert key in item0
