from src.core.models import Section, NetworkModel, TrainRequest
from src.core.solver import schedule_trains


def test_platform_capacity_single_section_dwell_nonoverlap():
    # Capacity 1 at S1 should make dwell intervals before entry non-overlapping
    s1 = Section(id="S1", headway_seconds=0, traverse_seconds=10, platform_capacity=1)
    network = NetworkModel(sections=[s1])
    # Two trains both need dwell before S1
    t1 = TrainRequest(id="T1", priority=1, planned_departure=0, route_sections=["S1"], dwell_before={"S1": 50})
    t2 = TrainRequest(id="T2", priority=1, planned_departure=0, route_sections=["S1"], dwell_before={"S1": 50})

    items = schedule_trains([t1, t2], network, solver="milp")
    # Extract S1 starts
    starts = sorted([(i.train_id, i.entry) for i in items if i.section_id == "S1"], key=lambda x: x[1])
    # With capacity=1 and 50s dwell each, the second train's start must be at least 50s after the first's start
    assert starts[1][1] - starts[0][1] >= 50
