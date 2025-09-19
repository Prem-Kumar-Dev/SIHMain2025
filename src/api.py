import json
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Dict, Any

from src.core.models import NetworkModel, Section, TrainRequest, ScheduleItem
from src.core.solver import schedule_trains
from src.sim.simulator import summarize_schedule, lateness_kpis
from src.sim.scenario import run_scenario, gantt_json
from src.sim.audit import write_audit
from src.store.db import (
    init_db,
    save_scenario,
    list_scenarios,
    get_scenario,
    save_run,
    get_run,
    list_runs_by_scenario,
    update_scenario,
    delete_scenario,
    delete_run,
)
from fastapi.responses import StreamingResponse, RedirectResponse, Response
from src.ai_core.predictive_engine.feature_engineering import build_features_from_state
from src.ai_core.predictive_engine.model import BaselineDelayRegressor
from src.ai_core.predictive_engine.conflict_detector import detect_future_conflicts
from src.ai_core.predictive_engine.config import PredictiveConfig
from src.ai_core.predictive_engine.gnn.graph_builder import build_hetero_graph
from src.ai_core.predictive_engine.gnn.model_stub import GNNDelayPredictor as StubGNNPredictor
try:  # prefer real lightweight GNN prototype
    from src.ai_core.predictive_engine.gnn.model_gnn import HetGNNDelayPredictor  # type: ignore
except Exception:
    HetGNNDelayPredictor = None  # type: ignore
try:  # existing MLP torch model
    from src.ai_core.predictive_engine.gnn.model_torch import TorchDelayPredictor  # type: ignore
except Exception:
    TorchDelayPredictor = None  # type: ignore
from src.ai_core.predictive_engine.data_client import RailRadarClient
from src.ai_core.predictive_engine.live_mapping import map_live_to_state
import io, csv

app = FastAPI(title="SIH Train Scheduler API")
init_db()

# Helper: sanitize incoming train dicts to match TrainRequest signature
_TRAIN_ALLOWED_KEYS = {"id", "priority", "route_sections", "planned_departure", "dwell_before", "due_time"}

def _clean_train_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(d, dict):
        return {}
    return {k: v for k, v in d.items() if k in _TRAIN_ALLOWED_KEYS}

@app.get("/")
async def root() -> RedirectResponse:
    # Redirect base URL to interactive docs to avoid 404 confusion
    return RedirectResponse(url="/docs")

@app.get("/favicon.ico")
async def favicon() -> Response:
    # Return empty 204 for favicon to avoid noisy 404s in logs
    return Response(status_code=204)

class SectionIn(BaseModel):
    id: str
    headway_seconds: int
    traverse_seconds: int
    block_windows: list[tuple[int, int]] | None = None
    platform_capacity: int | None = None
    conflicts_with: Dict[str, int] | None = None
    conflict_groups: Dict[str, int] | None = None

class TrainIn(BaseModel):
    id: str
    priority: int
    planned_departure: int
    route_sections: List[str]
    dwell_before: Dict[str, int] | None = None
    due_time: int | None = None

class ScheduleItemOut(BaseModel):
    train_id: str
    section_id: str
    entry: int
    exit: int


class HoldAdjustment(BaseModel):
    train_id: str
    add_seconds: int


class AdjustmentRequest(BaseModel):
    state: Dict[str, Any]
    holds: List[HoldAdjustment]
    solver: str | None = None
    otp_tolerance: int | None = 0



