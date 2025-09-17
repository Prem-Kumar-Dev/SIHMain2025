import json
from typing import Any, Dict
import streamlit as st
import pandas as pd
import plotly.express as px
import httpx

API_BASE = st.secrets.get("API_BASE", "http://localhost:8000")

st.set_page_config(page_title="SIH Train Scheduler", layout="wide")
st.title("SIH Train Scheduler – What-if Gantt & Scenarios")

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

# Scenarios Panel
st.markdown("---")
st.header("Scenarios (Persisted)")
sc_cols = st.columns([2, 1, 1, 2])
with sc_cols[0]:
    new_name = st.text_input("New Scenario Name", value="scenario-1")
with sc_cols[1]:
    save_btn = st.button("Save Scenario")
with sc_cols[2]:
    refresh_btn = st.button("Refresh List")

if save_btn:
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError as e:
        st.error(f"Invalid JSON: {e}")
    else:
        with httpx.Client(timeout=30) as client:
            r = client.post(f"{API_BASE}/scenarios", json={"name": new_name, "payload": payload})
            if r.status_code == 200:
                st.success(f"Saved scenario with id={r.json().get('id')}")
            else:
                st.error(f"Failed to save scenario: {r.status_code} {r.text}")

# Fetch scenarios
scenarios = []
with httpx.Client(timeout=30) as client:
    rs = client.get(f"{API_BASE}/scenarios")
    if rs.status_code == 200:
        scenarios = rs.json().get("items", [])

sc_ids = [str(s.get("id")) for s in scenarios]
selected_sid_str = st.selectbox("Select Scenario ID", options=["-"] + sc_ids, index=0)

run_saved = st.button("Run Selected Scenario")

if run_saved and selected_sid_str != "-":
    sid = int(selected_sid_str)
    with httpx.Client(timeout=60) as client:
        rr = client.post(f"{API_BASE}/scenarios/{sid}/run", params={"solver": solver})
        if rr.status_code == 200:
            st.info(f"Run created with run_id={rr.json().get('run_id')}")
        else:
            st.error(f"Run failed: {rr.status_code} {rr.text}")

# List runs for selected scenario
if selected_sid_str != "-":
    sid = int(selected_sid_str)
    with httpx.Client(timeout=30) as client:
        rl = client.get(f"{API_BASE}/scenarios/{sid}/runs")
        if rl.status_code == 200:
            runs = rl.json().get("items", [])
            st.subheader("Runs for Scenario")
            st.dataframe(runs)
            # Optionally fetch details for the first run
            if runs:
                rid = runs[0].get("id")
                rd = client.get(f"{API_BASE}/runs/{rid}")
                if rd.status_code == 200:
                    st.subheader("Latest Run (Full Details)")
                    st.json(rd.json().get("run"))
