"""Memory, Q&A, dashboard, metrics and run logs."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Query

from core.config import load_llm_settings
from core import db
from engine import memory_packs
from models import CleanupRequest, DecayRequest, MemoryPackImport, QAUpdateRequest

from .common import api_error, get_memory_store, get_metrics_store, llm_text
from .jobs import get_job_stats

router = APIRouter()
_log = logging.getLogger("backend")


# ── Memory ────────────────────────────────────────────────────────────────
@router.get("/memory/stats")
async def get_memory_stats():
    store = get_memory_store()
    if store:
        return store.get_stats()
    return {"total_memories": 0, "unique_domains": 0, "by_category": {}}


@router.get("/memory/domains")
async def get_memory_domains():
    store = get_memory_store()
    if store:
        return store.get_all_domains()
    return []


@router.get("/memory/domain/{domain}")
async def get_memories_for_domain(domain: str, limit: int = Query(50)):
    store = get_memory_store()
    if store:
        return store.search(website_domain=domain, success_only=False, limit=limit)
    return []


@router.get("/memory/search")
async def search_memories(q: str = Query(""), limit: int = Query(50)):
    store = get_memory_store()
    if not store or not q:
        return []
    # Simple text search across all memories
    all_mems = store.export_all()
    q_lower = q.lower()
    results = [m for m in all_mems if q_lower in m.get("content", "").lower() or q_lower in m.get("website_domain", "").lower()]
    return results[:limit]


@router.post("/memory/decay")
async def decay_memories(body: DecayRequest):
    store = get_memory_store()
    if store:
        affected = store.decay_confidence(days_old=body.days, decay_factor=body.factor)
        return {"success": True, "affected": affected}
    return {"success": False, "message": "Memory store not available"}


@router.post("/memory/cleanup")
async def cleanup_memories(body: CleanupRequest):
    store = get_memory_store()
    if store:
        deleted = store.delete_low_confidence(threshold=body.threshold)
        return {"success": True, "deleted": deleted}
    return {"success": False, "message": "Memory store not available"}


@router.get("/memory/export")
async def export_memories():
    store = get_memory_store()
    if store:
        return store.export_all()
    return []


# ── Metrics / Dashboard ───────────────────────────────────────────────────
@router.get("/dashboard")
async def get_dashboard():
    stats = await get_job_stats()
    mem_stats = await get_memory_stats()

    # Try to get metrics data
    metrics_data = {}
    metrics = get_metrics_store()
    if metrics:
        try:
            metrics_data = {
                "overall": metrics.get_overall_stats(),
                "memory_impact": metrics.get_memory_impact(),
                "domain_stats": metrics.get_domain_stats(),
                "trend": metrics.get_trend(window_size=5),
                "recent_runs": metrics.get_all_runs(limit=10),
                "ats": db.ats_success_rates(),
                "cost_7d_usd": metrics_cost_7d(metrics),
            }
        except (OSError, ValueError) as e:
            _log.warning(f"Failed to load metrics: {e}")

    return {
        "jobs": stats,
        "memory": mem_stats,
        "metrics": metrics_data,
    }


@router.get("/metrics/runs")
async def get_metric_runs(limit: int = Query(50)):
    metrics = get_metrics_store()
    if metrics:
        return metrics.get_all_runs(limit=limit)
    return []


@router.get("/metrics/domains")
async def get_metric_domains():
    metrics = get_metrics_store()
    if metrics:
        return metrics.get_domain_stats()
    return []


# ── Logs ──────────────────────────────────────────────────────────────────
@router.get("/logs/runs/{run_id}")
async def get_run_logs(run_id: str, limit: int = Query(500)):
    metrics = get_metrics_store()
    if metrics:
        return metrics.get_run_logs(run_id, limit=limit)
    return []


@router.get("/logs/recent")
async def get_recent_logs(limit: int = Query(100)):
    metrics = get_metrics_store()
    if metrics:
        return metrics.get_recent_logs(limit=limit)
    return []


@router.get("/logs/runs")
async def get_runs_with_logs(limit: int = Query(50)):
    metrics = get_metrics_store()
    if metrics:
        return metrics.get_runs_with_logs(limit=limit)
    return []


# ── Q&A Repository ────────────────────────────────────────────────────────

@router.get("/qa")
async def get_qa(search: str = Query(""), unanswered: bool = Query(False)):
    store = get_memory_store()
    if not store:
        return []
    return store.qa_list(search=search, unanswered_only=unanswered)

@router.get("/qa/stats")
async def get_qa_stats():
    store = get_memory_store()
    if not store:
        return {"total": 0, "answered": 0, "unanswered": 0}
    return store.qa_stats()

@router.put("/qa/{qa_id}")
async def update_qa(qa_id: int, body: QAUpdateRequest):
    store = get_memory_store()
    if not store:
        return api_error("no_store", "Memory store not available")
    store.qa_update(qa_id, body.answer)
    return {"success": True}

@router.delete("/qa/{qa_id}")
async def delete_qa(qa_id: int):
    store = get_memory_store()
    if not store:
        return api_error("no_store", "Memory store not available")
    store.qa_delete(qa_id)
    return {"success": True}

@router.post("/qa/{source_id}/merge/{target_id}")
async def merge_qa(source_id: int, target_id: int):
    store = get_memory_store()
    if not store:
        return api_error("no_store", "Memory store not available")
    store.qa_merge(source_id, target_id)
    return {"success": True}

@router.post("/qa/auto-squash")
async def auto_squash_qa():
    store = get_memory_store()
    if not store:
        return api_error("no_store", "Memory store not available")
    merged = store.qa_auto_squash()
    return {"success": True, "merged": merged}

@router.post("/qa/smart-squash")
async def smart_squash_qa():
    """LLM-based semantic deduplication of Q&A questions."""
    store = get_memory_store()
    if not store:
        return api_error("no_store", "Memory store not available")
    questions = store.qa_list()
    if len(questions) < 2:
        return {"success": True, "merged": 0}

    from core.llm_factory import create_llm
    llm_settings = load_llm_settings()
    if not llm_settings.get("provider"):
        return api_error("no_llm", "No LLM configured. Set up an LLM provider in Settings first.")

    llm = create_llm(llm_settings)
    q_list = "\n".join(f"[{q['id']}] {q['question']}" for q in questions)
    prompt = (
        "Below is a numbered list of screening questions from job applications. "
        "Find groups of questions that ask the same thing in different words. "
        "Return ONLY a JSON array of merge instructions: [{\"keep\": <id_to_keep>, \"merge\": [<ids_to_merge>]}, ...]. "
        "Only group questions that are truly semantically identical. If no duplicates exist, return [].\n\n"
        f"{q_list}"
    )
    try:
        from browser_use.llm.messages import UserMessage
        response = await llm.ainvoke([UserMessage(content=prompt)])
        import json as _json
        text = llm_text(response)
        # Extract JSON from response
        import re as _re_mod
        match = _re_mod.search(r"\[.*\]", text, _re_mod.DOTALL)
        if not match:
            return {"success": True, "merged": 0}
        groups = _json.loads(match.group(0))
        merged_count = 0
        for group in groups:
            keep_id = group.get("keep")
            merge_ids = group.get("merge", [])
            for mid in merge_ids:
                store.qa_merge(mid, keep_id)
                merged_count += 1
        return {"success": True, "merged": merged_count}
    except Exception as e:
        return api_error("llm_error", f"Smart squash failed: {str(e)}", 500)


def metrics_cost_7d(metrics) -> float:
    try:
        conn = metrics._get_conn()
        row = conn.execute(
            "SELECT COALESCE(SUM(cost_usd), 0) FROM run_metrics WHERE created_at >= datetime('now', '-7 days')"
        ).fetchone()
        return round(float(row[0] or 0), 4)
    except Exception:
        return 0.0


@router.get("/memory/packs/export")
async def export_memory_pack():
    """ATS-level memories only, scrubbed of personal details — safe to share."""
    return memory_packs.export_pack()


@router.post("/memory/packs/import")
async def import_memory_pack(body: MemoryPackImport):
    try:
        added = memory_packs.import_pack(body.pack)
    except ValueError as e:
        return api_error("invalid_pack", str(e), 400)
    return {"success": True, "added": added}
