from src.core.models import Section, NetworkModel, TrainRequest
from src.core.solver import schedule_trains
from src.sim.simulator import lateness_kpis


def test_otp_tolerance_effect():
    s1 = Section(id="S1", headway_seconds=0, traverse_seconds=10)
    network = NetworkModel(sections=[s1])
    # Two trains: one slightly late vs due_time, one very early
    t1 = TrainRequest(id="LATE", priority=1, planned_departure=0, route_sections=["S1"], due_time=5)
    t2 = TrainRequest(id="EARLY", priority=1, planned_departure=0, route_sections=["S1"], due_time=100)
    items = schedule_trains([t1, t2], network, solver="milp")
    k0 = lateness_kpis(items, [t1, t2], otp_tolerance_s=0)
    k300 = lateness_kpis(items, [t1, t2], otp_tolerance_s=300)
    assert k0["otp_end"] <= k300["otp_end"]