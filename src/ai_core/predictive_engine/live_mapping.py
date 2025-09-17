from __future__ import annotations
from typing import Any, Dict, List, Tuple


def _safe_get(d: Dict[str, Any], key: str, default=None):
    v = d.get(key)
    return v if v is not None else default


def map_live_to_state(live_payload: Any, sections_hint: List[Dict[str, Any]] | None = None, max_trains: int = 50) -> Dict[str, Any]:
    """Map RailRadar-like payload into our internal state shape.

    This function is defensive: it tries several likely shapes and falls back to empty.
    We preserve provided sections when passed (sections_hint), otherwise return an empty/default section list.
    """
    sections = sections_hint or []
    trains_out: List[Dict[str, Any]] = []

    # Likely shapes:
    # 1) { trains: [ { trainNumber, eta, lateness, nextSectionId, priority, ... }, ... ] }
    # 2) A flat list of trains
    # 3) Nested under data/response keys
    def extract_trains(obj: Any) -> List[Dict[str, Any]]:
        if isinstance(obj, list):
            return obj
        if isinstance(obj, dict):
            for k in ("trains", "data", "response", "items"):
                if k in obj:
                    v = obj[k]
                    if isinstance(v, list):
                        return v
                    if isinstance(v, dict):
                        return extract_trains(v)
        return []

    trains_live = extract_trains(live_payload)
    for t in trains_live[:max_trains]:
        if not isinstance(t, dict):
            continue
        tid = _safe_get(t, "trainNumber") or _safe_get(t, "id") or _safe_get(t, "name")
        if not isinstance(tid, str):
            continue
        # Heuristic fields
        next_sid = _safe_get(t, "nextSectionId") or _safe_get(t, "nextBlockId") or _safe_get(t, "nextStationId")
        priority = _safe_get(t, "priority", 1)
        delay_min = _safe_get(t, "delayMinutes", 0) or _safe_get(t, "current_delay_minutes", 0)
        planned_dep = int(_safe_get(t, "plannedDeparture", 0) or 0)

        # Assemble minimal train record
        train = {
            "id": str(tid),
            "priority": int(priority) if isinstance(priority, (int, float)) else 1,
            "planned_departure": planned_dep,
            "route_sections": [str(next_sid)] if next_sid else [],
            "current_delay_minutes": float(delay_min) if isinstance(delay_min, (int, float)) else 0.0,
        }
        trains_out.append(train)

    return {"sections": sections, "trains": trains_out}
