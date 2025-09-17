from src.core.models import Section, NetworkModel, TrainRequest
from src.core.solver import schedule_trains


def test_due_time_prioritizes_earlier_deadline_single_section():
    # Two trains, lower priority train has earlier due_time. MILP should meet earlier due when feasible.
    s1 = Section(id="S1", headway_seconds=60, traverse_seconds=50)
    network = NetworkModel(sections=[s1])
    # T1: higher priority but later due_time
    t1 = TrainRequest(id="T1", priority=3, planned_departure=0, route_sections=["S1"], due_time=400)
    # T2: lower priority but much earlier due_time
    t2 = TrainRequest(id="T2", priority=1, planned_departure=0, route_sections=["S1"], due_time=200)

    items = schedule_trains([t1, t2], network, solver="milp")
    # First entry should be for T2 to meet earlier due time if possible
    items_sorted = sorted([it for it in items if it.section_id == "S1"], key=lambda x: x.entry)
    assert items_sorted[0].train_id == "T2"


def test_due_time_with_dwell_and_multisec():
    # Multi-section route with dwell; train with earlier due_time should be favored at S2 entry.
    s1 = Section(id="S1", headway_seconds=60, traverse_seconds=50)
    s2 = Section(id="S2", headway_seconds=60, traverse_seconds=70)
    network = NetworkModel(sections=[s1, s2])

    tA = TrainRequest(id="A", priority=2, planned_departure=0, route_sections=["S1", "S2"], dwell_before={"S2": 30}, due_time=250)
    tB = TrainRequest(id="B", priority=3, planned_departure=0, route_sections=["S1", "S2"], dwell_before={"S2": 0}, due_time=400)

    items = schedule_trains([tA, tB], network, solver="milp")
    # Compare start times on last section S2
    a_s2 = min(i.entry for i in items if i.train_id == "A" and i.section_id == "S2")
    b_s2 = min(i.entry for i in items if i.train_id == "B" and i.section_id == "S2")
    assert a_s2 <= b_s2


def test_due_time_hetero_routes_shared_last_section():
    # Heterogeneous routes converging on S2; earlier due_time should get earlier S2 slot.
    s1 = Section(id="S1", headway_seconds=60, traverse_seconds=50)
    s3 = Section(id="S3", headway_seconds=60, traverse_seconds=50)
    s2 = Section(id="S2", headway_seconds=60, traverse_seconds=70)
    network = NetworkModel(sections=[s1, s2, s3])

    tA = TrainRequest(id="A", priority=2, planned_departure=0, route_sections=["S1", "S2"], due_time=250)
    tB = TrainRequest(id="B", priority=3, planned_departure=0, route_sections=["S3", "S2"], due_time=400)

    items = schedule_trains([tA, tB], network, solver="milp")
    # Compare start times on last common section S2
    a_s2 = min(i.entry for i in items if i.train_id == "A" and i.section_id == "S2")
    b_s2 = min(i.entry for i in items if i.train_id == "B" and i.section_id == "S2")
    assert a_s2 <= b_s2
