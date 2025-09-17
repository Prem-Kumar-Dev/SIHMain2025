from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Dict, Any

from src.core.models import NetworkModel, Section, TrainRequest, ScheduleItem
from src.core.solver import schedule_trains
from src.sim.simulator import summarize_schedule

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
    return {
        "kpis": kpis,
        "schedule": [ScheduleItemOut(**vars(it)).model_dump() for it in schedule_items],
    }
