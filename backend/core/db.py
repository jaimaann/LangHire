"""The app database: jobs, runs, run events and application records.

One SQLite file (``langhire.db`` in the data dir) with numbered migrations.
Memory and Q&A keep their own ``memory_store.db`` (see ``memory/store.py``).

On first open, a legacy ``jobs.json`` is imported and renamed to
``jobs.json.migrated`` so nothing is lost.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from .config import get_data_dir

DB_NAME = "langhire.db"

# Columns stored natively; anything else on a job dict goes into `extra` JSON.
JOB_COLUMNS = (
    "url", "title", "company", "location", "source", "search_title", "status",
    "easy_apply", "description", "error", "match_score", "collected_at",
    "applied_at", "updated_at",
)

MIGRATIONS: list[str] = [
    # 1 — initial schema
    """
    CREATE TABLE jobs (
        url TEXT PRIMARY KEY,
        title TEXT DEFAULT '',
        company TEXT DEFAULT '',
        location TEXT DEFAULT '',
        source TEXT DEFAULT '',
        search_title TEXT DEFAULT '',
        status TEXT NOT NULL DEFAULT 'pending',
        easy_apply INTEGER,
        description TEXT DEFAULT '',
        error TEXT,
        match_score REAL,
        collected_at TEXT,
        applied_at TEXT,
        updated_at TEXT,
        extra TEXT NOT NULL DEFAULT '{}'
    );
    CREATE INDEX idx_jobs_status ON jobs(status, source, collected_at);

    CREATE TABLE runs (
        id TEXT PRIMARY KEY,
        kind TEXT NOT NULL,
        status TEXT NOT NULL,
        params TEXT NOT NULL DEFAULT '{}',
        stats TEXT NOT NULL DEFAULT '{}',
        error TEXT,
        cost_usd REAL NOT NULL DEFAULT 0,
        started_at TEXT NOT NULL,
        finished_at TEXT
    );
    CREATE INDEX idx_runs_kind ON runs(kind, started_at);

    CREATE TABLE run_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        ts TEXT NOT NULL,
        type TEXT NOT NULL,
        level TEXT NOT NULL DEFAULT 'info',
        message TEXT NOT NULL DEFAULT '',
        data TEXT NOT NULL DEFAULT '{}'
    );
    CREATE INDEX idx_run_events_run ON run_events(run_id, id);

    CREATE TABLE applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_url TEXT NOT NULL,
        run_id TEXT,
        outcome TEXT NOT NULL,
        reason TEXT,
        confirmation TEXT,
        answers TEXT NOT NULL DEFAULT '[]',
        missing_info TEXT NOT NULL DEFAULT '[]',
        resume_path TEXT,
        screenshot_path TEXT,
        cost_usd REAL NOT NULL DEFAULT 0,
        steps INTEGER NOT NULL DEFAULT 0,
        source TEXT DEFAULT '',
        ats TEXT,
        created_at TEXT NOT NULL
    );
    CREATE INDEX idx_applications_job ON applications(job_url, created_at);
    CREATE INDEX idx_applications_day ON applications(source, created_at);
    """,
    # 2 — test mode (submit-intercept) bookkeeping
    """
    ALTER TABLE applications ADD COLUMN test_mode INTEGER NOT NULL DEFAULT 0;
    ALTER TABLE applications ADD COLUMN submit_clicks INTEGER NOT NULL DEFAULT 0;
    ALTER TABLE applications ADD COLUMN intercepted INTEGER NOT NULL DEFAULT 0;
    """,
]

_local = threading.local()
_init_lock = threading.Lock()
_initialized: set[str] = set()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def db_path() -> Path:
    return get_data_dir() / DB_NAME


def connect() -> sqlite3.Connection:
    """A per-thread connection to the app DB (schema migrated on first use)."""
    path = str(db_path())
    conns = getattr(_local, "conns", None)
    if conns is None:
        conns = _local.conns = {}
    conn = conns.get(path)
    if conn is None:
        conn = sqlite3.connect(path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conns[path] = conn
    if path not in _initialized:
        with _init_lock:
            if path not in _initialized:
                _migrate(conn)
                _import_legacy_jobs(conn)
                _initialized.add(path)
    return conn


def close_all() -> None:
    """Close this thread's connections (used before deleting the data dir)."""
    for conn in getattr(_local, "conns", {}).values():
        try:
            conn.close()
        except sqlite3.Error:
            pass
    _local.conns = {}
    _initialized.clear()


