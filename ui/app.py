import json
import os
from typing import Any, Dict
import streamlit as st
import pandas as pd
import plotly.express as px
import httpx

st.set_page_config(page_title="SIH Train Scheduler", layout="wide")

# Prefer environment variable to avoid secrets.toml warnings in dev
API_BASE = os.environ.get("API_BASE", "http://localhost:8000")
st.title("SIH Train Scheduler – What-if Gantt & Scenarios")

col1, col2 = st.columns(2)
with col1:
    solver = st.selectbox("Solver", ["greedy", "milp"], index=0)
with col2:
    run_btn = st.button("Run Scenario", type="primary")

otp_tolerance = st.number_input("OTP Tolerance (seconds)", min_value=0, value=0, step=30, help="Count trains as on-time if lateness is within this tolerance")

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
        r = client.post(f"{API_BASE}/whatif", json=payload, params={"solver": solver, "otp_tolerance": int(otp_tolerance)})
        if r.status_code != 200:
            st.error(f"API error: {r.status_code} {r.text}")
            st.stop()
        data = r.json()

    gantt = data.get("gantt", [])
    lateness_map = data.get("lateness_by_train", {})
    if not gantt:
        st.warning("No schedule returned.")
        st.stop()

    df = pd.DataFrame(gantt)
    # Add lateness for last-section bars using payload's declared last section per train
    try:
        payload = json.loads(payload_text)
    except Exception:
        payload = None
    last_section_map = {}
    if isinstance(payload, dict):
        for tr in payload.get("trains", []):
            if isinstance(tr, dict) and tr.get("route_sections"):
                last_section_map[tr.get("id")] = tr["route_sections"][-1]
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
    st.plotly_chart(fig, use_container_width=True)

    # Lateness table if available
    if lateness_map:
        st.subheader("Per-train Lateness (s)")
        lat_df = pd.DataFrame([
            {"train_id": k, "lateness_s": int(v)} for k, v in lateness_map.items()
        ]).sort_values(by=["lateness_s", "train_id"]) 
        st.dataframe(lat_df, use_container_width=True)

    # Fetch KPIs
    with httpx.Client(timeout=30) as client:
        rk = client.post(f"{API_BASE}/kpis", json=payload, params={"solver": solver, "otp_tolerance": int(otp_tolerance)})
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
with sc_cols[3]:
    limit = st.number_input("Page Size", min_value=1, max_value=100, value=10, step=1)
offset = st.number_input("Offset", min_value=0, value=0, step=1)

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

name_col, comment_col = st.columns(2)
with name_col:
    run_name = st.text_input("Run Name (optional)")
with comment_col:
    run_comment = st.text_input("Run Comment (optional)")

run_saved = st.button("Run Selected Scenario")

if run_saved and selected_sid_str != "-":
    sid = int(selected_sid_str)
    with httpx.Client(timeout=60) as client:
        rr = client.post(
            f"{API_BASE}/scenarios/{sid}/run",
            params={"solver": solver, "name": run_name or None, "comment": run_comment or None, "otp_tolerance": int(otp_tolerance)},
        )
        if rr.status_code == 200:
            st.info(f"Run created with run_id={rr.json().get('run_id')}")
        else:
            st.error(f"Run failed: {rr.status_code} {rr.text}")

# List runs for selected scenario
if selected_sid_str != "-":
    sid = int(selected_sid_str)
    with httpx.Client(timeout=30) as client:
        rl = client.get(f"{API_BASE}/scenarios/{sid}/runs", params={"limit": int(limit), "offset": int(offset)})
        if rl.status_code == 200:
            runs = rl.json().get("items", [])
            st.subheader("Runs for Scenario")
            st.dataframe(runs)
            col_r1, col_r2, col_r3 = st.columns(3)
            with col_r1:
                del_scn = st.button("Delete Scenario", type="secondary")
            with col_r2:
                del_run = st.button("Delete Latest Run")
            with col_r3:
                export_csv = st.button("Download Latest Run CSV")
            lat_csv_btn = st.button("Download Lateness CSV")
            # Optionally fetch details for the first run
            if runs:
                rid = runs[0].get("id")
                rd = client.get(f"{API_BASE}/runs/{rid}")
                if rd.status_code == 200:
                    st.subheader("Latest Run (Full Details)")
                    run_full = rd.json().get("run")
                    st.json(run_full)
                    # Actions
                    if del_run:
                        rr = client.delete(f"{API_BASE}/runs/{rid}")
                        if rr.status_code == 200 and rr.json().get("deleted"):
                            st.success("Latest run deleted. Click Refresh List.")
                        else:
                            st.error("Failed to delete run")
                    if del_scn:
                        rsd = client.delete(f"{API_BASE}/scenarios/{sid}")
                        if rsd.status_code == 200 and rsd.json().get("deleted"):
                            st.success("Scenario deleted. Click Refresh List.")
                        else:
                            st.error("Failed to delete scenario")
                    if export_csv:
                        # Build CSV from schedule
                        import io, csv
                        buf = io.StringIO()
                        writer = csv.DictWriter(buf, fieldnames=["train_id", "section_id", "entry", "exit"])
                        writer.writeheader()
                        for row in run_full.get("schedule", []):
                            writer.writerow({
                                "train_id": row.get("train_id"),
                                "section_id": row.get("section_id"),
                                "entry": row.get("entry"),
                                "exit": row.get("exit"),
                            })
                        st.download_button(
                            "Download CSV",
                            data=buf.getvalue(),
                            file_name=f"scenario_{sid}_run_{rid}.csv",
                            mime="text/csv",
                        )
                    if lat_csv_btn:
                        # Export lateness per train from KPIs if present
                        import io, csv
                        buf2 = io.StringIO()
                        # Attempt to read lateness_by_train from KPIs or recompute if not present
                        lateness_map = {}
                        kpis = run_full.get("kpis", {}) or {}
                        if isinstance(kpis, dict) and "lateness_by_train" in kpis:
                            lateness_map = kpis.get("lateness_by_train") or {}
                        # Fallback: compute from schedule and payload if available in run
                        if not lateness_map:
                            try:
                                payload = run_full.get("input_payload")
                                schedule = run_full.get("schedule", [])
                                # Build last-section map
                                last_map = {}
                                if isinstance(payload, dict):
                                    for tr in payload.get("trains", []):
                                        if isinstance(tr, dict) and tr.get("route_sections"):
                                            last_map[tr.get("id")] = tr["route_sections"][-1]
                                            # compute entry to last section
                                for tr in payload.get("trains", []):
                                    if tr.get("due_time") is not None and tr.get("id") in last_map:
                                        last = last_map[tr.get("id")]
                                        entries = [it.get("entry") for it in schedule if it.get("train_id") == tr.get("id") and it.get("section_id") == last]
                                        if entries:
                                            lateness_map[tr.get("id")] = max(0, int(entries[0]) - int(tr.get("due_time")))
                            except Exception:
                                pass
                        writer2 = csv.DictWriter(buf2, fieldnames=["train_id", "lateness_s"])
                        writer2.writeheader()
                        for k, v in (lateness_map or {}).items():
                            writer2.writerow({"train_id": k, "lateness_s": int(v)})
                        st.download_button(
                            "Download Lateness CSV",
                            data=buf2.getvalue(),
                            file_name=f"scenario_{sid}_run_{rid}_lateness.csv",
                            mime="text/csv",
                        )
