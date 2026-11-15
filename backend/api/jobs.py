"""Jobs, application records and the CSV export."""
from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from core import db
from core.config import load_profile
from core.shared_config import validate_job_url
from engine.matching import match_score
from models import JobAddRequest, JobsDeleteRequest, JobStatusUpdate

from .common import api_error

router = APIRouter()

STAT_KEYS = ("pending", "applied", "failed", "blocked", "in_progress", "skipped", "needs_input")


@router.get("/jobs")
async def get_jobs(status: Optional[str] = Query(None), search: Optional[str] = Query(None),
                   limit: int = Query(500, ge=1, le=10000)):
    result = []
    q = (search or "").lower()
    for url, job in db.read_jobs().items():
        job["url"] = url
        if status and job.get("status") != status:
            continue
        if q and q not in (job.get("title") or "").lower() and q not in (job.get("company") or "").lower():
            continue
        result.append(job)
    result.sort(key=lambda j: j.get("collected_at") or "", reverse=True)
    return result[:limit]


@router.get("/jobs/stats")
async def get_job_stats():
    counts = db.job_counts()
    stats = {"total": sum(counts.values()), **{k: 0 for k in STAT_KEYS}}
    for k, v in counts.items():
        if k in stats:
            stats[k] = v
    return stats


@router.get("/jobs/export")
async def export_jobs_csv():
    rows = list(db.read_jobs().values())
    rows.sort(key=lambda j: (j.get("applied_at") or "", j.get("collected_at") or ""), reverse=True)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Date Applied", "Date Collected", "Job Title", "Company", "Location", "Status",
                     "Source", "Easy Apply", "Match", "URL"])
    for j in rows:
        writer.writerow([
            j.get("applied_at") or "", j.get("collected_at") or "", j.get("title") or "",
            j.get("company") or "", j.get("location") or "", j.get("status") or "", j.get("source") or "",
            "" if j.get("easy_apply") is None else ("yes" if j.get("easy_apply") else "no"),
            "" if j.get("match_score") is None else int(j["match_score"]),
            j.get("url") or "",
        ])
    return StreamingResponse(
        iter([buf.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="langhire-jobs.csv"'},
    )


@router.put("/jobs/status")
async def update_job_status(body: JobStatusUpdate):
    url = body.url.strip()
    if db.get_job(url) is None:
        return api_error("not_found", "Job not found", 404)
    db.update_job(url, status=body.status, error=None)
    return {"success": True, "url": url, "status": body.status}


@router.post("/jobs/add")
async def add_job_manually(body: JobAddRequest):
    url = body.url.strip()
    if not validate_job_url(url):
        return api_error("invalid_url", "Invalid or internal URL", 400)
    if db.get_job(url) is not None:
        return api_error("duplicate", "Job already exists in the queue", 409)
    job: dict = {
        "url": url,
        "title": body.title.strip() or "Manually Added",
        "company": body.company.strip(),
        "location": body.location.strip(),
        "description": body.description.strip(),
        "easy_apply": None,
        "status": "pending",
        "source": body.source or "manual",
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "applied_at": None,
        "error": None,
    }
    job["match_score"] = match_score(job, load_profile())
    db.add_jobs([job])
    return {"success": True, "url": url}


@router.delete("/jobs")
async def delete_jobs(body: JobsDeleteRequest):
    existing = {u for u in body.urls if db.get_job(u) is not None}
    db.delete_jobs(list(existing))
    return {"success": True, "deleted": len(existing)}


@router.post("/jobs/rescore")
async def rescore_jobs():
    """Recompute match scores (after the profile changes)."""
    profile = load_profile()
    n = 0
    for url, job in db.read_jobs().items():
        db.update_job(url, match_score=match_score(job, profile))
        n += 1
    return {"success": True, "rescored": n}


@router.get("/applications")
async def list_applications(job_url: Optional[str] = Query(None), limit: int = Query(100, ge=1, le=1000)):
    """Application records: answers given, resume used, screenshot, outcome, cost."""
    return db.list_applications(job_url=job_url, limit=limit)


@router.get("/applications/ats")
async def ats_success_rates():
    """Success rate and average cost per applicant tracking system."""
    return db.ats_success_rates()
