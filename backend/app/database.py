from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from . import config

Path(config.DB_PATH).parent.mkdir(parents=True, exist_ok=True)

SCHEMA = """
CREATE TABLE IF NOT EXISTS cases (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    investigator TEXT DEFAULT '',
    status TEXT DEFAULT 'open',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS findings (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    tool TEXT NOT NULL,
    subject TEXT NOT NULL,
    subject_type TEXT NOT NULL,
    status TEXT NOT NULL,
    summary TEXT DEFAULT '',
    data_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS case_notes (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    note TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_findings_case ON findings(case_id);
CREATE INDEX IF NOT EXISTS idx_notes_case ON case_notes(case_id);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id() -> str:
    return uuid.uuid4().hex[:12]


@contextmanager
def get_conn():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)


# ---------- Cases ----------

def create_case(name: str, description: str = "", investigator: str = "") -> dict:
    cid = new_id()
    ts = now()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO cases (id, name, description, investigator, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 'open', ?, ?)",
            (cid, name, description, investigator, ts, ts),
        )
    return get_case(cid)


def list_cases() -> list:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT c.*, "
            "(SELECT COUNT(*) FROM findings f WHERE f.case_id = c.id) AS finding_count "
            "FROM cases c ORDER BY c.updated_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def get_case(case_id: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
        return dict(row) if row else None


def update_case_status(case_id: str, status: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE cases SET status = ?, updated_at = ? WHERE id = ?",
            (status, now(), case_id),
        )


def touch_case(case_id: str):
    with get_conn() as conn:
        conn.execute("UPDATE cases SET updated_at = ? WHERE id = ?", (now(), case_id))


def delete_case(case_id: str):
    with get_conn() as conn:
        conn.execute("DELETE FROM cases WHERE id = ?", (case_id,))


# ---------- Findings (the "case log") ----------

def log_finding(case_id: str, tool: str, subject: str, subject_type: str,
                status: str, summary: str, data: dict) -> dict:
    fid = new_id()
    ts = now()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO findings (id, case_id, tool, subject, subject_type, status, summary, data_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (fid, case_id, tool, subject, subject_type, status, summary, json.dumps(data), ts),
        )
        conn.execute("UPDATE cases SET updated_at = ? WHERE id = ?", (ts, case_id))
    return get_finding(fid)


def get_finding(finding_id: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM findings WHERE id = ?", (finding_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["data"] = json.loads(d.pop("data_json"))
        return d


def list_findings(case_id: str) -> list:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM findings WHERE case_id = ? ORDER BY created_at ASC", (case_id,)
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["data"] = json.loads(d.pop("data_json"))
            out.append(d)
        return out


def delete_finding(finding_id: str):
    with get_conn() as conn:
        conn.execute("DELETE FROM findings WHERE id = ?", (finding_id,))


# ---------- Notes ----------

def add_note(case_id: str, note: str) -> dict:
    nid = new_id()
    ts = now()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO case_notes (id, case_id, note, created_at) VALUES (?, ?, ?, ?)",
            (nid, case_id, note, ts),
        )
        conn.execute("UPDATE cases SET updated_at = ? WHERE id = ?", (ts, case_id))
    return {"id": nid, "case_id": case_id, "note": note, "created_at": ts}


def list_notes(case_id: str) -> list:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM case_notes WHERE case_id = ? ORDER BY created_at ASC", (case_id,)
        ).fetchall()
        return [dict(r) for r in rows]
