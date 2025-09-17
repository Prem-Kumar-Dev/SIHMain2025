# Module Breakdown and Interfaces

## 1) Data Ingestion & Integration
- Inputs: signalling state, TMS feeds, timetable CSV/JSON, rolling stock status.
- Responsibilities: connectors (REST/gRPC/mock), schema validation, time normalization (UTC), dedup, late data handling.
- Outputs: unified events and state snapshots in canonical schema.
- Interfaces:
  - `IDataSource` (pull/push), `Event` (id, ts, type, payload), `Snapshot`.
- Edge cases: missing sections, delayed events, out-of-order timestamps, duplicate trains.

## 2) Preprocessing & Features
- Responsibilities: cleaning, imputation, speed profiles, section capacity, dwell estimates, headway matrices.
- Outputs: `NetworkModel`, `TrainRequest[]`, constraints set.

## 3) Optimization & AI Engine
- Submodules:
  - Deterministic OR: MILP/CP for feasibility and near-optimality.
  - Heuristics/Metaheuristics: greedy, LNS, GA for fast re-optimization.
  - RL Policy (optional later): dispatch actions scored by learned value/Q.
- Contract:
  - Input: `NetworkModel`, `TrainRequest[]`, `Constraints`, `ObjectiveWeights`.
  - Output: `Schedule { trainId, sectionId, entryTime, exitTime, platform?, reason }` with no conflicts.
  - KPI function: throughput, average delay, max delay, conflicts=0.
- Edge: disruptions, maintenance blocks, priority overrides, platform unavailability.

## 4) Simulation & Scenario
- Discrete-event simulator consuming `Schedule` and disturbances.
- What-if batch runner.

## 5) UI/API
- REST API for recommendations and what-if runs.
- Controller dashboard: Gantt, map, conflict list, explainability notes, overrides.

## Canonical Data Schemas (draft)
- TrainRequest: `{ id, priority, type?, plannedDeparture, plannedArrival?, routeSections[] }`
- Section: `{ id, length?, gradient?, signals[]?, capacity?, headwaySeconds, traverseSeconds }`
- Constraint: `{ type, params }`
- ScheduleItem: `{ trainId, sectionId, entry, exit }`

## KPIs & Audit
- KPIs: throughput/hour, avg delay, on-time %, utilization (% occupancy), replan time.
- Audit: input hash, solver config, version, action rationale.

---

This document evolves alongside implementation; see `src/core` for code contracts.
