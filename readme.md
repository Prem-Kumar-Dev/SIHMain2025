Of course. A well-structured `README.md` is essential for a project of this scale, especially when collaborating with AI-powered tools like Copilot. It provides the necessary context, architecture, and roadmap for development.
# Maximizing Section Throughput Using AI-Powered Precise Train Traffic Control

This project targets an intelligent decision-support system to assist section controllers with real-time precedence and crossing decisions, maximizing throughput and minimizing delays. It combines operations research (OR) and AI.

## Key Docs
- Architecture: `architecture.md`
- Module breakdown: `docs/modules.md`
 - AI integration steps (Windows): `docs/AI_INTEGRATION_STEPS.md`

## Quick Start (PowerShell)

1) Create and activate a virtual environment (optional but recommended):
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2) Run the minimal scheduler demo:
```powershell
python -m src.main
```

3) Run tests (if `pytest` is available):
```powershell
pip install pytest
pytest -q
```

## Run the REST API (FastAPI)

Install dependencies and start the server:
```powershell
pip install -r requirements.txt
uvicorn src.api:app --reload --host 0.0.0.0 --port 8000
```

Try endpoints:
```powershell
curl http://localhost:8000/demo
```

Payload notes:
- Trains now support an optional `due_time` (integer seconds). When any train includes `due_time`, the MILP optimizer minimizes the priority-weighted sum of lateness (where lateness = max(0, last-section-entry - due_time)). If no `due_time` is present, it minimizes priority-weighted start times as before. A tiny EDD-style tie-break favors earlier due dates when multiple schedules have zero lateness.
- Sections support optional `platform_capacity` (currently capacity=1 is enforced). When set to 1, pre-entry dwell intervals before entering that section are modeled as mutually exclusive (no overlap).
 - Sections can define route conflicts via:
   - `conflicts_with`: `{ "OtherSectionId": clearance_seconds }` to block simultaneous entries between two sections.
   - `conflict_groups`: `{ "GroupId": clearance_seconds }` to block simultaneous entries among all sections sharing that group id; the max shared clearance applies between two sections.
 - KPI OTP tolerance: endpoints `/schedule`, `/whatif`, and `/kpis` accept an `otp_tolerance` query parameter (seconds). OTP counts trains with lateness ≤ tolerance as on-time (default 0). The UI exposes an "OTP Tolerance (seconds)" control and adds a "Download Lateness CSV" option in the Runs panel.

## Run the Streamlit UI

streamlit run ui/app.py
```
Optionally, set a different API base via secrets:
Create `.streamlit/secrets.toml` with:
```
API_BASE = "http://localhost:8000"
```

The UI includes a Scenarios panel:
- Save a scenario from the JSON editor to SQLite.
- List scenarios and run a selected scenario via the API.
- View recent runs for a scenario and inspect full run details.
 - Download schedule CSV and per-train lateness CSV from the latest run. The API also exposes `GET /runs/{rid}/lateness.csv` to download lateness directly.

Responses now include a `lateness_by_train` map when `due_time` is provided in the input.

Example request with `due_time`:
```json
  ],
  "trains": [
    { "id": "T1", "priority": 3, "planned_departure": 0, "route_sections": ["S1"], "due_time": 400 },
    { "id": "T2", "priority": 1, "planned_departure": 0, "route_sections": ["S1"], "due_time": 200 }
  ]
}
```

## Predictive Engine (early slice)

- New endpoint: `POST /predict`
  - Input: same shape as `/schedule` with optional dynamic fields like `current_delay_minutes` on trains.
  - Output: `{ predicted_delay_minutes: { [train_id]: minutes }, predicted_conflicts: [...] }` where conflicts flag trains aiming for the same first section within a short window based on predicted ETAs.
  - Current model: a baseline regressor; replaceable later with a trained GNN.

Environment variables (keep your API key private):
- Copy `.env.example` to `.env` and set:
  - `RAILRADAR_API_BASE=https://railradar.in/api/v1`
  - `RAILRADAR_API_KEY=...` (do not commit). The app will load `.env` automatically.
  - `PREDICTIVE_MODEL_PATH=path\to\weights.pt` (optional; enables GNN stub loading; baseline used if missing)

