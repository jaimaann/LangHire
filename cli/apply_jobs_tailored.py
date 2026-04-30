"""
Script 3: Apply to collected jobs with tailored resumes.
For each job, fetches the job description from LinkedIn, extracts key skills,
customizes the resume PDF by adding those skills, then applies with the tailored resume.

Usage:
  uv run python apply_jobs_tailored.py                          # 1 worker, easy apply
  uv run python apply_jobs_tailored.py --workers 3              # 3 concurrent workers
  uv run python apply_jobs_tailored.py --workers 2 --no-easy-apply
  uv run python apply_jobs_tailored.py --limit 10
"""
import argparse
import asyncio
import json
import re
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import fitz  # pymupdf
import boto3
from browser_use import Agent, BrowserSession

import backend.core.shared_config as config
from backend.core.shared_config import (
    BASE_DIR,
    JOBS_FILE, QA_FILE, CANDIDATE_PROFILE, LOGS_DIR, RESUME_PATH, RESUMES_DIR,
    BLOCKED_DOMAINS, AWS_PROFILE, AWS_REGION, MODEL_ID,
    load_json, refresh_credentials, credential_refresh_loop,
    read_jobs, update_job, get_memory_store,
)

# Base skills from the original resume
BASE_SKILLS = ["Collaboration", "Problem Solving", "Conflict Resolution", "Microsoft Office Suite", "SQL"]


async def fetch_job_description(job: dict, worker_id: int) -> str:
    """Use a browser agent to visit the LinkedIn job page and extract the full description."""
    url = job["url"]

    # If we already fetched and cached the description, reuse it
    cached = read_jobs().get(url, {}).get("description")
    if cached:
        return cached

    refresh_credentials()
    llm = config.get_llm()
    browser = BrowserSession(user_data_dir=str(BASE_DIR / "browser_profile"))

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
        save_conversation_path=str(LOGS_DIR / f"desc_{job.get('company', 'unknown').replace(' ', '_')}_{job.get('title', '').replace(' ', '_')[:20]}"),
    )

    result = await agent.run()

    # Extract description from agent memory
    description = ""
    for item in result.history:
        if not item.model_output:
            continue
        memory = getattr(item.model_output, "memory", "") or ""
        # Look for our marker
        match = re.search(r"@@JOB_DESCRIPTION:\s*(.+)", memory, re.DOTALL)
        if match:
            description = match.group(1).strip()
        # Fallback: use the longest memory block as the description
        elif len(memory) > len(description):
            description = memory.strip()

    # Cache description in jobs.json for reuse
    if description:
        update_job(url, description=description)

    return description


def extract_skills_from_description(description: str, job_title: str) -> list[str]:
    """Use Claude via Bedrock to extract key skills from the job description."""
    if not description:
        return []

    session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
    bedrock = session.client("bedrock-runtime")

    prompt = (
        f"You are analyzing a job posting for the role: {job_title}\n\n"
        f"Job Description:\n{description[:4000]}\n\n"
        f"The candidate already has these skills on their resume: {', '.join(BASE_SKILLS)}\n\n"
        f"Extract 3-5 additional SPECIFIC, CONCRETE skills from the job description that:\n"
        f"1. Are explicitly mentioned as required or preferred\n"
        f"2. Are NOT already in the candidate's base skills list\n"
        f"3. Are plausible for a business admin graduate with 1 year of analyst experience\n"
        f"4. Are real tool/technology/methodology names (e.g., 'Tableau', 'Excel', 'Agile', 'Salesforce', 'Google Analytics')\n\n"
        f"Return ONLY a JSON array of skill strings. Example: [\"Tableau\", \"Google Analytics\", \"Project Management\"]\n"
        f"If no additional relevant skills found, return: []"
    )

    try:
        response = bedrock.invoke_model(
            modelId=MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 300,
                "messages": [{"role": "user", "content": prompt}],
            }),
        )
        body = json.loads(response["body"].read())
        text = body["content"][0]["text"].strip()

        # Parse the JSON array from response
        match = re.search(r"\[.*?\]", text, re.DOTALL)
        if match:
            skills = json.loads(match.group())
            # Deduplicate against base skills (case-insensitive)
            base_lower = {s.lower() for s in BASE_SKILLS}
            return [s for s in skills if isinstance(s, str) and s.lower() not in base_lower][:5]
        return []
    except Exception as e:
        print(f"    ⚠️  Skill extraction failed: {e}")
        return []


