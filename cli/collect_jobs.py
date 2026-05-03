"""
Script 1: Collect job links and descriptions from LinkedIn.
Searches each target job title, collects job URLs with metadata, then fetches
full job descriptions for each collected job. Saves everything to jobs.json.

Usage:
  uv run python collect_jobs.py                    # collect for all titles
  uv run python collect_jobs.py --title "Data Analyst"  # single title
  uv run python collect_jobs.py --resume           # skip already-collected titles
  uv run python collect_jobs.py --skip-descriptions # skip description fetching phase
"""
import argparse
import asyncio
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

if not getattr(sys, 'frozen', False):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from browser_use import Agent, BrowserSession

try:
    import core.shared_config as config
    from core.shared_config import (
        JOBS_FILE, CANDIDATE_PROFILE, LOGS_DIR, BASE_DIR, BROWSER_PROFILE_DIR,
        load_json, save_json, refresh_credentials, credential_refresh_loop,
        read_jobs, write_jobs, update_job,
    )
    from core.agent_logger import on_step as _agent_on_step, on_done as _agent_on_done, log_run_start as _agent_log_start
except ImportError:
    import backend.core.shared_config as config
    from backend.core.shared_config import (
        JOBS_FILE, CANDIDATE_PROFILE, LOGS_DIR, BASE_DIR, BROWSER_PROFILE_DIR,
        load_json, save_json, refresh_credentials, credential_refresh_loop,
        read_jobs, write_jobs, update_job,
    )
    from backend.core.agent_logger import on_step as _agent_on_step, on_done as _agent_on_done, log_run_start as _agent_log_start


def load_jobs() -> dict:
    return read_jobs()


def save_jobs(jobs: dict):
    write_jobs(jobs)


