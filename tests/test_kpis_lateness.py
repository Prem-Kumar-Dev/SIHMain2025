from src.core.models import Section, NetworkModel, TrainRequest
from src.core.solver import schedule_trains
from src.sim.simulator import lateness_kpis


def test_lateness_kpis_basic():
    s1 = Section(id="S1", headway_seconds=0, traverse_seconds=10)
    network = NetworkModel(sections=[s1])
    t1 = TrainRequest(id="A", priority=1, planned_departure=0, route_sections=["S1"], due_time=5)
    t2 = TrainRequest(id="B", priority=1, planned_departure=0, route_sections=["S1"], due_time=100)
    items = schedule_trains([t1, t2], network, solver="milp")
    kp = lateness_kpis(items, [t1, t2])
    assert set(kp.keys()) == {"otp_end", "avg_lateness", "total_lateness"}
