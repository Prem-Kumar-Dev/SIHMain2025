import streamlit as st
import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from ui.api_client import ApiClient
from ui.state_manager import ensure_defaults, get_state_payload, set_state_payload, add_hold_action, clear_pending_holds
from ui.components.gantt_chart import render_gantt
from ui.components.kpi_display import render_kpis
from ui.components.time_distance import render_time_distance
from ui.components.track_schematic import render_track_schematic
import pandas as pd
import plotly.express as px
import time


# NOTE: Page config should be set once in ui/app.py for multipage apps.
# Do NOT call st.set_page_config() here to avoid Streamlit warnings.
ensure_defaults()
api = ApiClient()

st.title("Live Dashboard")

col_top = st.columns([1, 1, 1, 2, 1])
with col_top[0]:
    use_live = st.toggle("Use Live Feed", value=False)
with col_top[1]:
    max_trains = st.number_input("Max Trains", min_value=1, max_value=500, value=50, step=1)
with col_top[2]:
    solver = st.selectbox("Solver", ["greedy", "milp"], index=0)
with col_top[3]:
    otp_tolerance = st.number_input("OTP Tolerance (s)", min_value=0, value=0, step=30)
with col_top[4]:
    model_kind = st.selectbox("Model", ["auto", "baseline", "mlp", "gnn"], index=0, help="Choose which predictor the backend should use for /predict.")

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
    pred = api.predict_delays(state, model=model_kind)
    conflicts = pred.get("predicted_conflicts", [])
    st.json(pred)
except Exception as e:
    st.error(f"Prediction failed: {e}")
    conflicts = []

st.subheader("Resolution Advisory")
schedule_items = []
if conflicts:
    try:
        res = api.resolve_conflicts(state, conflicts, solver=solver, otp_tolerance=int(otp_tolerance))
        render_kpis(res.get("kpis", {}))
        st.caption("Suggested action derived from schedule ordering and headways. Controller remains in control.")
        schedule_items = res.get("schedule", []) or []

        # Basic advisory text (first conflict focus)
        with st.expander("Advisory Actions", expanded=True):
            if conflicts:
                c0 = conflicts[0]
                trains = ", ".join(c0.get("trains", []))
                sid = c0.get("section_id")
                st.write(f"Conflict predicted at section {sid} between: {trains}.")
            colA, colB, colC = st.columns(3)
            if colA.button("Accept Recommendation"):
                st.success("Recommendation accepted (no-op placeholder).")
            if colC.button("Reject"):
                st.warning("Recommendation rejected. You can adjust parameters and recompute.")

            # Modify dialog section
            with colB:
                show_mod = st.toggle("Modify", value=False, help="Enable to queue holds for multiple trains")
            if show_mod:
                mod_col1, mod_col2, mod_col3, mod_col4 = st.columns([2,2,1,1])
                train_ids = [t.get("id") for t in state.get("trains", [])]
                with mod_col1:
                    sel_train = st.selectbox("Train", train_ids, key="mod_train")
                with mod_col2:
                    add_hold = st.number_input("Hold (s)", min_value=0, value=60, step=30, key="mod_hold")
                with mod_col3:
                    queue_btn = st.button("Queue", key="queue_hold")
                with mod_col4:
                    apply_all_btn = st.button("Apply All", key="apply_all_holds")

                if queue_btn and sel_train:
                    add_hold_action(sel_train, int(add_hold))
                    st.info(f"Queued {add_hold}s hold for {sel_train}")
                if apply_all_btn:
                    # Call backend /adjust with current payload and queued holds
                    holds = list(getattr(st.session_state, 'pending_holds', []))
                    if not holds:
                        st.info("No holds queued.")
                    else:
                        try:
                            adj_body = {
                                "state": get_state_payload(),
                                "holds": holds,
                                "solver": solver,
                                "otp_tolerance": int(otp_tolerance),
                            }
                            import requests, json as _json
                            r = requests.post(f"{api.base_url}/adjust", json=adj_body, timeout=api.timeout)
                            r.raise_for_status()
                            adj = r.json()
                            k = adj.get("kpis", {})
                            if k:
                                render_kpis(k)
                            schedule_items[:] = adj.get("schedule", []) or []
                            st.success("Adjustment applied via backend /adjust.")
                            clear_pending_holds()
                        except Exception as e:
                            st.error(f"Adjustment failed: {e}")
                # Show pending queue
                if hasattr(st.session_state, 'pending_holds') and st.session_state.pending_holds:
                    st.caption("Pending Holds Queue")
                    st.table(st.session_state.pending_holds)
                if hasattr(st.session_state, 'action_log') and st.session_state.action_log:
                    with st.expander("Action Log"):
                        for line in reversed(st.session_state.action_log[-50:]):
                            st.write(line)
    except Exception as e:
        st.error(f"Resolution failed: {e}")
else:
    st.info("No conflicts detected.")
    # Fall back to computing a schedule directly to visualize
    try:
        sched_direct = api.schedule(state, solver=solver)
        schedule_items = sched_direct.get("schedule", []) or []
    except Exception as e:
        st.error(f"Schedule computation failed: {e}")

# Render a Schedule Gantt if we have items (from resolve or direct schedule)
st.markdown("---")
st.subheader("Schedule Gantt")
try:
    if schedule_items:
        gantt_rows = []
        for it in schedule_items:
            start = it.get("entry")
            end = it.get("exit")
            if start is None or end is None:
                continue
            gantt_rows.append({
                "start": start,
                "end": end,
                "train": it.get("train_id"),
                "section": it.get("section_id"),
            })
        if gantt_rows:
            fig_g = render_gantt(gantt_rows)
            st.plotly_chart(fig_g, use_container_width=True)
        else:
            st.caption("No timeline segments to plot from schedule.")
    else:
        st.caption("No schedule available to render Gantt.")
except Exception as e:
    st.error(f"Gantt render failed: {e}")

# Time-Distance and Live Movement
st.markdown("---")
st.subheader("Predictive Time-Distance")
try:
    # Reuse existing schedule if available, else fetch
    items = schedule_items
    if not items:
        sched = api.schedule(state, solver=solver)
        items = sched.get("schedule", [])
    if items:
        st.plotly_chart(render_time_distance(state, items, conflicts), use_container_width=True)
    else:
        st.caption("No schedule available for predictive overlay.")
except Exception as e:
    st.error(f"Time-distance render failed: {e}")

st.subheader("Live Train Movement (Derived)")
try:
    # Reuse existing schedule if available, else fetch
    items = schedule_items
    if not items:
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
                # Provide a reasonable step to make the slider responsive
                tmin_f, tmax_f = float(tmin), float(tmax)
                step = max((tmax_f - tmin_f) / 100.0, 1.0)
                now = st.slider("Current Time", min_value=tmin_f, max_value=tmax_f, value=tmin_f, step=step)
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

st.subheader("Track Schematic")
try:
    items = schedule_items or (api.schedule(state, solver=solver).get("schedule", []))
    if items:
        # Reuse the same 'now' as above if available, else default to current time
        now_val = 'now' in locals() and now or time.time()
        figt = render_track_schematic(state, items, now_val)
        st.plotly_chart(figt, use_container_width=True)
    else:
        st.caption("No schedule to render schematic.")
except Exception as e:
    st.error(f"Track schematic render failed: {e}")
