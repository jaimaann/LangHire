"""Collecting jobs from a job source plugin.

The old code ignored ``CollectRequest.source`` and always searched LinkedIn with
a hardcoded prompt, so the eight YAML source plugins were never used. Here the
chosen plugin's ``collection_prompt`` drives the agent, jobs are recorded via a
tool (markers still work), and descriptions are read straight from the page
DOM before falling back to an LLM agent.
"""
from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone

from core import db
from core.config import load_profile, load_settings
from core import shared_config as sc
from core.agent_logger import on_step as _log_step, on_done as _log_done, log_run_start as _log_start

from . import events, prompts
from .apply import safe_filename
from .browsers import close_session, make_browser_session
from .events import RunContext, emit
from .matching import match_score
from .tools import AgentReport, build_collect_tools
from . import vision

_JOB_FOUND = re.compile(r"@@JOB_FOUND:\s*(\{[^}]{1,2000}\})")


def parse_job_markers(text: str) -> list[dict]:
    out = []
    for m in _JOB_FOUND.finditer(text or ""):
        try:
            j = json.loads(m.group(1))
        except ValueError:
            continue
        if isinstance(j, dict) and j.get("url"):
            out.append(j)
    return out


def _normalize_url(url: str) -> str:
    url = (url or "").strip()
    # LinkedIn: keep only the canonical /jobs/view/<id>/ form
    # (LinkedIn now also uses /jobs/view/<slug>-<id>, which the old pattern missed)
    m = re.search(r"linkedin\.com/jobs/view/(?:[^/?#]*-)?(\d{6,})", url) or re.search(r"currentJobId=(\d+)", url)
    if m and "linkedin.com" in url:
        return f"https://www.linkedin.com/jobs/view/{m.group(1)}/"
    return url


async def collect_for_title(plugin, title: str, profile: dict, *, max_jobs: int, filters: dict | None,
                            ctx: RunContext | None = None) -> int:
    existing = db.read_jobs()
    known = [u for u, j in existing.items() if j.get("search_title") == title and j.get("source") == plugin.name]
    task = prompts.build_collect_task(
        plugin, title, list(profile.get("target_locations") or []), max_jobs, filters, known,
        list(profile.get("languages") or []),
    )
    report = AgentReport()
    tools = build_collect_tools(report)
    final_text = ""
    seen = set(existing)
    found = 0
    agent_ref: dict = {}

    def save(batch: list[dict]) -> int:
        nonlocal found
        now = datetime.now(timezone.utc).isoformat()
        new = []
        for j in batch:
            if max_jobs and found + len(new) >= max_jobs:
                break  # never collect more than asked for
            url = _normalize_url(j.get("url", ""))
            if not url or url in seen or not sc.validate_job_url(url, resolve=False):
                continue
            seen.add(url)
            job = {
                "url": url, "title": (j.get("title") or "").strip(), "company": (j.get("company") or "").strip(),
                "location": (j.get("location") or "").strip(), "easy_apply": j.get("easy_apply"),
                "source": plugin.name, "search_title": title, "status": "pending",
                "collected_at": now, "applied_at": None, "error": None,
            }
            job["match_score"] = match_score(job, profile)
            new.append(job)
        added = db.add_jobs(new)
        found += added
        for job in new:
            emit("job_found", f"💾 {job['title']} at {job['company']}", job_url=job["url"], source=plugin.name)
        if ctx is not None:
            ctx.counters["collected"] = ctx.counters.get("collected", 0) + added
        return added

    def on_step(state, output, n):
        _log_step(state, output, n)
        if report.jobs:
            batch, report.jobs[:] = list(report.jobs), []
            save(batch)
        if output is not None:
            save(parse_job_markers(getattr(output, "memory", "") or ""))
        if max_jobs and found >= max_jobs and agent_ref.get("agent"):
            events.info(f"✅ Reached {max_jobs} jobs — stopping")
            agent_ref["agent"].stop()

    # Fast path: read the result cards straight from the page (no model calls)
    from .collect_fastpath import SUPPORTED, collect_cards
    if plugin.name in SUPPORTED:
        fast_browser = make_browser_session()
        try:
            url = plugin.search_url_for([title], list(profile.get("target_locations") or []), max_jobs, filters)
            cards = await collect_cards(fast_browser, url, want=(max_jobs + len(known)) if max_jobs else 0)
            added = save(cards)
            events.info(f"⚡ Read {len(cards)} job card(s) from {plugin.display_name}; {added} new")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            events.warn(f"Fast collection failed ({type(e).__name__}: {e}); using the agent")
        finally:
            await close_session(fast_browser)
        if (max_jobs and found >= max_jobs) or (not max_jobs and found > 0):
            return found
        if max_jobs:
            events.info(f"Fast path found {found}/{max_jobs}; the agent will look for the rest")

    settings = load_settings()
    convo = None
    if int(settings.get("log_retention_days", 14) or 0) > 0:
        convo = str(sc.logs_dir() / f"collect_{safe_filename(plugin.name, title)}_{datetime.now():%Y%m%d%H%M%S}")

    from browser_use import Agent
    browser = make_browser_session()
    _log_start("collect", f"{plugin.display_name}: {title}")
    try:
        agent: Agent = Agent(
            task=task, llm=sc.get_llm(), tools=tools, use_vision=vision.use_vision(), llm_call_timeout=300,
            browser_session=browser, max_failures=int(settings.get("max_failures", 8) or 8), calculate_cost=True,
            register_new_step_callback=on_step, register_done_callback=_log_done,
            save_conversation_path=convo,
        )
        agent_ref["agent"] = agent
        history = await agent.run(max_steps=150)
        final_text = (history.final_result() or "").strip()
        if report.jobs:
            save(list(report.jobs))
        for item in history.history:
            mo = item.model_output
            if mo is None:
                continue
            save(parse_job_markers(getattr(mo, "memory", "") or ""))
            for act in getattr(mo, "action", []) or []:
                dumped = act.model_dump() if hasattr(act, "model_dump") else act
                save(parse_job_markers(json.dumps(dumped, default=str)))
        from .apply import _usage_cost
        if ctx is not None:
            ctx.cost_usd += _usage_cost(history)
    finally:
        await close_session(browser)
    if found == 0 and final_text:
        # Say why, instead of a bare "finished successfully"
        events.warn(f"No new jobs for '{title}'. Agent said: {final_text[:400]}")
    return found