@app.post("/predict")
async def predict(body: Dict[str, Any], model: str | None = None) -> Dict[str, Any]:
    """Predict per-train delay (minutes) and simple future conflicts.

    Input shape mirrors /schedule with optional dynamic fields like `current_delay_minutes`.
    Output includes per-train delay predictions and a naive conflict list for the next section.
    """
    cfg = PredictiveConfig()
    preds: Dict[str, float]
    choice = (model or cfg.model_kind or "auto").lower()
    preds = {}
    used: str | None = None
    if choice in ("mlp", "auto"):
        # Feature-based Torch MLP path if weights are available
        try:
            if cfg.model_path and TorchDelayPredictor is not None:
                feats = build_features_from_state(body)
                preds = TorchDelayPredictor(cfg.model_path).predict_minutes(feats)
        except Exception:
            preds = {}
        if preds:
            used = "mlp"
    if not preds and choice in ("gnn", "auto"):
        # GNN path: attempt real prototype, fallback to stub
        try:
            graph, idx = build_hetero_graph(body)
            if HetGNNDelayPredictor is not None:
                gnn = HetGNNDelayPredictor(model_path=cfg.model_path)
            else:
                gnn = StubGNNPredictor(model_path=cfg.model_path)
            preds = gnn.predict_minutes(graph, idx)
        except Exception:
            preds = {}
        if preds:
            used = "gnn"
    if not preds:
        # Baseline fallback
        feats = build_features_from_state(body)
        preds = BaselineDelayRegressor().predict(feats)
        used = used or "baseline"
    # Heuristic conflict detection using predicted ETAs
    conflicts = detect_future_conflicts(preds, body)
    # Provide legacy alias 'conflicts' expected by some tests/tools
    return {
        "predicted_delay_minutes": preds,
        "predicted_conflicts": conflicts,
        "conflicts": conflicts,
        "model_used": used or choice,
    }


@app.post("/resolve")
async def resolve(body: Dict[str, Any], solver: str = "greedy", otp_tolerance: int = 0, milp_time_limit: int | None = None) -> Dict[str, Any]:
    """Resolve predicted conflicts by scheduling only affected trains and sections.

    Body:
      {
        "state": { sections: [...], trains: [...] },
        "predicted_conflicts": [ { section_id, trains: [..] }, ... ]
      }
    """
    # Allow direct state payload (compat with tests calling /resolve with scenario directly)
    if "state" in body or "predicted_conflicts" in body:
        state = body.get("state") or {}
        conflicts = body.get("predicted_conflicts") or body.get("conflicts") or []
    else:
        # Assume full scenario body is passed directly
        state = body
        conflicts = []
    if not isinstance(state, dict) or not state.get("trains"):
        return {"error": "missing state"}
    # Determine involved train ids
    involved: set[str] = set()
    for c in conflicts:
        for tid in c.get("trains", []):
            if isinstance(tid, str):
                involved.add(tid)
    if not involved:
        # Without conflicts, fall back to full schedule of provided trains (acts like /schedule subset)
        try:
            sections = []
            for s in state.get("sections", []):
                bw = s.get("block_windows") or []
                sections.append(Section(
                    id=s["id"], headway_seconds=s["headway_seconds"], traverse_seconds=s["traverse_seconds"],
                    block_windows=[(int(a), int(b)) for a, b in bw] if bw else None,
                    platform_capacity=s.get("platform_capacity"),
                    conflicts_with=s.get("conflicts_with"),
                    conflict_groups=s.get("conflict_groups"),
                ))
            trains = [TrainRequest(**_clean_train_dict(t)) for t in (state.get("trains") or [])]
            network = NetworkModel(sections=sections)
            items = schedule_trains(trains, network, solver=solver, milp_time_limit=milp_time_limit)
            k = summarize_schedule(items)
            lk = lateness_kpis(items, trains, otp_tolerance_s=otp_tolerance)
            lk0 = lateness_kpis(items, trains, otp_tolerance_s=0)
            k = {**k, **lk, "otp0_end": lk0.get("otp_end", 0.0), "otp_tolerance_used": int(otp_tolerance)}
            sched = []
            for it in items:
                d = ScheduleItemOut(**vars(it)).model_dump()
                d["entry_time"], d["exit_time"] = d["entry"], d["exit"]
                sched.append(d)
            # KPI aliases
            if "otp_end" in k and "on_time_percentage" not in k:
                k["on_time_percentage"] = k.get("otp_end", 0.0)
            if "avg_lateness" in k and "avg_delay_minutes" not in k:
                try:
                    k["avg_delay_minutes"] = round(float(k.get("avg_lateness", 0.0)) / 60.0, 3)
                except Exception:
                    k["avg_delay_minutes"] = 0.0
            return {"kpis": k, "schedule": sched}
        except Exception:
            return {"kpis": {"total_trains": 0, "otp_tolerance_used": int(otp_tolerance)}, "schedule": []}
    # Filter trains
    trains_in = [t for t in (state.get("trains") or []) if t.get("id") in involved]
    # Collect referenced sections from their routes
    section_ids: set[str] = set()
    for t in trains_in:
        for sid in (t.get("route_sections") or []):
            section_ids.add(sid)
    sections_in = [s for s in (state.get("sections") or []) if s.get("id") in section_ids]
    # Build domain objects
    sections = []
    for s in sections_in:
        bw = s.get("block_windows") or []
        sections.append(Section(
            id=s["id"], headway_seconds=s["headway_seconds"], traverse_seconds=s["traverse_seconds"],
            block_windows=[(int(a), int(b)) for a, b in bw] if bw else None,
            platform_capacity=s.get("platform_capacity"),
            conflicts_with=s.get("conflicts_with"),
            conflict_groups=s.get("conflict_groups"),
        ))
    trains = [TrainRequest(**_clean_train_dict(t)) for t in trains_in]
    network = NetworkModel(sections=sections)
    items = schedule_trains(trains, network, solver=solver, milp_time_limit=milp_time_limit)
    k = summarize_schedule(items)
    lk = lateness_kpis(items, trains, otp_tolerance_s=otp_tolerance)
    lk0 = lateness_kpis(items, trains, otp_tolerance_s=0)
    k = {**k, **lk, "otp0_end": lk0.get("otp_end", 0.0), "otp_tolerance_used": int(otp_tolerance)}
    schedule_out = []
    for it in items:
        d = ScheduleItemOut(**vars(it)).model_dump()
        # Add aliases for compatibility with external tests expecting entry_time/exit_time
        d["entry_time"], d["exit_time"] = d["entry"], d["exit"]
        schedule_out.append(d)
    if "otp_end" in k and "on_time_percentage" not in k:
        k["on_time_percentage"] = k.get("otp_end", 0.0)
    if "avg_lateness" in k and "avg_delay_minutes" not in k:
        try:
            k["avg_delay_minutes"] = round(float(k.get("avg_lateness", 0.0)) / 60.0, 3)
        except Exception:
            k["avg_delay_minutes"] = 0.0
    return {"kpis": k, "schedule": schedule_out}


