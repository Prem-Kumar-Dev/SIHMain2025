# Project Status (Information Only)

This document summarizes what has been implemented so far across backend, optimization, UI, persistence, KPIs, tests, and tooling. It contains only descriptive information (no run instructions).

## Scope Overview
- Decision-support system for train traffic control with an OR/MILP optimizer, REST API, Streamlit UI, KPIs, and SQLite persistence.
- Focus on realistic railway constraints (headways, traversals, block windows, platforms, conflicts) and punctuality metrics (lateness, OTP with tolerance).

## Core Domain Models (src/core/models.py)
- Section
  - Fields: `id`, `headway_seconds`, `traverse_seconds`, `block_windows: list[tuple[int,int]] | None`, `platform_capacity: int | None`, `conflicts_with: Dict[str,int] | None`, `conflict_groups: Dict[str,int] | None`.
- TrainRequest
  - Fields: `id`, `priority`, `planned_departure`, `route_sections: list[str]`, `dwell_before: Dict[str,int] | None`, `due_time: int | None`.
- ScheduleItem: `train_id`, `section_id`, `entry`, `exit`.
- NetworkModel: holds sections; `section_by_id` helper.

## Scheduling/Optimization
- Greedy Scheduler (src/core/greedy_scheduler.py)
  - Baseline non-overlapping schedule with headways, traversals, dwell-before-next-section handling, and block-window avoidance.
- MILP Schedulers (src/core/milp_scheduler.py)
  - Single-section MILP
  - Multi-section MILP
  - Heterogeneous-route MILP (different routes per train)
  - Constraints/features across models:
    - Headways and traverse times per section
    - Block windows (no-entry intervals)
    - Intra-train precedence + dwell-before-next-section
    - Platform capacity k (k ≥ 1; assignment-based when k > 1)
    - Route conflicts via `conflicts_with` (pairwise clearance)
    - Conflict groups via `conflict_groups` (shared groups with max shared clearance)
    - Objective with `due_time` to minimize priority-weighted lateness; EDD-style tiebreak favoring earlier due dates
  - Dispatcher to select MILP variant; greedy fallback path exists in solver.

## KPIs and Lateness
- Basic KPIs (src/sim/simulator.py → `summarize_schedule`): total trains, makespan, utilization proxy, conflicts (0 placeholder).
- Lateness KPIs (src/sim/simulator.py → `lateness_kpis`):
  - Computes per-train lateness for trains with `due_time` (based on entry to last section).
  - Supports `otp_tolerance_s` parameter; OTP counts trains with lateness ≤ tolerance.
  - Reported metrics: `otp_end`, `avg_lateness`, `total_lateness`.
  - Additional fields provided in API responses: `otp0_end` (zero tolerance reference), `otp_tolerance_used` (seconds).
- Per-train lateness map exposed in API responses and saved run KPIs as `lateness_by_trai`.

## REST API (src/api.py)
- General
  - FastAPI app with base route `/` redirecting to `/docs` and `/favicon.ico` returning 204.
  - Pydantic input schemas mirror domain models; tuples enforced for block windows.
- Endpoints
  - `GET /demo` → sample schedule and KPIs.
  - `POST /schedule` → schedule items + KPIs + `lateness_by_train` (accepts `solver`, `otp_tolerance`).
  - `POST /whatif` → Gantt JSON + `lateness_by_train` (accepts `solver`, `otp_tolerance`).
  - `POST /kpis` → KPIs only (accepts `solver`, `otp_tolerance`).
  - Persistence:
    - `POST /scenarios` (save) → returns `id`.
    - `GET /scenarios` (list with pagination).
    - `PUT /scenarios/{sid}` (update name/payload).
    - `DELETE /scenarios/{sid}` (cascades runs delete), `GET /scenarios/{sid}/runs` (list runs with pagination).
    - `POST /scenarios/{sid}/run` (create run; accepts `solver`, `name`, `comment`, `otp_tolerance`) → returns `run_id` and KPIs.
    - `GET /runs/{rid}` (full run details), `DELETE /runs/{rid}` (delete run).
    - `GET /runs/{rid}/lateness.csv` (CSV export for per-train lateness; uses saved KPIs or recomputes from run payload/schedule).

## Persistence (src/store/db.py)
- SQLite database at `data/sih.db`.
- Tables: `scenarios` and `runs` (with `name`, `comment`, `input_payload`, `schedule`, `kpis`); migration guards for name/comment columns.
- Functions: set DB path, init, save/list/get scenarios, save/get/list runs, updates and deletes; pagination included where relevant.

