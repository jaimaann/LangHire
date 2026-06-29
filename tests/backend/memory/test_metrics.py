"""
Unit tests for backend/memory/metrics.py — the SQLite-backed MetricsStore.

Each test uses a fresh DB under ``tmp_path``. We craft run records with
controlled timestamps so aggregations (success rate, averages, trends) are
deterministic, and we explicitly cover empty / zero-record cases where SQLite
aggregates return NULL.
"""
from datetime import datetime, timedelta, timezone

import pytest

from memory.metrics import MetricsStore


# ── Fixtures / helpers ──────────────────────────────────────────────────────────

@pytest.fixture
def metrics(tmp_path):
    """A MetricsStore backed by a fresh, isolated SQLite file."""
    m = MetricsStore(db_path=tmp_path / "metrics.db")
    yield m
    m.close()


def _record(metrics, *, success=True, domain="x.com", duration=10.0,
            steps=5, injected=0, extracted=0, cost=0.01, run_id="r1",
            job_url="https://x.com/jobs/1", ats="ats", run_type="apply"):
    """Insert one run with a duration derived from the requested seconds."""
    start = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    finish = start + timedelta(seconds=duration)
    metrics.record_run(
        job_url=job_url, job_title="Engineer", company="Acme",
        website_domain=domain, ats_platform=ats, success=success,
        started_at=start, finished_at=finish, step_count=steps,
        memories_injected=injected, memories_extracted=extracted,
        cost_usd=cost, run_type=run_type, run_id=run_id,
    )


# ── record_run / get_all_runs ────────────────────────────────────────────────

def test_record_run_persists_fields(metrics):
    """A recorded run round-trips with computed duration and stored fields."""
    _record(metrics, duration=42.0, steps=7, success=True, cost=1.25)
    runs = metrics.get_all_runs()
    assert len(runs) == 1
    run = runs[0]
    assert run["duration_seconds"] == pytest.approx(42.0)
    assert run["step_count"] == 7
    assert run["success"] == 1
    assert run["cost_usd"] == pytest.approx(1.25)


def test_record_run_accepts_null_optionals(metrics):
    """cost_usd / error_message / ats may be None."""
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    metrics.record_run(
        job_url="https://x.com/1", job_title="E", company="C",
        website_domain="x.com", ats_platform=None, success=False,
        started_at=start, finished_at=start + timedelta(seconds=5),
        cost_usd=None, error_message="boom",
    )
    run = metrics.get_all_runs()[0]
    assert run["cost_usd"] is None
    assert run["ats_platform"] is None
    assert run["error_message"] == "boom"


def test_get_all_runs_orders_newest_first_and_limits(metrics):
    """Runs are ordered by created_at DESC and respect the limit."""
    for i in range(3):
        _record(metrics, run_id=f"r{i}", domain=f"d{i}.com")
    assert len(metrics.get_all_runs(limit=2)) == 2


def test_get_all_runs_empty(metrics):
    """No runs → empty list."""
    assert metrics.get_all_runs() == []


# ── get_domain_stats ─────────────────────────────────────────────────────────

def test_get_domain_stats_aggregates_per_domain(metrics):
    """Per-domain stats compute success rate and averages correctly."""
    _record(metrics, domain="a.com", success=True, duration=10, steps=4)
    _record(metrics, domain="a.com", success=False, duration=20, steps=6)
    _record(metrics, domain="b.com", success=True, duration=30, steps=2)
    stats = {d["website_domain"]: d for d in metrics.get_domain_stats()}
    a = stats["a.com"]
    assert a["total_runs"] == 2
    assert a["successes"] == 1
    assert a["failures"] == 1
    assert a["success_rate"] == pytest.approx(50.0)
    assert a["avg_duration"] == pytest.approx(15.0)
    assert a["avg_steps"] == pytest.approx(5.0)
    # Ordered by total_runs DESC.
    assert metrics.get_domain_stats()[0]["website_domain"] == "a.com"


