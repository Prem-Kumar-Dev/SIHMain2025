from typing import List, Dict, Any
from src.core.models import NetworkModel, Section, TrainRequest, ScheduleItem
from src.core.solver import schedule_trains


def run_scenario(network: NetworkModel, trains: List[TrainRequest], solver: str = "greedy") -> Dict[str, Any]:
    items = schedule_trains(trains, network, solver=solver)
    return {
        "schedule": items,
    }


def gantt_json(items: List[ScheduleItem]) -> List[Dict[str, Any]]:
    # Convert to a simple Gantt format: one entry per schedule item
    return [
        {
            "train": it.train_id,
            "section": it.section_id,
            "start": it.entry,
            "end": it.exit,
        }
        for it in items
    ]
