import os, sys
# Ensure project root is on sys.path so `ui.*` imports work when launched directly
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
	sys.path.insert(0, ROOT)
import os
import streamlit as st

st.set_page_config(page_title="SIH Train Scheduler", layout="wide")

st.title("SIH Train Scheduler – Controller C3I")
st.caption("Use the sidebar to navigate between Live Dashboard and Scenario Analysis.")

st.markdown("""
### Environment
- API Base: `{}`

### Pages
- Live Dashboard: Real-time view with predictions and conflict resolution advisories.
- Scenario Analysis: Edit scenarios, run what-if schedules, inspect KPIs, and manage persisted scenarios/runs.
""".format(os.environ.get("API_BASE", "http://localhost:8000")))

st.info("Tip: Start the backend API first (e.g., `./scripts/start_api.ps1 -Port 8000`). Set `API_BASE` env var if using a different host/port.")