## UI (ui/app.py)
- Streamlit interface with:
  - Solver selector (`greedy`/`milp`).
  - Scenario JSON editor and one-click “Run Scenario” for what-if.
  - Plotly Gantt chart with lateness hover on last section.
  - Lateness table (per train).
  - KPI display (merged basic + lateness KPIs).
  - OTP tolerance control (seconds) applied to `/whatif` and `/kpis`.
  - Scenarios panel: save/list/run/delete scenarios, view latest run details, download schedule CSV and lateness CSV.
  - Configures API base via environment variable; `set_page_config` ordering corrected.

## Audit (src/sim/audit.py)
- JSONL append-only audit at `audit/events.jsonl` for `/schedule`, `/whatif`, and `/kpis` calls.

## Tooling & Scripts
- PowerShell scripts (scripts/):
  - `start_api.ps1`: launches API server in a new PowerShell window.
  - `run_demo.ps1`: waits for API, calls `/kpis`, saves and runs a scenario, downloads lateness CSV, prints summary lines. Parameters: port, host, solver, OTP tolerance, scenario name, output dir, optional server start.

## Tests (tests/)
- Coverage across:
  - Greedy and MILP schedulers (single/multi/hetero), block windows.
  - Dwell precedence and platform capacity (including k > 1 assignment logic).
  - Route conflicts (`conflicts_with`) and conflict groups (`conflict_groups`).
  - Due-time objective and lateness KPIs, OTP tolerance effect.
  - API endpoints: `/demo`, `/schedule`, `/whatif`, `/kpis`, persistence flows, and CSV export (`/runs/{rid}/lateness.csv`).
- Current test suite status: 29 tests passing.

## Documentation
- `readme.md` updated to document: due-time objective, platform capacity, route conflicts and groups, OTP tolerance parameters, and the lateness CSV export.

## Checkpoints (Git Tags)
- `v0.8.0`: OTP tolerance added (API/UI), lateness exposure and KPIs; conflict groups integrated; initial docs.
- `v0.8.1`: KPIs include `otp0_end` and `otp_tolerance_used`; docs mention CSV endpoint and UI option.
- `v0.8.2`: Added `GET /runs/{rid}/lateness.csv` and tests.

## Notes
- The system currently optimizes schedules via MILP with realistic constraints and exposes lateness-focused KPIs. Predictive ML/RL components are not yet implemented (design placeholders only).

---

## New Additions (Predictive Engine Slice)

This section documents the incremental predictive features and related utilities added after the initial status snapshot.

### Predictive Engine Modules (src/ai_core/predictive_engine)
- `config.py`: Loads environment variables from `.env` (via `python-dotenv`). Keys include `RAILRADAR_API_BASE`, `RAILRADAR_API_KEY`, and optional `PREDICTIVE_MODEL_PATH` (for GNN weights). A boolean `is_live_enabled` indicates if a live API key is present.
- `feature_engineering.py`: Builds per-train feature vectors from a `{ sections, trains }` state including fields like `priority`, `current_delay_minutes`, time-of-day, simple density, and dwell hints.
- `model.py`: Baseline `BaselineDelayRegressor` producing per-train delay predictions (minutes) from engineered features.
- `conflict_detector.py`: Heuristic to flag short-gap conflicts on the next section using predicted ETAs.
- `data_client.py`: Async `RailRadarClient` with methods to fetch live map and schedules, sending the `x-api-key` header when available.
- `live_mapping.py`: Best-effort mapper from live payloads into the internal `{ sections, trains }` shape; preserves any `sections` supplied in the request, respects `max_trains`.
- `gnn/graph_builder.py` and `gnn/model_stub.py`: Stubs to convert state to a graph and produce GNN-based delay predictions if `PREDICTIVE_MODEL_PATH` is set; safe fallback to baseline otherwise.
- `gnn/model_torch.py`: Feature-based Torch MLP predictor (`TorchDelayPredictor`) supporting real inference from engineered features.
- `gnn/train_torch.py`: Simple trainer that fits the MLP on `training_data.csv`, standardizes features, and saves a `.pt` checkpoint with metadata (feature order and normalization).
- `generate_training_data.py`: Simulation-driven dataset creator that perturbs initial delays, schedules via MILP, and writes a labeled CSV with per-train targets. Now includes base-state validation, optional RNG seed, and summary stats (min/median/mean/p95/max).

### New API Endpoints (src/api.py)
- `POST /predict`
  - Input: same shape as `/schedule`; trains may include `current_delay_minutes`.
  - Output: `{ predicted_delay_minutes: {train_id: minutes}, predicted_conflicts: [...] }`.
  - Behavior: Uses baseline regressor via feature engineering; attempts GNN path when `PREDICTIVE_MODEL_PATH` is configured, with fallback to baseline. Conflicts are detected via a simple ETA-gap heuristic.

