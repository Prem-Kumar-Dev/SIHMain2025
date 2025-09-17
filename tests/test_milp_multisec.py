from src.core.models import NetworkModel, Section, TrainRequest
from src.core.solver import schedule_trains


def test_multisec_milp_non_overlap_and_compares_to_greedy():
    # Two sections in sequence, shared by all trains
    s1 = Section(id="S1", headway_seconds=60, traverse_seconds=100)
    s2 = Section(id="S2", headway_seconds=60, traverse_seconds=80)
    network = NetworkModel(sections=[s1, s2])

    trains = [
        TrainRequest(id="A", priority=1, planned_departure=0, route_sections=["S1", "S2"]),
        TrainRequest(id="B", priority=3, planned_departure=20, route_sections=["S1", "S2"]),
        TrainRequest(id="C", priority=2, planned_departure=10, route_sections=["S1", "S2"]),
    ]

    g = schedule_trains(trains, network, solver="greedy")
    m = schedule_trains(trains, network, solver="milp")

    # Non-overlap per section
    for sid in ("S1", "S2"):
        sg = sorted([i for i in g if i.section_id == sid], key=lambda x: x.entry)
        sm = sorted([i for i in m if i.section_id == sid], key=lambda x: x.entry)
        for a, b in zip(sm, sm[1:]):
            assert a.exit <= b.entry

    # Makespan comparison
    gspan = max(i.exit for i in g) - min(i.entry for i in g)
    mspan = max(i.exit for i in m) - min(i.entry for i in m)
    assert mspan <= gspan
