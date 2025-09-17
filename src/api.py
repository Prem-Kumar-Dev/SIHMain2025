import json
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Dict, Any

from src.core.models import NetworkModel, Section, TrainRequest, ScheduleItem
from src.core.solver import schedule_trains
from src.sim.simulator import summarize_schedule, lateness_kpis
from src.sim.scenario import run_scenario, gantt_json
from src.sim.audit import write_audit
from src.store.db import (
    init_db,
    save_scenario,
    list_scenarios,
    get_scenario,
    save_run,
    get_run,
    list_runs_by_scenario,
    update_scenario,
    delete_scenario,
    delete_run,
)

app = FastAPI(title="SIH Train Scheduler API")
init_db()

class SectionIn(BaseModel):
    id: str
    headway_seconds: int
    traverse_seconds: int
    block_windows: list[tuple[int, int]] | None = None
    platform_capacity: int | None = None
    conflicts_with: Dict[str, int] | None = None
    conflict_groups: Dict[str, int] | None = None

class TrainIn(BaseModel):
    id: str
    priority: int
    planned_departure: int
    route_sections: List[str]
    dwell_before: Dict[str, int] | None = None
    due_time: int | None = None

class ScheduleItemOut(BaseModel):
    train_id: str
    section_id: str
    entry: int
    exit: int

@app.get("/demo")
async def demo(solver: str = "greedy") -> Dict[str, Any]:
    sections = [
        Section(id="S1", headway_seconds=120, traverse_seconds=100),
        Section(id="S2", headway_seconds=120, traverse_seconds=120),
    ]
    network = NetworkModel(sections=sections)
    trains = [
        TrainRequest(id="T1", priority=1, planned_departure=0, route_sections=["S1", "S2"]),
        TrainRequest(id="T2", priority=2, planned_departure=60, route_sections=["S1"]),
    ]
    schedule = schedule_trains(trains, network, solver=solver)
    kpis = summarize_schedule(schedule)
    return {
        "kpis": kpis,
        "schedule": [ScheduleItemOut(**vars(it)).model_dump() for it in schedule],
    }

@app.post("/schedule")
async def schedule(body: Dict[str, Any], solver: str = "greedy", otp_tolerance: int = 0) -> Dict[str, Any]:
    # Pydantic coercion helps, but we construct Section explicitly to ensure tuples
    sections = []
    for s in body.get("sections", []):
        bw = s.get("block_windows") or []
        section = Section(
            id=s["id"],
            headway_seconds=s["headway_seconds"],
            traverse_seconds=s["traverse_seconds"],
            block_windows=[(int(a), int(b)) for a, b in bw] if bw else None,
            platform_capacity=s.get("platform_capacity"),
            conflicts_with=s.get("conflicts_with"),
            conflict_groups=s.get("conflict_groups"),
        )
        sections.append(section)
    trains = [TrainRequest(**t) for t in body.get("trains", [])]
    network = NetworkModel(sections=sections)
    schedule_items = schedule_trains(trains, network, solver=solver)
    kpis = summarize_schedule(schedule_items)
    # Extend with lateness KPIs if applicable
    lk = lateness_kpis(schedule_items, trains, otp_tolerance_s=otp_tolerance)
    kpis = {**kpis, **lk}
    # Compute per-train lateness if due_time present
    lateness_by_train: Dict[str, int] = {}
    for t in trains:
        if t.due_time is not None:
            # find last leg entry for this train
            last_sid = t.route_sections[-1]
            entries = [it.entry for it in schedule_items if it.train_id == t.id and it.section_id == last_sid]
            if entries:
                lateness_by_train[t.id] = max(0, int(entries[0]) - int(t.due_time))
    resp = {
        "kpis": kpis,
        "schedule": [ScheduleItemOut(**vars(it)).model_dump() for it in schedule_items],
        "lateness_by_train": lateness_by_train,
    }
    write_audit({
        "type": "schedule",
        "solver": solver,
        "kpis": kpis,
        "count": len(schedule_items),
    })
    return resp


@app.post("/whatif")
async def whatif(body: Dict[str, Any], solver: str = "greedy", otp_tolerance: int = 0) -> Dict[str, Any]:
    # Build network and trains as in /schedule
    sections = []
    for s in body.get("sections", []):
        bw = s.get("block_windows") or []
        section = Section(
            id=s["id"],
            headway_seconds=s["headway_seconds"],
            traverse_seconds=s["traverse_seconds"],
            block_windows=[(int(a), int(b)) for a, b in bw] if bw else None,
            platform_capacity=s.get("platform_capacity"),
            conflicts_with=s.get("conflicts_with"),
            conflict_groups=s.get("conflict_groups"),
        )
        sections.append(section)
    trains = [TrainRequest(**t) for t in body.get("trains", [])]
    network = NetworkModel(sections=sections)

    result = run_scenario(network, trains, solver=solver)
    items = result["schedule"]
    # lateness map
    lateness_by_train: Dict[str, int] = {}
    for t in trains:
        if t.due_time is not None:
            last_sid = t.route_sections[-1]
            entries = [it.entry for it in items if it.train_id == t.id and it.section_id == last_sid]
            if entries:
                lateness_by_train[t.id] = max(0, int(entries[0]) - int(t.due_time))
    resp = {
        "gantt": gantt_json(items),
        "count": len(items),
        "lateness_by_train": lateness_by_train,
    }
    write_audit({
        "type": "whatif",
        "solver": solver,
        "count": len(items),
    })
    return resp


