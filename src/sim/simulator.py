from typing import List, Dict
from src.core.models import ScheduleItem

# Minimal simulation utilities (placeholder for later detailed DES)

def summarize_schedule(items: List[ScheduleItem]) -> Dict[str, int]:
    # returns basic KPIs: total_trains, makespan, max_delay (placeholder 0), conflicts (0 assumed)
    if not items:
        return {"total_trains": 0, "makespan": 0, "max_delay": 0, "conflicts": 0}
    makespan = max(i.exit for i in items) - min(i.entry for i in items)
    return {"total_trains": len(set(i.train_id for i in items)), "makespan": makespan, "max_delay": 0, "conflicts": 0}