@app.post("/adjust")
async def adjust(body: AdjustmentRequest) -> Dict[str, Any]:
    """Apply a list of hold adjustments (departure delays) and return a new schedule.

    Body shape:
      {
        "state": {sections: [...], trains: [...]},
        "holds": [ {train_id, add_seconds}, ... ],
        "solver": "greedy" | "milp" (optional),
        "otp_tolerance": int (optional)
      }

    Behaviour:
      - Adjusts each referenced train's planned_departure += add_seconds.
      - Re-schedules ALL trains (simpler + ensures downstream KPIs coherent).
      - Returns schedule + KPIs (with legacy aliases) so UI can refresh.
    """
    state = body.state or {}
    holds = body.holds or []
    solver = body.solver or "greedy"
    otp_tolerance = int(body.otp_tolerance or 0)
    if not isinstance(state, dict) or not state.get("trains"):
        return {"error": "missing state"}
    trains_in = state.get("trains") or []
    by_id = {t.get("id"): t for t in trains_in if isinstance(t, dict)}
    for h in holds:
        if h.train_id in by_id:
            try:
                base = int(by_id[h.train_id].get("planned_departure", 0) or 0)
                by_id[h.train_id]["planned_departure"] = base + int(h.add_seconds)
            except Exception:
                pass
    # Build domain objects and reuse schedule logic
    sections = []
    for s in state.get("sections", []):
        bw = s.get("block_windows") or []
        sections.append(Section(
            id=s["id"], headway_seconds=s["headway_seconds"], traverse_seconds=s["traverse_seconds"],
            block_windows=[(int(a), int(b)) for a, b in bw] if bw else None,
            platform_capacity=s.get("platform_capacity"),
            conflicts_with=s.get("conflicts_with"),
            conflict_groups=s.get("conflict_groups"),
        ))
    trains = [TrainRequest(**_clean_train_dict(t)) for t in trains_in]
    network = NetworkModel(sections=sections)
    items = schedule_trains(trains, network, solver=solver)
    k = summarize_schedule(items)
    lk = lateness_kpis(items, trains, otp_tolerance_s=otp_tolerance)
    lk0 = lateness_kpis(items, trains, otp_tolerance_s=0)
    k = {**k, **lk, "otp0_end": lk0.get("otp_end", 0.0), "otp_tolerance_used": int(otp_tolerance)}
    sched = []
    for it in items:
        d = ScheduleItemOut(**vars(it)).model_dump()
        d["entry_time"], d["exit_time"] = d["entry"], d["exit"]
        sched.append(d)
    # KPI aliases
    if "otp_end" in k and "on_time_percentage" not in k:
        k["on_time_percentage"] = k.get("otp_end", 0.0)
    if "avg_lateness" in k and "avg_delay_minutes" not in k:
        try:
            k["avg_delay_minutes"] = round(float(k.get("avg_lateness", 0.0)) / 60.0, 3)
        except Exception:
            k["avg_delay_minutes"] = 0.0
    return {"kpis": k, "schedule": sched, "applied_holds": [h.model_dump() for h in holds]}


