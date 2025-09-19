"""Minimal large scenario generator (clean rewrite)."""
import argparse, random, json, os, sys
from typing import List, Dict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def build_sections(n: int) -> List[Dict]:
    out: List[Dict] = []
    for i in range(n):
        headway = random.randint(60, 240)
        traverse = random.randint(90, 300)
        if random.random() < 0.1:
            s = random.randint(600, 1800)
            bw = [(s, s + random.randint(120, 600))]
        else:
            bw = []
        out.append({
            "id": f"S{i+1}",
            "headway_seconds": headway,
            "traverse_seconds": traverse,
            "block_windows": bw
        })
    return out


def build_trains(n: int, sec_ids: List[str], avg_len: int, stagger: int, include_due: bool) -> List[Dict]:
    trains: List[Dict] = []
    for i in range(n):
        dep = i * 30 + random.randint(0, stagger)
        if avg_len >= len(sec_ids):
            route = sec_ids[:]
        else:
            length = max(1, min(len(sec_ids), int(random.gauss(avg_len, 1))))
            start = random.randint(0, max(0, len(sec_ids) - length))
            route = sec_ids[start:start+length]
        tr = {
            "id": f"T{i+1}",
            "priority": random.randint(1, 3),
            "planned_departure": dep,
            "route_sections": route
        }
        if include_due and random.random() < 0.5:
            nominal = dep + sum(random.randint(90, 240) for _ in route)
            tr["due_time"] = nominal + random.randint(-120, 180)
        trains.append(tr)
    return trains


def main():
    p = argparse.ArgumentParser()
    p.add_argument('-Trains', type=int, default=50)
    p.add_argument('-Sections', type=int, default=20)
    p.add_argument('-RouteLen', type=int, default=6)
    p.add_argument('-Stagger', type=int, default=300)
    p.add_argument('-Seed', type=int, default=42)
    p.add_argument('-Out', type=str, default='large_scenario.json')
    p.add_argument('-IncludeDue', action='store_true')
    a = p.parse_args()

    random.seed(a.Seed)
    sections = build_sections(a.Sections)
    trains = build_trains(a.Trains, [s['id'] for s in sections], a.RouteLen, a.Stagger, a.IncludeDue)
    scenario = {"sections": sections, "trains": trains}
    with open(a.Out, 'w') as f:
        json.dump(scenario, f, indent=2)
    print(f"Wrote {len(sections)} sections & {len(trains)} trains -> {a.Out}")


if __name__ == '__main__':
    main()
