"""Applying to jobs.

``run_apply`` picks the jobs, enforces the daily cap per source and the LLM
budget for the run, and runs N workers. ``apply_to_job`` drives one agent and
turns its tool reports into a job status, Q&A entries, memories, metrics and an
application record (answers, resume used, final screenshot, cost).
"""
from __future__ import annotations

import asyncio
import hashlib
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from core import db
from core.config import load_profile, load_settings
from core import shared_config as sc
from memory import extract_learnings_from_markers, extract_learnings_via_llm, store_learnings
from memory.metrics import MetricsStore
from core.agent_logger import on_step as _log_step, on_done as _log_done, log_run_start as _log_start

from . import events, prompts
from .ats_fastpath import detect_ats
from .browsers import close_session, make_browser_session
from .events import RunContext, emit
from .tools import AgentReport, ApplicationResult, build_apply_tools
from . import vision

_ERROR_MAP = [
    # AI provider errors (checked first: they often also contain "Timeout" or "Error")
    ("content.type", "This model can't read screenshots. Pick a vision model in LLM Settings, or the app will retry without screenshots."),
    ("image_url", "This model can't read screenshots. Pick a vision model in LLM Settings, or the app will retry without screenshots."),
    ("invalid api key", "The AI provider rejected the API key. Check it in LLM Settings."),
    ("incorrect api key", "The AI provider rejected the API key. Check it in LLM Settings."),
    ("error code: 401", "The AI provider rejected the API key. Check it in LLM Settings."),
    ("insufficient balance", "Your AI provider account is out of credit. Top it up or switch provider in LLM Settings."),
    ("insufficient_quota", "Your AI provider account is out of credit. Top it up or switch provider in LLM Settings."),
    ("error code: 402", "Your AI provider account is out of credit. Top it up or switch provider in LLM Settings."),
    ("model_not_found", "The AI provider doesn't know this model name. Check the model in LLM Settings."),
    ("model does not exist", "The AI provider doesn't know this model name. Check the model in LLM Settings."),
    ("context length", "The page was too large for this model's context window. Try a model with a larger context."),
    ("maximum context", "The page was too large for this model's context window. Try a model with a larger context."),
    ("did not answer within", "The AI provider was too slow to answer. Try again, or pick a faster model in LLM Settings."),
    ("error code: 429", "API rate limit reached. Wait a moment and try again."),
    ("'NoneType' object is not subscriptable", "Browser agent encountered an unexpected page state. The page may have changed or timed out."),
    ("'NoneType' object has no attribute", "Browser agent lost track of a page element. The site may have redirected or loaded slowly."),
    ("net::ERR_", "Network error — the page failed to load. Check your internet connection."),
    ("ERR_CONNECTION_REFUSED", "Could not connect to the website. It may be temporarily down."),
    ("Timeout", "Operation timed out. The page took too long to respond."),
    ("rate limit", "API rate limit reached. Wait a moment and try again."),
    ("context was destroyed", "Browser page closed unexpectedly during the application."),
    ("Target page, context or browser has been closed", "Browser closed unexpectedly during the application."),
]

STATUS_FOR_OUTCOME = {"submitted": "applied", "failed": "failed", "needs_input": "needs_input", "skipped": "skipped",
                      "ready_to_submit": "test_passed"}


_OUTCOME_TEXT = re.compile(r"outcome[^\n]{0,80}?\b(submitted|failed|needs_input|skipped|ready_to_submit)\b", re.I)
_MISSING_TEXT = re.compile(r"missing_info\s*[=:]\s*\[([^\]]*)\]", re.I)
_REASON_TEXT = re.compile(r"reason\s*[=:]\s*['\"]?([^\n'\"]{3,300})", re.I)


def parse_outcome_text(text: str) -> tuple[str, str, list[str]] | None:
    """Outcome written as text in the final message instead of a tool call.

    Seen live: the model wrote 'report_application_result: outcome=needs_input
    missing_info=[...]' inside done(), so the job was marked failed with no reason.
    """
    m = _OUTCOME_TEXT.search(text or "")
    if not m:
        return None
    missing = []
    mm = _MISSING_TEXT.search(text)
    if mm:
        quoted = re.findall(r"['\"]([^'\"]+)['\"]", mm.group(1))
        missing = [q.strip() for q in quoted] or [x.strip() for x in mm.group(1).split(",") if x.strip()]
    rm = _REASON_TEXT.search(text)
    return m.group(1).lower(), (rm.group(1).strip() if rm else text[:300]), missing


