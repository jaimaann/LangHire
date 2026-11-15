"""Typed run events.

Engine code calls ``emit("job_started", "Applying to X", job_url=...)`` instead
of printing emoji to stdout. Each event is:

* written to the ``run_events`` table (persistent run history),
* appended to the run's in-memory log (for the legacy polling endpoints),
* pushed to every live SSE subscriber.

The current run is tracked with a context variable, so concurrent runs (a
collection and an apply at the same time) never mix their events.
"""
from __future__ import annotations

import asyncio
import contextvars
import logging
import re
import threading
from dataclasses import dataclass, field
from typing import Any

from core import db
from memory.metrics import MetricsStore

_log = logging.getLogger("engine")

current_run: contextvars.ContextVar["RunContext | None"] = contextvars.ContextVar("current_run", default=None)
# The job a worker task is applying to; events without a job_url get it, so the UI
# can show a per-job timeline even with several workers.
current_job: contextvars.ContextVar[str | None] = contextvars.ContextVar("current_job", default=None)

EVENT_TYPES = {
    "run_started", "run_finished", "log",
    "job_found", "job_started", "job_finished", "job_skipped",
    "field_filled", "answer_needed", "description_fetched",
    "cost", "learning", "agent_step", "job_result",
}

MAX_LOG_LINES = 500
_ANSI = re.compile(r"\x1b\[[0-9;]*m")


@dataclass
class RunContext:
    run_id: str
    kind: str
    log: list[str] = field(default_factory=list)
    counters: dict[str, Any] = field(default_factory=dict)
    cost_usd: float = 0.0


class EventBus:
    def __init__(self) -> None:
        self._subs: list[tuple[asyncio.AbstractEventLoop, asyncio.Queue]] = []
        self._lock = threading.Lock()

    def subscribe(self) -> asyncio.Queue:
        """Subscribe from a coroutine; events are delivered on the caller's loop."""
        q: asyncio.Queue = asyncio.Queue(maxsize=2000)
        with self._lock:
            self._subs.append((asyncio.get_running_loop(), q))
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        with self._lock:
            self._subs = [(l, s) for (l, s) in self._subs if s is not q]

    def publish(self, event: dict) -> None:
        with self._lock:
            subs = list(self._subs)
        for loop, q in subs:
            try:
                loop.call_soon_threadsafe(_put_nowait, q, event)
            except RuntimeError:  # loop closed
                self.unsubscribe(q)


def _put_nowait(q: asyncio.Queue, event: dict) -> None:
    try:
        q.put_nowait(event)
    except asyncio.QueueFull:
        pass  # a slow client drops events; it can resync from /runs/{id}/events


bus = EventBus()
_metrics_store: MetricsStore | None = None
_metrics_lock = threading.Lock()


def _metrics() -> MetricsStore:
    global _metrics_store
    with _metrics_lock:
        if _metrics_store is None or not str(_metrics_store.db_path).startswith(str(db.get_data_dir())):
            _metrics_store = MetricsStore()
        return _metrics_store


def emit(type_: str, message: str = "", level: str = "info", **data: Any) -> None:
    """Record an event for the current run (or just log it when there is none)."""
    ctx = current_run.get()
    job = current_job.get()
    if job and "job_url" not in data:
        data["job_url"] = job
    message = _ANSI.sub("", message or "").strip()
    log_fn = {"error": _log.error, "warning": _log.warning}.get(level, _log.info)
    if ctx is None:
        if message:
            log_fn(message)
        return
    if message:
        ctx.log.append(message)
        if len(ctx.log) > MAX_LOG_LINES:
            del ctx.log[: len(ctx.log) - MAX_LOG_LINES // 2]
    try:
        event_id = db.add_event(ctx.run_id, type_, level, message, data)
        if message:  # the Logs page reads run_logs
            _metrics().log(ctx.run_id, message, level=level.upper(), job_url=data.get("job_url"))
    except Exception as e:  # persistence must never break a run
        _log.warning(f"event persist failed: {e}")
        event_id = 0
    bus.publish({
        "id": event_id, "run_id": ctx.run_id, "kind": ctx.kind, "type": type_,
        "level": level, "message": message, "data": data,
    })


def info(message: str, **data: Any) -> None:
    emit("log", message, "info", **data)


def warn(message: str, **data: Any) -> None:
    emit("log", message, "warning", **data)


def error(message: str, **data: Any) -> None:
    emit("log", message, "error", **data)


class RunLogHandler(logging.Handler):
    """Forwards browser-use / agent log records into the current run's events."""

    _noise = {"httpx", "httpcore", "urllib3", "filelock", "websockets",
              "charset_normalizer", "botocore", "boto3", "s3transfer", "engine",
              "backend", "uvicorn", "asyncio"}

    def emit(self, record: logging.LogRecord) -> None:  # noqa: A003 - logging API
        if record.name.split(".")[0] in self._noise:
            return
        if current_run.get() is None:
            return
        try:
            msg = record.getMessage()
        except Exception:
            return
        if not msg.strip():
            return
        level = "error" if record.levelno >= logging.ERROR else "warning" if record.levelno >= logging.WARNING else "info"
        emit("log", msg, level, logger=record.name)
