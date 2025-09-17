from __future__ import annotations
from typing import Dict, List, Any


def detect_future_conflicts(predicted_delays_min: Dict[str, float], state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Very simple conflict heuristic.

    - Shift each train's planned entry to its next section by predicted delay.
    - If two trains target the same first section within a small window, flag a conflict.
    """
    trains = state.get("trains", [])
    by_next_section: Dict[str, List[Dict[str, Any]]] = {}
    for t in trains:
        route = t.get("route_sections", [])
        if not route:
            continue
        next_sid = route[0]
        planned = float(t.get("planned_departure", 0))
        delay_s = float(predicted_delays_min.get(t.get("id"), 0.0)) * 60.0
        eta = planned + delay_s
        by_next_section.setdefault(next_sid, []).append({"train_id": t.get("id"), "eta": eta})

    conflicts: List[Dict[str, Any]] = []
    clearance = 120.0  # 2 minutes window heuristic
    for sid, arrivals in by_next_section.items():
        arrivals = sorted(arrivals, key=lambda x: x["eta"])  # soonest first
        for i in range(len(arrivals) - 1):
            a = arrivals[i]
            b = arrivals[i + 1]
            if b["eta"] - a["eta"] < clearance:
                conflicts.append({
                    "section_id": sid,
                    "trains": [a["train_id"], b["train_id"]],
                    "etas": [a["eta"], b["eta"]],
                    "gap_seconds": b["eta"] - a["eta"],
                })
    return conflicts