async def collect_for_title(title: str, existing_jobs: dict, profile: dict, max_jobs: int = 0) -> list[dict]:
    """Use an agent to collect job listings for a single title."""
    import json as _json, re as _re
    from datetime import datetime, timezone

    locations = ", ".join(profile["target_locations"])

    known_urls = [
        url for url, j in existing_jobs.items()
        if j.get("search_title") == title
    ]
    known_count = len(known_urls)

    resume_hint = ""
    if known_count > 0:
        resume_hint = (
            f"\n\nIMPORTANT — SKIP KNOWN JOBS: {known_count} jobs were already collected for this search. "
            f"Do NOT count these toward your target. Only count NEW jobs not in the list below. "
            f"As you scroll, skip any jobs with these URLs — keep scrolling past them to find new ones.\n"
            f"Known job URLs (already collected — DO NOT count these):\n"
            + "\n".join(known_urls[-50:])
        )

    seen_urls = set(existing_jobs.keys())
    found = []

    def _extract_jobs_from_text(text: str):
        """Parse jobs from a text block and save new ones immediately."""
        new_in_step = []

        # Structured markers
        for m in _re.finditer(r"@@JOB_FOUND:\s*(\{[^}]{1,2000}\})", text):
            try:
                job = _json.loads(m.group(1))
                url = job.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    new_in_step.append(job)
            except _json.JSONDecodeError:
                pass

        # LinkedIn job URLs with metadata in surrounding text
        # (bare URLs without @@JOB_FOUND are skipped — no useful metadata)

        # Bare job IDs: "4356842209: Associate Data Analyst - PitchBook - Easy Apply"
        for m in _re.finditer(r"(\d{10,})\s*:\s*(.+?)(?:\s*-\s*(.+?))?(?:\s*-\s*(Easy Apply|NO Easy Apply))?(?:\n|$)", text):
            url = f"https://www.linkedin.com/jobs/view/{m.group(1)}/"
            if url not in seen_urls:
                seen_urls.add(url)
                new_in_step.append({
                    "url": url,
                    "title": (m.group(2) or "").strip(),
                    "company": (m.group(3) or "").strip(),
                    "location": "",
                    "easy_apply": m.group(4) == "Easy Apply" if m.group(4) else None,
                })

        if new_in_step:
            # Save to disk immediately
            now = datetime.now(timezone.utc).isoformat()
            jobs = read_jobs()
            for job in new_in_step:
                url = job.get("url") or job.pop("url", "")
                jobs[url] = {
                    **job, "url": url,
                    "search_title": title, "status": "pending",
                    "collected_at": now, "applied_at": None, "error": None,
                }
            write_jobs(jobs)
            found.extend(new_in_step)
            print(f"    💾 Saved {len(new_in_step)} new jobs (total this title: {len(found)})")

    def on_step(browser_state, agent_output, step_num):
        _agent_on_step(browser_state, agent_output, step_num)
        if not agent_output:
            return
        memory = getattr(agent_output, "memory", "") or ""
        _extract_jobs_from_text(memory)

    # Refresh credentials before each title to avoid mid-run expiry
    refresh_credentials()
    _agent_log_start("collect", title)

    llm = config.get_llm()
    browser = BrowserSession(user_data_dir=str(BROWSER_PROFILE_DIR))

    agent = Agent(
        task=(
            f"FIRST — LOGIN CHECK:\n"
            f"1. Go to https://www.linkedin.com/feed/ to check if you're logged into LinkedIn.\n"
            f"   - If you see the feed/home page → logged in ✓\n"
            f"   - If you see a login page → WAIT for user to log in manually. Check every 15 seconds (refresh). Wait up to 5 minutes.\n"
            f"2. Open a new tab and go to https://mail.google.com/mail/u/0/#inbox to check Gmail.\n"
            f"   - If you see the Gmail inbox (list of emails) → logged in ✓\n"
            f"   - If you see a Google sign-in page or redirect → WAIT for user to log in manually. Check every 15 seconds. Wait up to 5 minutes.\n"
            f"3. Close the Gmail tab and switch back to LinkedIn.\n\n"
            f"THEN: Go to https://www.linkedin.com/jobs and search for '{title}' in '{locations}' "
            f"posted in the last 10 days. Look for entry level jobs asking up to 2 years of experience.\n\n"
            f"CRITICAL — For EACH job you see, you MUST output a @@JOB_FOUND marker in your memory field IMMEDIATELY in the SAME step you see it. "
            f"Do NOT batch them. Do NOT wait until the end. Output them one by one as you scroll.\n"
            f"Format (one per job, in your memory field):\n"
            f'@@JOB_FOUND: {{"title": "<job title>", "company": "<company>", "location": "<location>", '
            f'"url": "<linkedin job URL>", "easy_apply": true/false}}\n\n'
            f"Scroll through results and collect jobs. "
            f"{'Stop after collecting ' + str(max_jobs) + ' NEW jobs (not already in the known list) and call done. ' if max_jobs > 0 else ''}"
            f"Include BOTH Easy Apply and non-Easy Apply jobs. "
            f"Do NOT apply to any jobs — only collect the listings.\n\n"
            f"Skip jobs requiring languages other than: {', '.join(profile['languages'])}.\n"
            f"After scrolling through all results, call done."
            f"{resume_hint}"
        ),
        llm=llm,
        use_vision=True,
        llm_call_timeout=300,  # 5 minutes per step
        browser_session=browser,
        max_failures=10,
        message_compaction=True,
        max_history_items=10,
        max_clickable_elements_length=5000,
        include_recent_events=5,
        register_new_step_callback=on_step,
        register_done_callback=_agent_on_done,
        save_conversation_path=str(LOGS_DIR / f"collect_{title.replace(' ', '_')}"),
    )

    result = await agent.run()

    # Extract jobs from the final done text (agent often puts @@JOB_FOUND there)
    if result and result.history:
        for item in result.history:
            if not item.model_output:
                continue
            # Check memory field
            memory = getattr(item.model_output, "memory", "") or ""
            if "@@JOB_FOUND" in memory:
                _extract_jobs_from_text(memory)
            # Check done action text
            actions = getattr(item.model_output, "action", []) or []
            for act in actions:
                text = getattr(act, "text", "") or ""
                if "@@JOB_FOUND" in text:
                    _extract_jobs_from_text(text)

    return found


async def fetch_description_for_job(url: str, job: dict) -> str:
    """Visit a single LinkedIn job page and extract the full description."""
    refresh_credentials()
    llm = config.get_llm()
    browser = BrowserSession(user_data_dir=str(BROWSER_PROFILE_DIR))

    title = job.get("title", "Unknown")
    company = job.get("company", "unknown")

    agent = Agent(
        task=(
            f"Go to {url} on LinkedIn. Extract the FULL job description text including:\n"
            f"- Job title\n- Company name\n- Location\n- About the job / description\n"
            f"- Qualifications / requirements\n- Skills mentioned\n- Responsibilities\n\n"
            f"Output ALL of this text in your memory field prefixed with:\n"
            f"@@JOB_DESCRIPTION: <the full text>\n\n"
            f"Do NOT apply. Just read and extract the description, then call done."
        ),
        llm=llm,
        use_vision=True,
        browser_session=browser,
        max_failures=5,
        message_compaction=True,
        max_history_items=5,
        max_clickable_elements_length=3000,
        include_recent_events=3,
        save_conversation_path=str(LOGS_DIR / f"desc_{company.replace(' ', '_')}_{title.replace(' ', '_')[:20]}"),
    )

    result = await agent.run()

    # Extract description from agent memory
    description = ""
    for item in result.history:
        if not item.model_output:
            continue
        memory = getattr(item.model_output, "memory", "") or ""
        match = re.search(r"@@JOB_DESCRIPTION:\s*(.+)", memory, re.DOTALL)
        if match:
            description = match.group(1).strip()
        elif len(memory) > len(description):
            description = memory.strip()

    return description


