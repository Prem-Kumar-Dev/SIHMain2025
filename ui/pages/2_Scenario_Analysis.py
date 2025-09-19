import io
import csv
import time
import json as _json
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

# Large Scenario Utilities
util_cols = st.columns([1,1,1,2])
with util_cols[0]:
    up_file = st.file_uploader("Load Scenario JSON", type=["json"], help="Upload a scenario file generated externally or via the generator below.")
    if up_file is not None:
        try:
            import json as _jsonu
            data = _jsonu.loads(up_file.read())
            if isinstance(data, dict) and data.get("sections") and data.get("trains"):
                set_state_payload(data)
                st.success(f"Loaded scenario: {len(data['sections'])} sections, {len(data['trains'])} trains.")
            else:
                st.error("Invalid scenario structure (expect keys: sections, trains).")
        except Exception as e:
            st.error(f"Failed to parse JSON: {e}")
with util_cols[1]:
    if st.button("Reset to Default", help="Reset scenario editor to a minimal default payload"):
        set_state_payload(default_payload())
        st.experimental_rerun()
with util_cols[2]:
    with st.expander("Generate Synthetic Scenario", expanded=False):
        g_cols = st.columns(4)
        g_tr = g_cols[0].number_input("Trains", min_value=1, max_value=5000, value=200, step=50, help="Total trains to synthesize")
        g_sec = g_cols[1].number_input("Sections", min_value=1, max_value=1000, value=40, step=10, help="Infrastructure sections")
        g_route = g_cols[2].number_input("Avg Route Len", min_value=1, max_value=200, value=8, step=1, help="Approx mean contiguous route length")
        g_stagger = g_cols[3].number_input("Stagger (s)", min_value=0, max_value=3600, value=300, step=30, help="Max random extra departure seconds")
        g_seed = st.number_input("Seed", min_value=0, max_value=999999, value=42, step=1)
        g_due = st.toggle("Include Due Times", value=True, help="Assign due_time to ~50% of trains")
        gen_btn = st.button("Generate Scenario", key="gen_large_scenario")
        if gen_btn:
            import random, math
            random.seed(int(g_seed))
            sections = []
            for i in range(int(g_sec)):
                sections.append({
                    "id": f"S{i+1}",
                    "headway_seconds": random.randint(60, 240),
                    "traverse_seconds": random.randint(90, 300),
                    "block_windows": []
                })
            sec_ids = [s['id'] for s in sections]
            trains = []
            for t in range(int(g_tr)):
                base_dep = t * 30 + random.randint(0, int(g_stagger))
                if g_route >= len(sec_ids):
                    route = sec_ids[:]
                else:
                    length = max(1, min(len(sec_ids), int(random.gauss(g_route, 1))))
                    start = random.randint(0, max(0, len(sec_ids) - length))
                    route = sec_ids[start:start+length]
                tr = {
                    "id": f"T{t+1}",
                    "priority": random.randint(1,3),
                    "planned_departure": base_dep,
                    "route_sections": route
                }
                if g_due and random.random() < 0.5:
                    est = base_dep + sum(random.randint(90, 240) for _ in route)
                    tr["due_time"] = est + random.randint(-120, 180)
                trains.append(tr)
            payload_gen = {"sections": sections, "trains": trains}
            set_state_payload(payload_gen)
            st.success(f"Generated scenario with {len(sections)} sections & {len(trains)} trains.")
        # Download current generated scenario if available
        if st.session_state.get('payload') and isinstance(st.session_state.payload, dict):
            import json as _jsond
            st.download_button(
                "Download Current Scenario JSON",
                data=_jsond.dumps(st.session_state.payload, indent=2),
                file_name=f"scenario_{len(st.session_state.payload.get('trains', []))}x{len(st.session_state.payload.get('sections', []))}.json",
                mime="application/json"
            )