_DESC_JS = r"""() => {
  const pick = ['.jobs-description__content', '.jobs-box__html-content', '#jobDescriptionText',
                '[data-automation="jobAdDetails"]', '.description', '#content', 'main', 'article'];
  for (const sel of pick) {
    const el = document.querySelector(sel);
    if (el && el.innerText && el.innerText.trim().length > 300) return el.innerText.trim();
  }
  return (document.body && document.body.innerText || '').trim();
}"""


async def fetch_description(url: str, job: dict) -> str:
    """Read the posting text from the DOM; use an LLM agent only if that fails."""
    browser = make_browser_session()
    try:
        await browser.start()
        page = await browser.get_current_page()
        if page is None:
            page = await browser.new_page(url)
        else:
            await page.goto(url)
        await asyncio.sleep(3)
        text = await page.evaluate(_DESC_JS)
        text = (text or "").strip()
        if len(text) >= 300:
            return text[:20000]
    except Exception as e:
        events.info(f"  DOM read failed ({type(e).__name__}); using the agent")
    finally:
        await close_session(browser)

    from browser_use import Agent
    browser = make_browser_session()
    try:
        agent: Agent = Agent(
            task=(f"Go to {url}. Extract the full job description (title, company, location, description, "
                  "requirements, responsibilities) and return it as your final done text. Do not apply."),
            llm=sc.get_llm(), use_vision=False, browser_session=browser, max_failures=5,
        )
        history = await agent.run(max_steps=8)
        return (history.final_result() or "").strip()
    finally:
        await close_session(browser)


async def run_collect(ctx: RunContext, *, title: str | None, source: str, max_jobs: int,
                      filters: dict | None) -> dict:
    profile = load_profile()
    plugin = prompts.registry().get_by_name(source or "linkedin")
    if plugin is None:
        raise ValueError(f"Unknown job source '{source}'")
    if not plugin.enabled:
        raise ValueError(f"Job source '{plugin.display_name}' is disabled")
    titles = [title] if title else list(profile.get("target_job_titles") or [])
    if not titles:
        raise ValueError("Add at least one target job title to your profile first")
    ctx.counters.setdefault("collected", 0)
    total = 0
    for i, t in enumerate(titles, start=1):
        events.info(f"[{i}/{len(titles)}] Collecting '{t}' from {plugin.display_name}")
        try:
            n = await collect_for_title(plugin, t, profile, max_jobs=max_jobs, filters=filters, ctx=ctx)
            total += n
            events.info(f"  Found {n} new job(s)")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            events.error(f"  Error collecting '{t}': {e}")

    needs = [(u, j) for u, j in db.read_jobs().items()
             if j.get("status") == "pending" and not j.get("description") and j.get("source") == plugin.name]
    if needs:
        events.info(f"📋 Fetching descriptions for {len(needs)} job(s)...")
    for i, (url, job) in enumerate(needs, start=1):
        try:
            desc = await fetch_description(url, job)
            if desc:
                job["description"] = desc
                db.update_job(url, description=desc, match_score=match_score(job, profile))
                emit("description_fetched", f"  [{i}/{len(needs)}] ✅ {job.get('title', '')} ({len(desc)} chars)",
                     job_url=url)
            else:
                events.warn(f"  [{i}/{len(needs)}] ⚠️ No description for {job.get('title', '')}")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            events.warn(f"  [{i}/{len(needs)}] ❌ {e}")
    if total == 0:
        events.warn(f"Collection finished with no new jobs from {plugin.display_name}. Try another title, "
                    "a broader location, or a job site that covers your country.")
    else:
        events.info(f"Collection complete: {total} new job(s) from {plugin.display_name}")
    return {"collected": total}
