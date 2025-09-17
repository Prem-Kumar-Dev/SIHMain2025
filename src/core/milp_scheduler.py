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

    # Pairwise disjunctive constraints
    for i in range(n):
        for j in range(i + 1, n):
            ti = trains[i]
            tj = trains[j]
            y_ij = y[(ti.id, tj.id)]
            # If y_ij=1 then i before j; else j before i
            prob += s[tj.id] >= s[ti.id] + D + H - M * (1 - y_ij)
            prob += s[ti.id] >= s[tj.id] + D + H - M * (y_ij)

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
    # Support only the case where each train has exactly one section and all the same section id
    if not trains:
        return []
    first_route = trains[0].route_sections
    if len(first_route) != 1:
        raise ValueError("MILP scheduler currently supports single-section routes only")
    sid = first_route[0]
    if any(len(t.route_sections) != 1 or t.route_sections[0] != sid for t in trains):
        raise ValueError("All trains must have identical single-section routes for MILP scheduler")
    section = network.section_by_id(sid)
    return schedule_trains_single_section_milp(trains, section)
