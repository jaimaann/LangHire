"""
Application run metrics tracking.

Records per-run metrics (duration, steps, success, memories used) to measure
the impact of the memory system on agent performance over time.
"""

import sqlite3
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


try:
    from core.config import get_data_dir
except ImportError:
    from backend.core.config import get_data_dir


def _get_db_path() -> Path:
    if getattr(sys, 'frozen', False):
        return get_data_dir() / "memory_store.db"
    return Path(__file__).parent.parent.parent / "memory_store.db"

DB_PATH = _get_db_path()


class MetricsStore:
    """SQLite-backed metrics store — shares the same DB as MemoryStore."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._local = threading.local()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(str(self.db_path))
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
        return self._local.conn

    def close(self):
        """Close the thread-local connection if open."""
        if hasattr(self._local, "conn") and self._local.conn is not None:
            try:
                self._local.conn.close()
            except Exception:
                pass
            self._local.conn = None

    def __del__(self):
        self.close()

    def _init_db(self):
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS run_metrics (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id            TEXT,
                job_url           TEXT NOT NULL,
                job_title         TEXT,
                company           TEXT,
                website_domain    TEXT,
                ats_platform      TEXT,
                success           INTEGER NOT NULL,
                error_message     TEXT,
                started_at        TEXT NOT NULL,
                finished_at       TEXT NOT NULL,
                duration_seconds  REAL NOT NULL,
                step_count        INTEGER,
                memories_injected INTEGER DEFAULT 0,
                memories_extracted INTEGER DEFAULT 0,
                cost_usd          REAL,
                run_type          TEXT DEFAULT 'apply',
                created_at        TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS run_logs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id      TEXT NOT NULL,
                job_url     TEXT,
                timestamp   TEXT NOT NULL,
                level       TEXT NOT NULL DEFAULT 'INFO',
                message     TEXT NOT NULL,
                created_at  TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_metrics_domain
                ON run_metrics(website_domain);
            CREATE INDEX IF NOT EXISTS idx_metrics_success
                ON run_metrics(success);
            CREATE INDEX IF NOT EXISTS idx_metrics_created
                ON run_metrics(created_at);
            CREATE INDEX IF NOT EXISTS idx_run_logs_run_id
                ON run_logs(run_id);
            CREATE INDEX IF NOT EXISTS idx_run_logs_job_url
                ON run_logs(job_url);
        """)
        # Migration: add run_id column to run_metrics if missing
        cols = {r[1] for r in conn.execute("PRAGMA table_info(run_metrics)").fetchall()}
        if "run_id" not in cols:
            conn.execute("ALTER TABLE run_metrics ADD COLUMN run_id TEXT")
        conn.commit()

    def record_run(
        self,
        job_url: str,
        job_title: str,
        company: str,
        website_domain: str,
        ats_platform: str | None,
        success: bool,
        started_at: datetime,
        finished_at: datetime,
        step_count: int = 0,
        memories_injected: int = 0,
        memories_extracted: int = 0,
        cost_usd: float | None = None,
        error_message: str | None = None,
        run_type: str = "apply",
        run_id: str | None = None,
    ):
        """Record a completed application run."""
        duration = (finished_at - started_at).total_seconds()
        now = datetime.now(timezone.utc).isoformat()
        conn = self._get_conn()
        conn.execute(
            """INSERT INTO run_metrics
               (run_id, job_url, job_title, company, website_domain, ats_platform,
                success, error_message, started_at, finished_at, duration_seconds,
                step_count, memories_injected, memories_extracted, cost_usd,
                run_type, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                run_id, job_url, job_title, company, website_domain, ats_platform,
                int(success), error_message,
                started_at.isoformat(), finished_at.isoformat(), duration,
                step_count, memories_injected, memories_extracted, cost_usd,
                run_type, now,
            ),
        )
        conn.commit()

    def get_all_runs(self, limit: int = 500) -> list[dict]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM run_metrics ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_domain_stats(self) -> list[dict]:
        """Aggregated stats per domain."""
        conn = self._get_conn()
        rows = conn.execute("""
            SELECT
                website_domain,
                ats_platform,
                COUNT(*)                                            AS total_runs,
                SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END)       AS successes,
                SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END)       AS failures,
                ROUND(AVG(CASE WHEN success = 1 THEN 1.0 ELSE 0.0 END) * 100, 1)
                                                                    AS success_rate,
                ROUND(AVG(duration_seconds), 1)                     AS avg_duration,
                ROUND(AVG(step_count), 1)                           AS avg_steps,
                ROUND(AVG(memories_injected), 1)                    AS avg_memories_injected,
                ROUND(AVG(memories_extracted), 1)                   AS avg_memories_extracted,
                ROUND(SUM(COALESCE(cost_usd, 0)), 4)               AS total_cost
            FROM run_metrics
            GROUP BY website_domain
            ORDER BY total_runs DESC
        """).fetchall()
        return [dict(r) for r in rows]

    def get_overall_stats(self) -> dict:
        """Overall aggregate stats."""
        conn = self._get_conn()
        row = conn.execute("""
            SELECT
                COUNT(*)                                            AS total_runs,
                SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END)       AS successes,
                SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END)       AS failures,
                ROUND(AVG(CASE WHEN success = 1 THEN 1.0 ELSE 0.0 END) * 100, 1)
                                                                    AS success_rate,
                ROUND(AVG(duration_seconds), 1)                     AS avg_duration,
                ROUND(AVG(step_count), 1)                           AS avg_steps,
                ROUND(AVG(memories_injected), 1)                    AS avg_memories_injected,
                ROUND(AVG(memories_extracted), 1)                   AS avg_memories_extracted,
                ROUND(SUM(COALESCE(cost_usd, 0)), 4)               AS total_cost,
                MIN(created_at)                                     AS first_run,
                MAX(created_at)                                     AS last_run
            FROM run_metrics
        """).fetchone()
        return dict(row) if row else {}

    def get_memory_impact(self) -> dict:
        """Compare metrics for runs WITH vs WITHOUT memory injection."""
        conn = self._get_conn()
        with_mem = conn.execute("""
            SELECT
                COUNT(*) AS runs,
                ROUND(AVG(CASE WHEN success=1 THEN 1.0 ELSE 0.0 END)*100, 1) AS success_rate,
                ROUND(AVG(duration_seconds), 1) AS avg_duration,
                ROUND(AVG(step_count), 1) AS avg_steps
            FROM run_metrics WHERE memories_injected > 0
        """).fetchone()

        without_mem = conn.execute("""
            SELECT
                COUNT(*) AS runs,
                ROUND(AVG(CASE WHEN success=1 THEN 1.0 ELSE 0.0 END)*100, 1) AS success_rate,
                ROUND(AVG(duration_seconds), 1) AS avg_duration,
                ROUND(AVG(step_count), 1) AS avg_steps
            FROM run_metrics WHERE memories_injected = 0
        """).fetchone()

        return {
            "with_memory": dict(with_mem) if with_mem else {},
            "without_memory": dict(without_mem) if without_mem else {},
        }

    def get_trend(self, window_size: int = 5) -> list[dict]:
        """Get rolling success rate trend over time (grouped by window_size runs)."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT id, success, duration_seconds, step_count, memories_injected, "
            "created_at FROM run_metrics ORDER BY created_at ASC"
        ).fetchall()

        if not rows:
            return []

        trend = []
        for i in range(0, len(rows), window_size):
            window = rows[i:i + window_size]
            if not window:
                break
            successes = sum(r["success"] for r in window)
            trend.append({
                "batch": len(trend) + 1,
                "runs": len(window),
                "success_rate": round(successes / len(window) * 100, 1),
                "avg_duration": round(sum(r["duration_seconds"] for r in window) / len(window), 1),
                "avg_steps": round(sum(r["step_count"] or 0 for r in window) / len(window), 1),
                "avg_memories": round(sum(r["memories_injected"] for r in window) / len(window), 1),
                "period": f"{window[0]['created_at'][:10]} → {window[-1]['created_at'][:10]}",
            })

        return trend

    # ── Run logs ─────────────────────────────────────────────────────────

    def log(self, run_id: str, message: str, level: str = "INFO", job_url: str | None = None):
        """Persist a single log line for a run."""
        now = datetime.now(timezone.utc).isoformat()
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO run_logs (run_id, job_url, timestamp, level, message, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (run_id, job_url, now, level, message, now),
        )
        conn.commit()

    def log_batch(self, rows: list[tuple]):
        """Persist multiple log lines efficiently. Each row: (run_id, job_url, level, message)."""
        now = datetime.now(timezone.utc).isoformat()
        conn = self._get_conn()
        conn.executemany(
            "INSERT INTO run_logs (run_id, job_url, timestamp, level, message, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [(r[0], r[1], now, r[2], r[3], now) for r in rows],
        )
        conn.commit()

    def get_run_logs(self, run_id: str, limit: int = 500) -> list[dict]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM run_logs WHERE run_id = ? ORDER BY id ASC LIMIT ?",
            (run_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_job_logs(self, job_url: str, limit: int = 200) -> list[dict]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM run_logs WHERE job_url = ? ORDER BY id DESC LIMIT ?",
            (job_url, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_recent_logs(self, limit: int = 100) -> list[dict]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM run_logs ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_runs_with_logs(self, limit: int = 50) -> list[dict]:
        """Get recent runs with log line counts."""
        conn = self._get_conn()
        rows = conn.execute("""
            SELECT m.*, COALESCE(l.log_count, 0) AS log_count
            FROM run_metrics m
            LEFT JOIN (
                SELECT run_id, COUNT(*) AS log_count FROM run_logs GROUP BY run_id
            ) l ON m.run_id = l.run_id
            ORDER BY m.created_at DESC LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]

    def cleanup_old_logs(self, days: int = 30) -> int:
        conn = self._get_conn()
        affected = conn.execute(
            "DELETE FROM run_logs WHERE julianday('now') - julianday(created_at) > ?",
            (days,),
        ).rowcount
        conn.commit()
        return affected
