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
                name TEXT,
                comment TEXT,
                input_payload TEXT NOT NULL,
                schedule TEXT NOT NULL,
                kpis TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(scenario_id) REFERENCES scenarios(id)
            )
            """
        )
        # Ensure columns exist for backward-compatible upgrades
        try:
            cols = {row[1] for row in conn.execute("PRAGMA table_info(runs)").fetchall()}
            if "name" not in cols:
                conn.execute("ALTER TABLE runs ADD COLUMN name TEXT")
            if "comment" not in cols:
                conn.execute("ALTER TABLE runs ADD COLUMN comment TEXT")
        except Exception:
            pass
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


def save_run(
    scenario_id: Optional[int],
    solver: str,
    input_payload: Dict[str, Any],
    schedule: List[Dict[str, Any]],
    kpis: Dict[str, Any],
    name: Optional[str] = None,
    comment: Optional[str] = None,
) -> int:
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO runs(scenario_id, solver, name, comment, input_payload, schedule, kpis) VALUES(?,?,?,?,?,?,?)",
            (
                scenario_id,
                solver,
                name,
                comment,
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


def list_runs_by_scenario(sid: int, offset: int = 0, limit: int = 50) -> List[Dict[str, Any]]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT id, solver, name, comment, created_at FROM runs WHERE scenario_id=? ORDER BY id DESC LIMIT ? OFFSET ?",
            (sid, limit, offset),
        ).fetchall()
        return [dict(r) for r in rows]


def list_scenarios(offset: int = 0, limit: int = 50) -> List[Dict[str, Any]]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT id, name, payload, created_at FROM scenarios ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [dict(r) for r in rows]


def update_scenario(sid: int, name: Optional[str] = None, payload: Optional[Dict[str, Any]] = None) -> bool:
    sets = []
    args: List[Any] = []
    if name is not None:
        sets.append("name=?")
        args.append(name)
    if payload is not None:
        sets.append("payload=?")
        args.append(json.dumps(payload, ensure_ascii=False))
    if not sets:
        return False
    args.append(sid)
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute(f"UPDATE scenarios SET {', '.join(sets)} WHERE id=?", tuple(args))
        conn.commit()
        return cur.rowcount > 0


def delete_run(rid: int) -> bool:
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM runs WHERE id=?", (rid,))
        conn.commit()
        return cur.rowcount > 0


def delete_scenario(sid: int) -> bool:
    with _conn() as conn:
        cur = conn.cursor()
        # Delete runs first, then scenario
        cur.execute("DELETE FROM runs WHERE scenario_id=?", (sid,))
        cur.execute("DELETE FROM scenarios WHERE id=?", (sid,))
        conn.commit()
        return cur.rowcount > 0