with util_cols[3]:
    filt_exp = st.expander("Plot Filters", expanded=False)
    with filt_exp:
        max_plot_trains = st.number_input("Max Trains to Plot (Gantt)", min_value=10, max_value=2000, value=300, step=10, help="Limit number of trains shown to keep Plotly responsive.")
        train_prefix = st.text_input("Train ID Prefix Filter", value="", help="If set, only trains whose id starts with this prefix are used in Gantt.")
        st.session_state["plot_filters"] = {"max_trains": int(max_plot_trains), "prefix": train_prefix.strip()}

payload = editor("Scenario JSON", get_state_payload())
set_state_payload(payload)

# Quick sample loader for debugging
sample_col = st.columns([1,1,6])
with sample_col[0]:
    if st.button("Load Sample", help="Load a minimal sample scenario"):
        sample = {
            "sections": [
                {"id": "S1", "headway_seconds": 120, "traverse_seconds": 100},
                {"id": "S2", "headway_seconds": 120, "traverse_seconds": 140}
            ],
            "trains": [
                {"id": "A", "priority": 1, "planned_departure": 0, "route_sections": ["S1", "S2"]},
                {"id": "B", "priority": 2, "planned_departure": 60, "route_sections": ["S1", "S2"]},
                {"id": "C", "priority": 3, "planned_departure": 120, "route_sections": ["S1"]}
            ]
        }
        set_state_payload(sample)
        st.experimental_rerun()

col = st.columns([1, 1, 2])
with col[0]:
    solver = st.selectbox("Solver", ["greedy", "milp"], index=0, key="sc_solver")
with col[1]:
    otp_tolerance = st.number_input("OTP Tolerance (s)", min_value=0, value=0, step=30, key="sc_otp")
with col[2]:
    run_btn = st.button("Run What-If", type="primary")

# Initialize session storage for last what-if
if "last_whatif" not in st.session_state:
    st.session_state.last_whatif = None
if "last_whatif_kpis" not in st.session_state:
    st.session_state.last_whatif_kpis = None
if "last_whatif_error" not in st.session_state:
    st.session_state.last_whatif_error = None

if run_btn:
    with st.spinner("Running what-if scenario..."):
        try:
            result = api.run_whatif(payload, solver=solver, otp_tolerance=int(otp_tolerance))
            # Persist raw result
            st.session_state.last_whatif = result
            # Fetch KPIs separately (could be merged later)
            k = api.get_kpis(payload, solver=solver, otp_tolerance=int(otp_tolerance))
            st.session_state.last_whatif_kpis = k.get("kpis", {})
            st.session_state.last_whatif_error = None
            st.success("What-if run complete.")
        except Exception as e:
            st.session_state.last_whatif_error = str(e)
            st.error(f"What-if failed: {e}")

