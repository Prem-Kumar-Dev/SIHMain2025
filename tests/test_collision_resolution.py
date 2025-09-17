import os
import time
import json
import requests

API_BASE = os.getenv("API_BASE", "http://127.0.0.1:8000")


def load_payload():
    base = os.path.join(os.path.dirname(__file__), "..", "data", "scenarios", "collision_heavy.json")
    with open(os.path.abspath(base), "r", encoding="utf-8") as f:
        return json.load(f)


def post_json(path, payload):
    r = requests.post(f"{API_BASE}{path}", json=payload, timeout=30)
    r.raise_for_status()
    return r.json()


def test_predict_then_resolve_conflicts():
    payload = load_payload()

    # Ensure API is up; simple GET on root should redirect/200
    r = requests.get(f"{API_BASE}/", allow_redirects=True, timeout=10)
    assert r.status_code in (200, 307, 308)

    # 1) Predict to surface conflicts first
    pred = post_json("/predict", payload)

    assert "conflicts" in pred
    conflicts = pred["conflicts"]
    # We expect at least 1 conflict in a dense departure scenario
    assert isinstance(conflicts, list)
    assert len(conflicts) >= 1

    # 2) Resolve to produce a conflict-free schedule subject to headways
    res = post_json("/resolve", payload)

    assert "schedule" in res
    schedule = res["schedule"]
    assert isinstance(schedule, list)
    assert len(schedule) >= len(payload["trains"])  # at least one entry per train

    # Build per-section ordered entry times to assert headway constraints
    # schedule items expected shape: {train_id, section_id, entry_time, exit_time}
    by_section = {}
    for item in schedule:
        sec = item.get("section_id")
        if not sec:
            continue
        by_section.setdefault(sec, []).append(item)

    # Get headways from payload sections
    headways = {s["id"]: s.get("headway_seconds", 0) for s in payload.get("sections", [])}

    for sec, items in by_section.items():
        items.sort(key=lambda x: x.get("entry_time", 0))
        for i in range(1, len(items)):
            prev = items[i-1]
            curr = items[i]
            gap = (curr.get("entry_time", 0) or 0) - (prev.get("exit_time", 0) or 0)
            assert gap >= headways.get(sec, 0), f"Headway violated on {sec}: gap={gap}, need>={headways.get(sec, 0)}"

    # Basic KPI presence check
    assert "kpis" in res
    kpis = res["kpis"]
    assert isinstance(kpis, dict)
    assert "on_time_percentage" in kpis or "avg_delay_minutes" in kpis
