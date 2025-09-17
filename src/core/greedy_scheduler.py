from typing import List, Dict
from .models import TrainRequest, NetworkModel, ScheduleItem

# Simple greedy scheduler:
# - Iterate trains by (priority desc, planned_departure asc)
# - For each section in route, find earliest feasible entry time given headways and current occupancy
# - Append scheduled items

def schedule_trains(trains: List[TrainRequest], network: NetworkModel) -> List[ScheduleItem]:
    # occupancy[section_id] = list of (entry, exit) intervals sorted by entry
    occupancy: Dict[str, List[ScheduleItem]] = {s.id: [] for s in network.sections}
    result: List[ScheduleItem] = []

    # sort trains by priority desc, then planned departure asc
    trains_sorted = sorted(trains, key=lambda t: (-t.priority, t.planned_departure))

    for t in trains_sorted:
        current_time = t.planned_departure
        prev_exit = current_time
        for sid in t.route_sections:
            sec = network.section_by_id(sid)
            headway = sec.headway_seconds
            traverse = sec.traverse_seconds

            # find earliest feasible entry respecting headway with previous scheduled items
            entry = max(prev_exit, t.planned_departure)
            entry = _find_earliest(entry, headway, traverse, occupancy[sid])
            exit_time = entry + traverse

            item = ScheduleItem(train_id=t.id, section_id=sid, entry=entry, exit=exit_time)
            _insert_occupancy(occupancy[sid], item)
            result.append(item)

            prev_exit = exit_time + headway  # ensure separation before next section

    return result


def _find_earliest(start: int, headway: int, traverse: int, occ: List[ScheduleItem]) -> int:
    # Occ intervals are non-overlapping and sorted; find earliest entry >= start such that
    # [entry, entry+traverse) doesn't violate headway with neighbors.
    entry = start
    i = 0
    while i < len(occ):
        cur = occ[i]
        # enforce separation from previous interval
        earliest_after_prev = cur.exit + headway
        # If proposed interval overlaps with current occupancy or violates headway, push after
        if not (entry + traverse + headway <= cur.entry or entry >= earliest_after_prev):
            entry = max(earliest_after_prev, cur.exit + headway)
            i = 0  # restart scan since entry changed
            continue
        i += 1
    return entry


def _insert_occupancy(occ: List[ScheduleItem], item: ScheduleItem) -> None:
    # insert maintaining sort by entry
    idx = 0
    while idx < len(occ) and occ[idx].entry <= item.entry:
        idx += 1
    occ.insert(idx, item)