# Render last what-if result if available
if st.session_state.last_whatif:
    result = st.session_state.last_whatif
    gantt = result.get("gantt", [])
    lateness_map = result.get("lateness_by_train", {})
    last_section_map = {}
    for tr in payload.get("trains", []):
        if isinstance(tr, dict) and tr.get("route_sections"):
            last_section_map[tr.get("id")] = tr["route_sections"][-1]
    st.subheader("Latest What-If Schedule")
    if gantt:
        # Apply plot filters
        pf = st.session_state.get("plot_filters", {})
        max_tr = pf.get("max_trains") or 1000
        pref = pf.get("prefix") or ""
        if pref:
            gantt_f = [g for g in gantt if str(g.get("train", "")).startswith(pref)]
        else:
            gantt_f = gantt
        # Cap number of trains by first-seen ordering
        seen = []
        allowed_trains = set()
        for g in gantt_f:
            tid = g.get("train")
            if tid not in allowed_trains:
                seen.append(tid)
                allowed_trains.add(tid)
            if len(seen) >= max_tr:
                break
        if len(allowed_trains) < len({g.get('train') for g in gantt_f}):
            st.caption(f"Showing first {len(allowed_trains)} trains (filtered by prefix/pagination).")
        gantt_f = [g for g in gantt_f if g.get("train") in allowed_trains]
        fig = render_gantt(gantt_f, lateness_map, last_section_map)
        # Detect zero visible bars (all zero-duration) -> Plotly may not show them clearly
        zero_durations = sum(1 for g in gantt if (g.get("end") == g.get("start")))
        st.plotly_chart(fig, use_container_width=True)
        if zero_durations == len(gantt):
            st.info("All schedule intervals have zero duration (start == end); bars may appear invisible. Consider verifying traverse/headway data.")
    else:
        reason = result.get("reason") or "No schedule returned in last what-if result."
        st.warning(reason)
        st.caption(f"What-If returned 0 gantt items; trains={len(payload.get('trains', []))} sections={len(payload.get('sections', []))}")
        # Attempt fallback schedule to help user
        try:
            fallback = api.schedule(payload, solver=solver, otp_tolerance=int(otp_tolerance))
            f_sched = fallback.get("schedule", [])
            if f_sched:
                st.caption("Fallback full schedule (from /schedule):")
                import pandas as _pd
                st.dataframe(_pd.DataFrame(f_sched))
        except Exception as _e:
            st.info(f"Fallback schedule failed: {_e}")
    # Show tabular schedule from what-if if present
    sched_items = result.get("schedule") or []
    if sched_items:
        import pandas as _pd
        st.caption("What-If Schedule Items")
        st.dataframe(_pd.DataFrame(sched_items))
    if st.session_state.last_whatif_kpis:
        render_kpis(st.session_state.last_whatif_kpis)
    with st.expander("Raw What-If Response & KPIs"):
        st.json({"whatif": st.session_state.last_whatif, "kpis": st.session_state.last_whatif_kpis})
    # Diagnostics
    with st.expander("Diagnostics"):
        trains = payload.get("trains", []) if isinstance(payload, dict) else []
        sections = payload.get("sections", []) if isinstance(payload, dict) else []
        st.write({
            "train_count": len(trains),
            "section_count": len(sections),
            "gantt_items": len(gantt),
            "whatif_schedule_items": len(result.get("schedule") or []),
            "lateness_map_size": len(lateness_map),
        })
elif st.session_state.last_whatif_error:
    st.warning(f"Last what-if error: {st.session_state.last_whatif_error}")
else:
    st.caption("Run a What-If to see schedule and KPIs here.")

st.markdown("---")
st.header("Model Benchmark (Baseline vs MLP vs GNN)")
# Initialize benchmark history in session state
if "benchmark_history" not in st.session_state:
    st.session_state.benchmark_history = []  # list of {ts, model_metrics: [{model,..}], config: {...}}
