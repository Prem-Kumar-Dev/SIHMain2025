from src.core.models import NetworkModel, Section, TrainRequest
from src.core.solver import schedule_trains


def test_dwell_respected_in_greedy_and_milp():
    s1 = Section(id="S1", headway_seconds=0, traverse_seconds=100)
    s2 = Section(id="S2", headway_seconds=0, traverse_seconds=50)
    network = NetworkModel(sections=[s1, s2])

    t = TrainRequest(id="T1", priority=1, planned_departure=0, route_sections=["S1", "S2"], dwell_before={"S2": 60})

    g = schedule_trains([t], network, solver="greedy")
    m = schedule_trains([t], network, solver="milp")

    # Extract entries on S2
    g_s2 = [it for it in g if it.section_id == "S2"][0]
    m_s2 = [it for it in m if it.section_id == "S2"][0]

    # S2 entry should be at least S1 exit + dwell
    g_s1 = [it for it in g if it.section_id == "S1"][0]
    m_s1 = [it for it in m if it.section_id == "S1"][0]

    assert g_s2.entry >= g_s1.exit + 60
    assert m_s2.entry >= m_s1.exit + 60