def test_get_domain_stats_empty(metrics):
    """No runs → empty per-domain list."""
    assert metrics.get_domain_stats() == []


# ── get_overall_stats ────────────────────────────────────────────────────────

def test_get_overall_stats(metrics):
    """Overall aggregate computes totals, rate, and cost."""
    _record(metrics, success=True, duration=10, cost=0.5)
    _record(metrics, success=True, duration=30, cost=0.25)
    _record(metrics, success=False, duration=20, cost=0.25)
    stats = metrics.get_overall_stats()
    assert stats["total_runs"] == 3
    assert stats["successes"] == 2
    assert stats["failures"] == 1
    assert stats["success_rate"] == pytest.approx(66.7)
    assert stats["avg_duration"] == pytest.approx(20.0)
    assert stats["total_cost"] == pytest.approx(1.0)
    assert stats["first_run"] is not None and stats["last_run"] is not None


def test_get_overall_stats_empty_no_division_error(metrics):
    """With zero runs the AVG/SUM aggregates are NULL — no division-by-zero."""
    stats = metrics.get_overall_stats()
    # COUNT(*) is 0; the rest are NULL but the call must not raise.
    assert stats["total_runs"] == 0
    assert stats["successes"] is None
    assert stats["success_rate"] is None
    assert stats["first_run"] is None


# ── get_memory_impact ────────────────────────────────────────────────────────

def test_get_memory_impact_splits_with_without(metrics):
    """Runs split into with-memory (injected>0) and without (injected=0) buckets."""
    _record(metrics, injected=3, success=True, duration=10)
    _record(metrics, injected=5, success=True, duration=20)
    _record(metrics, injected=0, success=False, duration=30)
    impact = metrics.get_memory_impact()
    assert impact["with_memory"]["runs"] == 2
    assert impact["with_memory"]["success_rate"] == pytest.approx(100.0)
    assert impact["without_memory"]["runs"] == 1
    assert impact["without_memory"]["success_rate"] == pytest.approx(0.0)


def test_get_memory_impact_empty(metrics):
    """With no runs both buckets report 0 runs and NULL rates (no crash)."""
    impact = metrics.get_memory_impact()
    assert impact["with_memory"]["runs"] == 0
    assert impact["without_memory"]["runs"] == 0
    assert impact["with_memory"]["success_rate"] is None


# ── get_trend ────────────────────────────────────────────────────────────────

def test_get_trend_windows(metrics):
    """Trend groups runs into fixed-size windows with per-window aggregates."""
    # 5 runs; window_size 2 → windows of 2,2,1.
    for i in range(5):
        _record(metrics, run_id=f"r{i}", success=(i % 2 == 0),
                duration=float(i + 1), steps=i, injected=1)
    trend = metrics.get_trend(window_size=2)
    assert len(trend) == 3
    assert [t["runs"] for t in trend] == [2, 2, 1]
    assert [t["batch"] for t in trend] == [1, 2, 3]
    # Each entry exposes a period string and aggregates.
    assert "→" in trend[0]["period"]
    assert trend[0]["success_rate"] in (0.0, 50.0, 100.0)


def test_get_trend_handles_null_step_count(metrics):
    """step_count NULL is treated as 0 in the avg_steps computation."""
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    metrics.record_run(
        job_url="https://x.com/1", job_title="E", company="C",
        website_domain="x.com", ats_platform=None, success=True,
        started_at=start, finished_at=start + timedelta(seconds=5),
        step_count=None, memories_injected=0,
    )
    trend = metrics.get_trend(window_size=5)
    assert len(trend) == 1
    assert trend[0]["avg_steps"] == pytest.approx(0.0)


def test_get_trend_empty(metrics):
    """No runs → empty trend list."""
    assert metrics.get_trend() == []


def test_get_trend_single_window(metrics):
    """Fewer runs than window_size still yields one window."""
    _record(metrics, success=True, duration=10, steps=3, injected=2)
    trend = metrics.get_trend(window_size=10)
    assert len(trend) == 1
    assert trend[0]["runs"] == 1
    assert trend[0]["success_rate"] == pytest.approx(100.0)
    assert trend[0]["avg_memories"] == pytest.approx(2.0)


