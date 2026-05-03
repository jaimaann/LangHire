
"""
Script 2: Apply to collected jobs with multiple concurrent workers.
One agent per job. Tracks status in jobs.json.

Usage:
  uv run python apply_jobs.py                          # 1 worker, easy apply
  uv run python apply_jobs.py --workers 3              # 3 concurrent workers
  uv run python apply_jobs.py --workers 2 --no-easy-apply  # non-easy apply
  uv run python apply_jobs.py --limit 10               # apply to max 10 jobs
"""
import argparse
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

if not getattr(sys, 'frozen', False):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from browser_use import Agent, BrowserSession

try:
    import core.shared_config as config
    from core.shared_config import (
        BASE_DIR, BROWSER_PROFILE_DIR,
        JOBS_FILE, QA_FILE, CANDIDATE_PROFILE, LOGS_DIR, RESUME_PATH, SENSITIVE_DATA, BLOCKED_DOMAINS,
        AWS_PROFILE, AWS_REGION, MODEL_ID,
        load_json, save_json, refresh_credentials, credential_refresh_loop,
        build_memory_context, extract_from_history, normalize_question,
        read_jobs, claim_job, update_job, get_memory_store,
    )
    from memory import extract_learnings_from_markers, extract_learnings_via_llm, store_learnings
    from memory.metrics import MetricsStore
    from core.agent_logger import on_step as _agent_on_step, on_done as _agent_on_done, log_run_start as _agent_log_start
except ImportError:
    import backend.core.shared_config as config
    from backend.core.shared_config import (
        BASE_DIR, BROWSER_PROFILE_DIR,
        JOBS_FILE, QA_FILE, CANDIDATE_PROFILE, LOGS_DIR, RESUME_PATH, SENSITIVE_DATA, BLOCKED_DOMAINS,
        AWS_PROFILE, AWS_REGION, MODEL_ID,
        load_json, save_json, refresh_credentials, credential_refresh_loop,
        build_memory_context, extract_from_history, normalize_question,
        read_jobs, claim_job, update_job, get_memory_store,
    )
    from backend.memory import extract_learnings_from_markers, extract_learnings_via_llm, store_learnings
    from backend.memory.metrics import MetricsStore
    from backend.core.agent_logger import on_step as _agent_on_step, on_done as _agent_on_done, log_run_start as _agent_log_start

# Lock for thread-safe QA file writes
_qa_lock = asyncio.Lock()


_ERROR_MAP = [
    ("'NoneType' object is not subscriptable", "Browser agent encountered an unexpected page state. The page may have changed or timed out."),
    ("'NoneType' object has no attribute", "Browser agent lost track of a page element. The site may have redirected or loaded slowly."),
    ("net::ERR_", "Network error — the page failed to load. Check your internet connection."),
    ("Timeout", "Operation timed out. The page took too long to respond."),
    ("ERR_CONNECTION_REFUSED", "Could not connect to the website. It may be temporarily down."),
    ("security token", "AWS credentials expired. They will be refreshed automatically on retry."),
    ("rate limit", "API rate limit reached. Wait a moment and try again."),
    ("context was destroyed", "Browser page closed unexpectedly during the application."),
    ("Target page, context or browser has been closed", "Browser closed unexpectedly during the application."),
]


def _friendly_error(raw: str) -> str:
    """Translate raw Python/browser errors into user-readable messages."""
    for pattern, friendly in _ERROR_MAP:
        if pattern.lower() in raw.lower():
            return friendly
    if len(raw) > 200 and ("Traceback" in raw or "Error:" in raw):
        return "Application failed due to an unexpected error. Check the Logs page for details."
    return raw


async def save_job_status(url: str, status: str, error: str | None = None):
    fields: dict = {"status": status}
    if error:
        fields["error"] = _friendly_error(error)
    else:
        fields["error"] = None
    if status == "applied":
        fields["applied_at"] = datetime.now(timezone.utc).isoformat()
    update_job(url, **fields)


async def save_new_qa(new_questions: dict, source_domain: str = ""):
    if not new_questions:
        return
    async with _qa_lock:
        store = get_memory_store()
        if store:
            for q, a in new_questions.items():
                store.qa_add(question=q, answer=a or "", source_domain=source_domain)
        else:
            qa = load_json(QA_FILE, {})
            existing_norms = {normalize_question(k) for k in qa}
            for q, a in new_questions.items():
                if normalize_question(q) not in existing_norms:
                    qa[q] = a
                    existing_norms.add(normalize_question(q))
            save_json(QA_FILE, qa)


