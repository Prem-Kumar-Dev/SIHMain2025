from __future__ import annotations
from typing import Any, Dict, List
from dataclasses import dataclass


@dataclass
class TrainFeature:
    train_id: str
    features: Dict[str, float]


def build_features_from_state(state: Dict[str, Any]) -> List[TrainFeature]:
    """Transform a network state payload into per-train features.

    Expected minimal input shape (compatible subset with existing /schedule input):
    {
      "sections": [{"id": "S1", "headway_seconds": 120, "traverse_seconds": 100, ...}, ...],
      "trains": [{
          "id": "T1", "priority": 1, "planned_departure": 0,
          "route_sections": ["S1", "S2"],
          "dwell_before": {"S2": 60},
          "due_time": 800,
          "current_delay_minutes": 3
      }, ...]
    }
    """
    sections = {s["id"]: s for s in state.get("sections", [])}
    trains = state.get("trains", [])

    density_per_section: Dict[str, int] = {sid: 0 for sid in sections.keys()}
    for t in trains:
        # naive: count a train against its next section if exists
        next_sid = (t.get("route_sections") or [None])[0]
        if next_sid in density_per_section:
            density_per_section[next_sid] += 1

    feats: List[TrainFeature] = []
    for t in trains:
        route = t.get("route_sections", [])
        total_route_len = float(len(route))
        remaining_stops = float(max(0, len(route)))
        next_sid = route[0] if route else None
        next_section = sections.get(next_sid) if next_sid else None
        density = float(density_per_section.get(next_sid, 0)) if next_sid else 0.0
        dwell_next = 0.0
        if isinstance(t.get("dwell_before"), dict) and next_sid in t["dwell_before"]:
            dwell_next = float(t["dwell_before"][next_sid])

        feats.append(TrainFeature(
            train_id=t.get("id"),
            features={
                "priority": float(t.get("priority", 1)),
                "current_delay_minutes": float(t.get("current_delay_minutes", 0.0)),
                "time_of_day": float((t.get("planned_departure", 0) % 86400) / 3600.0),
                "day_of_week": float(0),  # placeholder unless provided
                "total_route_length": total_route_len,
                "remaining_stops": remaining_stops,
                "traffic_density_in_section": density,
                "scheduled_dwell_time_at_next_station": dwell_next,
                "upcoming_traverse_seconds": float(next_section["traverse_seconds"]) if next_section else 0.0,
                "upcoming_headway_seconds": float(next_section["headway_seconds"]) if next_section else 0.0,
            }
        ))
    return feats
