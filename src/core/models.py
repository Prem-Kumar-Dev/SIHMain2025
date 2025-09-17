from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict

Seconds = int

@dataclass
class Section:
    id: str
    headway_seconds: Seconds  # minimum separation between consecutive trains
    traverse_seconds: Seconds  # time to traverse the section
    # List of [start, end) intervals during which section is blocked/unavailable
    block_windows: Optional[List[Tuple[Seconds, Seconds]]] = None
    # Optional platform capacity at the entry to this section (e.g., station platform). If 1, enforce non-overlapping dwell intervals before entering this section.
    platform_capacity: Optional[int] = None
    # Optional: map of conflicting section_id -> clearance seconds. If present, enforce disjunctive separation
    # between entries on this section and entries on the conflicting section.
    conflicts_with: Optional[Dict[str, Seconds]] = None
    # Optional: conflict groups within a junction/station: group_id -> clearance seconds.
    # Any two legs assigned to the same group must be separated by the group's clearance time.
    conflict_groups: Optional[Dict[str, Seconds]] = None

@dataclass
class TrainRequest:
    id: str
    priority: int  # higher = more important
    route_sections: List[str]
    planned_departure: Seconds  # epoch seconds or t=0 reference
    # Optional: dwell time required before entering a given section (e.g., station dwell)
    # Key: section_id, Value: dwell seconds
    dwell_before: Optional[Dict[str, Seconds]] = None
    # Optional target time for last-section entry (or completion proxy)
    due_time: Optional[Seconds] = None

@dataclass
class ScheduleItem:
    train_id: str
    section_id: str
    entry: Seconds
    exit: Seconds

@dataclass
class NetworkModel:
    sections: List[Section]

    def section_by_id(self, sid: str) -> Section:
        for s in self.sections:
            if s.id == sid:
                return s
        raise KeyError(f"Section {sid} not found")
