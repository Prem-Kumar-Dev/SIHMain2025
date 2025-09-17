from typing import List, Dict, Tuple
from dataclasses import dataclass
import pulp

from src.core.models import TrainRequest, Section, ScheduleItem, NetworkModel

# MILP for single-section sequencing with headway and traverse time.
# Objective: minimize weighted start times (higher priority => larger weight)


def schedule_trains_single_section_milp(trains: List[TrainRequest], section: Section) -> List[ScheduleItem]:
    n = len(trains)
    if n == 0:
        return []

    # Problem
    prob = pulp.LpProblem("single_section_schedule", pulp.LpMinimize)

    # Variables
    s = {t.id: pulp.LpVariable(f"s_{t.id}", lowBound=t.planned_departure, cat=pulp.LpContinuous) for t in trains}
    y: Dict[Tuple[str, str], pulp.LpVariable] = {}
    for i in range(n):
        for j in range(i + 1, n):
            y[(trains[i].id, trains[j].id)] = pulp.LpVariable(f"y_{trains[i].id}_before_{trains[j].id}", lowBound=0, upBound=1, cat=pulp.LpBinary)

    H = section.headway_seconds
    D = section.traverse_seconds
    # Big-M: choose a sufficiently large number, e.g., max horizon
    # Estimate horizon as max planned + n*(D+H)
    latest_dep = max(t.planned_departure for t in trains)
    M = latest_dep + n * (D + H) + 1000

    # Pairwise disjunctive constraints (headway and traverse)
    for i in range(n):
        for j in range(i + 1, n):
            ti = trains[i]
            tj = trains[j]
            y_ij = y[(ti.id, tj.id)]
            # If y_ij=1 then i before j; else j before i
            prob += s[tj.id] >= s[ti.id] + D + H - M * (1 - y_ij)
            prob += s[ti.id] >= s[tj.id] + D + H - M * (y_ij)

    # Block window avoidance: for each train and window [a,b), enforce
    # (s_t + D <= a) OR (s_t >= b)
    if section.block_windows:
        for t in trains:
            for w_idx, (a, b) in enumerate(section.block_windows):
                z = pulp.LpVariable(f"z_{t.id}_win{w_idx}", lowBound=0, upBound=1, cat=pulp.LpBinary)
                prob += s[t.id] + D <= int(a) + M * z
                prob += s[t.id] >= int(b) - M * (1 - z)

    # Objective: minimize weighted start times (priority weight)
    prob += pulp.lpSum([ti.priority * s[ti.id] for ti in trains])

    # Solve
    prob.solve(pulp.PULP_CBC_CMD(msg=False))

    # Build schedule items
    items: List[ScheduleItem] = []
    for t in trains:
        start = int(pulp.value(s[t.id]))
        items.append(ScheduleItem(train_id=t.id, section_id=section.id, entry=start, exit=start + D))

    # Sort by entry
    items.sort(key=lambda it: it.entry)
    return items


def schedule_trains_milp(network: NetworkModel, trains: List[TrainRequest]) -> List[ScheduleItem]:
    # If no trains, return early
    if not trains:
        return []
    route = trains[0].route_sections
    # Ensure all trains share identical route
    if any(t.route_sections != route for t in trains):
        raise ValueError("All trains must have identical routes for MILP scheduler")
    # Block windows are supported below via additional disjunctive constraints

    if len(route) == 1:
        section = network.section_by_id(route[0])
        return schedule_trains_single_section_milp(trains, section)
    else:
        return schedule_trains_multi_section_milp(trains, [network.section_by_id(sid) for sid in route])


def schedule_trains_multi_section_milp(trains: List[TrainRequest], sections: List[Section]) -> List[ScheduleItem]:
    n = len(trains)
    m = len(sections)
    prob = pulp.LpProblem("multi_section_schedule", pulp.LpMinimize)

    # Start time variables s[t,k] for train t on section k (index-based)
    s: Dict[Tuple[int, int], pulp.LpVariable] = {}
    for ti, t in enumerate(trains):
        for k in range(m):
            lb = t.planned_departure if k == 0 else 0
            s[(ti, k)] = pulp.LpVariable(f"s_{t.id}_{k}", lowBound=lb, cat=pulp.LpContinuous)

    # Precedence within a train across sections: start next section after completing previous + dwell
    for ti, t in enumerate(trains):
        for k in range(1, m):
            prev = sections[k - 1]
            dwell = 0
            if t.dwell_before:
                next_sid = sections[k].id
                dwell = int(t.dwell_before.get(next_sid, 0))
            prob += s[(ti, k)] >= s[(ti, k - 1)] + prev.traverse_seconds + dwell

    # Pairwise non-overlap with headway per section
    y: Dict[Tuple[int, int, int], pulp.LpVariable] = {}
    # Big-M
    latest_dep = max(t.planned_departure for t in trains)
    maxD = sum(sec.traverse_seconds + sec.headway_seconds for sec in sections)
    M = latest_dep + n * maxD + 1000

    for k, sec in enumerate(sections):
        Dk = sec.traverse_seconds
        Hk = sec.headway_seconds
        for i in range(n):
            for j in range(i + 1, n):
                y[(i, j, k)] = pulp.LpVariable(f"y_t{i}_t{j}_k{k}", lowBound=0, upBound=1, cat=pulp.LpBinary)
                # if y=1 then i before j on section k
                prob += s[(j, k)] >= s[(i, k)] + Dk + Hk - M * (1 - y[(i, j, k)])
                prob += s[(i, k)] >= s[(j, k)] + Dk + Hk - M * (y[(i, j, k)])

        # Block windows for this section
        if sec.block_windows:
            for ti, t in enumerate(trains):
                for w_idx, (a, b) in enumerate(sec.block_windows):
                    z = pulp.LpVariable(f"z_t{ti}_k{k}_w{w_idx}", lowBound=0, upBound=1, cat=pulp.LpBinary)
                    prob += s[(ti, k)] + Dk <= int(a) + M * z
                    prob += s[(ti, k)] >= int(b) - M * (1 - z)

    # Objective: minimize weighted completion times at last section start (approx) or sum starts
    last_idx = m - 1
    prob += pulp.lpSum([trains[ti].priority * s[(ti, last_idx)] for ti in range(n)])

    prob.solve(pulp.PULP_CBC_CMD(msg=False))

    # Build schedule items for each train and section
    items: List[ScheduleItem] = []
    for ti, t in enumerate(trains):
        for k, sec in enumerate(sections):
            start = int(pulp.value(s[(ti, k)]))
            items.append(ScheduleItem(train_id=t.id, section_id=sec.id, entry=start, exit=start + sec.traverse_seconds))

    # Sort by start time
    items.sort(key=lambda it: (it.section_id, it.entry))
    return items
