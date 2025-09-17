import json
from pathlib import Path
from typing import Any, Dict, List

AUDIT_DIR = Path(__file__).parents[2] / "audit"
AUDIT_DIR.mkdir(exist_ok=True)
AUDIT_FILE = AUDIT_DIR / "events.jsonl"


def write_audit(event: Dict[str, Any]) -> None:
    # append a JSONL entry
    with AUDIT_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