@app.post("/live/snapshot")
async def live_snapshot(body: Dict[str, Any] | None = None, use_live: bool = False, max_trains: int = 50) -> Dict[str, Any]:
    """Return a network state.

    - If use_live=true and RAILRADAR_API_KEY is set, this will eventually fetch from RailRadar.
    - For now, returns the provided body (if any) or a minimal sample to avoid external calls by default.
    """
    cfg = PredictiveConfig()
    if use_live and not cfg.is_live_enabled:
        return {"enabled": False, "reason": "RAILRADAR_API_KEY not set", "state": None}
    fetched_count = 0
    fetch_error: str | None = None
    mapped_state = None
    if use_live and cfg.is_live_enabled:
        try:
            client = RailRadarClient.from_config(cfg)
            live = await client.get_live_map()
            # Attempt to count trains conservatively
            if isinstance(live, dict):
                if isinstance(live.get("trains"), list):
                    fetched_count = len(live["trains"])  # typical shape
                else:
                    # fallback: count top-level list-like fields
                    fetched_count = sum(1 for _ in live.values() if isinstance(_, list))
            elif isinstance(live, list):
                fetched_count = len(live)
            # Map live payload to internal state, preserving provided sections if present in body
            sections_hint = []
            if isinstance(body, dict) and isinstance(body.get("sections"), list):
                sections_hint = body.get("sections")
            mapped_state = map_live_to_state(live, sections_hint=sections_hint, max_trains=max_trains)
        except Exception as e:
            fetch_error = "fetch_failed"
    # Echo provided state if present
    if isinstance(body, dict) and body.get("sections") and body.get("trains"):
        return {"enabled": bool(cfg.is_live_enabled and use_live), "state": body}
    # If we have a mapped live state, return it
    if isinstance(mapped_state, dict) and mapped_state.get("trains"):
        return {
            "enabled": bool(cfg.is_live_enabled and use_live),
            "fetched_count": int(fetched_count),
            "fetch_error": fetch_error,
            "state": mapped_state,
        }
    # Minimal sample fallback
    sample = {
        "sections": [
            {"id": "S1", "headway_seconds": 120, "traverse_seconds": 100},
            {"id": "S2", "headway_seconds": 120, "traverse_seconds": 120},
        ],
        "trains": [
            {"id": "A", "priority": 1, "planned_departure": 0, "route_sections": ["S1", "S2"], "current_delay_minutes": 0.0},
            {"id": "B", "priority": 2, "planned_departure": 30, "route_sections": ["S1"], "current_delay_minutes": 1.0},
        ],
    }
    return {
        "enabled": bool(cfg.is_live_enabled and use_live),
        "fetched_count": int(fetched_count),
        "fetch_error": fetch_error,
        "state": sample,
    }

@app.get("/demo")
async def demo(solver: str = "greedy") -> Dict[str, Any]:
    sections = [
        Section(id="S1", headway_seconds=120, traverse_seconds=100),
        Section(id="S2", headway_seconds=120, traverse_seconds=120),
    ]
    network = NetworkModel(sections=sections)
    trains = [
        TrainRequest(id="T1", priority=1, planned_departure=0, route_sections=["S1", "S2"]),
        TrainRequest(id="T2", priority=2, planned_departure=60, route_sections=["S1"]),
    ]
    schedule = schedule_trains(trains, network, solver=solver)
    kpis = summarize_schedule(schedule)
    return {
        "kpis": kpis,
        "schedule": [ScheduleItemOut(**vars(it)).model_dump() for it in schedule],
    }

