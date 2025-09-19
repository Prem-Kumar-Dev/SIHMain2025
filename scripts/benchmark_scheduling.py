"""Benchmark scheduling performance for varying numbers of trains.

Usage (PowerShell):
    python scripts/benchmark_scheduling.py -Min 10 -Max 50 -Step 10 -Sections 8 -RouteLen 4 -Solver greedy
    python -m scripts.benchmark_scheduling -Min 10 -Max 50 -Step 10 -Sections 8 -RouteLen 4 -Solver greedy

Notes:
    - Greedy solver complexity ≈ O(T * L * C).
    - MILP solver is exponential; keep train counts small when using -Solver milp.
"""

from __future__ import annotations
import argparse, random, statistics, json, time, os, sys
from typing import List

# Ensure project root on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.core.models import Section, TrainRequest, NetworkModel  # type: ignore
from src.core.solver import schedule_trains  # type: ignore


def build_random_network(num_sections: int) -> NetworkModel:
    sections: List[Section] = []
    for i in range(num_sections):
        headway = random.randint(60, 180)
        traverse = random.randint(80, 200)
        sections.append(Section(id=f"S{i+1}", headway_seconds=headway, traverse_seconds=traverse))
    return NetworkModel(sections=sections)


def build_random_trains(n: int, network: NetworkModel, avg_route_len: int) -> List[TrainRequest]:
    trains: List[TrainRequest] = []
    sec_ids = [s.id for s in network.sections]
    for i in range(n):
        dep = random.randint(0, 600)
        if avg_route_len >= len(sec_ids):
            route = sec_ids[:]
        else:
            length = max(1, min(len(sec_ids), int(random.gauss(avg_route_len, 1))))
            start = random.randint(0, max(0, len(sec_ids) - length))
            route = sec_ids[start:start+length]
        priority = random.randint(1, 3)
        trains.append(TrainRequest(id=f"T{i+1}", priority=priority, route_sections=route, planned_departure=dep))
    return trains


def run_once(n_trains: int, network: NetworkModel, avg_route_len: int, solver: str) -> dict:
    trains = build_random_trains(n_trains, network, avg_route_len)
    t0 = time.perf_counter()
    schedule = schedule_trains(trains, network, solver=solver)
    dt = time.perf_counter() - t0
    horizon = max((it.exit for it in schedule), default=0)
    return {
        "n_trains": n_trains,
        "solver": solver,
        "routes_mean_len": statistics.fmean(len(t.route_sections) for t in trains) if trains else 0.0,
        "elapsed_s": dt,
        "items": len(schedule),
        "horizon_s": horizon,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-Min', type=int, default=10)
    ap.add_argument('-Max', type=int, default=50)
    ap.add_argument('-Step', type=int, default=10)
    ap.add_argument('-Sections', type=int, default=8)
    ap.add_argument('-RouteLen', type=int, default=4)
    ap.add_argument('-Repeats', type=int, default=3)
    ap.add_argument('-Solver', type=str, default='greedy', choices=['greedy','milp'])
    ap.add_argument('-Json', action='store_true')
    args = ap.parse_args()

    random.seed(42)
    network = build_random_network(args.Sections)
    rows = []
    for n in range(args.Min, args.Max + 1, args.Step):
        for _ in range(args.Repeats):
            row = run_once(n, network, args.RouteLen, args.Solver)
            rows.append(row)
            if args.Json:
                print(json.dumps(row))
            else:
                print(f"Trains={row['n_trains']:<3} elapsed={row['elapsed_s']*1000:7.2f} ms items={row['items']:<4} horizon={row['horizon_s']:<6} solver={row['solver']}")
    if not args.Json:
        from collections import defaultdict
        by_n = defaultdict(list)
        for r in rows:
            by_n[r['n_trains']].append(r['elapsed_s'])
        print('\nSummary (mean ms per train count)')
        for n in sorted(by_n):
            ms = statistics.fmean(by_n[n]) * 1000
            print(f"  {n:>3}: {ms:7.2f} ms")


if __name__ == '__main__':
    main()
