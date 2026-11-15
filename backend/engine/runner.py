"""Run manager: one background event loop that hosts every engine run.

Replaces the old pattern of a new thread + new event loop per run with
stdout redirected into a list. Runs are asyncio tasks on a single engine loop;
cancelling a run cancels its task (and then closes the browsers it opened).
Each run is a row in the ``runs`` table, so history survives restarts.
"""
from __future__ import annotations

import asyncio
import logging
import threading
import uuid
from datetime import datetime
from typing import Any, Awaitable, Callable, Coroutine

from core import db

from . import events
from .events import RunContext, current_run, emit

_log = logging.getLogger("engine")

RunFactory = Callable[[RunContext], Awaitable[dict | None]]


class RunState:
    def __init__(self, ctx: RunContext, params: dict):
        self.ctx = ctx
        self.params = params
        self.task: asyncio.Task | None = None
        self.running = True
        self.cancel_requested = False
        self.error: str | None = None
        self.finished_at: str | None = None
        self.stats: dict = {}

    def as_status(self) -> dict:
        """Shape of the legacy /apply/status and /jobs/collect/status payloads."""
        out = {
            "running": self.running,
            "run_id": self.ctx.run_id,
            "log": list(self.ctx.log),
            "error": self.error,
            "finished_at": self.finished_at,
            "cancel_requested": self.cancel_requested,
            "cost_usd": round(self.ctx.cost_usd, 4),
            "stats": self.stats,
        }
        out.update(self.params.get("_status_extra", {}))
        out.update(self.ctx.counters)
        return out


class RunManager:
    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._started = threading.Event()
        self._lock = threading.Lock()
        self._latest: dict[str, RunState] = {}  # kind -> most recent run
        self._log_handler = events.RunLogHandler()

    # ── loop lifecycle ────────────────────────────────────────────────────
    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        with self._lock:
            if self._loop is None or not (self._thread and self._thread.is_alive()):
                self._started.clear()
                self._thread = threading.Thread(target=self._run_loop, name="engine-loop", daemon=True)
                self._thread.start()
                self._started.wait(10)
                logging.getLogger().addHandler(self._log_handler)
        assert self._loop is not None
        return self._loop

    def _run_loop(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._started.set()
        loop.run_forever()

    # ── public API ────────────────────────────────────────────────────────
    def is_running(self, kind: str) -> bool:
        st = self._latest.get(kind)
        return bool(st and st.running)

    def status(self, kind: str) -> dict:
        st = self._latest.get(kind)
        if st is None:
            return {"running": False, "log": [], "error": None, "finished_at": None}
        return st.as_status()

    def get(self, kind: str) -> RunState | None:
        return self._latest.get(kind)

    def start(self, kind: str, factory: RunFactory, params: dict | None = None,
              first_message: str = "") -> RunState:
        """Start a run of `kind` unless one is already running. Returns its state."""
        params = dict(params or {})
        with self._lock:
            if self.is_running(kind):
                raise RuntimeError(f"A {kind} run is already in progress")
            run_id = uuid.uuid4().hex[:12]
            ctx = RunContext(run_id=run_id, kind=kind)
            state = RunState(ctx, params)
            self._latest[kind] = state
        db.create_run(run_id, kind, {k: v for k, v in params.items() if not k.startswith("_")})
        loop = self._ensure_loop()

        async def _wrapper():
            token = current_run.set(ctx)
            try:
                emit("run_started", first_message or f"Started {kind}", kind=kind)
                result = await factory(ctx)
                state.stats = result or {}
                if state.cancel_requested:
                    state.error = "cancelled"
                    emit("run_finished", "🛑 Stopped by user", status="cancelled")
                else:
                    emit("run_finished", "✅ Finished successfully", status="succeeded", stats=state.stats)
            except asyncio.CancelledError:
                state.error = "cancelled"
                emit("run_finished", "🛑 Stopped by user", status="cancelled")
            except Exception as e:
                _log.error(f"{kind} run {run_id} failed: {e}", exc_info=True)
                state.error = str(e)
                emit("run_finished", f"❌ Error: {e}", "error", status="failed")
            finally:
                state.running = False
                state.finished_at = datetime.now().isoformat()
                status = "cancelled" if state.error == "cancelled" else ("failed" if state.error else "succeeded")
                try:
                    db.finish_run(run_id, status, None if status != "failed" else state.error,
                                  state.stats, ctx.cost_usd)
                except Exception as e:
                    _log.warning(f"finish_run failed: {e}")
                current_run.reset(token)

        fut = asyncio.run_coroutine_threadsafe(self._spawn(_wrapper(), state), loop)
        fut.result(timeout=10)
        return state

    async def _spawn(self, coro, state: RunState) -> None:
        state.task = asyncio.get_running_loop().create_task(coro)

    def cancel(self, kind: str) -> bool:
        """Cancel the running run of `kind`. Returns False if none is running."""
        st = self._latest.get(kind)
        if not st or not st.running:
            return False
        st.cancel_requested = True
        if st.task and self._loop:
            self._loop.call_soon_threadsafe(st.task.cancel)
        return True

    def cancel_all(self, wait: float = 5.0) -> None:
        for kind in list(self._latest):
            self.cancel(kind)
        if self._loop:
            deadline = asyncio.run_coroutine_threadsafe(asyncio.sleep(0), self._loop)
            try:
                deadline.result(timeout=wait)
            except Exception:
                pass

    def run_sync(self, coro: Coroutine[Any, Any, Any], timeout: float | None = None) -> Any:
        """Run a coroutine on the engine loop from another thread and wait for it."""
        loop = self._ensure_loop()
        return asyncio.run_coroutine_threadsafe(coro, loop).result(timeout=timeout)


manager = RunManager()
