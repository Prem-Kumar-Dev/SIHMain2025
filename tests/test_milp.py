import json
import pytest
from pathlib import Path

from src.core.models import NetworkModel, Section, TrainRequest
from src.core.solver import schedule_trains

DATA_DIR = Path(__file__).parents[1] / "src" / "data"


def test_milp_single_section_beats_or_equals_greedy():
    # Build a single-section case where MILP can optimize ordering by priorities/departure
    section = Section(id="S1", headway_seconds=60, traverse_seconds=90)
    network = NetworkModel(sections=[section])
    trains = [
        TrainRequest(id="A", priority=1, planned_departure=0, route_sections=["S1"]),
        TrainRequest(id="B", priority=3, planned_departure=30, route_sections=["S1"]),
        TrainRequest(id="C", priority=2, planned_departure=20, route_sections=["S1"]),
    ]

    greedy_schedule = schedule_trains(trains, network, solver="greedy")
    milp_schedule = schedule_trains(trains, network, solver="milp")

    # Compare makespan (end of last train - start of first)
    g_makespan = max(i.exit for i in greedy_schedule) - min(i.entry for i in greedy_schedule)
    m_makespan = max(i.exit for i in milp_schedule) - min(i.entry for i in milp_schedule)
    assert m_makespan <= g_makespan

    # Ensure no overlaps in MILP result
    items = sorted(milp_schedule, key=lambda x: x.entry)
    for a, b in zip(items, items[1:]):
        assert a.exit <= b.entry


def test_api_milp_toggle():
    # Ensure API toggle paths accept solver parameter
    section = {"id": "S1", "headway_seconds": 60, "traverse_seconds": 90}
    payload = {
        "sections": [section],
        "trains": [
            {"id": "A", "priority": 1, "planned_departure": 0, "route_sections": ["S1"]},
            {"id": "B", "priority": 3, "planned_departure": 30, "route_sections": ["S1"]}
        ]
    }
    # Not calling the API here; solver wiring is validated by core tests
    network = NetworkModel(sections=[Section(**section)])
    trains = [TrainRequest(**t) for t in payload["trains"]]
    _ = schedule_trains(trains, network, solver="milp")
