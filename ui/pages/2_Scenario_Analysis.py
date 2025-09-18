import io
import csv
import streamlit as st
import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from ui.api_client import ApiClient
from ui.state_manager import ensure_defaults, get_state_payload, set_state_payload, default_payload
from ui.components.gantt_chart import render_gantt
from ui.components.scenario_editor import editor
from ui.components.kpi_display import render_kpis


st.set_page_config(page_title="Scenario Analysis", layout="wide")
ensure_defaults()
api = ApiClient()

st.title("Scenario Analysis")

payload = editor("Scenario JSON", get_state_payload())
set_state_payload(payload)

col = st.columns([1, 1, 2])
with col[0]:
    solver = st.selectbox("Solver", ["greedy", "milp"], index=0, key="sc_solver")
with col[1]:
    otp_tolerance = st.number_input("OTP Tolerance (s)", min_value=0, value=0, step=30, key="sc_otp")
with col[2]:
    run_btn = st.button("Run What-If", type="primary")

if run_btn:
    try:
        result = api.run_whatif(payload, solver=solver, otp_tolerance=int(otp_tolerance))
        gantt = result.get("gantt", [])
        lateness_map = result.get("lateness_by_train", {})
        # last section mapping from payload
        last_section_map = {}
        for tr in payload.get("trains", []):
            if isinstance(tr, dict) and tr.get("route_sections"):
                last_section_map[tr.get("id")] = tr["route_sections"][-1]
        if gantt:
            st.plotly_chart(render_gantt(gantt, lateness_map, last_section_map), use_container_width=True)
        else:
            st.warning("No schedule returned")
        # KPIs
        k = api.get_kpis(payload, solver=solver, otp_tolerance=int(otp_tolerance))
        render_kpis(k.get("kpis", {}))
    except Exception as e:
        st.error(f"What-if failed: {e}")

st.markdown("---")
st.header("Model Benchmark (Baseline vs MLP vs GNN)")
with st.expander("Benchmark Panel", expanded=False):
    st.write("Runs /predict for each model kind and compares predicted delay minutes against proxy ground truth (current_delay_minutes field if present). This is a lightweight, same-state diagnostic, not a historical evaluation.")
    bench_cols = st.columns([1,1,1,1])
    run_bench = bench_cols[0].button("Run Benchmark", key="run_benchmark")
    show_raw = bench_cols[1].toggle("Show Raw JSON", value=False, key="bench_show_raw")
    use_auto = bench_cols[2].toggle("Include Auto", value=False, key="bench_auto")
    sort_metric = bench_cols[3].selectbox("Sort By", ["mae", "max_error", "mean_pred"], index=0)
    if run_bench:
        try:
            models = ["baseline", "mlp", "gnn"] + (["auto"] if use_auto else [])
            results = []
            import requests, statistics
            truth_map = {}
            # Build truth map (proxy) from trains
            for tr in payload.get("trains", []):
                tid = tr.get("id")
                if isinstance(tid, str):
                    truth_map[tid] = float(tr.get("current_delay_minutes", 0.0) or 0.0)
            for mk in models:
                try:
                    r = requests.post(f"{api.base_url}/predict", json=payload, params={"model": mk}, timeout=api.timeout)
                    r.raise_for_status()
                    pj = r.json()
                except Exception as e:
                    pj = {"error": str(e)}
                preds = pj.get("predicted_delay_minutes", {}) if isinstance(pj, dict) else {}
                errors = []
                for tid, tval in truth_map.items():
                    p = float(preds.get(tid, 0.0) or 0.0)
                    errors.append(abs(p - tval))
                mae = statistics.fmean(errors) if errors else 0.0
                max_err = max(errors) if errors else 0.0
                mean_pred = statistics.fmean(preds.values()) if preds else 0.0
                results.append({
                    "model": mk,
                    "mae": round(mae, 3),
                    "max_error": round(max_err, 3),
                    "mean_pred": round(mean_pred, 3),
                    "n_trains": len(truth_map),
                    "used": pj.get("model_used"),
                })
            # sort
            results.sort(key=lambda d: d.get(sort_metric, 0.0))
            import pandas as _pd
            st.dataframe(_pd.DataFrame(results))
            if show_raw:
                st.subheader("Raw Prediction Payloads")
                # Re-run quickly (avoid storing large objects long-term)
                for mk in models:
                    try:
                        r = requests.post(f"{api.base_url}/predict", json=payload, params={"model": mk}, timeout=api.timeout)
                        r.raise_for_status()
                        st.caption(f"Model={mk}")
                        st.json(r.json())
                    except Exception as e:
                        st.error(f"Predict {mk} failed: {e}")
        except Exception as e:
            st.error(f"Benchmark failed: {e}")

st.markdown("---")
st.header("Scenarios (Persisted)")

name = st.text_input("New Scenario Name", value="scenario-1")
if st.button("Save Scenario"):
    try:
        r = api.save_scenario(payload, name)
        st.success(f"Saved scenario with id={r.get('id')}")
    except Exception as e:
        st.error(f"Save failed: {e}")

sc_list = api.get_scenarios().get("items", [])
sid_opts = ["-"] + [str(s.get("id")) for s in sc_list]
sid_sel = st.selectbox("Select Scenario", options=sid_opts, index=0)

if sid_sel != "-":
    sid = int(sid_sel)
    runs = api.list_runs(sid).get("items", [])
    st.dataframe(runs)
    if runs:
        rid = runs[0].get("id")
        rd = api.get_run(rid).get("run", {})
        st.subheader("Latest Run (Full Details)")
        st.json(rd)
        c1, c2, c3, c4 = st.columns(4)
        if c1.button("Delete Scenario"):
            try:
                d = api.delete_scenario(sid)
                st.success("Scenario deleted")
            except Exception as e:
                st.error(f"Delete scenario failed: {e}")
        if c2.button("Delete Latest Run"):
            try:
                d = api.delete_run(rid)
                st.success("Run deleted")
            except Exception as e:
                st.error(f"Delete run failed: {e}")
        if c3.button("Download Schedule CSV"):
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=["train_id", "section_id", "entry", "exit"])
            writer.writeheader()
            for row in rd.get("schedule", []):
                writer.writerow({
                    "train_id": row.get("train_id"),
                    "section_id": row.get("section_id"),
                    "entry": row.get("entry"),
                    "exit": row.get("exit"),
                })
            st.download_button("Download CSV", data=buf.getvalue(), file_name=f"scenario_{sid}_run_{rid}.csv", mime="text/csv")
        if c4.button("Download Lateness CSV"):
            # call backend CSV endpoint for accuracy
            try:
                import requests
                url = f"{api.base_url}/runs/{rid}/lateness.csv"
                resp = requests.get(url, timeout=30)
                resp.raise_for_status()
                st.download_button("Download Lateness CSV", data=resp.text, file_name=f"scenario_{sid}_run_{rid}_lateness.csv", mime="text/csv")
            except Exception as e:
                st.error(f"CSV download failed: {e}")
