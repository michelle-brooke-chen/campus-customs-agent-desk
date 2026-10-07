"""Append-only audit trail at output/audit_trail.json.

Every MCP tool call an agent makes, every teammate consultation, every plan,
every human approval decision, and every executed action is appended here.
Each entry gets an increasing `id`, so the board can ask for "events since N".
A database reset starts a fresh trail; the previous one is moved to output/audit_archive/.
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

AUDIT_PATH = Path(__file__).resolve().parent.parent / "output" / "audit_trail.json"
ARCHIVE_DIR = AUDIT_PATH.parent / "audit_archive"
RUN_ID = uuid.uuid4().hex[:12]
MAX_FIELD_CHARS = 4000
UNCLIPPED_FIELDS = {"plan", "summary", "arguments"}  # what a human approves (and its exact arguments) stays whole


def _clip(value: Any) -> Any:
    text = json.dumps(value, default=str)
    if len(text) <= MAX_FIELD_CHARS:
        return json.loads(text)
    return text[:MAX_FIELD_CHARS] + "...[truncated]"


def read_all() -> list[dict]:
    return json.loads(AUDIT_PATH.read_text(encoding="utf-8")) if AUDIT_PATH.exists() else []


def record(event: str, actor: str, ticket_id: int | None = None, **details: Any) -> dict:
    entries = read_all()
    entry = {
        "id": (entries[-1].get("id", len(entries)) + 1) if entries else 1,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "run_id": RUN_ID,
        "ticket_id": ticket_id,
        "actor": actor,
        "event": event,
        **{k: v if k in UNCLIPPED_FIELDS else _clip(v) for k, v in details.items()},
    }
    entries.append(entry)
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_PATH.write_text(json.dumps(entries, indent=2), encoding="utf-8")
    return entry


def start_fresh() -> Path | None:
    """Archive the current trail so the next run starts a clean one. Returns the archive path."""
    if not AUDIT_PATH.exists() or not read_all():
        return None
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = ARCHIVE_DIR / f"audit_trail_{stamp}_{uuid.uuid4().hex[:6]}.json"
    AUDIT_PATH.replace(target)
    return target


def recent(since_id: int = 0, ticket_id: int | None = None, limit: int = 100) -> list[dict]:
    events = [
        e for e in read_all()
        if e.get("id", 0) > since_id and (ticket_id is None or e.get("ticket_id") == ticket_id)
    ]
    return events[-limit:]
