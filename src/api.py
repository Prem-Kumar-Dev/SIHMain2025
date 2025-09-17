from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Dict, Any

from src.core.models import NetworkModel, Section, TrainRequest, ScheduleItem
from src.core.solver import schedule_trains
from src.sim.simulator import summarize_schedule
from src.sim.scenario import run_scenario, gantt_json
from src.sim.audit import write_audit

app = FastAPI(title="SIH Train Scheduler API")

class SectionIn(BaseModel):
    id: str
    headway_seconds: int
    traverse_seconds: int
    block_windows: list[tuple[int, int]] | None = None

class TrainIn(BaseModel):
    id: str
    priority: int
    planned_departure: int
    route_sections: List[str]
    dwell_before: Dict[str, int] | None = None

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
async def schedule(body: Dict[str, Any], solver: str = "greedy") -> Dict[str, Any]:
    # Pydantic coercion helps, but we construct Section explicitly to ensure tuples
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
    schedule_items = schedule_trains(trains, network, solver=solver)
    kpis = summarize_schedule(schedule_items)
    resp = {
        "kpis": kpis,
        "schedule": [ScheduleItemOut(**vars(it)).model_dump() for it in schedule_items],
    }
    write_audit({
        "type": "schedule",
        "solver": solver,
        "kpis": kpis,
        "count": len(schedule_items),
    })
    return resp


@app.post("/whatif")
async def whatif(body: Dict[str, Any], solver: str = "greedy") -> Dict[str, Any]:
    # Build network and trains as in /schedule
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

    result = run_scenario(network, trains, solver=solver)
    items = result["schedule"]
    resp = {
        "gantt": gantt_json(items),
        "count": len(items),
    }
    write_audit({
        "type": "whatif",
        "solver": solver,
        "count": len(items),
    })
    return resp


@app.post("/kpis")
async def kpis(body: Dict[str, Any], solver: str = "greedy") -> Dict[str, Any]:
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
    write_audit({
        "type": "kpis",
        "solver": solver,
        "kpis": k,
        "count": len(items),
    })
    return {"kpis": k}
