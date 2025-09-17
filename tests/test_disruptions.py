from src.core.models import NetworkModel, Section, TrainRequest
from src.core.solver import schedule_trains


def test_scheduler_avoids_block_windows():
    # Section blocked from t=50 to t=200; train arriving at 40 must either fit before or after block
    s = Section(id="S1", headway_seconds=60, traverse_seconds=100, block_windows=[(50, 200)])
    network = NetworkModel(sections=[s])
    # One train wants to start at 0; will enter, but second starts at 80 and should be pushed after block
    t1 = TrainRequest(id="A", priority=1, planned_departure=0, route_sections=["S1"])
    t2 = TrainRequest(id="B", priority=1, planned_departure=80, route_sections=["S1"])
    items = schedule_trains([t1, t2], network, solver="greedy")
    items = sorted(items, key=lambda x: x.entry)

    # No train may overlap the block [50,200); both should be pushed to >= 200
    assert items[0].entry >= 200
    # Respect traverse duration
    assert items[0].exit == items[0].entry + 100
    # Second must respect headway after the first
    assert items[1].entry >= items[0].exit + 60
