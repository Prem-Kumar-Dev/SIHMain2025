from typing import List, Dict
from src.core.models import ScheduleItem

# Minimal simulation utilities (placeholder for later detailed DES)

def summarize_schedule(items: List[ScheduleItem]) -> Dict[str, int]:
    # returns basic KPIs: total_trains, makespan, utilization proxy, conflicts (assume 0)
    if not items:
        return {"total_trains": 0, "makespan": 0, "utilization": 0, "conflicts": 0}
    start = min(i.entry for i in items)
    end = max(i.exit for i in items)
    makespan = end - start
    # utilization proxy: sum of durations divided by span (capped at 100)
    total_time = sum(i.exit - i.entry for i in items)
    utilization = int(100 * total_time / makespan) if makespan > 0 else 0
    return {
        "total_trains": len(set(i.train_id for i in items)),
        "makespan": makespan,
        "utilization": min(utilization, 100),
        "conflicts": 0,
    }