def _migrate(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
    row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
    current = row[0] or 0
    for i, sql in enumerate(MIGRATIONS[current:], start=current + 1):
        with conn:
            conn.executescript(sql)
            conn.execute("INSERT INTO schema_version (version) VALUES (?)", (i,))


def _import_legacy_jobs(conn: sqlite3.Connection) -> None:
    legacy = get_data_dir() / "jobs.json"
    if not legacy.exists():
        return
    try:
        data = json.loads(legacy.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    if isinstance(data, dict):
        with conn:
            for url, job in data.items():
                if isinstance(job, dict):
                    _upsert(conn, {**job, "url": job.get("url") or url})
    legacy.replace(legacy.with_name("jobs.json.migrated"))


# ── Jobs ────────────────────────────────────────────────────────────────────

def _row_to_job(row: sqlite3.Row) -> dict:
    job = {k: row[k] for k in JOB_COLUMNS}
    if job["easy_apply"] is not None:
        job["easy_apply"] = bool(job["easy_apply"])
    try:
        extra = json.loads(row["extra"] or "{}")
    except ValueError:
        extra = {}
    return {**extra, **job}


def _upsert(conn: sqlite3.Connection, job: dict) -> None:
    cols = {k: job.get(k) for k in JOB_COLUMNS if k != "updated_at"}
    if cols.get("easy_apply") is not None:
        cols["easy_apply"] = 1 if cols["easy_apply"] else 0
    cols["status"] = cols.get("status") or "pending"
    for k in ("title", "company", "location", "source", "search_title", "description"):
        cols[k] = cols.get(k) or ""
    extra = {k: v for k, v in job.items() if k not in JOB_COLUMNS}
    cols["extra"] = json.dumps(extra, ensure_ascii=False)
    cols["updated_at"] = now_iso()
    names = ", ".join(cols)
    marks = ", ".join("?" for _ in cols)
    updates = ", ".join(f"{k}=excluded.{k}" for k in cols if k != "url")
    conn.execute(
        f"INSERT INTO jobs ({names}) VALUES ({marks}) ON CONFLICT(url) DO UPDATE SET {updates}",
        list(cols.values()),
    )


def read_jobs() -> dict[str, dict]:
    rows = connect().execute("SELECT * FROM jobs ORDER BY collected_at, rowid").fetchall()
    return {r["url"]: _row_to_job(r) for r in rows}


def get_job(url: str) -> dict | None:
    row = connect().execute("SELECT * FROM jobs WHERE url = ?", (url,)).fetchone()
    return _row_to_job(row) if row else None


def write_jobs(jobs: dict[str, dict]) -> None:
    """Replace the whole job set (kept for callers that edit the dict in bulk)."""
    conn = connect()
    with conn:
        existing = {r[0] for r in conn.execute("SELECT url FROM jobs")}
        for url, job in jobs.items():
            _upsert(conn, {**job, "url": job.get("url") or url})
        gone = existing - set(jobs)
        conn.executemany("DELETE FROM jobs WHERE url = ?", [(u,) for u in gone])


def add_jobs(jobs: list[dict]) -> int:
    """Insert jobs that aren't known yet; return how many were new."""
    conn = connect()
    added = 0
    with conn:
        for job in jobs:
            url = job.get("url")
            if not url:
                continue
            if conn.execute("SELECT 1 FROM jobs WHERE url = ?", (url,)).fetchone():
                continue
            _upsert(conn, job)
            added += 1
    return added


def update_job(url: str, **fields) -> bool:
    conn = connect()
    with conn:
        job = get_job(url)
        if job is None:
            return False
        job.update(fields)
        _upsert(conn, job)
    return True


def delete_jobs(urls: list[str]) -> int:
    conn = connect()
    with conn:
        cur = conn.executemany("DELETE FROM jobs WHERE url = ?", [(u,) for u in urls])
    return cur.rowcount if cur.rowcount is not None else 0


def claim_job(url: str) -> bool:
    """Atomically move a job from pending to in_progress."""
    conn = connect()
    with conn:
        cur = conn.execute(
            "UPDATE jobs SET status='in_progress', updated_at=? WHERE url=? AND status='pending'",
            (now_iso(), url),
        )
    return cur.rowcount == 1


def recover_stale_jobs() -> int:
    conn = connect()
    with conn:
        cur = conn.execute("UPDATE jobs SET status='pending' WHERE status='in_progress'")
    return cur.rowcount


def job_counts() -> dict[str, int]:
    rows = connect().execute("SELECT status, COUNT(*) c FROM jobs GROUP BY status").fetchall()
    return {r["status"]: r["c"] for r in rows}


# ── Runs and events ─────────────────────────────────────────────────────────

def create_run(run_id: str, kind: str, params: dict) -> None:
    conn = connect()
    with conn:
        conn.execute(
            "INSERT INTO runs (id, kind, status, params, started_at) VALUES (?, ?, 'running', ?, ?)",
            (run_id, kind, json.dumps(params, ensure_ascii=False, default=str), now_iso()),
        )


def finish_run(run_id: str, status: str, error: str | None, stats: dict, cost_usd: float) -> None:
    conn = connect()
    with conn:
        conn.execute(
            "UPDATE runs SET status=?, error=?, stats=?, cost_usd=?, finished_at=? WHERE id=?",
            (status, error, json.dumps(stats, default=str), cost_usd, now_iso(), run_id),
        )


def mark_interrupted_runs() -> int:
    conn = connect()
    with conn:
        cur = conn.execute(
            "UPDATE runs SET status='interrupted', finished_at=? WHERE status='running'", (now_iso(),)
        )
    return cur.rowcount


def list_runs(limit: int = 50, kind: str | None = None) -> list[dict]:
    q = "SELECT * FROM runs"
    args: list = []
    if kind:
        q += " WHERE kind = ?"
        args.append(kind)
    q += " ORDER BY started_at DESC LIMIT ?"
    args.append(limit)
    out = []
    for r in connect().execute(q, args).fetchall():
        d = dict(r)
        d["params"] = json.loads(d["params"] or "{}")
        d["stats"] = json.loads(d["stats"] or "{}")
        out.append(d)
    return out


def add_event(run_id: str, type_: str, level: str, message: str, data: dict) -> int:
    conn = connect()
    with conn:
        cur = conn.execute(
            "INSERT INTO run_events (run_id, ts, type, level, message, data) VALUES (?, ?, ?, ?, ?, ?)",
            (run_id, now_iso(), type_, level, message, json.dumps(data, ensure_ascii=False, default=str)),
        )
    return int(cur.lastrowid or 0)


def list_events(run_id: str, after_id: int = 0, limit: int = 1000) -> list[dict]:
    rows = connect().execute(
        "SELECT * FROM run_events WHERE run_id = ? AND id > ? ORDER BY id LIMIT ?",
        (run_id, after_id, limit),
    ).fetchall()
    return [{**dict(r), "data": json.loads(r["data"] or "{}")} for r in rows]


def prune_events(older_than_days: int) -> int:
    conn = connect()
    with conn:
        cur = conn.execute(
            "DELETE FROM run_events WHERE ts < datetime('now', ?)", (f"-{int(older_than_days)} days",)
        )
    return cur.rowcount


# ── Application records ─────────────────────────────────────────────────────

def add_application(record: dict) -> int:
    conn = connect()
    with conn:
        cur = conn.execute(
            """INSERT INTO applications (job_url, run_id, outcome, reason, confirmation, answers,
                   missing_info, resume_path, screenshot_path, cost_usd, steps, source, ats, created_at,
                   test_mode, submit_clicks, intercepted)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record["job_url"], record.get("run_id"), record["outcome"], record.get("reason"),
                record.get("confirmation"),
                json.dumps(record.get("answers") or [], ensure_ascii=False),
                json.dumps(record.get("missing_info") or [], ensure_ascii=False),
                record.get("resume_path"), record.get("screenshot_path"),
                float(record.get("cost_usd") or 0), int(record.get("steps") or 0),
                record.get("source") or "", record.get("ats"), now_iso(),
                1 if record.get("test_mode") else 0, int(record.get("submit_clicks") or 0),
                int(record.get("intercepted") or 0),
            ),
        )
    return int(cur.lastrowid or 0)


def list_applications(job_url: str | None = None, limit: int = 100) -> list[dict]:
    q = "SELECT * FROM applications"
    args: list = []
    if job_url:
        q += " WHERE job_url = ?"
        args.append(job_url)
    q += " ORDER BY created_at DESC LIMIT ?"
    args.append(limit)
    out = []
    for r in connect().execute(q, args).fetchall():
        d = dict(r)
        d["answers"] = json.loads(d["answers"] or "[]")
        d["missing_info"] = json.loads(d["missing_info"] or "[]")
        out.append(d)
    return out


def applications_today(source: str) -> int:
    """Submitted applications for a source since local midnight."""
    start = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
    row = connect().execute(
        "SELECT COUNT(*) FROM applications WHERE outcome='submitted' AND source=? AND created_at >= ?",
        (source, start.astimezone(timezone.utc).isoformat()),
    ).fetchone()
    return int(row[0])


def ats_success_rates() -> list[dict]:
    rows = connect().execute(
        """SELECT COALESCE(ats, 'other') ats,
                  COUNT(*) attempts,
                  SUM(CASE WHEN outcome IN ('submitted', 'ready_to_submit') THEN 1 ELSE 0 END) submitted,
                  SUM(cost_usd) cost_usd
           FROM applications GROUP BY COALESCE(ats, 'other') ORDER BY attempts DESC"""
    ).fetchall()
    out = []
    for r in rows:
        attempts = r["attempts"] or 0
        out.append({
            "ats": r["ats"], "attempts": attempts, "submitted": r["submitted"] or 0,
            "success_rate": round((r["submitted"] or 0) / attempts, 3) if attempts else 0.0,
            "avg_cost_usd": round((r["cost_usd"] or 0) / attempts, 4) if attempts else 0.0,
        })
    return out