@app.post("/kpis")
async def kpis(body: Dict[str, Any], solver: str = "greedy", otp_tolerance: int = 0) -> Dict[str, Any]:
    # Compute KPIs for provided scenario without returning the full schedule
    sections = []
    for s in body.get("sections", []):
        bw = s.get("block_windows") or []
        section = Section(
            id=s["id"],
            headway_seconds=s["headway_seconds"],
            traverse_seconds=s["traverse_seconds"],
            block_windows=[(int(a), int(b)) for a, b in bw] if bw else None,
        )
        sections.append(section)
    trains = [TrainRequest(**t) for t in body.get("trains", [])]
    network = NetworkModel(sections=sections)
    items = schedule_trains(trains, network, solver=solver)
    k = summarize_schedule(items)
    lk = lateness_kpis(items, trains, otp_tolerance_s=otp_tolerance)
    k = {**k, **lk}
    write_audit({
        "type": "kpis",
        "solver": solver,
        "kpis": k,
        "count": len(items),
    })
    return {"kpis": k}


# Persistence APIs
@app.post("/scenarios")
async def create_scenario(body: Dict[str, Any]) -> Dict[str, Any]:
    name = body.get("name", "scenario")
    payload = body.get("payload")
    if not isinstance(payload, dict):
        return {"error": "payload must be an object"}
    sid = save_scenario(name, payload)
    return {"id": sid}


@app.get("/scenarios")
async def scenarios(offset: int = 0, limit: int = 50) -> Dict[str, Any]:
    return {"items": list_scenarios(offset=offset, limit=limit)}


@app.post("/scenarios/{sid}/run")
async def run_saved_scenario(sid: int, solver: str = "greedy", name: str | None = None, comment: str | None = None, otp_tolerance: int = 0) -> Dict[str, Any]:
    s = get_scenario(sid)
    if not s:
        return {"error": "scenario not found"}
    payload = json.loads(s["payload"])
    # Reuse /schedule path
    sections = []
    for sec in payload.get("sections", []):
        bw = sec.get("block_windows") or []
        sections.append(Section(
            id=sec["id"], headway_seconds=sec["headway_seconds"], traverse_seconds=sec["traverse_seconds"],
            block_windows=[(int(a), int(b)) for a, b in bw] if bw else None,
            platform_capacity=sec.get("platform_capacity"),
            conflicts_with=sec.get("conflicts_with"),
            conflict_groups=sec.get("conflict_groups"),
        ))
    trains = [TrainRequest(**t) for t in payload.get("trains", [])]
    network = NetworkModel(sections=sections)
    items = schedule_trains(trains, network, solver=solver)
    k = summarize_schedule(items)
    # enrich with lateness KPIs and map
    lk = lateness_kpis(items, trains, otp_tolerance_s=otp_tolerance)
    k = {**k, **lk}
    lateness_by_train: Dict[str, int] = {}
    for t in trains:
        if t.due_time is not None and t.route_sections:
            last_sid = t.route_sections[-1]
            entries = [it.entry for it in items if it.train_id == t.id and it.section_id == last_sid]
            if entries:
                lateness_by_train[t.id] = max(0, int(entries[0]) - int(t.due_time))
    # Save run
    rid = save_run(
        scenario_id=sid,
        solver=solver,
        input_payload=payload,
        schedule=[vars(it) for it in items],
    kpis={**k, "lateness_by_train": lateness_by_train},
        name=name,
        comment=comment,
    )
    return {"run_id": rid, "kpis": {**k, "lateness_by_train": lateness_by_train}}


@app.get("/runs/{rid}")
async def get_run_details(rid: int) -> Dict[str, Any]:
    r = get_run(rid)
    if not r:
        return {"error": "run not found"}
    # Decode JSON fields
    r["input_payload"] = json.loads(r["input_payload"])
    r["schedule"] = json.loads(r["schedule"])
    r["kpis"] = json.loads(r["kpis"])
    return {"run": r}


@app.get("/scenarios/{sid}/runs")
async def list_runs_for_scenario(sid: int, offset: int = 0, limit: int = 50) -> Dict[str, Any]:
    # Return lightweight list of runs for a scenario
    runs = list_runs_by_scenario(sid, offset=offset, limit=limit)
    return {"items": runs}


@app.put("/scenarios/{sid}")
async def update_scenario_api(sid: int, body: Dict[str, Any]) -> Dict[str, Any]:
    name = body.get("name")
    payload = body.get("payload")
    ok = update_scenario(sid, name=name, payload=payload if isinstance(payload, dict) else None)
    return {"updated": bool(ok)}


@app.delete("/scenarios/{sid}")
async def delete_scenario_api(sid: int) -> Dict[str, Any]:
    ok = delete_scenario(sid)
    return {"deleted": bool(ok)}


@app.delete("/runs/{rid}")
async def delete_run_api(rid: int) -> Dict[str, Any]:
    ok = delete_run(rid)
    return {"deleted": bool(ok)}
