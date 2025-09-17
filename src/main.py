import json
from pathlib import Path
from typing import List

from src.core.models import NetworkModel, Section, TrainRequest
from src.core.greedy_scheduler import schedule_trains
from src.sim.simulator import summarize_schedule

DATA_DIR = Path(__file__).parent / "data"


def load_network() -> NetworkModel:
    data = json.loads((DATA_DIR / "sample_network.json").read_text())
    sections = [Section(**s) for s in data["sections"]]
    return NetworkModel(sections=sections)


def load_trains() -> List[TrainRequest]:
    data = json.loads((DATA_DIR / "sample_trains.json").read_text())
    return [TrainRequest(**t) for t in data["trains"]]


if __name__ == "__main__":
    network = load_network()
    trains = load_trains()

    schedule = schedule_trains(trains, network)

    kpis = summarize_schedule(schedule)
    print("KPIs:", kpis)
    print("First 5 schedule items:")
    for it in schedule[:5]:
        print(vars(it))