async def apply_to_job(job: dict, profile: dict, qa: dict, applied_labels: list[str], easy_apply: bool, worker_id: int, resume_path_override: str | None = None) -> str:
    """Apply to a single job. Returns final status."""
    url = job["url"]
    title = job.get("title", "Unknown")
    company = job.get("company", "Unknown")
    print(f"  🚀 [W{worker_id}] Starting: {title} at {company}")

    if not config.validate_job_url(url):
        await save_job_status(url, "blocked", "Invalid or internal URL")
        print(f"  🚫 [W{worker_id}] Blocked (invalid URL): {title} at {company}")
        return "blocked"

    if any(domain in url for domain in BLOCKED_DOMAINS):
        await save_job_status(url, "blocked", "Blocked domain")
        print(f"  🚫 [W{worker_id}] Blocked: {title} at {company}")
        return "blocked"

    if not claim_job(url):
        print(f"  ⏭️  [W{worker_id}] Skipped (already claimed): {title} at {company}")
        return "skipped"

    # Always refresh credentials before each job to avoid mid-run expiry
    refresh_credentials()

    llm = config.get_llm()
    # Use the shared browser profile in OS data dir (same as login endpoint)
    browser = BrowserSession(user_data_dir=str(BROWSER_PROFILE_DIR))
    mem_store = get_memory_store()
    # Count memories injected for metrics tracking
    domain = mem_store.extract_domain(url)
    memories_before = mem_store.get_domain_memories(url, limit=50)
    memories_injected_count = len(memories_before) if memories_before else 0
    memory = build_memory_context(profile, qa, applied_labels, job_url=url)
    run_started_at = datetime.now(timezone.utc)

    resume_path = resume_path_override or RESUME_PATH

    # Profile email is for application forms; credentials email/password are for ATS login
    agent_sensitive_data = {
        "email": profile.get("email", "").strip(),
        "account_email": SENSITIVE_DATA.get("email", "").strip(),
        "password": SENSITIVE_DATA.get("password", ""),
    }
    if not agent_sensitive_data["email"]:
        agent_sensitive_data["email"] = agent_sensitive_data["account_email"]

    login_preamble = (
        f"FIRST — LOGIN CHECK:\n"
        f"1. Go to https://www.linkedin.com/feed/ to check if you're logged into LinkedIn.\n"
        f"   - If you see the feed/home page → logged in ✓\n"
        f"   - If you see a login page → WAIT for user to log in manually. Check every 15 seconds (refresh). Wait up to 5 minutes.\n"
        f"2. Open a new tab and go to https://mail.google.com/mail/u/0/#inbox to check Gmail.\n"
        f"   - If you see the Gmail inbox (list of emails) → logged in ✓\n"
        f"   - If you see a Google sign-in page or redirect → WAIT for user to log in manually. Check every 15 seconds. Wait up to 5 minutes.\n"
        f"3. Close the Gmail tab and switch back to LinkedIn.\n\n"
    )

    otp_instructions = (
        "\n\nOTP/VERIFICATION CODES: If ANY site asks for a verification code, OTP, or 2FA token:\n"
        "1. Choose the EMAIL option if given a choice\n"
        "2. Open a new tab and go to https://mail.google.com\n"
        "3. Find the most recent email with the verification/OTP code\n"
        "4. Copy the code, switch back to the application tab, and enter it\n"
        "5. This is NOT a blocker — always attempt to retrieve the code from Gmail before giving up"
    )

    if easy_apply:
        apply_instructions = (
            f"{login_preamble}"
            f"THEN: Go to {url} on LinkedIn. Click Easy Apply and complete the application. "
            f"Use resume at {resume_path}. Auto-fill all fields from candidate profile."
            f"{otp_instructions}"
        )
    else:
        has_password = bool(agent_sensitive_data.get("password", "").strip())
        password_note = ""
        if not has_password:
            password_note = (
                "\n\nIMPORTANT: No password is configured in Settings. If the external site requires "
                "account creation or login:\n"
                "1. First check if you can apply as a guest (without creating an account)\n"
                "2. Try 'Sign in with LinkedIn' or 'Sign in with Google' buttons\n"
                "3. If no SSO option, CREATE A NEW ACCOUNT using <secret>account_email</secret> and a generated password "
                "(create a strong password like 'JobApp2026!')\n"
                "4. If account creation also fails, try 'Forgot password' → reset via email\n"
                "5. If nothing works after 3 attempts, report failure and move to the next job\n"
            )

        apply_instructions = (
            f"{login_preamble}"
            f"THEN: Go to {url} on LinkedIn. Click Apply and follow through to the external application page. "
            f"Use resume at {resume_path}. Auto-fill all fields from candidate profile.\n\n"
            f"NAVIGATING EXTERNAL SITES:\n"
            f"- The LinkedIn 'Apply' button often opens a company careers page, NOT the application form directly.\n"
            f"- You MUST explore the landing page: look for 'Apply Now', 'Submit Application', or similar buttons.\n"
            f"- Scroll down — the apply button is often below the job description.\n"
            f"- If you see a job listing page, click on the specific job title first, then look for the apply button.\n"
            f"- Some sites require you to click through 2-3 pages before reaching the actual form.\n"
            f"- If the page looks blank or is loading, wait 3-5 seconds and try scrolling.\n"
            f"- NEVER give up just because the form isn't immediately visible — always explore the page first.\n\n"
            f"EMAIL USAGE:\n"
            f"- For APPLICATION FORM fields (contact email, email address, etc.): use <secret>email</secret>\n"
            f"- For LOGGING IN or CREATING ACCOUNTS on external ATS sites: use <secret>account_email</secret> and <secret>password</secret>\n"
            f"{password_note}"
            f"If it's a video funnel or recruitment pitch, report failure and stop. "
            f"If the external form is broken after 3 attempts, report failure and stop.\n\n"
            f"BLOCKED SITES — if redirected to any of these, immediately call done with success=false: {', '.join(BLOCKED_DOMAINS)}"
            f"{otp_instructions}"
        )

    _agent_log_start("apply", f"{title} at {company}")

    agent = Agent(
        task=(
            f"{apply_instructions}\n\n"
            f"PERSISTENCE: Do NOT give up easily. Try at least 3 different approaches before reporting failure. "
            f"Scroll the page, look for alternative buttons, try clicking different elements. "
            f"Only call done with success=false after genuinely exhausting all options.\n\n"
            f"TRACKING: Include in memory field after submission:\n"
            f'@@JOB_APPLIED: {{"title": "{title}", "company": "{company}", "location": "{job.get("location", "")}"}}\n'
            f"For each form question: @@QUESTION: {{\"question\": \"...\", \"answer\": \"...\", \"type\": \"...\"}}"
        ),
        llm=llm,
        use_vision=True,
        llm_call_timeout=300,  # 5 minutes per step
        max_failures=10,
        browser_session=browser,
        sensitive_data=agent_sensitive_data,
        extend_system_message=memory,
        available_file_paths=[resume_path],
        save_conversation_path=str(LOGS_DIR / f"apply_{company.replace(' ', '_')}_{title.replace(' ', '_')[:30]}"),
        calculate_cost=True,
        message_compaction=True,
        max_history_items=10,
        max_clickable_elements_length=5000,
        include_recent_events=5,
        register_new_step_callback=_agent_on_step,
        register_done_callback=_agent_on_done,
    )

    try:
        result = await agent.run()

        # Extract Q&A from history
        _, new_questions = extract_from_history(result)
        domain = ""
        try:
            from urllib.parse import urlparse
            domain = urlparse(url).hostname or ""
            if domain.startswith("www."):
                domain = domain[4:]
        except Exception:
            pass
        await save_new_qa(new_questions, source_domain=domain)

        # Determine success/failure
        success = result.is_successful()

        # ── Memory extraction (self-learning) ─────────────────────────────
        mem_store = get_memory_store()
        # 1. Marker-based: extract @@LEARNING tags the agent emitted
        marker_learnings = extract_learnings_from_markers(result)
        if marker_learnings:
            store_learnings(mem_store, marker_learnings, url, success)
        # 2. LLM-based: use the configured LLM to summarise the run into procedural learnings
        llm_learnings = []
        try:
            def _llm_call(prompt):
                """Use the user's configured LLM for memory extraction."""
                import asyncio
                from browser_use.llm.messages import UserMessage
                extraction_llm = config.get_llm()
                loop = asyncio.new_event_loop()
                try:
                    resp = loop.run_until_complete(
                        asyncio.wait_for(
                            extraction_llm.ainvoke([UserMessage(content=prompt)]),
                            timeout=30,
                        )
                    )
                    return resp.completion if hasattr(resp, 'completion') else (resp.content if hasattr(resp, 'content') else str(resp))
                finally:
                    loop.close()

            llm_learnings = extract_learnings_via_llm(
                result, job_url=url, job_title=title, success=success,
                llm_call=_llm_call,
            )
            if llm_learnings:
                store_learnings(mem_store, llm_learnings, url, success)
        except Exception as mem_err:
            print(f"    ⚠️  [W{worker_id}] Memory extraction failed (non-fatal): {mem_err}")

        # ── Record metrics ────────────────────────────────────────────────
        run_finished_at = datetime.now(timezone.utc)
        memories_extracted_count = len(marker_learnings) + len(llm_learnings)
        try:
            MetricsStore().record_run(
                job_url=url, job_title=title, company=company,
                website_domain=domain, ats_platform=mem_store.detect_ats_platform(domain),
                success=success, started_at=run_started_at, finished_at=run_finished_at,
                step_count=len(result.history),
                memories_injected=memories_injected_count,
                memories_extracted=memories_extracted_count,
                error_message=(result.errors()[-1][:2000] if result.errors() else None) if not success else None,
            )
        except Exception as metrics_err:
            print(f"    ⚠️  [W{worker_id}] Metrics recording failed (non-fatal): {metrics_err}")

        if success:
            await save_job_status(url, "applied")
            print(f"  ✅ [W{worker_id}] Applied: {title} at {company}")
            return "applied"
        else:
            error_msg = result.errors()[-1] if result.errors() else "Agent reported failure"
            await save_job_status(url, "failed", error_msg[:2000])
            print(f"  ❌ [W{worker_id}] Failed: {title} at {company} — {error_msg[:100]}")
            return "failed"

    except Exception as e:
        error_str = str(e)
        if "security token" in error_str.lower() or "expired" in error_str.lower():
            refresh_credentials()
            await save_job_status(url, "pending", "credentials_expired_retry")
            print(f"  🔑 [W{worker_id}] Credentials expired on: {title} at {company} — refreshed, will retry")
            return "retry"
        await save_job_status(url, "failed", error_str[:2000])
        print(f"  ❌ [W{worker_id}] Error: {title} at {company} — {error_str[:100]}")
        return "failed"
    finally:
        try:
            await browser.close()
        except Exception as close_err:
            print(f"    ⚠️  [W{worker_id}] Browser cleanup error: {close_err}")