def customize_resume(job: dict, extra_skills: list[str]) -> str:
    """Create a customized resume PDF with additional skills. Returns the path to the new file.

    Opens the original resume, finds the Skills line, replaces it with an expanded
    skills list that includes the job-specific skills, and saves to resumes/ folder.
    """
    RESUMES_DIR.mkdir(parents=True, exist_ok=True)

    # Build safe filename from job details (empty strings need fallback too)
    company = re.sub(r"[^\w\s-]", "", job.get("company") or "unknown").strip().replace(" ", "_")[:30]
    title = re.sub(r"[^\w\s-]", "", job.get("title") or "unknown").strip().replace(" ", "_")[:30]
    # Build filename from candidate profile name
    from backend.core.shared_config import load_json, CANDIDATE_PROFILE
    profile = load_json(CANDIDATE_PROFILE, {})
    candidate_name = (profile.get("name") or "Candidate").replace(" ", "_")
    filename = f"{candidate_name}_{company}_{title}.pdf"
    output_path = RESUMES_DIR / filename

    # If already generated for this job, reuse it
    if output_path.exists():
        print(f"    📄 Reusing existing tailored resume: {filename}")
        return str(output_path)

    # Merge base skills with extra skills (no duplicates)
    all_skills = list(BASE_SKILLS)
    seen = {s.lower() for s in BASE_SKILLS}
    for skill in extra_skills:
        if skill.lower() not in seen:
            all_skills.append(skill)
            seen.add(skill.lower())

    new_skills_text = " · ".join(all_skills)

    # Open the original PDF and modify the Skills line
    doc = fitz.open(RESUME_PATH)

    for page in doc:
        # Search for the existing skills text block
        # The resume has: "Collaboration · Problem Solving · Conflict \nResolution · Microsoft Office Suite · SQL"
        # We need to find text blocks containing these skills
        blocks = page.get_text("dict")["blocks"]

        for block in blocks:
            if "lines" not in block:
                continue

            block_text = ""
            for line in block["lines"]:
                for span in line["spans"]:
                    block_text += span["text"]

            # Check if this block contains our skills section
            if "Collaboration" in block_text and "SQL" in block_text:
                block_rect = fitz.Rect(block["bbox"])
                first_span = block["lines"][0]["spans"][0]
                font_size = first_span["size"]
                c = first_span["color"]
                font_color = ((c >> 16) & 0xFF) / 255, ((c >> 8) & 0xFF) / 255, (c & 0xFF) / 255

                # Redact old skills text
                page.add_redact_annot(block_rect, fill=(1, 1, 1))
                page.apply_redactions()

                # Expand rect height to fit more skills (left column has room below)
                expanded_rect = fitz.Rect(
                    block_rect.x0, block_rect.y0,
                    block_rect.x1, block_rect.y1 + 40,
                )

                # Use the full Bitter-Regular font (embedded subset lacks glyphs for new text)
                bitter_font = Path(__file__).parent / "fonts" / "Bitter-Regular.ttf"

                if bitter_font.exists():
                    page.insert_font(fontname="Bitter", fontfile=str(bitter_font))
                    page.insert_textbox(
                        expanded_rect,
                        new_skills_text,
                        fontsize=font_size,
                        fontname="Bitter",
                        color=font_color,
                        align=fitz.TEXT_ALIGN_LEFT,
                    )
                else:
                    page.insert_textbox(
                        expanded_rect,
                        new_skills_text,
                        fontsize=font_size,
                        fontname="helv",
                        color=font_color,
                        align=fitz.TEXT_ALIGN_LEFT,
                    )
                break

    doc.save(str(output_path))
    doc.close()

    # Also save a metadata sidecar so we know what skills were added
    meta_path = output_path.with_suffix(".json")
    meta = {
        "job_url": job.get("url", ""),
        "job_title": job.get("title", ""),
        "company": job.get("company", ""),
        "base_skills": BASE_SKILLS,
        "added_skills": extra_skills,
        "all_skills": all_skills,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    meta_path.write_text(json.dumps(meta, indent=2))

    print(f"    📄 Created tailored resume: {filename} (+{len(extra_skills)} skills: {', '.join(extra_skills)})")
    return str(output_path)


async def apply_to_job(job: dict, profile: dict, qa: dict, applied_labels: list[str], easy_apply: bool, worker_id: int) -> str:
    """Apply to a single job with a tailored resume. Returns final status."""
    from apply_jobs import apply_to_job as _base_apply

    url = job["url"]
    title = job.get("title", "Unknown")
    company = job.get("company", "Unknown")

    # --- Step 1: Fetch job description ---
    print(f"  📋 [W{worker_id}] Fetching job description...")
    description = ""
    try:
        description = await fetch_job_description(job, worker_id)
        if description:
            print(f"  📋 [W{worker_id}] Got description ({len(description)} chars)")
    except Exception as e:
        print(f"  ⚠️  [W{worker_id}] Description fetch failed: {e}")

    # --- Step 2: Extract skills and customize resume ---
    resume_path = None  # None = use default in base apply
    try:
        if description:
            extra_skills = extract_skills_from_description(description, title)
            if extra_skills:
                resume_path = customize_resume(job, extra_skills)
                update_job(url, tailored_resume=resume_path, added_skills=extra_skills)
            else:
                print(f"  ℹ️  [W{worker_id}] No extra skills found, using base resume")
    except Exception as e:
        print(f"  ⚠️  [W{worker_id}] Resume customization failed: {e}, using base resume")

    # --- Step 3: Delegate to shared apply logic ---
    return await _base_apply(job, profile, qa, applied_labels, easy_apply, worker_id, resume_path_override=resume_path)


async def worker(name: str, worker_id: int, queue: asyncio.Queue, profile: dict, qa: dict, applied_labels: list, easy_apply: bool, stats: dict, cancel_flag: dict | None = None):
    """Worker that pulls jobs from queue and applies with tailored resumes."""
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
    """Main entry point — parse args, filter jobs, dispatch workers."""
    parser = argparse.ArgumentParser(description="Apply to collected jobs with tailored resumes")
    parser.add_argument("--workers", type=int, default=1, help="Number of concurrent workers")
    parser.add_argument("--limit", type=int, help="Max jobs to process")
    parser.add_argument("--easy-apply", dest="easy_apply", action="store_true", default=True)
    parser.add_argument("--no-easy-apply", dest="easy_apply", action="store_false")
    args = parser.parse_args()

    jobs = load_json(JOBS_FILE, {})
    profile = load_json(CANDIDATE_PROFILE, {})
    qa = load_json(QA_FILE, {})
    LOGS_DIR.mkdir(exist_ok=True)
    RESUMES_DIR.mkdir(exist_ok=True)

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
        f"{j.get('title', '')} at {j.get('company', '')}"
        for j in jobs.values() if j.get("status") == "applied"
    ]

    mode = "Easy Apply" if args.easy_apply else "Non-Easy Apply"
    print(f"🎯 Applying to {len(pending)} {mode} jobs with {args.workers} worker(s)")
    print(f"📄 Resumes will be saved to: {RESUMES_DIR}/\n")

    queue = asyncio.Queue()
    for job in pending:
        queue.put_nowait(job)

    stats = {}
    num_workers = min(args.workers, len(pending))

    # Background credential refresh every 14 min
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
    print(f"Tailored resumes saved in: {RESUMES_DIR}/")

    # Memory stats
    mem_stats = get_memory_store().get_stats()
    print(f"🧠 Agent memory: {mem_stats['total_memories']} memories across {mem_stats['unique_domains']} domains")


if __name__ == "__main__":
    asyncio.run(main())