with st.expander("Benchmark Panel", expanded=False):
    st.write("Runs /predict for each model kind and compares predicted delay minutes against proxy ground truth (current_delay_minutes field if present). This is a lightweight, same-state diagnostic, not a historical evaluation.")
    bench_cols = st.columns([1,1,1,1])
    run_bench = bench_cols[0].button("Run Benchmark", key="run_benchmark")
    show_raw = bench_cols[1].toggle("Show Raw JSON", value=False, key="bench_show_raw")
    use_auto = bench_cols[2].toggle("Include Auto", value=False, key="bench_auto")
    sort_metric = bench_cols[3].selectbox("Sort By", ["mae", "rmse", "bias", "max_error", "mean_pred"], index=0)
    adv_cols = st.columns([1,1,1])
    exclude_missing = adv_cols[0].toggle("Exclude Missing Truth", value=True, key="bench_exclude_missing")
    include_mape = adv_cols[1].toggle("Include MAPE", value=False, key="bench_include_mape", help="Only for trains with current_delay_minutes > 0")
    show_ci = adv_cols[2].toggle("Show 95% CI", value=True, key="bench_show_ci", help="Approx normal CI on MAE using stderr = sigma/sqrt(n)")
    hist_cols = st.columns([1,1,2])
    persist_file = hist_cols[0].text_input("Persist History File", value="benchmark_history.json", help="If provided, history will be appended (created if missing). Leave blank to keep in-memory only.")
    plot_history = hist_cols[1].toggle("Show History Plot", value=False, key="bench_plot_history")
    clear_hist = hist_cols[2].button("Clear History", key="bench_clear")
    if clear_hist:
        st.session_state.benchmark_history = []
        if persist_file:
            try:
                open(persist_file, 'w').write('[]')
            except Exception:
                pass
        st.info("Benchmark history cleared.")
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
                abs_errors = []
                sq_errors = []
                signed_errors = []
                mape_terms = []
                considered = 0
                for tid, tval in truth_map.items():
                    # Skip missing when exclude_missing is True and truth is 0 and not actually present in payload
                    present = any(isinstance(tr, dict) and tr.get("id") == tid and "current_delay_minutes" in tr for tr in payload.get("trains", []))
                    if exclude_missing and not present:
                        continue
                    p = float(preds.get(tid, 0.0) or 0.0)
                    err = p - tval
                    signed_errors.append(err)
                    abs_errors.append(abs(err))
                    sq_errors.append(err * err)
                    if include_mape and tval > 0:
                        mape_terms.append(abs(err) / max(1e-9, tval))
                    considered += 1
                mae = statistics.fmean(abs_errors) if abs_errors else 0.0
                rmse = (sum(sq_errors) / len(sq_errors)) ** 0.5 if sq_errors else 0.0
                bias = statistics.fmean(signed_errors) if signed_errors else 0.0
                max_err = max(abs_errors) if abs_errors else 0.0
                mean_pred = statistics.fmean(preds.values()) if preds else 0.0
                mape_val = (statistics.fmean(mape_terms) * 100.0) if mape_terms else 0.0
                # 95% CI for MAE (approx) -> std of abs errors / sqrt(n) * 1.96
                if show_ci and len(abs_errors) > 1:
                    mean_abs = mae
                    var_abs = sum((e - mean_abs) ** 2 for e in abs_errors) / (len(abs_errors) - 1)
                    se = (var_abs ** 0.5) / (len(abs_errors) ** 0.5)
                    ci_low = mae - 1.96 * se
                    ci_high = mae + 1.96 * se
                else:
                    ci_low = ci_high = mae
                result_row = {
                    "model": mk,
                    "mae": round(mae, 3),
                    "rmse": round(rmse, 3),
                    "bias": round(bias, 3),
                    "max_error": round(max_err, 3),
                    "mean_pred": round(mean_pred, 3),
                    "n_trains": len(truth_map),
                    "n_eval": considered,
                    "used": pj.get("model_used"),
                }
                if include_mape:
                    result_row["mape_pct"] = round(mape_val, 2)
                if show_ci:
                    result_row["mae_ci_low"] = round(ci_low, 3)
                    result_row["mae_ci_high"] = round(ci_high, 3)
                results.append(result_row)
            # sort
            results.sort(key=lambda d: d.get(sort_metric, 0.0))
            import pandas as _pd
            st.dataframe(_pd.DataFrame(results))
            # Append to history
            ts = int(time.time())
            hist_entry = {"ts": ts, "metrics": results, "sort": sort_metric, "include_auto": use_auto, "n_trains": len(truth_map), "exclude_missing": exclude_missing, "include_mape": include_mape}
            st.session_state.benchmark_history.append(hist_entry)
            # Persist to file if requested
            if persist_file:
                try:
                    existing = []
                    if os.path.exists(persist_file):
                        with open(persist_file, 'r') as f:
                            existing = _json.load(f) or []
                    existing.append(hist_entry)
                    with open(persist_file, 'w') as f:
                        _json.dump(existing, f, indent=2)
                except Exception as _e:
                    st.warning(f"Failed to persist history: {_e}")
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
    # History visualization
    if st.session_state.benchmark_history and plot_history:
        import pandas as _pd
        # Flatten per-model metrics for plotting
        rows = []
        for entry in st.session_state.benchmark_history:
            for m in entry.get("metrics", []):
                row = {"ts": entry.get("ts"), **m}
                rows.append(row)
        if rows:
            dfh = _pd.DataFrame(rows)
            try:
                import plotly.express as _px
                fig_hist = _px.line(dfh, x="ts", y="mae", color="model", markers=True, title="MAE Over Benchmark Runs")
                st.plotly_chart(fig_hist, use_container_width=True)
            except Exception as _e:
                st.warning(f"Plot failed: {_e}")
        st.caption(f"History entries: {len(st.session_state.benchmark_history)}")

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