Quick demo in PowerShell:
```powershell
.\n+scripts\run_predict_demo.ps1 -ApiBase http://localhost:8000
```

Related endpoints:
- `POST /live/snapshot?use_live=false&max_trains=50`
  - Default: returns the provided `body` state if present; otherwise a minimal sample state.
  - When `use_live=true` and `RAILRADAR_API_KEY` is set, fetches a live map and maps it to `{ sections, trains }`. It respects `max_trains` and preserves any `sections` you pass in the body.
  - Notes: live mapping is best-effort and may not include full route topology; you can provide `sections` in the body to control topology.
- `POST /resolve?solver=milp&otp_tolerance=300`
  - Input: `{ state, predicted_conflicts }` where `state` is `{ sections, trains }` and conflicts are from `/predict`.
  - Output: `{ kpis, schedule }` for the reduced instance covering only trains and sections involved in conflicts.

### Collision-heavy demo and tests

We include a synthetic scenario that induces multiple conflicts to showcase prediction and resolution:

- Scenario file: `data/scenarios/collision_heavy.json`
- Pytest: `tests/test_collision_resolution.py` (assumes API running at `http://127.0.0.1:8000`; override with env var `API_BASE`)
- Demo script (PowerShell): `scripts/run_collision_demo.ps1`

Usage (Windows PowerShell):

1) Ensure the API is running in a separate terminal
```powershell
uvicorn src.api:app --reload --host 127.0.0.1 --port 8000
```

2) Run the demo script
```powershell
./scripts/run_collision_demo.ps1 -ApiBase http://127.0.0.1:8000
```
This prints predicted conflict counts, resolves the schedule, shows basic KPIs, and warns if any section headway is violated.

3) Run the pytest
```powershell
pip install pytest; pytest -q tests/test_collision_resolution.py
```
The test first calls `/predict` and asserts conflicts exist, then calls `/resolve` and asserts the returned schedule respects per-section headway constraints.

## Benchmark Panel (Model Comparison)

The Scenario Analysis page includes a Benchmark Panel to compare delay prediction models (`baseline`, `mlp`, `gnn`, and optional `auto`). It uses the current scenario payload as a single-state diagnostic (not a longitudinal validation set).

Metrics per model:
- `mae`: Mean Absolute Error vs `current_delay_minutes` (proxy ground truth).
- `rmse`: Root Mean Squared Error (penalizes larger deviations).
- `bias`: Mean signed error (positive = overprediction, negative = underprediction).
- `max_error`: Largest absolute error among evaluated trains.
- `mean_pred`: Mean predicted delay minutes.
- `mape_pct` (optional): Mean Absolute Percentage Error (only trains with ground-truth > 0).
- `mae_ci_low`, `mae_ci_high`: Approximate 95% confidence interval for MAE (normal approximation using sample standard deviation of absolute errors / sqrt(n)).
- `n_trains`: Total trains in scenario; `n_eval`: Trains actually evaluated (can differ if excluding missing truth values).

Controls:
- Include Auto: Adds a run with `model=auto` to see selection logic outcome.
- Exclude Missing Truth: When enabled (default), trains lacking explicit `current_delay_minutes` are excluded from error metrics (rather than treated as zero).
- Include MAPE: Adds percentage error column where ground-truth delay > 0.
- Show 95% CI: Toggles confidence interval columns.
- Persist History File: Filename to append time-stamped benchmark results (JSON). Empty string keeps history in-memory only.
- Show History Plot: Renders a line plot of MAE over past benchmark runs per model.
- Clear History: Resets in-memory (and file if provided) history entries.

History JSON structure (appended entries):
```json
{
  "ts": 1710000000,
  "metrics": [ { "model": "baseline", "mae": 0.5, ... }, ... ],
  "sort": "mae",
  "include_auto": true,
  "n_trains": 12,
  "exclude_missing": true,
  "include_mape": false
}
```