async def worker(name: str, worker_id: int, queue: asyncio.Queue, profile: dict, qa: dict, applied_labels: list, easy_apply: bool, stats: dict, cancel_flag: dict | None = None):
    """Worker that pulls jobs from queue and applies."""
    while True:
        if cancel_flag and cancel_flag.get("cancel_requested"):
            print(f"  🛑 [{name}] Stop requested — halting")
            break
        try:
            job = queue.get_nowait()
        except asyncio.QueueEmpty:
            break

        status = await apply_to_job(job, profile, qa, applied_labels, easy_apply, worker_id)
        stats[status] = stats.get(status, 0) + 1

        # On retry, put back in queue
        if status == "retry":
            queue.put_nowait(job)

        queue.task_done()


async def main():
    parser = argparse.ArgumentParser(description="Apply to collected jobs")
    parser.add_argument("--workers", type=int, default=1, help="Number of concurrent workers")
    parser.add_argument("--limit", type=int, help="Max jobs to process")
    parser.add_argument("--easy-apply", dest="easy_apply", action="store_true", default=True)
    parser.add_argument("--no-easy-apply", dest="easy_apply", action="store_false")
    args = parser.parse_args()

    jobs = load_json(JOBS_FILE, {})
    profile = load_json(CANDIDATE_PROFILE, {})
    qa = load_json(QA_FILE, {})
    LOGS_DIR.mkdir(exist_ok=True)

    # Filter pending jobs by type
    pending = [
        j for j in jobs.values()
        if j.get("status") == "pending"
        and (j.get("easy_apply") is True) == args.easy_apply
    ]

    if args.limit:
        pending = pending[:args.limit]

    if not pending:
        print("No pending jobs to apply to. Run collect_jobs.py first.")
        return

    applied_labels = [
        f"{j.get('title','')} at {j.get('company','')}"
        for j in jobs.values() if j.get("status") == "applied"
    ]

    mode = "Easy Apply" if args.easy_apply else "Non-Easy Apply"
    print(f"Applying to {len(pending)} {mode} jobs with {args.workers} worker(s)\n")

    queue = asyncio.Queue()
    for job in pending:
        queue.put_nowait(job)

    stats = {}
    num_workers = min(args.workers, len(pending))

    # Background credential refresh every 14 min — auto-cancelled when workers finish
    cred_task = asyncio.create_task(credential_refresh_loop(14))

    workers = []
    for i in range(num_workers):
        if i > 0:
            await asyncio.sleep(5)  # stagger browser launches
        workers.append(
            asyncio.create_task(worker(f"W{i+1}", i+1, queue, profile, qa, applied_labels, args.easy_apply, stats))
        )
    await asyncio.gather(*workers)
    cred_task.cancel()

    print(f"\n{'='*60}")
    print(f"Results: {stats}")
    total_applied = sum(1 for j in load_json(JOBS_FILE, {}).values() if j.get("status") == "applied")
    print(f"Total applied across all runs: {total_applied}")

    # Memory stats
    mem_stats = get_memory_store().get_stats()
    print(f"🧠 Agent memory: {mem_stats['total_memories']} memories across {mem_stats['unique_domains']} domains")


if __name__ == "__main__":
    asyncio.run(main())