# ── Run logs ─────────────────────────────────────────────────────────────────

def test_log_and_get_run_logs(metrics):
    """A single log line is persisted and retrieved in insertion order."""
    metrics.log("run-1", "starting", level="INFO", job_url="https://x.com/1")
    metrics.log("run-1", "done", level="DEBUG", job_url="https://x.com/1")
    logs = metrics.get_run_logs("run-1")
    assert [l["message"] for l in logs] == ["starting", "done"]
    assert logs[0]["level"] == "INFO"


def test_log_batch(metrics):
    """log_batch inserts several rows at once."""
    metrics.log_batch([
        ("run-2", "https://x.com/2", "INFO", "line a"),
        ("run-2", "https://x.com/2", "WARN", "line b"),
    ])
    logs = metrics.get_run_logs("run-2")
    assert len(logs) == 2
    assert {l["level"] for l in logs} == {"INFO", "WARN"}


def test_get_job_logs_newest_first(metrics):
    """Job logs come back newest-first and filtered by job_url."""
    metrics.log("r", "first", job_url="https://x.com/job")
    metrics.log("r", "second", job_url="https://x.com/job")
    metrics.log("r", "other", job_url="https://x.com/elsewhere")
    logs = metrics.get_job_logs("https://x.com/job")
    assert [l["message"] for l in logs] == ["second", "first"]


def test_get_recent_logs(metrics):
    """Recent logs are returned newest-first across all runs."""
    metrics.log("a", "m1")
    metrics.log("b", "m2")
    recent = metrics.get_recent_logs(limit=10)
    assert recent[0]["message"] == "m2"


def test_get_run_logs_empty(metrics):
    """Unknown run id → empty log list."""
    assert metrics.get_run_logs("nope") == []


def test_get_runs_with_logs_counts(metrics):
    """get_runs_with_logs joins metrics rows with their log counts."""
    _record(metrics, run_id="run-x", domain="x.com")
    metrics.log("run-x", "l1", job_url="https://x.com/jobs/1")
    metrics.log("run-x", "l2", job_url="https://x.com/jobs/1")
    rows = metrics.get_runs_with_logs()
    assert len(rows) == 1
    assert rows[0]["run_id"] == "run-x"
    assert rows[0]["log_count"] == 2


def test_get_runs_with_logs_zero_for_logless_run(metrics):
    """A run with no logs reports log_count 0 (LEFT JOIN COALESCE)."""
    _record(metrics, run_id="run-y")
    rows = metrics.get_runs_with_logs()
    assert rows[0]["log_count"] == 0


def test_cleanup_old_logs(metrics):
    """Logs older than the retention window are deleted; fresh ones kept."""
    metrics.log("r", "fresh")
    # Backdate one log row directly.
    conn = metrics._get_conn()
    conn.execute(
        "INSERT INTO run_logs (run_id, job_url, timestamp, level, message, created_at) "
        "VALUES ('r', NULL, '2000-01-01', 'INFO', 'old', '2000-01-01T00:00:00+00:00')"
    )
    conn.commit()
    removed = metrics.cleanup_old_logs(days=30)
    assert removed == 1
    remaining = [l["message"] for l in metrics.get_run_logs("r")]
    assert remaining == ["fresh"]


# ── Lifecycle ─────────────────────────────────────────────────────────────────

def test_close_idempotent_and_reopen(metrics):
    """close() is safe to call repeatedly and the store reopens lazily."""
    metrics.close()
    metrics.close()
    assert metrics.get_overall_stats()["total_runs"] == 0


def test_schema_has_run_id_column(metrics):
    """The run_metrics table includes the migrated run_id column."""
    conn = metrics._get_conn()
    cols = {r[1] for r in conn.execute("PRAGMA table_info(run_metrics)").fetchall()}
    assert "run_id" in cols
