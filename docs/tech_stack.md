# Tech Stack Plan

- Core language: Python 3.10+
- Optimization:
  - Phase 1: Greedy + heuristics (already scaffolded)
  - Phase 2: MILP via OR-Tools or PuLP; CP-SAT for discrete constraints
- API: FastAPI (async), Uvicorn for dev server
- UI: Streamlit for quick dashboards (or React + ECharts for production)
- Data storage: SQLite (local dev) → PostgreSQL (prod)
- Messaging/integration: REST/JSON; later gRPC for performance
- Telemetry: Logging + structured audit JSON; Prometheus-compatible metrics later
- Testing: pytest, pytest-cov; mypy for types (optional)
- Packaging: `requirements.txt` for now; `pyproject.toml` later

## Rationale
- Python has rich OR/AI libraries; FastAPI provides clean async APIs; Streamlit enables rapid controller dashboards.