- `POST /resolve`
  - Input: `{ state, predicted_conflicts }` where `state` is `{ sections, trains }` and conflicts derive from `/predict`.
  - Output: `{ kpis, schedule }` for a reduced problem covering only trains/sections involved in conflicts. KPIs include lateness metrics and `otp_tolerance_used`.

- `POST /live/snapshot`
  - Behavior: If `use_live=true` and a `RAILRADAR_API_KEY` is set, fetches a live map and maps it into `{ sections, trains }`, preserving `sections` provided in the body and honoring `max_trains`. Otherwise, echoes the provided state or returns a minimal sample. Returns metadata fields such as `enabled`, `fetched_count`, and `fetch_error`.

### Environment & Security
- `.env.example` extended with `PREDICTIVE_MODEL_PATH`. The application loads `.env` automatically; real keys are never logged and `.env` is gitignored.

### Scripts (scripts/)
- `run_predict_demo.ps1`: Calls `/predict` on a small in-memory scenario.
- `generate_training_data.ps1`: Runs the training data generator with configurable sample count and paths.
- `train_delay_model.ps1`: Trains the Torch MLP on a CSV and writes a `.pt` checkpoint; intended for CPU by default.

### Tests (tests/)
- `test_predict_endpoint.py`: Smoke test for `/predict` structure and non-negative delays.
- `test_resolve_endpoint.py`: Smoke test for `/resolve` returning KPIs and schedule.

### Documentation
- `readme.md` updated with predictive engine overview, environment variable guidance, brief usage notes for `/predict`, `/resolve`, and `/live/snapshot`, and corrected PowerShell examples.

---

## Checkpoint 2025-09-18 (v0.9.0 - Predictive MLP online)

Summary
- End-to-end predictive path is operational using Torch MLP (`PREDICTIVE_MODEL_PATH`), with graceful fallback to baseline when not configured.
- API endpoints hardened to accept dynamic train fields (e.g., `current_delay_minutes`) by sanitizing input before constructing `TrainRequest`.
- Training pipeline is runnable locally: dataset generator → trainer → model inference in `/predict`.

Key Changes
- `src/api.py`: Added `_clean_train_dict` and applied it across `/resolve`, `/schedule`, `/whatif`, `/kpis`, and `/scenarios/{sid}/run` to ignore non-model keys.
- `src/ai_core/predictive_engine/generate_training_data.py`: Now strips unsupported keys before `TrainRequest(**d)`; supports `--seed` and prints dataset stats.
- `src/ai_core/predictive_engine/gnn/train_torch.py`: Trains MLP on CSV features (minutes target), saves `.pt` with feature order and normalization.
- Scripts: `generate_training_data.ps1` (seed-aware) and `train_delay_model.ps1` (venv-aware) for quick runs.
- `.env`: Includes `PREDICTIVE_MODEL_PATH=./data/delay_model.pt` for model-backed predictions.

Demo Snapshot (PowerShell)
1) Start API in Terminal A:
```
./scripts/start_api.ps1 -Port 8000
```
2) Predict in Terminal B:
```
$body = @'
{
  "sections": [
    { "id": "S1", "headway_seconds": 120, "traverse_seconds": 100 },
    { "id": "S2", "headway_seconds": 120, "traverse_seconds": 120 }
  ],
  "trains": [
    { "id": "A", "priority": 3, "planned_departure": 0,  "route_sections": ["S1","S2"], "current_delay_minutes": 0 },
    { "id": "B", "priority": 2, "planned_departure": 60, "route_sections": ["S1"],      "current_delay_minutes": 1 }
  ]
}
'@
Invoke-RestMethod -Uri 'http://localhost:8000/predict' -Method Post -ContentType 'application/json' -Body $body | ConvertTo-Json -Depth 6
```
3) Resolve conflicts (optional):
```
$pred = Invoke-RestMethod -Uri 'http://localhost:8000/predict' -Method Post -ContentType 'application/json' -Body $body
$resolveBody = [PSCustomObject]@{ state = ($body | ConvertFrom-Json); predicted_conflicts = $pred.predicted_conflicts } | ConvertTo-Json -Depth 8
Invoke-RestMethod -Uri 'http://localhost:8000/resolve?solver=greedy&otp_tolerance=60' -Method Post -ContentType 'application/json' -Body $resolveBody | ConvertTo-Json -Depth 8
```

Next Steps (Optional)
- Improve prediction quality by generating more training samples (e.g., N=3000) and training longer.
- Enhance live mapping fidelity to real RailRadar schema.
- Explore a true graph model (PyG) replacing the stub path.