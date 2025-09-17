from dataclasses import dataclass
from typing import List, Optional

Seconds = int

@dataclass
class Section:
    id: str
    headway_seconds: Seconds  # minimum separation between consecutive trains
    traverse_seconds: Seconds  # time to traverse the section

@dataclass
class TrainRequest:
    id: str
    priority: int  # higher = more important
    route_sections: List[str]
    planned_departure: Seconds  # epoch seconds or t=0 reference

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
