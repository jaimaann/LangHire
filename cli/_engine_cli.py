"""Run an engine coroutine from the command line, printing its events."""
import asyncio
import logging
import sys
import uuid
from pathlib import Path

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from core import db  # noqa: E402
from engine.events import RunContext, RunLogHandler, current_run  # noqa: E402


def run(kind: str, factory, params: dict) -> dict:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ctx = RunContext(run_id=uuid.uuid4().hex[:12], kind=kind)
    db.create_run(ctx.run_id, kind, params)
    logging.getLogger().addHandler(RunLogHandler())

    async def main():
        token = current_run.set(ctx)
        try:
            return await factory(ctx)
        finally:
            current_run.reset(token)

    status, error, stats = "succeeded", None, {}
    try:
        stats = asyncio.run(main()) or {}
        return stats
    except KeyboardInterrupt:
        status = "cancelled"
        return {}
    except Exception as e:
        status, error = "failed", str(e)
        raise
    finally:
        db.finish_run(ctx.run_id, status, error, stats, ctx.cost_usd)
        print(f"\nRun {ctx.run_id}: {status}. LLM cost ${ctx.cost_usd:.3f}")
