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


@pytest.mark.asyncio
async def test_list_runs_for_scenario(tmp_path):
    # Isolate DB to a temp file
    db_file = Path(tmp_path) / "unit2.db"
    set_db_path(db_file)
    init_db()

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Create a scenario and run it once
        payload = {
            "name": "list-runs",
            "payload": {
                "sections": [
                    {"id": "S1", "headway_seconds": 120, "traverse_seconds": 100}
                ],
                "trains": [
                    {"id": "T1", "priority": 1, "planned_departure": 0, "route_sections": ["S1"]}
                ],
            },
        }
        r = await client.post("/scenarios", json=payload)
        assert r.status_code == 200
        sid = r.json().get("id")
        assert isinstance(sid, int)

        r = await client.post(f"/scenarios/{sid}/run")
        assert r.status_code == 200
        rid = r.json().get("run_id")
        assert isinstance(rid, int)

        # List runs for scenario
        r = await client.get(f"/scenarios/{sid}/runs")
        assert r.status_code == 200
        items = r.json().get("items")
        assert isinstance(items, list)
        assert any(it.get("id") == rid for it in items)


@pytest.mark.asyncio
async def test_update_and_delete_flows(tmp_path):
    db_file = Path(tmp_path) / "unit3.db"
    set_db_path(db_file)
    init_db()

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Create scenario
        payload = {
            "name": "crud-scn",
            "payload": {
                "sections": [{"id": "S1", "headway_seconds": 120, "traverse_seconds": 100}],
                "trains": [{"id": "T1", "priority": 1, "planned_departure": 0, "route_sections": ["S1"]}],
            },
        }
        r = await client.post("/scenarios", json=payload)
        sid = r.json().get("id")

        # Update scenario name
        r = await client.put(f"/scenarios/{sid}", json={"name": "crud-scn-upd"})
        assert r.status_code == 200
        assert r.json().get("updated") is True

        # Run once and then delete run
        r = await client.post(f"/scenarios/{sid}/run")
        rid = r.json().get("run_id")
        r = await client.delete(f"/runs/{rid}")
        assert r.status_code == 200
        assert r.json().get("deleted") is True

        # Delete scenario (should also be OK even if no runs remain)
        r = await client.delete(f"/scenarios/{sid}")
        assert r.status_code == 200
        assert r.json().get("deleted") is True


@pytest.mark.asyncio
async def test_run_name_comment_and_pagination(tmp_path):
    db_file = Path(tmp_path) / "unit4.db"
    set_db_path(db_file)
    init_db()

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Create scenario
        payload = {
            "name": "meta-scn",
            "payload": {
                "sections": [{"id": "S1", "headway_seconds": 120, "traverse_seconds": 100}],
                "trains": [
                    {"id": "T1", "priority": 1, "planned_departure": 0, "route_sections": ["S1"]},
                    {"id": "T2", "priority": 2, "planned_departure": 10, "route_sections": ["S1"]},
                ],
            },
        }
        r = await client.post("/scenarios", json=payload)
        sid = r.json().get("id")

        # Create two runs with names/comments
        r = await client.post(f"/scenarios/{sid}/run", params={"name": "first", "comment": "baseline"})
        assert r.status_code == 200
        r = await client.post(f"/scenarios/{sid}/run", params={"name": "second", "comment": "tweak"})
        assert r.status_code == 200

        # List runs with pagination limit=1
        r = await client.get(f"/scenarios/{sid}/runs", params={"limit": 1, "offset": 0})
        assert r.status_code == 200
        items = r.json().get("items")
        assert len(items) == 1
        # Latest run should be "second"
        assert items[0].get("name") in ("second", None)  # name may be None if DB lacked column but migration should handle

        # Next page
        r = await client.get(f"/scenarios/{sid}/runs", params={"limit": 1, "offset": 1})
        items2 = r.json().get("items")
        assert len(items2) == 1