@app.post("/schedule")
async def schedule(body: Dict[str, Any], solver: str = "greedy", otp_tolerance: int = 0, milp_time_limit: int | None = None) -> Dict[str, Any]:
    # Pydantic coercion helps, but we construct Section explicitly to ensure tuples
    sections = []
    for s in body.get("sections", []):
        bw = s.get("block_windows") or []
        section = Section(
            id=s["id"],
            headway_seconds=s["headway_seconds"],
            traverse_seconds=s["traverse_seconds"],
            block_windows=[(int(a), int(b)) for a, b in bw] if bw else None,
            platform_capacity=s.get("platform_capacity"),
            conflicts_with=s.get("conflicts_with"),
            conflict_groups=s.get("conflict_groups"),
        )
        sections.append(section)
    trains = [TrainRequest(**_clean_train_dict(t)) for t in body.get("trains", [])]
    network = NetworkModel(sections=sections)
    schedule_items = schedule_trains(trains, network, solver=solver, milp_time_limit=milp_time_limit)
    kpis = summarize_schedule(schedule_items)
    # Extend with lateness KPIs if applicable
    lk = lateness_kpis(schedule_items, trains, otp_tolerance_s=otp_tolerance)
    lk0 = lateness_kpis(schedule_items, trains, otp_tolerance_s=0)
    kpis = {**kpis, **lk, "otp0_end": lk0.get("otp_end", 0.0), "otp_tolerance_used": int(otp_tolerance)}
    # Compute per-train lateness if due_time present
    lateness_by_train: Dict[str, int] = {}
    for t in trains:
        if t.due_time is not None:
            # find last leg entry for this train
            last_sid = t.route_sections[-1]
            entries = [it.entry for it in schedule_items if it.train_id == t.id and it.section_id == last_sid]
            if entries:
                lateness_by_train[t.id] = max(0, int(entries[0]) - int(t.due_time))
    # KPI aliases for compatibility
    if "otp_end" in kpis and "on_time_percentage" not in kpis:
        kpis["on_time_percentage"] = kpis.get("otp_end", 0.0)
    if "avg_lateness" in kpis and "avg_delay_minutes" not in kpis:
        try:
            kpis["avg_delay_minutes"] = round(float(kpis.get("avg_lateness", 0.0)) / 60.0, 3)
        except Exception:
            kpis["avg_delay_minutes"] = 0.0
    resp = {
        "kpis": kpis,
        "schedule": [ScheduleItemOut(**vars(it)).model_dump() for it in schedule_items],
        "lateness_by_train": lateness_by_train,
    }
    write_audit({
        "type": "schedule",
        "solver": solver,
        "kpis": kpis,
        "count": len(schedule_items),
    })
    return resp


@app.post("/whatif")
async def whatif(body: Dict[str, Any], solver: str = "greedy", otp_tolerance: int = 0, milp_time_limit: int | None = None) -> Dict[str, Any]:
    # Build network and trains as in /schedule
    sections = []
    for s in body.get("sections", []):
        bw = s.get("block_windows") or []
        section = Section(
            id=s["id"],
            headway_seconds=s["headway_seconds"],
            traverse_seconds=s["traverse_seconds"],
            block_windows=[(int(a), int(b)) for a, b in bw] if bw else None,
            platform_capacity=s.get("platform_capacity"),
            conflicts_with=s.get("conflicts_with"),
            conflict_groups=s.get("conflict_groups"),
        )
        sections.append(section)
    trains = [TrainRequest(**_clean_train_dict(t)) for t in body.get("trains", [])]
    network = NetworkModel(sections=sections)

    # run_scenario currently doesn't accept time limit; call schedule_trains directly for control
    items = schedule_trains(trains, network, solver=solver, milp_time_limit=milp_time_limit)
    result = {"schedule": items}
    items = result["schedule"]
    # lateness map
    lateness_by_train: Dict[str, int] = {}
    for t in trains:
        if t.due_time is not None:
            last_sid = t.route_sections[-1]
            entries = [it.entry for it in items if it.train_id == t.id and it.section_id == last_sid]
            if entries:
                lateness_by_train[t.id] = max(0, int(entries[0]) - int(t.due_time))
    resp = {
        "gantt": gantt_json(items),
        "count": len(items),
        "lateness_by_train": lateness_by_train,
        "reason": None if items else "No schedule items produced (check sections/trains input)",
        "schedule": [
            {**ScheduleItemOut(**vars(it)).model_dump(), "entry_time": it.entry, "exit_time": it.exit}
            for it in items
        ],
    }
    write_audit({
        "type": "whatif",
        "solver": solver,
        "count": len(items),
    })
    return resp