async def collect_descriptions(jobs: dict):
    """Phase 2: Fetch descriptions for all jobs that don't have one yet."""
    needs_desc = [
        (url, j) for url, j in jobs.items()
        if j.get("status") == "pending" and not j.get("description")
    ]

    if not needs_desc:
        print("All jobs already have descriptions.")
        return

    print(f"\n📋 Fetching descriptions for {len(needs_desc)} jobs...\n")

    for i, (url, job) in enumerate(needs_desc):
        title = job.get("title", "Unknown")
        company = job.get("company", "Unknown")
        print(f"  [{i+1}/{len(needs_desc)}] {title} at {company}...")

        for attempt in range(2):
            try:
                description = await fetch_description_for_job(url, job)
                if description:
                    update_job(url, description=description)
                    print(f"    ✅ Got description ({len(description)} chars)")
                else:
                    print(f"    ⚠️  No description extracted")
                break
            except Exception as e:
                error_str = str(e).lower()
                if "security token" in error_str or "expired" in error_str:
                    print(f"    🔑 Credentials expired — refreshing...")
                    refresh_credentials()
                    if attempt < 1:
                        continue
                print(f"    ❌ Error: {e}")
                break


async def main():
    parser = argparse.ArgumentParser(description="Collect LinkedIn job listings")
    parser.add_argument("--title", help="Collect for a single job title")
    parser.add_argument("--resume", action="store_true", help="Skip titles already collected")
    parser.add_argument("--skip-descriptions", action="store_true", help="Skip description fetching phase")
    args = parser.parse_args()

    profile = load_json(CANDIDATE_PROFILE, {})
    jobs = load_jobs()
    LOGS_DIR.mkdir(exist_ok=True)

    if args.title:
        titles = [args.title]
    else:
        titles = profile.get("target_job_titles", [])

    # Track which titles have been collected
    collected_titles = set()
    if args.resume:
        for j in jobs.values():
            if "search_title" in j:
                collected_titles.add(j["search_title"])

    # Background credential refresh every 14 min
    cred_task = asyncio.create_task(credential_refresh_loop(14))

    for i, title in enumerate(titles):
        if args.resume and title in collected_titles:
            print(f"[{i+1}/{len(titles)}] Skipping '{title}' (already collected)")
            continue

        print(f"\n{'='*60}")
        print(f"[{i+1}/{len(titles)}] Collecting: {title}")
        print(f"{'='*60}")

        for attempt in range(3):
            try:
                found = await collect_for_title(title, jobs, profile)
                jobs = load_jobs()  # reload since step callback writes directly
                print(f"  Found {len(found)} new jobs (total: {len(jobs)})")
                break
            except Exception as e:
                error_str = str(e).lower()
                if "security token" in error_str or "expired" in error_str:
                    print(f"  🔑 Credentials expired (attempt {attempt+1}/3) — refreshing...")
                    refresh_credentials()
                    if attempt < 2:
                        continue
                print(f"  Error: {e}")
                break

    cred_task.cancel()

    # Phase 2: Fetch descriptions for all pending jobs without one
    if not args.skip_descriptions:
        jobs = load_jobs()  # reload latest
        cred_task2 = asyncio.create_task(credential_refresh_loop(14))
        await collect_descriptions(jobs)
        cred_task2.cancel()
        jobs = load_jobs()  # reload after descriptions

    # Summary
    jobs = load_jobs()
    has_desc = sum(1 for j in jobs.values() if j.get("description"))
    easy = sum(1 for j in jobs.values() if j.get("easy_apply"))
    non_easy = len(jobs) - easy
    pending = sum(1 for j in jobs.values() if j.get("status") == "pending")
    print(f"\n{'='*60}")
    print(f"Collection complete!")
    print(f"Total jobs: {len(jobs)} (Easy Apply: {easy}, Non-Easy Apply: {non_easy})")
    print(f"Jobs with descriptions: {has_desc}/{len(jobs)}")
    print(f"Pending applications: {pending}")


if __name__ == "__main__":
    asyncio.run(main())
