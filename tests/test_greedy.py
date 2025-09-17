import json
from pathlib import Path

from src.core.models import NetworkModel, Section, TrainRequest
from src.core.greedy_scheduler import schedule_trains

DATA_DIR = Path(__file__).parents[1] / "src" / "data"


def test_basic_schedule_no_conflicts():
    data = json.loads((DATA_DIR / "sample_network.json").read_text())
    sections = [Section(**s) for s in data["sections"]]
    network = NetworkModel(sections=sections)

    trains_data = json.loads((DATA_DIR / "sample_trains.json").read_text())
    trains = [TrainRequest(**t) for t in trains_data["trains"]]

    schedule = schedule_trains(trains, network)

    # Check that within each section, items are non-overlapping with headway
    occ = {}
    for it in schedule:
        occ.setdefault(it.section_id, []).append(it)

    for sid, items in occ.items():
        items.sort(key=lambda x: x.entry)
        for a, b in zip(items, items[1:]):
            assert a.exit <= b.entry, f"Overlap in section {sid}: {a} vs {b}"

    # Ensure all trains have all route sections scheduled
    by_train = {}
    for it in schedule:
        by_train.setdefault(it.train_id, []).append(it)

    for t in trains:
        assert len(by_train[t.id]) >= len(t.route_sections)


def test_headway_enforced_and_priority_affects_order():
    # Smaller fixture inline to make assertions easier
    sections = [Section(id="S1", headway_seconds=120, traverse_seconds=100)]
    network = NetworkModel(sections=sections)

    # T2 has higher priority and departs slightly later; it should go before T1 if conflict arises
    t1 = TrainRequest(id="T1", priority=1, planned_departure=0, route_sections=["S1"])
    t2 = TrainRequest(id="T2", priority=2, planned_departure=60, route_sections=["S1"])

    schedule = schedule_trains([t1, t2], network)
    s_sorted = sorted([s for s in schedule if s.section_id == "S1"], key=lambda x: x.entry)

    # T2 should be scheduled first or at least not violate headway
    first, second = s_sorted[0], s_sorted[1]
    assert first.exit + sections[0].headway_seconds <= second.entry
    # Ensure that if T2 is first, that reflects higher priority impact under congestion
    # Note: Greedy sorts by priority desc then departure asc
    assert first.train_id == "T2"