@app.post("/kpis")
async def kpis(body: Dict[str, Any], solver: str = "greedy", otp_tolerance: int = 0, milp_time_limit: int | None = None) -> Dict[str, Any]:
    # Compute KPIs for provided scenario without returning the full schedule
    sections = []
    for s in body.get("sections", []):
        bw = s.get("block_windows") or []
        section = Section(
            id=s["id"],
            headway_seconds=s["headway_seconds"],
            traverse_seconds=s["traverse_seconds"],
            block_windows=[(int(a), int(b)) for a, b in bw] if bw else None,
        )
        sections.append(section)
    trains = [TrainRequest(**_clean_train_dict(t)) for t in body.get("trains", [])]
    network = NetworkModel(sections=sections)
    items = schedule_trains(trains, network, solver=solver, milp_time_limit=milp_time_limit)
    k = summarize_schedule(items)
    lk = lateness_kpis(items, trains, otp_tolerance_s=otp_tolerance)
    lk0 = lateness_kpis(items, trains, otp_tolerance_s=0)
    k = {**k, **lk, "otp0_end": lk0.get("otp_end", 0.0), "otp_tolerance_used": int(otp_tolerance)}
    if "otp_end" in k and "on_time_percentage" not in k:
        k["on_time_percentage"] = k.get("otp_end", 0.0)
    if "avg_lateness" in k and "avg_delay_minutes" not in k:
        try:
            k["avg_delay_minutes"] = round(float(k.get("avg_lateness", 0.0)) / 60.0, 3)
        except Exception:
            k["avg_delay_minutes"] = 0.0
    write_audit({
        "type": "kpis",
        "solver": solver,
        "kpis": k,
        "count": len(items),
    })
    return {"kpis": k}


# Persistence APIs
@app.post("/scenarios")
async def create_scenario(body: Dict[str, Any]) -> Dict[str, Any]:
    name = body.get("name", "scenario")
    payload = body.get("payload")
    if not isinstance(payload, dict):
        return {"error": "payload must be an object"}
    sid = save_scenario(name, payload)
    return {"id": sid}


@app.get("/scenarios")
async def scenarios(offset: int = 0, limit: int = 50) -> Dict[str, Any]:
    return {"items": list_scenarios(offset=offset, limit=limit)}


@app.post("/scenarios/{sid}/run")
async def run_saved_scenario(sid: int, solver: str = "greedy", name: str | None = None, comment: str | None = None, otp_tolerance: int = 0, milp_time_limit: int | None = None) -> Dict[str, Any]:
    s = get_scenario(sid)
    if not s:
        return {"error": "scenario not found"}
    payload = json.loads(s["payload"])
    # Reuse /schedule path
    sections = []
    for sec in payload.get("sections", []):
        bw = sec.get("block_windows") or []
        sections.append(Section(
            id=sec["id"], headway_seconds=sec["headway_seconds"], traverse_seconds=sec["traverse_seconds"],
            block_windows=[(int(a), int(b)) for a, b in bw] if bw else None,
            platform_capacity=sec.get("platform_capacity"),
            conflicts_with=sec.get("conflicts_with"),
            conflict_groups=sec.get("conflict_groups"),
        ))
    trains = [TrainRequest(**_clean_train_dict(t)) for t in payload.get("trains", [])]
    network = NetworkModel(sections=sections)
    items = schedule_trains(trains, network, solver=solver, milp_time_limit=milp_time_limit)
    k = summarize_schedule(items)
    # enrich with lateness KPIs and map, plus otp0 and tolerance used
    lk = lateness_kpis(items, trains, otp_tolerance_s=otp_tolerance)
    lk0 = lateness_kpis(items, trains, otp_tolerance_s=0)
    k = {**k, **lk, "otp0_end": lk0.get("otp_end", 0.0), "otp_tolerance_used": int(otp_tolerance)}
    if "otp_end" in k and "on_time_percentage" not in k:
        k["on_time_percentage"] = k.get("otp_end", 0.0)
    if "avg_lateness" in k and "avg_delay_minutes" not in k:
        try:
            k["avg_delay_minutes"] = round(float(k.get("avg_lateness", 0.0)) / 60.0, 3)
        except Exception:
            k["avg_delay_minutes"] = 0.0
    lateness_by_train: Dict[str, int] = {}
    for t in trains:
        if t.due_time is not None and t.route_sections:
            last_sid = t.route_sections[-1]
            entries = [it.entry for it in items if it.train_id == t.id and it.section_id == last_sid]
            if entries:
                lateness_by_train[t.id] = max(0, int(entries[0]) - int(t.due_time))
    # Save run
    rid = save_run(
        scenario_id=sid,
        solver=solver,
        input_payload=payload,
        schedule=[vars(it) for it in items],
    kpis={**k, "lateness_by_train": lateness_by_train},
        name=name,
        comment=comment,
    )
    return {"run_id": rid, "kpis": {**k, "lateness_by_train": lateness_by_train}}


