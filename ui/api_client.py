import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
import os
import requests
from typing import Any, Dict, List, Optional


class ApiClient:
    def __init__(self, base_url: Optional[str] = None, timeout: float = 120.0) -> None:
        self.base_url = base_url or os.environ.get("API_BASE", "http://localhost:8000")
        self.timeout = timeout

    def _post(self, path: str, json: Dict[str, Any] | None = None, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
        r = requests.post(f"{self.base_url}{path}", json=json, params=params, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def _get(self, path: str, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
        r = requests.get(f"{self.base_url}{path}", params=params, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    # Live
    def get_live_snapshot(self, state: Optional[Dict[str, Any]] = None, use_live: bool = False, max_trains: int = 50) -> Dict[str, Any]:
        params = {"use_live": str(use_live).lower(), "max_trains": max_trains}
        return self._post("/live/snapshot", json=state or {}, params=params)

    # Predict/Resolve
    def predict_delays(self, state: Dict[str, Any], model: Optional[str] = None) -> Dict[str, Any]:
        params = {"model": model} if model else None
        return self._post("/predict", json=state, params=params)

    def resolve_conflicts(self, state: Dict[str, Any], conflicts: List[Dict[str, Any]], solver: str = "greedy", otp_tolerance: int = 0) -> Dict[str, Any]:
        body = {"state": state, "predicted_conflicts": conflicts}
        return self._post("/resolve", json=body, params={"solver": solver, "otp_tolerance": int(otp_tolerance)})

    # Scheduling/KPIs
    def run_whatif(self, state: Dict[str, Any], solver: str = "greedy", otp_tolerance: int = 0, milp_time_limit: int | None = None) -> Dict[str, Any]:
        params = {"solver": solver, "otp_tolerance": int(otp_tolerance)}
        if milp_time_limit is not None:
            params["milp_time_limit"] = int(milp_time_limit)
        return self._post("/whatif", json=state, params=params)

    def get_kpis(self, state: Dict[str, Any], solver: str = "greedy", otp_tolerance: int = 0, milp_time_limit: int | None = None) -> Dict[str, Any]:
        params = {"solver": solver, "otp_tolerance": int(otp_tolerance)}
        if milp_time_limit is not None:
            params["milp_time_limit"] = int(milp_time_limit)
        return self._post("/kpis", json=state, params=params)

    def schedule(self, state: Dict[str, Any], solver: str = "greedy", otp_tolerance: int = 0, milp_time_limit: int | None = None) -> Dict[str, Any]:
        params = {"solver": solver, "otp_tolerance": int(otp_tolerance)}
        if milp_time_limit is not None:
            params["milp_time_limit"] = int(milp_time_limit)
        return self._post("/schedule", json=state, params=params)

    # Persistence
    def save_scenario(self, payload: Dict[str, Any], name: str) -> Dict[str, Any]:
        return self._post("/scenarios", json={"name": name, "payload": payload})

    def get_scenarios(self, offset: int = 0, limit: int = 50) -> Dict[str, Any]:
        return self._get("/scenarios", params={"offset": offset, "limit": limit})

    def run_saved_scenario(self, sid: int, solver: str = "greedy", name: Optional[str] = None, comment: Optional[str] = None, otp_tolerance: int = 0) -> Dict[str, Any]:
        return self._post(f"/scenarios/{sid}/run", params={"solver": solver, "name": name, "comment": comment, "otp_tolerance": int(otp_tolerance)})

    def list_runs(self, sid: int, offset: int = 0, limit: int = 50) -> Dict[str, Any]:
        return self._get(f"/scenarios/{sid}/runs", params={"offset": offset, "limit": limit})

    def get_run(self, rid: int) -> Dict[str, Any]:
        return self._get(f"/runs/{rid}")

    def delete_run(self, rid: int) -> Dict[str, Any]:
        r = requests.delete(f"{self.base_url}/runs/{rid}", timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def delete_scenario(self, sid: int) -> Dict[str, Any]:
        r = requests.delete(f"{self.base_url}/scenarios/{sid}", timeout=self.timeout)
        r.raise_for_status()
        return r.json()
