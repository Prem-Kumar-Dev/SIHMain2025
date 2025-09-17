import json
from typing import Any, Dict
import streamlit as st
import pandas as pd
import plotly.express as px
import httpx

API_BASE = st.secrets.get("API_BASE", "http://localhost:8000")

st.set_page_config(page_title="SIH Train Scheduler", layout="wide")
st.title("SIH Train Scheduler – What-if Gantt")

col1, col2 = st.columns(2)
with col1:
    solver = st.selectbox("Solver", ["greedy", "milp"], index=0)
with col2:
    run_btn = st.button("Run Scenario", type="primary")

def default_payload() -> Dict[str, Any]:
    return {
        "sections": [
            {"id": "S1", "headway_seconds": 120, "traverse_seconds": 300},
            {"id": "S2", "headway_seconds": 120, "traverse_seconds": 240}
        ],
        "trains": [
            {"id": "T1", "priority": 2, "planned_departure": 0,   "route_sections": ["S1", "S2"]},
            {"id": "T2", "priority": 3, "planned_departure": 60,  "route_sections": ["S1", "S2"]},
            {"id": "T3", "priority": 1, "planned_departure": 120, "route_sections": ["S1", "S2"]}
        ]
    }

payload_text = st.text_area("Scenario JSON", json.dumps(default_payload(), indent=2), height=300)

if run_btn:
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError as e:
        st.error(f"Invalid JSON: {e}")
        st.stop()

    with httpx.Client(timeout=30) as client:
        r = client.post(f"{API_BASE}/whatif", json=payload, params={"solver": solver})
        if r.status_code != 200:
            st.error(f"API error: {r.status_code} {r.text}")
            st.stop()
        data = r.json()

    gantt = data.get("gantt", [])
    if not gantt:
        st.warning("No schedule returned.")
        st.stop()

    df = pd.DataFrame(gantt)
    fig = px.timeline(df, x_start="start", x_end="end", y="train", color="section")
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(fig, use_container_width=True)

    # Fetch KPIs
    with httpx.Client(timeout=30) as client:
        rk = client.post(f"{API_BASE}/kpis", json=payload, params={"solver": solver})
        if rk.status_code == 200:
            st.subheader("KPIs")
            st.json(rk.json()["kpis"])
        else:
            st.warning("KPIs unavailable")
