import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from typing import Any, Dict, List, Tuple, Optional
import pandas as pd
import plotly.graph_objects as go


def _section_map(state: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {s.get("id"): s for s in state.get("sections", [])}


def _build_scheduled_segments(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Construct scheduled segments per train-section based on planned departure and traverse_seconds.
    Returns list of dicts with keys: train, section, start, end, layer="scheduled".
    """
    sec_map = _section_map(state)
    segments: List[Dict[str, Any]] = []
    for t in state.get("trains", []):
        pid = t.get("id")
        t0 = float(t.get("planned_departure", 0) or 0)
        cur = t0
        for sid in t.get("route_sections", []) or []:
            trav = float((sec_map.get(sid, {}) or {}).get("traverse_seconds", 0) or 0)
            start, end = cur, cur + trav
            segments.append({"train": pid, "section": sid, "start": start, "end": end, "layer": "scheduled"})
            cur = end
    return segments


def _build_predicted_segments(schedule_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    segs: List[Dict[str, Any]] = []
    for it in schedule_items:
        st = it.get("entry")
        en = it.get("exit")
        if st is None or en is None:
            continue
        segs.append({
            "train": it.get("train_id"),
            "section": it.get("section_id"),
            "start": float(st),
            "end": float(en),
            "layer": "predicted"
        })
    return segs


def render_time_distance(state: Dict[str, Any], schedule_items: List[Dict[str, Any]], conflicts: Optional[List[Dict[str, Any]]] = None) -> go.Figure:
    """Render an overlaid time-distance style chart with two layers:
    - scheduled (from timetable)
    - predicted (from resolved or direct schedule)
    Y-axis is sections (geographical order as listed). X-axis is time (seconds).
    """
    sched = _build_scheduled_segments(state)
    pred = _build_predicted_segments(schedule_items)
    df = pd.DataFrame(sched + pred)
    if df.empty:
        return go.Figure()

    # Establish section order as in input state
    section_order = [s.get("id") for s in state.get("sections", [])]
    df["section"] = pd.Categorical(df["section"], categories=section_order, ordered=True)

    fig = go.Figure()
    # Plot scheduled as semi-transparent dashed bars
    for _, row in df[df["layer"] == "scheduled"].iterrows():
        fig.add_trace(go.Scatter(
            x=[row["start"], row["end"]],
            y=[row["section"], row["section"]],
            mode="lines",
            line=dict(color="#888", width=6, dash="dash"),
            name=f"{row['train']} scheduled",
            legendgroup=f"{row['train']}",
            hovertemplate=f"Train={row['train']}<br>Section={row['section']}<br>Start={row['start']:.1f}<br>End={row['end']:.1f}<extra></extra>",
            showlegend=False,
        ))
    # Plot predicted as solid brighter bars
    for _, row in df[df["layer"] == "predicted"].iterrows():
        fig.add_trace(go.Scatter(
            x=[row["start"], row["end"]],
            y=[row["section"], row["section"]],
            mode="lines",
            line=dict(width=8),
            name=f"{row['train']} predicted",
            legendgroup=f"{row['train']}",
            hovertemplate=f"Train={row['train']}<br>Section={row['section']}<br>Start={row['start']:.1f}<br>End={row['end']:.1f}<extra></extra>",
            showlegend=False,
        ))
    # Overlay conflict markers if provided
    if conflicts:
        for c in conflicts:
            sid = c.get("section_id")
            etas = c.get("etas", []) or []
            for eta in etas:
                fig.add_trace(go.Scatter(
                    x=[eta], y=[sid],
                    mode="markers",
                    marker=dict(color="#e74c3c", size=10, symbol="x"),
                    name="conflict",
                    showlegend=False,
                    hovertemplate=f"Conflict at section={sid}<br>ETA={eta:.1f}<extra></extra>",
                ))

    fig.update_layout(
        title="Predictive Time-Distance (Scheduled vs Predicted)",
        xaxis_title="Time (s)",
        yaxis_title="Section",
        yaxis=dict(categoryorder="array", categoryarray=section_order),
        height=500,
        margin=dict(l=40, r=10, t=60, b=40),
    )
    return fig