Planned enhancements:
- Persisted multi-scenario aggregate benchmarking.
- True labels sourced from historical arrival events instead of current snapshot delays.
- Uncertainty intervals once models output prediction variance.


## Run everything (one command)

We provide helper scripts to bring up the full stack (API + Streamlit UI) and optionally run the collision demo:

```powershell
# From repo root
./scripts/run_all.ps1 -HostApi 127.0.0.1 -PortApi 8000 -UiPort 8501 -RunDemo -OpenBrowser -UseNewWindows

# Later, to stop servers
./scripts/stop_all.ps1 -PortApi 8000 -UiPort 8501
```

Notes:
- The script will create `.venv`, install `requirements.txt`, and train a delay model if `data/delay_model.pt` is missing (requires `scripts/train_delay_model.ps1`). Use `-SkipTrainModel` to skip training.
- `-UseNewWindows` starts API and UI in separate PowerShell windows; omit it to run them as background processes.
- `-RunDemo` executes the collision demo after the API is up.
## Next Steps
- Replace greedy with MILP/CP for higher optimality.
- Add disruption handling and rapid re-optimization.
- Build REST API and controller dashboard.

Background and problem statement are in the SIH prompt text provided by the author.
Here is a comprehensive `README.md` file tailored for your project.

-----


## 1\. Project Overview

This project aims to develop an intelligent Decision Support System (DSS) to maximize section throughput and optimize train traffic control for Indian Railways. The current system relies heavily on the manual, experience-based decisions of Section Controllers, which is becoming increasingly insufficient due to rising traffic density and network complexity.[1, 2]


## 2\. System Architecture

The system is designed with a modular, multi-layered architecture. The core philosophy is **augmented intelligence**, where the AI assists the human controller, who retains final authority.[4, 5, 6]


1.  **Data Ingestion & Integration Layer**: The system's sensory interface. It connects to various railway data sources, cleans and standardizes the data, and feeds it into the system.[7, 8, 9, 10, 11]
2.  **Digital Twin & Simulation Environment**: The heart of the system. It maintains a high-fidelity, real-time virtual model of the railway network. This serves as the single source of truth for the AI and a sandbox for "what-if" analysis.[8, 12, 13, 14]
3.  **AI Core (Prediction & Optimization Engines)**: The "brain" of the DSS. It processes data from the Digital Twin to forecast future states and generate optimized operational plans.[15, 16]
4.  **Controller Command & Control Interface (C3I)**: The frontend HMI through which the controller interacts with the system, visualizes data, and acts on AI-driven recommendations.[17, 18, 4]

## 3\. Technology Stack

This project will leverage a modern, Python-based stack suitable for data science, machine learning, and real-time applications.

  * **Backend Language**: Python 3.9+
  * **API Framework**: FastAPI / Flask
  * **Data Processing**:
      * Pandas, NumPy
      * Apache NiFi (for managing complex data pipelines) [8]
  * **Databases**:
      * **Time-Series**: InfluxDB or TimescaleDB (for high-frequency train position data)
      * **Data Warehouse**: PostgreSQL or a cloud-based solution (for historical data, timetables)
  * **AI & Machine Learning**:
      * **Core Libraries**: TensorFlow 2.x / PyTorch
      * **GNNs**: PyTorch Geometric (PyG) or Deep Graph Library (DGL)
      * **General ML**: Scikit-learn [19]
      * **RL**: Stable Baselines3, RLlib
  * **Optimization**:
      * **Constraint Programming**: Google OR-Tools [20]
      * **MILP Solvers**: PuLP (wrapper), with solvers like CBC, Gurobi, or CPLEX
      * **Metaheuristics**: Libraries like `geneticalgorithm`, `simanneal`, or custom implementations.
  * **Frontend (C3I)**:
      * **Framework**: React or Vue.js
      * **Visualization**: D3.js, Vis.js (for time-distance graphs), Mapbox/Leaflet (for geographic maps)
  * **Deployment**: Docker, Kubernetes

## 4\. Project Structure

A modular structure is proposed to keep the codebase organized and maintainable.

