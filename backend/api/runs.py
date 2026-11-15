"""Starting and stopping collection / apply runs, run history and live events.

``/events`` is a Server-Sent Events stream of typed engine events
(``job_found``, ``job_started``, ``field_filled``, ``job_finished``, ``cost``,
``run_finished`` …). The ``/…/status`` endpoints remain for polling clients.
"""
from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from core import db
from engine import apply as apply_engine
from engine import collect as collect_engine
from engine.browsers import kill_profile_browsers
from engine.events import bus
from engine.runner import manager
from models import ApplyRequest, CollectRequest

router = APIRouter()
_log = logging.getLogger("backend")


# ── Collection ─────────────────────────────────────────────────────────────

@router.post("/jobs/collect")
async def start_collection(body: CollectRequest):
    if manager.is_running("collect"):
        return {"success": False, "message": "Collection already running"}
    kill_profile_browsers()
    label = body.title or "all titles"

    async def run(ctx):
        return await collect_engine.run_collect(ctx, title=body.title, source=body.source,
                                                max_jobs=body.max_jobs, filters=body.filters)

    manager.start("collect", run, {
        "title": body.title, "source": body.source, "max_jobs": body.max_jobs,
        "_status_extra": {"title": label, "max_jobs": body.max_jobs, "source": body.source},
    }, first_message=f"Starting collection from {body.source}... This may take several minutes per job title.")
    return {"success": True, "message": f"Collection started for {label}"}


@router.post("/jobs/collect/stop")
async def stop_collection():
    stopped = manager.cancel("collect")
    return {"success": True, "message": "Stop requested" if stopped else "Nothing running"}


@router.get("/jobs/collect/status")
async def collection_status():
    st = manager.status("collect")
    st["log"] = st.get("log", [])[-100:]
    st.setdefault("collected", 0)
    return st


# ── Apply ──────────────────────────────────────────────────────────────────

@router.post("/apply/start")
async def start_applying(body: ApplyRequest):
    if manager.is_running("apply"):
        return {"success": False, "message": "Application already running"}
    kill_profile_browsers()
    workers = 1 if body.job_url else body.workers

    async def run(ctx):
        return await apply_engine.run_apply(ctx, mode=body.mode, workers=workers, limit=body.limit,
                                            job_url=body.job_url, job_urls=body.job_urls)

    if body.job_url:
        first = "Applying to single job..."
    elif body.job_urls:
        first = f"Applying to {len(body.job_urls)} selected jobs..."
    else:
        first = f"Starting {body.mode} apply with {workers} worker(s)..."
    manager.start("apply", run, {
        "mode": body.mode, "workers": workers, "limit": body.limit,
        "job_url": body.job_url, "job_urls": body.job_urls,
        "_status_extra": {"mode": body.mode, "workers": workers},
    }, first_message=first)
    return {"success": True, "message": f"Started {body.mode} apply with {workers} worker(s)"}


@router.post("/apply/stop")
async def stop_applying():
    stopped = manager.cancel("apply")
    return {"success": True, "message": "Stop requested" if stopped else "Nothing running"}


@router.get("/apply/status")
async def apply_status():
    st = manager.status("apply")
    st["log"] = st.get("log", [])[-100:]
    st.setdefault("mode", None)
    st.setdefault("workers", 1)
    return st


# ── History and live events ────────────────────────────────────────────────

@router.get("/runs")
async def list_runs(limit: int = Query(50, ge=1, le=500), kind: str | None = Query(None)):
    return db.list_runs(limit=limit, kind=kind)


@router.get("/runs/{run_id}/events")
async def run_events(run_id: str, after: int = Query(0, ge=0), limit: int = Query(1000, ge=1, le=5000)):
    return db.list_events(run_id, after_id=after, limit=limit)


@router.get("/events")
async def event_stream(request: Request):
    """Server-Sent Events: one `data:` line of JSON per engine event."""
    queue = bus.subscribe()

    async def gen():
        try:
            yield "retry: 3000\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                yield f"id: {event.get('id', 0)}\nevent: {event['type']}\ndata: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"
        finally:
            bus.unsubscribe(queue)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
