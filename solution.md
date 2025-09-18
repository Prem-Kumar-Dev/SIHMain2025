## 1. Problem Understanding and Goals

- Objective: Maximize section throughput and punctuality while preserving safety and operational constraints.
- Scope: Single‑line/double‑line block sections with headways, traversals, platforms, and route conflicts; real‑time re‑dispatch during perturbations.
- Primary KPIs:
  - On‑Time Performance (OTP) with tolerance window
  - Average and total delay (minutes)
  - Makespan/throughput proxy; utilization
- Operating constraints (hard):
  - Headway clearances per section; single occupancy during traversal
  - Block windows (no‑entry intervals)
  - Platform capacity and pre‑entry dwell exclusivity when capacity=1
  - Route conflicts: pairwise (`conflicts_with`) and group‑wise (`conflict_groups`)
  - Precedence along route; dwell‑before‑next‑section when required

## 2. Architecture Overview

- Data & Live Integration: Optional connectors (e.g., RailRadar) wrapped with secure env config.
- Digital Twin: A compact network model `{sections, trains}` suitable for fast scheduling and what‑if simulation.
- AI Core:
  - Predictive Engine: Feature‑based delay prediction (Torch MLP), pathway to GNN.
  - Optimization Engine: MILP/Greedy schedulers with realistic constraints and due‑time aware objective.
- Orchestration API (FastAPI): `/predict`, `/resolve`, `/schedule`, `/whatif`, `/live/snapshot`, KPIs, and persistence.
- C3I Frontend (Streamlit): Live dashboard, scenario analysis, Gantt, KPIs, JSON editor, and CSV exports.

## 3. Decision Loop (Predict → Detect → Resolve)

1) Predict: Estimate near‑term delays per train from current context (priority, initial delay, density, TOD, etc.).
2) Detect Conflicts: Use predicted ETAs to flag short‑gap entries to the same (or conflicting) section.
3) Resolve: Build a reduced instance (only involved trains/sections) and re‑schedule via MILP/Greedy subject to constraints and due‑time weighted objective.
4) Assess: Compute KPIs (OTP with tolerance, delays) and present actionable advisories to the controller.

This loop can run on‑demand (operator click) or on a short cadence (e.g., every 30–60s) with guardrails.

## 4. Optimization Approach (OR/MILP)

- Decision variables: entry/exit times per (train, section), optional platform assignment when capacity>1.
- Constraints:
  - Headway and traversal per section: `entry[j] ≥ exit[i] + headway` for consecutive uses
  - Dwell‑before‑next section within the same train; route order precedence
  - Block windows: `entry ∉ ⋃ no‑entry intervals`
  - Platform capacity=1 → pre‑entry dwell exclusivity; capacity>1 → assignment + mutual exclusion
  - Route conflicts (pairwise/groups) → induced no‑overlap with clearance
- Objective:
  - If any train has `due_time`, minimize priority‑weighted lateness: `Σ w_t * max(0, last_entry_t − due_time_t)`
  - Else minimize priority‑weighted start times with an EDD tie‑break
- Solvers: PuLP/CBC default; Greedy fallback for speed and degraded modes.

## 5. Predictive Approach (ML)

- Baseline model: Torch MLP trained on simulation‑generated data.
  - Features: priority, current_delay_minutes, section densities, time‑of‑day, route length, simple dwell hints
  - Target: future delay minutes (per train)
- Inference: Standardize features; predict delays; feed into conflict detector.
- GNN Roadmap: Replace features with learned embeddings over the network graph (PyG/DGL), capturing interactions and topology.
- Data pipeline: Synthetic generator perturbs initial delays, schedules via MILP, labels outcomes → CSV for training.

## 6. KPIs and Safety Metrics

- OTP with tolerance (e.g., 0–300s)
- Avg/total delay; per‑train lateness map
- Makespan and utilization proxy
- Conflict checks (headway gaps verified post‑resolution)

## 7. Interfaces and UX (C3I)

- Live Dashboard: Snapshot → Predict → Conflicts → Resolve → KPIs, with a live movement visual and controls for OTP tolerance.
- Scenario Analysis: JSON editor, saved scenarios (SQLite), runs list, Gantt + KPIs, CSV downloads.
- Operator Guardrails: Clear advisory text, explainability (why a hold/over‑take), and reversible actions.

## 8. Security, Reliability, and Ops

- Secrets: `.env` via `python-dotenv`; `.env.example` documented; no secret logging.
- Resilience: API sanitizes dynamic fields (e.g., `current_delay_minutes`), consistent schema handling.
- Scripts: PowerShell for “run all”, training, and demos; testable in Windows environments.
- Port & path robustness for UI (PYTHONPATH, auto‑bump port).

## 9. Testing & Validation

- Unit and MILP tests for constraints (headways, blocks, platforms, conflicts, due‑time objective).
- API smoke tests for `/predict`, `/resolve`, `/schedule`, KPIs, persistence, and CSV export.
- Collision‑heavy integration test: predict → must detect conflicts; resolve → headways satisfied.
- Offline evaluation: Train/validation split for predictive models; target MAPE/RMSE on delays.

## 10. Deployment Strategy

- Local: `scripts/run_all.ps1` launches API + UI, ensures model, optional demo.
- On‑prem/Cloud: Uvicorn with workers behind reverse proxy; Streamlit or React UI fronted by nginx.
- Future: Dockerization and infra as code; secrets via vault.

## 11. Roadmap

- Phase 1 (MVP, done): Greedy/MILP scheduling with constraints; KPIs; REST API; Streamlit C3I; SQLite; predictive MLP; conflict detection; targeted resolve; demos and tests.
- Phase 2 (Predictive upgrade): Larger training sets, hyper‑param search, feature ablations; add confidence bands; integrate historical/real feeds.
- Phase 3 (GNN path): Graph builder + PyG model; transfer learning from synthetic → live; online fine‑tuning.
- Phase 4 (Ops & UX): Continuous scheduling on cadence; richer advisories; audit and replay; role‑based access.
- Phase 5 (Scale): Multi‑section corridors, multi‑objective optimization (throughput vs. fairness), and batch re‑planning.

## 12. Assumptions and Non‑Goals

- Assumptions: Accurate traverse/headway inputs; controller oversight remains; live data availability is best‑effort.
- Non‑Goals (current): Signaling interlocking details at relay level; high‑fidelity physics; full nationwide topology ingestion.

## 13. Why This Works for SIH25022

- Safety first: Hard constraints enforce headways/conflicts; advisories never violate occupancy rules.
- Throughput and punctuality: MILP optimizes lateness and start times; predictive inference anticipates congestion.
- Practical: Controller‑centric UI, explainable decisions, and demo‑ready scripts; portable Windows setup.
- Extensible: Clear path to GNNs and richer data sources without re‑architecting the system.

---

References to Implementation
- The accompanying codebase implements the above: FastAPI endpoints (`/predict`, `/resolve`, `/schedule`), Torch MLP inference and training, MILP/Greedy schedulers with realistic constraints, KPIs with OTP tolerance, Streamlit UI pages, SQLite persistence, demo/test scripts, and a collision‑heavy test scenario.
