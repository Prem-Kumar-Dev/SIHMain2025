import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from typing import Any, Dict, List
import pandas as pd
import plotly.graph_objects as go


def _active_sections(schedule_items: List[Dict[str, Any]], now: float) -> Dict[str, List[str]]:
    occ: Dict[str, List[str]] = {}
    for it in schedule_items:
        st, en = it.get("entry"), it.get("exit")
        if st is None or en is None:
            continue
        if st <= now <= en:
            sec = it.get("section_id")
            occ.setdefault(sec, []).append(it.get("train_id"))
    return occ


def render_track_schematic(state: Dict[str, Any], schedule_items: List[Dict[str, Any]], now: float) -> go.Figure:
    sections = [s.get("id") for s in state.get("sections", [])]
    occ = _active_sections(schedule_items, now)
    # Build a simple horizontal line per section, color if occupied
    fig = go.Figure()
    y_positions = {sid: i for i, sid in enumerate(sections)}
    occupied_total = 0
    for sid in sections:
        y = y_positions[sid]
        color = "#2ecc71" if sid not in occ else "#e74c3c"
        width = 6 if sid not in occ else 10
        label = sid if sid not in occ else f"{sid} ({', '.join(occ[sid])})"
        if sid in occ:
            occupied_total += 1
        fig.add_trace(go.Scatter(
            x=[0, 1], y=[y, y], mode="lines",
            line=dict(color=color, width=width),
            hovertemplate=f"Section={sid}<br>Occupied by={', '.join(occ.get(sid, []))}<extra></extra>",
            showlegend=False,
            name=label,
        ))
    # Add legend markers manually
    fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers", marker=dict(color="#e74c3c"), name="Occupied"))
    fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers", marker=dict(color="#2ecc71"), name="Free"))
    fig.update_yaxes(
        tickmode="array",
        tickvals=list(y_positions.values()),
        ticktext=sections,
    )
    fig.update_xaxes(range=[0, 1], showticklabels=False)
    fig.update_layout(
        title=f"Track Schematic – {occupied_total}/{len(sections)} occupied",
        height=300,
        margin=dict(l=40, r=10, t=60, b=10),
    )
    return fig
