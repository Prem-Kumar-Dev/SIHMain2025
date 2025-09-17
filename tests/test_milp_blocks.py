from src.core.models import NetworkModel, Section, TrainRequest
from src.core.solver import schedule_trains


def test_milp_single_section_with_block_windows():
    s = Section(id="S1", headway_seconds=60, traverse_seconds=100, block_windows=[(50, 200)])
    network = NetworkModel(sections=[s])
    t1 = TrainRequest(id="A", priority=2, planned_departure=0, route_sections=["S1"])
    t2 = TrainRequest(id="B", priority=1, planned_departure=80, route_sections=["S1"])
    items = schedule_trains([t1, t2], network, solver="milp")
    items = sorted([it for it in items if it.section_id == "S1"], key=lambda x: x.entry)
    assert items[0].entry >= 200
    assert items[1].entry >= items[0].exit + 60


def test_milp_multi_section_with_block_windows():
    s1 = Section(id="S1", headway_seconds=60, traverse_seconds=100, block_windows=[(50, 200)])
    s2 = Section(id="S2", headway_seconds=60, traverse_seconds=100, block_windows=None)
    network = NetworkModel(sections=[s1, s2])
    t1 = TrainRequest(id="A", priority=2, planned_departure=0, route_sections=["S1", "S2"])
    t2 = TrainRequest(id="B", priority=1, planned_departure=0, route_sections=["S1", "S2"])
    items = schedule_trains([t1, t2], network, solver="milp")
    s1_items = sorted([it for it in items if it.section_id == "S1"], key=lambda x: x.entry)
    s2_items = sorted([it for it in items if it.section_id == "S2"], key=lambda x: x.entry)
    assert s1_items[0].entry >= 200
    # Precedence across sections maintained with dwell (none here): S2 starts after S1 exit
    assert s2_items[0].entry >= s1_items[0].exit