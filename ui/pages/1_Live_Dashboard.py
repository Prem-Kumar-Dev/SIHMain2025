import streamlit as st
import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from ui.api_client import ApiClient
from ui.state_manager import ensure_defaults, get_state_payload, set_state_payload
from ui.components.gantt_chart import render_gantt
from ui.components.kpi_display import render_kpis
import pandas as pd
import plotly.express as px
import time


st.set_page_config(page_title="Live Dashboard", layout="wide")
ensure_defaults()
api = ApiClient()

st.title("Live Dashboard")

col_top = st.columns([1, 1, 1, 2])
with col_top[0]:
    use_live = st.toggle("Use Live Feed", value=False)
with col_top[1]:
    max_trains = st.number_input("Max Trains", min_value=1, max_value=500, value=50, step=1)
with col_top[2]:
    solver = st.selectbox("Solver", ["greedy", "milp"], index=0)
with col_top[3]:
    otp_tolerance = st.number_input("OTP Tolerance (s)", min_value=0, value=0, step=30)

if st.button("Refresh Live Data"):
    try:
        snap = api.get_live_snapshot(state=get_state_payload(), use_live=use_live, max_trains=int(max_trains))
        state = snap.get("state") or {}
        set_state_payload(state)
    except Exception as e:
        st.error(f"Snapshot failed: {e}")

state = get_state_payload()
if not state:
    st.info("No state available yet. Click 'Refresh Live Data'.")
    st.stop()

st.subheader("Predictions & Conflicts")
try:
    pred = api.predict_delays(state)
    conflicts = pred.get("predicted_conflicts", [])
    st.json(pred)
except Exception as e:
    st.error(f"Prediction failed: {e}")
    conflicts = []

st.subheader("Resolution Advisory")
if conflicts:
    try:
        res = api.resolve_conflicts(state, conflicts, solver=solver, otp_tolerance=int(otp_tolerance))
        render_kpis(res.get("kpis", {}))
        st.caption("Suggested action derived from schedule ordering and headways. Controller remains in control.")
    except Exception as e:
        st.error(f"Resolution failed: {e}")
else:
    st.info("No conflicts detected.")

# Live Movement (experimental): derive current positions from schedule
st.markdown("---")
st.subheader("Live Train Movement (Derived)")
try:
    sched = api.schedule(state, solver=solver)
    items = sched.get("schedule", [])
    if items:
        # Determine time bounds from schedule
        entries = [it.get("entry") for it in items if it.get("entry") is not None]
        exits = [it.get("exit") for it in items if it.get("exit") is not None]
        if not entries or not exits:
            raise ValueError("Schedule missing entry/exit times")
        tmin, tmax = min(entries), max(exits)

        ctime_cols = st.columns([1, 3])
        with ctime_cols[0]:
            use_real_clock = st.toggle("Use Real Clock", value=False, help="If off, use the slider below to scrub through the schedule timeline.")
        if use_real_clock:
            now = time.time()
        else:
            with ctime_cols[1]:
                now = st.slider("Current Time", min_value=float(tmin), max_value=float(tmax), value=float(tmin))
        rows = []
        for it in items:
            start = it.get("entry")
            end = it.get("exit")
            if start is None or end is None:
                continue
            # If the train is currently traversing this section, interpolate position 0..1
            if start <= now <= end:
                frac = (now - start) / max(1, (end - start))
                rows.append({
                    "train_id": it.get("train_id"),
                    "section_id": it.get("section_id"),
                    "progress": max(0.0, min(1.0, frac)),
                })
        dfm = pd.DataFrame(rows)
        if not dfm.empty:
            figm = px.scatter(
                dfm, x="progress", y="section_id", color="train_id",
                range_x=[0, 1],
                labels={"progress": "Section Progress (0=start, 1=end)"},
                title="Current Train Positions by Section"
            )
            st.plotly_chart(figm, use_container_width=True)
        else:
            st.caption("No trains currently traversing a section at this moment.")
    else:
        st.caption("No schedule available to derive positions.")
except Exception as e:
    st.error(f"Live movement render failed: {e}")