def is_rate_limited(text: str) -> bool:
    low = (text or "").lower()
    return "429" in low or "rate limit" in low or "too many requests" in low or "quota" in low


def friendly_error(raw: str) -> str:
    for pattern, friendly in _ERROR_MAP:
        if pattern.lower() in raw.lower():
            return friendly
    if len(raw) > 200 and ("Traceback" in raw or "Error:" in raw):
        return "Application failed due to an unexpected error. Check the Logs page for details."
    return raw


def safe_filename(*parts: str, limit: int = 60) -> str:
    """A filename that is valid on Windows, macOS and Linux."""
    text = "_".join(p for p in parts if p)
    text = re.sub(r"[^\w\-.]+", "_", text, flags=re.UNICODE).strip("._")[:limit] or "run"
    return text


def _domain(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _set_status(url: str, status: str, error: str | None = None) -> None:
    fields: dict = {"status": status, "error": friendly_error(error) if error else None}
    if status == "applied":
        fields["applied_at"] = datetime.now(timezone.utc).isoformat()
    db.update_job(url, **fields)


def _usage_cost(history) -> float:
    usage = getattr(history, "usage", None)
    if usage is None:
        return 0.0
    for attr in ("total_cost", "total_cost_usd"):
        v = getattr(usage, attr, None)
        if isinstance(v, (int, float)):
            return float(v)
    return float(getattr(usage, "total_prompt_cost", 0) or 0) + float(getattr(usage, "total_completion_cost", 0) or 0)


def usage_tokens(history) -> dict:
    """Exact token counts the provider reported for one agent run (browser-use sums every step)."""
    usage = getattr(history, "usage", None) if history is not None else None
    if usage is None:
        return {"prompt_tokens": 0, "cached_tokens": 0, "completion_tokens": 0, "llm_model": None}
    by_model = getattr(usage, "by_model", None) or {}
    return {
        "prompt_tokens": int(getattr(usage, "total_prompt_tokens", 0) or 0),
        "cached_tokens": int(getattr(usage, "total_prompt_cached_tokens", 0) or 0),
        "completion_tokens": int(getattr(usage, "total_completion_tokens", 0) or 0),
        "llm_model": next(iter(by_model), None),
    }


def add_run_usage(ctx, tokens: dict) -> None:
    """Running totals for the whole run, shown in the run status and sent to analytics."""
    if ctx is None:
        return
    total = ctx.counters.setdefault("usage", {"prompt_tokens": 0, "cached_tokens": 0, "completion_tokens": 0})
    for k in ("prompt_tokens", "cached_tokens", "completion_tokens"):
        total[k] += int(tokens.get(k) or 0)
    if tokens.get("llm_model"):
        total["llm_model"] = tokens["llm_model"]


def _cost_unknown(history) -> bool:
    """Tokens were used but the model has no price entry, so the cost reads 0 when it isn't."""
    usage = getattr(history, "usage", None)
    tokens = getattr(usage, "total_tokens", 0) if usage is not None else 0
    return bool(isinstance(tokens, (int, float)) and tokens > 0 and _usage_cost(history) == 0)


def _save_answers(answers: dict[str, str], domain: str) -> None:
    if not answers:
        return
    store = sc.get_memory_store()
    for q, a in answers.items():
        store.qa_add(question=q, answer=a or "", source_domain=domain)


async def _llm_learnings(history, url: str, title: str, success: bool) -> list[dict]:
    """LLM summary of the run into learnings. Runs in a worker thread with its own loop
    (the old code called run_until_complete inside the running loop, which always raised)."""
    def _call(prompt: str) -> str:
        from browser_use.llm.messages import UserMessage

        async def _go():
            resp = await asyncio.wait_for(sc.get_llm().ainvoke([UserMessage(content=prompt)]), timeout=120)
            return getattr(resp, "completion", None) or getattr(resp, "content", None) or str(resp)
        return asyncio.run(_go())

    return await asyncio.to_thread(
        extract_learnings_via_llm, history, job_url=url, job_title=title, success=success, llm_call=_call,
    )


async def apply_to_job(job: dict, *, profile: dict, qa: dict, applied_labels: list[str],
                       worker_id: int, ctx: RunContext | None = None,
                       resume_override: str | None = None, _vision: bool | None = None,
                       test_mode: bool = False) -> dict:
    """Apply to one job. Returns {"status", "cost_usd", "outcome"}."""
    url = job["url"]
    title, company = job.get("title") or "Unknown", job.get("company") or "Unknown"
    tag = f"[W{worker_id}]"
    settings = load_settings()
    blocked = list(settings.get("blocked_domains") or [])

    if not sc.validate_job_url(url):
        _set_status(url, "blocked", "Invalid or internal URL")
        emit("job_skipped", f"🚫 {tag} Blocked (invalid URL): {title} at {company}", job_url=url)
        return {"status": "blocked", "cost_usd": 0.0}
    if sc.is_blocked_domain(url, blocked):
        _set_status(url, "blocked", "Blocked domain")
        emit("job_skipped", f"🚫 {tag} Blocked domain: {title} at {company}", job_url=url)
        return {"status": "blocked", "cost_usd": 0.0}
    if not db.claim_job(url):
        emit("job_skipped", f"⏭️ {tag} Skipped (already claimed): {title} at {company}", job_url=url)
        return {"status": "skipped", "cost_usd": 0.0}

    events.current_job.set(url)  # task-local: each worker task has its own copy
    emit("job_started", f"🚀 {tag} Starting: {title} at {company}", job_url=url, title=title, company=company)
    resume_path = resume_override or settings.get("resume_path", "") or ""
    from resume.tailor import get_tailored_resume_path
    tailored = get_tailored_resume_path(url)
    if tailored:
        resume_path = tailored
        emit("log", f"📄 {tag} Using tailored resume")

    store = sc.get_memory_store()
    domain = _domain(url)
    ats = detect_ats(url) or store.detect_ats_platform(domain)
    injected = len(store.get_domain_memories(url, limit=50) or [])
    memory_ctx = sc.build_memory_context(profile, qa, applied_labels, job_url=url, include_tracking=False)
    creds = sc.sensitive_data()
    has_password = bool((creds.get("password") or "").strip())
    sensitive = {
        "email": (profile.get("email") or creds.get("email") or "").strip(),
        "account_email": (creds.get("email") or profile.get("email") or "").strip(),
    }
    plugin = prompts.plugin_for_job(job)
    if plugin is not None and not plugin.is_builtin and not plugin.requires_login:
        has_password = False  # community plugins that don't declare a login never see the password
    if has_password:
        sensitive["password"] = creds["password"]

    task = prompts.build_apply_task(
        job, profile, qa, resume_path, memory_ctx,
        has_password=has_password, gmail_otp=bool(settings.get("email_otp_via_gmail")), blocked=blocked,
        test_mode=test_mode,
    )
    report = AgentReport()
    tools = build_apply_tools(report, profile, resume_path)
    interceptor = None
    retention = int(settings.get("log_retention_days", 14) or 0)
    convo_path = None
    if retention > 0:
        convo_path = str(sc.logs_dir() / f"apply_{safe_filename(company, title)}_{datetime.now():%Y%m%d%H%M%S}")

    steps = {"n": 0}

    def on_step(state, output, n):
        _log_step(state, output, n)
        steps["n"] += 1
        goal = (getattr(output, "next_goal", "") or "").strip()
        emit("agent_step", "", step=steps["n"], goal=goal[:160])  # no log line: the timeline reads it
        if steps["n"] >= prompts.MAX_APPLY_STEPS:
            raise RuntimeError(f"Reached maximum of {prompts.MAX_APPLY_STEPS} steps")

    from browser_use import Agent
    vision_on = vision.use_vision() if _vision is None else _vision
    browser = make_browser_session(worker_id, keep_alive=True)  # we screenshot, then close it ourselves
    started = datetime.now(timezone.utc)
    _log_start("apply", f"{title} at {company}")
    history = None
    screenshot_path = None
    status, outcome, reason, cost = "failed", "failed", "", 0.0
    try:
        if test_mode:
            # Fail closed: never run a test-mode application without the network guard
            from .submit_guard import SubmitInterceptor, install_click_hook
            interceptor = SubmitInterceptor(browser, profile)
            if not await interceptor.install():
                raise RuntimeError("Test mode: could not install the submission guard; job not attempted")
            install_click_hook(tools, interceptor, report)
        agent: Agent = Agent(
            task=task,
            llm=sc.get_llm(),
            tools=tools,
            use_vision=vision_on,
            llm_timeout=180,  # (was llm_call_timeout, which browser-use silently ignored: 75 s default)
            max_failures=int(settings.get("max_failures", 8) or 8),
            loop_detection_enabled=True,
            loop_detection_window=5,
            browser_session=browser,
            sensitive_data=sensitive,
            # The outcome is part of done() itself, so it survives browser-use's forced
            # "done only" final step (seen live: the result tool was unavailable there)
            output_model_schema=ApplicationResult,
            extend_system_message=memory_ctx,
            available_file_paths=[resume_path] if resume_path else [],
            save_conversation_path=convo_path,
            calculate_cost=True,
            register_new_step_callback=on_step,
            register_done_callback=_log_done,
        )
        history = await agent.run(max_steps=prompts.MAX_APPLY_STEPS)
        if vision_on and vision.history_rejected_images(history):
            vision.remember_text_only()  # next runs skip screenshots from the start
        if vision_on and report.result is None and vision.history_rejected_images(history):
            emit("log", f"🖼️ {tag} This model does not accept screenshots; retrying without them", "warning")
            await close_session(browser)
            db.update_job(url, status="pending", error=None)
            return await apply_to_job(job, profile=profile, qa=qa, applied_labels=applied_labels,
                                      worker_id=worker_id, ctx=ctx, resume_override=resume_override, _vision=False,
                                      test_mode=test_mode)
        cost = _usage_cost(history)
        # Final screenshot for the application record
        try:
            shots = sc.data_dir() / "records"
            shots.mkdir(parents=True, exist_ok=True)
            p = shots / f"{hashlib.sha1(url.encode()).hexdigest()[:16]}_{datetime.now():%Y%m%d%H%M%S}.png"
            await browser.take_screenshot(path=str(p))
            screenshot_path = str(p) if p.exists() else None
        except Exception:
            screenshot_path = None

        if report.result is None:
            try:
                structured = history.get_structured_output(ApplicationResult)
            except Exception:
                structured = None
            if structured is not None:
                report.result = structured
        if report.result is not None:
            outcome, reason = report.result.outcome, report.result.reason
        else:  # the model didn't call the tool: read its final text, then fall back to done()
            final = (history.final_result() or "").strip()
            parsed = parse_outcome_text(final)
            if parsed:
                outcome, reason, missing_from_text = parsed
                report.missing_from_text = missing_from_text
            else:
                ok = bool(history.is_successful())
                outcome = "submitted" if ok else "failed"
                reason = "" if ok else (history.errors()[-1] if history.errors() else "") or ""
            if not reason and outcome != "submitted":
                # never leave the user with a bare "Failed"
                reason = final[:500] or "The agent stopped without reporting a reason"
        if test_mode:
            # Trust the network guard over the model's own claim
            if report.intercepted and outcome in ("submitted", "ready_to_submit", "failed"):
                outcome, reason = "ready_to_submit", reason or "Form passed validation; submission intercepted"
            elif outcome in ("submitted", "ready_to_submit"):
                outcome = "failed"
                reason = (f"No application request was captured (submit clicks: {report.submit_clicks}). "
                          + (reason or ""))
            early = (sum(b.application for b in interceptor.blocked) - report.intercepted) if interceptor else 0
            if outcome == "failed" and early > 0:
                # A multi-step form saves each step server-side; test mode blocks those saves,
                # so this failure may be caused by the test itself, not the site or the agent.
                reason = (f"[test mode blocked {early} intermediate save(s)] " + (reason or "")).strip()
        status = STATUS_FOR_OUTCOME[outcome]
    except asyncio.CancelledError:
        db.update_job(url, status="pending", error=None)
        emit("job_finished", f"🛑 {tag} Cancelled: {title} at {company}", job_url=url, status="cancelled")
        raise
    except Exception as e:
        reason = str(e)
        status, outcome = "failed", "failed"
    finally:
        await close_session(browser)

    if status == "failed" and is_rate_limited(reason):
        # The provider throttled us: not the job's fault. Put it back and let the worker retry later.
        db.update_job(url, status="pending", error=None)
        emit("job_finished", f"⏳ {tag} AI provider rate limit hit on {title}; will retry", "warning",
             job_url=url, status="retry")
        if ctx is not None:
            ctx.cost_usd += cost
        add_run_usage(ctx, usage_tokens(history))
        return {"status": "retry", "cost_usd": cost, "outcome": "retry"}

    # Q&A: tool-reported answers, plus legacy markers
    answers = {a["question"]: a["answer"] for a in report.answers if a.get("question")}
    if history is not None:
        _, marker_qs = sc.extract_from_history(history)
        for q, a in marker_qs.items():
            answers.setdefault(q, a)
    missing = list(report.result.missing_info) if report.result else list(report.missing_from_text)
    _save_answers(answers, domain)
    for q in missing:  # unanswered questions show up in the Q&A page for the user
        sc.get_memory_store().qa_add(question=q, answer="", source_domain=domain)

    # Memory (self-learning)
    learned = 0
    success = outcome in ("submitted", "ready_to_submit")  # a test-mode pass is a successful run
    if history is not None:
        tool_learnings = [{"domain": domain, "category": l["category"], "content": l["insight"]} for l in report.learnings]
        marker_learnings = extract_learnings_from_markers(history)
        if tool_learnings or marker_learnings:
            store_learnings(store, tool_learnings + marker_learnings, url, success)
        try:
            llm_l = await _llm_learnings(history, url, title, success)
            if llm_l:
                store_learnings(store, llm_l, url, success)
            learned = len(tool_learnings) + len(marker_learnings) + len(llm_l or [])
        except Exception as e:
            emit("log", f"⚠️ {tag} Memory extraction failed (non-fatal): {e}", "warning")

    _set_status(url, status, None if status in ("applied", "skipped") else (reason or None))
    if status == "needs_input" and missing:
        db.update_job(url, error="Needs your answer: " + "; ".join(missing)[:500])

    finished = datetime.now(timezone.utc)
    try:
        MetricsStore().record_run(
            job_url=url, job_title=title, company=company, website_domain=domain, ats_platform=ats,
            success=success, started_at=started, finished_at=finished,
            step_count=len(history.history) if history is not None else steps["n"],
            memories_injected=injected, memories_extracted=learned, cost_usd=cost,
            error_message=None if success else (reason[:2000] or None),
            run_id=ctx.run_id if ctx else None,
        )
    except Exception as e:
        emit("log", f"⚠️ {tag} Metrics recording failed (non-fatal): {e}", "warning")

    tokens = usage_tokens(history)
    add_run_usage(ctx, tokens)
    db.add_application({
        **tokens,
        "job_url": url, "run_id": ctx.run_id if ctx else None, "outcome": outcome, "reason": reason[:2000],
        "confirmation": report.result.confirmation_text if report.result else None,
        "answers": report.answers, "missing_info": missing, "resume_path": resume_path,
        "screenshot_path": screenshot_path,
        "cost_usd": None if history is not None and _cost_unknown(history) else cost,
        "steps": len(history.history) if history is not None else steps["n"],
        "source": job.get("source") or "", "ats": ats,
        "test_mode": test_mode, "submit_clicks": report.submit_clicks, "intercepted": report.intercepted,
    })

    icon = {"applied": "✅", "needs_input": "❓", "skipped": "⏭️", "test_passed": "🧪"}.get(status, "❌")
    label = {"applied": "Applied", "needs_input": "Needs your input", "skipped": "Skipped",
             "test_passed": "Test passed (submission intercepted)"}.get(status, "Failed")
    emit("job_finished", f"{icon} {tag} {label}: {title} at {company}" + (f" — {reason[:120]}" if reason and status != "applied" else ""),
         "info" if status in ("applied", "skipped") else "warning",
         job_url=url, status=status, outcome=outcome, cost_usd=round(cost, 4), prefilled=report.prefilled)
    if ctx is not None and history is not None and _cost_unknown(history) and not ctx.counters.get("cost_unknown_warned"):
        ctx.counters["cost_unknown_warned"] = True
        events.warn("This model has no price data, so LLM cost shows as unknown and the run budget "
                       "(max cost per run) cannot stop the run. Use the daily cap to limit volume.")
    if ctx is not None:
        ctx.cost_usd += cost
        emit("cost", f"💰 Run LLM cost so far: ${ctx.cost_usd:.3f}", cost_usd=round(ctx.cost_usd, 4))
    return {"status": status, "cost_usd": cost, "outcome": outcome}


def select_jobs(mode: str, limit: int | None, job_url: str | None, job_urls: list[str] | None) -> list[dict]:
    jobs = db.read_jobs()
    if job_url or job_urls:
        picked = []
        for u in ([job_url] if job_url else []) + list(job_urls or []):
            j = jobs.get(u)
            if j and j.get("status") in ("pending", "failed", "needs_input", "test_passed", "skipped"):
                db.update_job(u, status="pending", error=None)
                j["status"] = "pending"
                picked.append(j)
        return picked
    pending = [j for j in jobs.values() if j.get("status") == "pending"]
    if mode == "easy":
        pending = [j for j in pending if j.get("easy_apply") is True]
    elif mode == "external":
        pending = [j for j in pending if j.get("easy_apply") is not True]
    pending.sort(key=lambda j: -(j.get("match_score") or 0))  # best matches first
    return pending[:limit] if limit else pending


async def run_apply(ctx: RunContext, *, mode: str = "all", workers: int = 1, limit: int | None = None,
                    job_url: str | None = None, job_urls: list[str] | None = None,
                    test_mode: bool = False) -> dict:
    settings = load_settings()
    profile = load_profile()
    qa: dict = {}
    pending = select_jobs(mode, limit, job_url, job_urls)
    if not pending:
        events.info("No pending jobs to apply to.")
        return {"applied": 0}

    applied_labels = [f"{j.get('title', '')} at {j.get('company', '')}"
                      for j in db.read_jobs().values() if j.get("status") == "applied"]
    cap = int(settings.get("daily_apply_cap", 25) or 0)
    budget = float(settings.get("max_run_cost_usd", 5.0) or 0)
    stagger = int(settings.get("stagger_delay", 5) or 0)
    events.info(f"Applying to {len(pending)} job(s) with {min(workers, len(pending))} worker(s)"
                + (f"; daily cap {cap}/source" if cap else "") + (f"; budget ${budget:.2f}" if budget else ""))

    queue: asyncio.Queue = asyncio.Queue()
    for j in pending:
        queue.put_nowait(j)
    stats: dict[str, int] = {}
    lock = asyncio.Lock()

    async def worker(wid: int):
        while True:
            try:
                job = queue.get_nowait()
            except asyncio.QueueEmpty:
                return
            async with lock:
                if budget and ctx.cost_usd >= budget:
                    events.warn(f"💸 Budget of ${budget:.2f} reached — not starting more applications")
                    while not queue.empty():
                        queue.get_nowait()
                    return
                source = job.get("source") or _domain(job["url"])
                if cap and db.applications_today(source) >= cap:
                    emit("job_skipped", f"⏸️ Daily cap of {cap} reached for {source}; leaving "
                                        f"{job.get('title', '')} pending", job_url=job["url"])
                    stats["capped"] = stats.get("capped", 0) + 1
                    continue
            res = await apply_to_job(job, profile=profile, qa=qa, applied_labels=applied_labels,
                                     worker_id=wid, ctx=ctx, test_mode=test_mode)
            if res["status"] == "retry":
                tries = job.get("_retries", 0) + 1
                if tries <= 2:
                    job["_retries"] = tries
                    await asyncio.sleep(60 * tries)  # back off before trying the provider again
                    queue.put_nowait(job)
                    continue
                db.update_job(job["url"], status="failed", error="AI provider rate limit; try again later")
                res["status"] = "failed"
            stats[res["status"]] = stats.get(res["status"], 0) + 1
            ctx.counters["applied"] = stats.get("applied", 0)
            if stagger and not queue.empty():
                await asyncio.sleep(stagger)

    # Clone worker profiles before any browser starts: once worker 1's Chrome is
    # running, Windows locks its cookie database and it can't be copied.
    from .browsers import uses_own_chrome, worker_profile_dir
    if not uses_own_chrome():
        for wid in range(2, min(workers, len(pending)) + 1):
            await asyncio.to_thread(worker_profile_dir, wid)

    tasks = []
    for i in range(min(workers, len(pending))):
        if i:
            await asyncio.sleep(5)  # stagger browser launches
        tasks.append(asyncio.create_task(worker(i + 1)))
    try:
        await asyncio.gather(*tasks)
    finally:
        for t in tasks:
            t.cancel()
    events.info(f"Results: {stats}")
    return stats
