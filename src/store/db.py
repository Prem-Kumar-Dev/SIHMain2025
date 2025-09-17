import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

DATA_DIR = (Path(__file__).parents[2] / "data")
DATA_DIR.mkdir(exist_ok=True)
DB_PATH: Path = DATA_DIR / "sih.db"


def set_db_path(path: Path) -> None:
    global DB_PATH
    DB_PATH = Path(path)


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS scenarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scenario_id INTEGER,
                solver TEXT NOT NULL,
                input_payload TEXT NOT NULL,
                schedule TEXT NOT NULL,
                kpis TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(scenario_id) REFERENCES scenarios(id)
            )
            """
        )
        conn.commit()


def save_scenario(name: str, payload: Dict[str, Any]) -> int:
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("INSERT INTO scenarios(name, payload) VALUES(?, ?)", (name, json.dumps(payload, ensure_ascii=False)))
        conn.commit()
        return int(cur.lastrowid)


def list_scenarios() -> List[Dict[str, Any]]:
    with _conn() as conn:
        rows = conn.execute("SELECT id, name, payload, created_at FROM scenarios ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]


def get_scenario(sid: int) -> Optional[Dict[str, Any]]:
    with _conn() as conn:
        r = conn.execute("SELECT id, name, payload, created_at FROM scenarios WHERE id=?", (sid,)).fetchone()
        return dict(r) if r else None


def save_run(scenario_id: Optional[int], solver: str, input_payload: Dict[str, Any], schedule: List[Dict[str, Any]], kpis: Dict[str, Any]) -> int:
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO runs(scenario_id, solver, input_payload, schedule, kpis) VALUES(?,?,?,?,?)",
            (
                scenario_id,
                solver,
                json.dumps(input_payload, ensure_ascii=False),
                json.dumps(schedule, ensure_ascii=False),
                json.dumps(kpis, ensure_ascii=False),
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def get_run(rid: int) -> Optional[Dict[str, Any]]:
    with _conn() as conn:
        r = conn.execute("SELECT * FROM runs WHERE id=?", (rid,)).fetchone()
        return dict(r) if r else None


def list_runs_by_scenario(sid: int) -> List[Dict[str, Any]]:
    with _conn() as conn:
        rows = conn.execute("SELECT id, solver, created_at FROM runs WHERE scenario_id=? ORDER BY id DESC", (sid,)).fetchall()
        return [dict(r) for r in rows]