@app.get("/runs/{rid}")
async def get_run_details(rid: int) -> Dict[str, Any]:
    r = get_run(rid)
    if not r:
        return {"error": "run not found"}
    # Decode JSON fields
    r["input_payload"] = json.loads(r["input_payload"])
    r["schedule"] = json.loads(r["schedule"])
    r["kpis"] = json.loads(r["kpis"])
    return {"run": r}


@app.get("/scenarios/{sid}/runs")
async def list_runs_for_scenario(sid: int, offset: int = 0, limit: int = 50) -> Dict[str, Any]:
    # Return lightweight list of runs for a scenario
    runs = list_runs_by_scenario(sid, offset=offset, limit=limit)
    return {"items": runs}


@app.put("/scenarios/{sid}")
async def update_scenario_api(sid: int, body: Dict[str, Any]) -> Dict[str, Any]:
    name = body.get("name")
    payload = body.get("payload")
    ok = update_scenario(sid, name=name, payload=payload if isinstance(payload, dict) else None)
    return {"updated": bool(ok)}


@app.delete("/scenarios/{sid}")
async def delete_scenario_api(sid: int) -> Dict[str, Any]:
    ok = delete_scenario(sid)
    return {"deleted": bool(ok)}


@app.delete("/runs/{rid}")
async def delete_run_api(rid: int) -> Dict[str, Any]:
    ok = delete_run(rid)
    return {"deleted": bool(ok)}


@app.get("/runs/{rid}/lateness.csv")
async def download_lateness_csv(rid: int) -> StreamingResponse:
    r = get_run(rid)
    if not r:
        return StreamingResponse(io.StringIO("error,run not found\n"), media_type="text/csv")
    # Decode columns
    payload = json.loads(r.get("input_payload")) if r.get("input_payload") else {}
    schedule = json.loads(r.get("schedule")) if isinstance(r.get("schedule"), str) else r.get("schedule")
    kpis = json.loads(r.get("kpis")) if isinstance(r.get("kpis"), str) else r.get("kpis")
    lateness_map = {}
    if isinstance(kpis, dict) and "lateness_by_train" in kpis:
        lateness_map = kpis.get("lateness_by_train") or {}
    # Fallback compute if missing
    if not lateness_map:
        try:
            last_map = {}
            for tr in payload.get("trains", []):
                if isinstance(tr, dict) and tr.get("route_sections"):
                    last_map[tr.get("id")] = tr["route_sections"][-1]
            for tr in payload.get("trains", []):
                if tr.get("due_time") is not None and tr.get("id") in last_map:
                    last = last_map[tr.get("id")]
                    entries = [it.get("entry") for it in (schedule or []) if it.get("train_id") == tr.get("id") and it.get("section_id") == last]
                    if entries:
                        lateness_map[tr.get("id")] = max(0, int(entries[0]) - int(tr.get("due_time")))
        except Exception:
            pass
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=["train_id", "lateness_s"])
    writer.writeheader()
    for k, v in (lateness_map or {}).items():
        writer.writerow({"train_id": k, "lateness_s": int(v)})
    buf.seek(0)
    return StreamingResponse(buf, media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=run_{rid}_lateness.csv"})
