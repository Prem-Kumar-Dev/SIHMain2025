import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from typing import Any, Dict, List
import pandas as pd
import plotly.express as px


def render_gantt(gantt: List[Dict[str, Any]], lateness_map: Dict[str, int] | None = None, last_section_map: Dict[str, str] | None = None):
    df = pd.DataFrame(gantt)
    lateness_map = lateness_map or {}
    last_section_map = last_section_map or {}

    def compute_lateness(row):
        t = row.get("train")
        sec = row.get("section")
        if t in lateness_map and last_section_map.get(t) == sec:
            return int(lateness_map.get(t, 0))
        return None

    df["lateness_s"] = df.apply(compute_lateness, axis=1)
    fig = px.timeline(
        df,
        x_start="start",
        x_end="end",
        y="train",
        color="section",
        hover_data=["lateness_s"],
        custom_data=["section", "lateness_s"],
    )
    fig.update_yaxes(autorange="reversed")
    fig.update_traces(hovertemplate="Train=%{y}<br>Section=%{customdata[0]}<br>Start=%{x}<br>End=%{x_end}<br>Lateness(s)=%{customdata[1]}")
    return fig
