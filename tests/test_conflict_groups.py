from src.core.models import Section, NetworkModel, TrainRequest
from src.core.solver import schedule_trains


def test_conflict_groups_enforced():
    # S1 and S2 share group G with 90s clearance
    s1 = Section(id="S1", headway_seconds=0, traverse_seconds=30, conflict_groups={"G": 90})
    s2 = Section(id="S2", headway_seconds=0, traverse_seconds=30, conflict_groups={"G": 90})
    network = NetworkModel(sections=[s1, s2])
    t1 = TrainRequest(id="A", priority=1, planned_departure=0, route_sections=["S1"]) 
    t2 = TrainRequest(id="B", priority=1, planned_departure=0, route_sections=["S2"]) 

    items = schedule_trains([t1, t2], network, solver="milp")
    a_entry = min(i.entry for i in items if i.section_id == "S1")
    b_entry = min(i.entry for i in items if i.section_id == "S2")
    assert abs(a_entry - b_entry) >= 90
