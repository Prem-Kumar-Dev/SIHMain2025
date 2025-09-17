import os
import httpx
import pytest
from httpx import ASGITransport
from src.api import app

@pytest.mark.asyncio
async def test_kpis_endpoint_and_audit_file_written(tmp_path, monkeypatch):
    # Redirect audit dir to temp
    from src.sim import audit as audit_mod
    audit_mod.AUDIT_DIR = tmp_path
    audit_mod.AUDIT_FILE = tmp_path / "events.jsonl"

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
        r = await client.post("/kpis", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert "kpis" in data
        assert data["kpis"]["total_trains"] == 2

    # Ensure audit written
    assert (audit_mod.AUDIT_FILE).exists()
    content = audit_mod.AUDIT_FILE.read_text(encoding="utf-8").strip().splitlines()
    assert any('"type": "kpis"' in line for line in content)
