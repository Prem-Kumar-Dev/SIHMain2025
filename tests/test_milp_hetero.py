from src.core.models import NetworkModel, Section, TrainRequest
from src.core.solver import schedule_trains


def test_milp_hetero_routes_shared_section_nonoverlap():
    # Trains with different routes but sharing S2 must not overlap on S2
    s1 = Section(id="S1", headway_seconds=60, traverse_seconds=80)
    s2 = Section(id="S2", headway_seconds=60, traverse_seconds=90)
    s3 = Section(id="S3", headway_seconds=60, traverse_seconds=70)
    network = NetworkModel(sections=[s1, s2, s3])

    tA = TrainRequest(id="A", priority=2, planned_departure=0, route_sections=["S1", "S2"])  # goes S1->S2
    tB = TrainRequest(id="B", priority=1, planned_departure=0, route_sections=["S3", "S2"])  # goes S3->S2

    items = schedule_trains([tA, tB], network, solver="milp")
    s2_items = sorted([it for it in items if it.section_id == "S2"], key=lambda x: x.entry)
    assert len(s2_items) == 2
    assert s2_items[0].exit + 60 <= s2_items[1].entry


def test_milp_hetero_routes_with_block_window():
    # Shared S2 has a block window; ensure both trains schedule around it
    s1 = Section(id="S1", headway_seconds=60, traverse_seconds=80)
    s2 = Section(id="S2", headway_seconds=60, traverse_seconds=90, block_windows=[(50, 200)])
    s3 = Section(id="S3", headway_seconds=60, traverse_seconds=70)
    network = NetworkModel(sections=[s1, s2, s3])

    tA = TrainRequest(id="A", priority=2, planned_departure=0, route_sections=["S1", "S2"])  # goes S1->S2
    tB = TrainRequest(id="B", priority=1, planned_departure=0, route_sections=["S3", "S2"])  # goes S3->S2

    items = schedule_trains([tA, tB], network, solver="milp")
    s2_items = sorted([it for it in items if it.section_id == "S2"], key=lambda x: x.entry)
    assert s2_items[0].entry >= 200
    assert s2_items[0].exit + 60 <= s2_items[1].entry