```
.
├── data/                  # Sample data (CSV, JSON, GTFS) for development
│   ├── raw/
│   └── processed/
├── notebooks/             # Jupyter notebooks for EDA, model prototyping
├── src/                   # Main source code
│   ├── api/               # FastAPI endpoints and logic
│   ├── ai_core/           # Core AI and optimization models
│   │   ├── predictive_engine/
│   │   └── optimization_engine/
│   ├── data_ingestion/    # Scripts for data collection and processing
│   ├── digital_twin/      # Simulation environment and network model
│   └── c3i_frontend/      # Frontend application code (React/Vue)
├── tests/                 # Unit and integration tests
├── docs/                  # Project documentation
├──.env.example           # Environment variable template
├── docker-compose.yml     # Docker configuration
├── README.md              # This file
└── requirements.txt       # Python dependencies
```

## 5\. Data Sources & Schema

The system requires access to diverse, real-time, and static data sources.

| Data Category | Potential Sources / Feeds | Format | Update Frequency |
| :--- | :--- | :--- | :--- |
| **Train Position** | Live Train Status APIs (e.g., RailRadar API) [21, 22], Train Describer (TD) [23, 24] | JSON/XML | Real-time |
| **Train Events** | TRUST Feed, Live Status APIs [23, 22] | JSON/XML | Real-time |
| **Timetables** | Official Schedule Feeds, GTFS/GTFS-RT [25, 26, 27] | CIF, JSON, TXT | Daily / Real-time |
| **Infrastructure** | IR Planning Systems, railML [28], Public GIS Data | XML, JSON | As updated |
| **External Data** | Weather APIs, Public Event Calendars | JSON | Real-time/Hourly |

#### **API Integration:**

Initial development can leverage public APIs for Indian Railways data. The **RailRadar API** is a strong candidate.[22]

  * **Base URL**: `https://railradar.in/api/v1`
  * **Authentication**: Requires an `x-api-key` header.
  * **Key Endpoints**:
      * `GET /trains/live-map`: Real-time position of all running trains.
      * `GET /trains/{trainNumber}/schedule`: Detailed schedule for a specific train.
      * `GET /trains/between`: Find all trains between two stations.

## 6\. Backend Modules & Functionalities (Development Roadmap)

This section outlines the core components to be built for the backend.

#### **Module 1: Data Ingestion**

  * **Task 1.1: API Connectors**: Implement Python clients to fetch data from railway APIs (e.g., RailRadar) and weather APIs.
  * **Task 1.2: Data Parsers**: Create functions to parse and standardize incoming data (GTFS, JSON) into a unified internal schema.
  * **Task 1.3: Data Storage**: Write scripts to load processed data into the appropriate databases (time-series data into InfluxDB, static/historical data into PostgreSQL).

#### **Module 2: Digital Twin**

  * **Task 2.1: Network Graph Model**: Use a library like `networkx` to represent the railway network. Nodes will be stations, signals, and junctions. Edges will be track segments with attributes like length, speed limit, and block status.
  * **Task 2.2: State Management**: Develop a class to manage the real-time state of the network, updating train positions, signal aspects, and track occupancy based on ingested data.
  * **Task 2.3: Simulation Engine**: Implement a discrete-time simulation loop that can project future train movements based on current state, physics, and signaling rules (Absolute Block System).[29] This is crucial for "what-if" analysis.

#### **Module 3: AI Core - Predictive Engine**

  * **Task 3.1: GNN for State Representation**: Build a Heterogeneous Graph Neural Network (HetGNN) using PyG/DGL. The model will learn embeddings for trains and stations that capture complex network interactions.[30, 31]
  * **Task 3.2: Delay Prediction Model**: Use the GNN embeddings as features for a downstream model (e.g., MLP, LSTM) to predict train delays at future points in their journey.[32, 33, 34, 19]
  * **Task 3.3: Conflict Detection**: Write logic that uses the predicted trajectories from the simulation engine to identify potential future conflicts (e.g., two trains predicted to occupy the same block section).

