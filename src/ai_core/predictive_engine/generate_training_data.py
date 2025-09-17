from __future__ import annotations
import csv
import json
import random
import statistics
from pathlib import Path
from typing import Dict, Any, List

from src.core.models import NetworkModel, Section, TrainRequest
from src.core.solver import schedule_trains
from src.sim.simulator import lateness_kpis
from .feature_engineering import build_features_from_state


def simulate_once(base_state: Dict[str, Any], delay_prob: float = 0.3, max_init_delay_min: int = 10) -> Dict[str, Any]:
    # Copy and introduce random delays on a subset of trains
    state = json.loads(json.dumps(base_state))
    for t in state.get("trains", []):
        if random.random() < delay_prob:
            t["current_delay_minutes"] = random.randint(1, max_init_delay_min)
        else:
            t["current_delay_minutes"] = 0
    # Build domain objects
    sections = []
    for s in state.get("sections", []):
        bw = s.get("block_windows") or []
        sections.append(Section(
            id=s["id"], headway_seconds=s["headway_seconds"], traverse_seconds=s["traverse_seconds"],
            block_windows=[(int(a), int(b)) for a, b in bw] if bw else None,
            platform_capacity=s.get("platform_capacity"),
            conflicts_with=s.get("conflicts_with"),
            conflict_groups=s.get("conflict_groups"),
        ))
    # Sanitize train dicts to only include TrainRequest fields (ignore dynamic keys like current_delay_minutes)
    def _to_train_request(d: Dict[str, Any]) -> TrainRequest:
        allowed = {
            "id",
            "priority",
            "route_sections",
            "planned_departure",
            "dwell_before",
            "due_time",
        }
        clean = {k: v for k, v in d.items() if k in allowed}
        return TrainRequest(**clean)

    trains = [_to_train_request(t) for t in state.get("trains", [])]
    network = NetworkModel(sections=sections)
    items = schedule_trains(trains, network, solver="milp")
    lk = lateness_kpis(items, trains, otp_tolerance_s=0)
    # Features are built before scheduling — use those as inputs
    feats = build_features_from_state(state)
    # Target: per-train lateness in seconds at last section
    lateness_map: Dict[str, int] = {}
    for t in trains:
        if t.due_time is not None and t.route_sections:
            last_sid = t.route_sections[-1]
            entries = [it.entry for it in items if it.train_id == t.id and it.section_id == last_sid]
            if entries:
                lateness_map[t.id] = max(0, int(entries[0]) - int(t.due_time))
    return {"features": feats, "lateness_by_train": lateness_map}


def write_training_csv(samples: List[Dict[str, Any]], out_path: Path) -> None:
    # Flatten to a simple row per train: features..., target_seconds
    # Collect all feature keys
    feat_keys = set()
    for s in samples:
        for tf in s["features"]:
            feat_keys.update(tf.features.keys())
    feat_keys = sorted(list(feat_keys))
    columns = ["train_id"] + feat_keys + ["target_lateness_s"]
    with out_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns)
        w.writeheader()
        for s in samples:
            lat = s["lateness_by_train"]
            for tf in s["features"]:
                row = {"train_id": tf.train_id}
                for k in feat_keys:
                    row[k] = tf.features.get(k, 0.0)
                row["target_lateness_s"] = int(lat.get(tf.train_id, 0))
                w.writerow(row)


def _validate_base_state(base_state: Dict[str, Any]) -> None:
    if not isinstance(base_state, dict):
        raise ValueError("base_state must be a JSON object")
    if not isinstance(base_state.get("sections"), list):
        raise ValueError("base_state.sections must be a list")
    if not isinstance(base_state.get("trains"), list):
        raise ValueError("base_state.trains must be a list")


def main() -> None:
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--base", type=Path, required=True, help="Path to a JSON file containing a base state")
    p.add_argument("--out", type=Path, default=Path("training_data.csv"))
    p.add_argument("--n", type=int, default=2000)
    p.add_argument("--delay-prob", type=float, default=0.3)
    p.add_argument("--max-delay-min", type=int, default=10)
    p.add_argument("--seed", type=int, default=None, help="Optional RNG seed for reproducibility")
    args = p.parse_args()

    # Optional seeding for reproducibility
    if args.seed is not None:
        random.seed(int(args.seed))

    base_state = json.loads(args.base.read_text())
    _validate_base_state(base_state)
    samples: List[Dict[str, Any]] = []
    for _ in range(args.n):
        samples.append(simulate_once(base_state, delay_prob=args.delay_prob, max_init_delay_min=args.max_delay_min))
    write_training_csv(samples, args.out)
    # Summary stats on targets
    total_rows = sum(len(s["features"]) for s in samples)
    targets: List[int] = []
    for s in samples:
        lat = s.get("lateness_by_train", {})
        for tf in s["features"]:
            targets.append(int(lat.get(tf.train_id, 0)))
    nonzero_targets = sum(1 for v in targets if v > 0)
    if targets:
        mean_v = statistics.fmean(targets)
        median_v = statistics.median(targets)
        min_v = min(targets)
        max_v = max(targets)
        # crude p95
        p95 = sorted(targets)[max(0, int(0.95 * (len(targets) - 1)))]
        print(
            f"Wrote {args.out} with {len(samples)} sims and {total_rows} rows | nonzero={nonzero_targets} | "
            f"min={min_v}s median={int(median_v)}s mean={int(mean_v)}s p95={p95}s max={max_v}s"
        )
    else:
        print(f"Wrote {args.out} with {len(samples)} sims and 0 rows")


if __name__ == "__main__":
    main()
