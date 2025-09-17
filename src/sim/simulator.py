from typing import List, Dict
from src.core.models import ScheduleItem, TrainRequest

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


def lateness_kpis(items: List[ScheduleItem], trains: List[TrainRequest], otp_tolerance_s: int = 0) -> Dict[str, float]:
    # Compute lateness-based KPIs if due_time present on any train
    if not items or not trains:
        return {"otp_end": 0.0, "avg_lateness": 0.0, "total_lateness": 0.0}
    lateness_by_train: Dict[str, int] = {}
    for t in trains:
        if t.due_time is not None and t.route_sections:
            last_sid = t.route_sections[-1]
            entries = [it.entry for it in items if it.train_id == t.id and it.section_id == last_sid]
            if entries:
                lateness_by_train[t.id] = max(0, int(entries[0]) - int(t.due_time))
    if not lateness_by_train:
        return {"otp_end": 0.0, "avg_lateness": 0.0, "total_lateness": 0.0}
    total = float(sum(lateness_by_train.values()))
    avg = total / len(lateness_by_train)
    # OTP within tolerance seconds
    tol = int(otp_tolerance_s or 0)
    otp = 100.0 * sum(1 for v in lateness_by_train.values() if v <= tol) / len(lateness_by_train)
    return {"otp_end": otp, "avg_lateness": avg, "total_lateness": total}