#### **Module 4: AI Core - Optimization Engine**

  * **Task 4.1: Constraint Satisfaction Model**: Using Google OR-Tools, define the hard constraints of the railway system (e.g., a track segment can only be occupied by one train at a time).[35, 36, 20, 4] This module will validate the feasibility of any proposed schedule.
  * **Task 4.2: Real-time Rescheduling (Metaheuristics)**: Implement a **Genetic Algorithm** or **Simulated Annealing** to resolve predicted conflicts.[37, 38, 39, 40, 41, 42] The algorithm will search for a new, near-optimal schedule (e.g., by adjusting hold times or overtakes) that minimizes the primary KPI (total delay).
  * **Task 4.3 (Advanced): Reinforcement Learning**: Develop a MARL environment using the Digital Twin. Each train can be an agent that learns an optimal dispatching policy to navigate the network and avoid conflicts.[43, 15, 44, 16, 45, 46, 47, 48, 49]

#### **Module 5: Backend API**

  * **Task 5.1: Expose System State**: Create endpoints to provide the C3I frontend with real-time data from the Digital Twin.
  * **Task 5.2: Deliver AI Insights**: Develop endpoints that serve predictions, identified conflicts, and the optimized schedules generated by the AI Core.
  * **Task 5.3: Enable "What-If" Scenarios**: Create an endpoint that allows the frontend to submit a hypothetical action (e.g., "hold train X for 5 mins") and returns the simulated outcome.

## 7\. Setup and Installation

1.  **Clone the repository:**

    ```bash
    git clone <repository-url>
    cd <repository-name>
    ```

2.  **Set up environment variables:**
    Copy the `.env.example` file to `.env` and fill in your credentials (e.g., API keys, database connection strings).

    ```bash
  cp .env.example .env
    ```

3.  **Install dependencies:**
    It is recommended to use a virtual environment.

    ```bash
    python -m venv venv
  source venv/bin/activate  # On Windows PowerShell: `.\\venv\\Scripts\\Activate.ps1`
    pip install -r requirements.txt
    ```

4.  **Run the application:**
  Start the API locally:

  ```powershell
  uvicorn src.api:app --host 0.0.0.0 --port 8000
  ```

5.  **Run tests:**

    ```bash
    pytest
    ```

## Persistence (SQLite) endpoints

The API includes simple persistence to save scenarios and runs in a local SQLite DB at `data/sih.db`.

 `PUT /scenarios/{sid}` → update scenario name/payload
 `DELETE /scenarios/{sid}` → delete scenario and its runs
 `DELETE /runs/{rid}` → delete a run

Examples (PowerShell with curl):
 - Delete selected scenario or its latest run.
 - Download the latest run’s schedule as CSV.
```powershell
$payload = @{
  name = "demo-s1"
  payload = @{
    sections = @(@{ id = "S1"; headway_seconds = 120; traverse_seconds = 100 })
    trains = @(
      @{ id = "A"; priority = 1; planned_departure = 0; route_sections = @("S1") },
      @{ id = "B"; priority = 2; planned_departure = 30; route_sections = @("S1") }
    )
  }
} | ConvertTo-Json -Depth 6

curl -s -X POST http://localhost:8000/scenarios -H "Content-Type: application/json" -d $payload

curl -s http://localhost:8000/scenarios

# Assume previous response had id=1
curl -s -X POST "http://localhost:8000/scenarios/1/run?solver=milp&otp_tolerance=300"

# Assume previous response had run_id=1
curl -s http://localhost:8000/runs/1 | ConvertFrom-Json | Format-List

# List runs for scenario id=1
curl -s http://localhost:8000/scenarios/1/runs | ConvertFrom-Json | Format-List
```

## 8\. How to Contribute

Contributions are welcome\! Please follow these steps:

1.  Fork the repository.
2.  Create a new branch for your feature (`git checkout -b feature/your-feature-name`).
3.  Make your changes and commit them with clear, descriptive messages.
4.  Ensure all tests pass.
5.  Push your changes to your fork (`git push origin feature/your-feature-name`).
6.  Create a pull request to the `main` branch of the original repository.

Please adhere to the project's coding standards (e.g., PEP 8 for Python).

## 9\. License

This project is licensed under the MIT License. See the `LICENSE` file for details.