import streamlit as st
import os, sys, random, time, statistics, json
from typing import List

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

st.set_page_config(page_title="Scheduling Benchmark", layout="wide")

st.title("Scheduling Throughput Benchmark")
st.caption("In-process benchmark of the greedy (or MILP) scheduler over synthetic randomized instances. Uses the same core solver modules as the API, bypassing HTTP overhead.")

try:
    from src.core.models import Section, TrainRequest, NetworkModel  # type: ignore
    from src.core.solver import schedule_trains  # type: ignore
except Exception as e:  # pragma: no cover
    st.error(f"Failed to import scheduling core: {e}")
    st.stop()

with st.expander("Benchmark Configuration", expanded=True):
    c1, c2, c3, c4 = st.columns(4)
    min_tr = c1.number_input("Min Trains", min_value=1, max_value=10000, value=50, step=10)
    max_tr = c2.number_input("Max Trains", min_value=1, max_value=10000, value=250, step=10)
    step_tr = c3.number_input("Step", min_value=1, max_value=5000, value=50, step=10)
    repeats = c4.number_input("Repeats", min_value=1, max_value=50, value=3, step=1)
    c5, c6, c7, c8 = st.columns(4)
    n_sections = c5.number_input("Sections", min_value=1, max_value=2000, value=20, step=5)
    route_len = c6.number_input("Avg Route Len", min_value=1, max_value=500, value=6, step=1)
    solver = c7.selectbox("Solver", options=["greedy", "milp"], index=0)
    seed = c8.number_input("Seed", min_value=0, max_value=999999, value=42, step=1)
    emit_json = st.toggle("Emit JSON Rows", value=False, help="Show each run row as JSON (can copy to file)")
    run_btn = st.button("Run Benchmark", type="primary")

def build_random_network(num_sections: int) -> NetworkModel:
    secs: List[Section] = []
    for i in range(num_sections):
        secs.append(Section(id=f"S{i+1}", headway_seconds=random.randint(60,180), traverse_seconds=random.randint(80,200)))
    return NetworkModel(sections=secs)

def build_random_trains(n: int, net: NetworkModel, avg_len: int) -> List[TrainRequest]:
    trains: List[TrainRequest] = []
    sec_ids = [s.id for s in net.sections]
    for i in range(n):
        dep = random.randint(0, 600)
        if avg_len >= len(sec_ids):
            route = sec_ids[:]
        else:
            length = max(1, min(len(sec_ids), int(random.gauss(avg_len, 1))))
            start = random.randint(0, max(0, len(sec_ids) - length))
            route = sec_ids[start:start+length]
        trains.append(TrainRequest(id=f"T{i+1}", priority=random.randint(1,3), route_sections=route, planned_departure=dep))
    return trains

def run_once(n_tr: int, net: NetworkModel, avg_len: int, solver: str):
    trains = build_random_trains(n_tr, net, avg_len)
    t0 = time.perf_counter()
    sched = schedule_trains(trains, net, solver=solver)
    dt = time.perf_counter() - t0
    horizon = max((it.exit for it in sched), default=0)
    return {
        "n_trains": n_tr,
        "elapsed_s": dt,
        "items": len(sched),
        "horizon": horizon,
        "mean_route": statistics.fmean(len(t.route_sections) for t in trains) if trains else 0.0,
    }

if run_btn:
    if max_tr < min_tr:
        st.error("Max Trains must be >= Min Trains")
    else:
        random.seed(int(seed))
        net = build_random_network(int(n_sections))
        rows = []
        prog = st.progress(0.0, text="Running benchmark...")
        total_iters = ((int(max_tr) - int(min_tr)) // int(step_tr) + 1) * int(repeats)
        done = 0
        for n in range(int(min_tr), int(max_tr) + 1, int(step_tr)):
            for _ in range(int(repeats)):
                r = run_once(n, net, int(route_len), solver)
                rows.append(r)
                done += 1
                prog.progress(done / total_iters, text=f"{done}/{total_iters} runs")
                if emit_json:
                    st.code(json.dumps(r), language="json")
        prog.empty()
        # Aggregate summary
        from collections import defaultdict
        bucket = defaultdict(list)
        for r in rows:
            bucket[r['n_trains']].append(r['elapsed_s'])
        summary = []
        for n in sorted(bucket):
            summary.append({"n_trains": n, "mean_ms": statistics.fmean(bucket[n]) * 1000, "runs": len(bucket[n])})
        try:
            import pandas as _pd
            st.subheader("Run Rows")
            st.dataframe(_pd.DataFrame(rows))
            st.subheader("Summary")
            st.dataframe(_pd.DataFrame(summary))
            # Plot
            import plotly.express as px
            fig = px.line(_pd.DataFrame(summary), x="n_trains", y="mean_ms", markers=True, title="Mean Scheduling Time (ms) vs Trains")
            st.plotly_chart(fig, use_container_width=True)
            # Download buttons
            st.download_button("Download Rows JSON", data=json.dumps(rows, indent=2), file_name="benchmark_rows.json", mime="application/json")
            st.download_button("Download Summary JSON", data=json.dumps(summary, indent=2), file_name="benchmark_summary.json", mime="application/json")
            # Simple scaling heuristic text
            if len(summary) >= 2:
                first = summary[0]
                last = summary[-1]
                scale = (last['mean_ms'] / first['mean_ms']) if first['mean_ms'] else 0
                st.caption(f"Scaling factor from {first['n_trains']} -> {last['n_trains']}: {scale:.1f}x (approx linear expectation {(last['n_trains']/first['n_trains']):.1f}x)")
        except Exception as e:  # pragma: no cover
            st.error(f"Display failed: {e}")

st.markdown("---")
st.caption("Note: MILP solver runs may become very slow beyond small train counts; prefer greedy for large scale benchmarking.")