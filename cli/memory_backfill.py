#!/usr/bin/env python3
"""
Backfill agent memory from historical conversation logs.

Scans all logs/apply_* directories, extracts conversation summaries,
and uses Claude to generate per-website procedural learnings that are
stored in memory_store.db.

Usage:
  uv run python memory_backfill.py                   # Process all logs, generate memories
  uv run python memory_backfill.py --dry-run         # Parse logs but don't call LLM
  uv run python memory_backfill.py --limit 5         # Only process first 5 log dirs
  uv run python memory_backfill.py --verbose         # Show detailed progress
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import boto3

from backend.memory import MemoryStore, CATEGORIES
from backend.memory.extractors import store_learnings
from backend.core.shared_config import AWS_PROFILE, AWS_REGION, MODEL_ID

LOGS_DIR = Path(__file__).resolve().parent.parent / "logs"


# ── Log parsing ──────────────────────────────────────────────────────────────

def get_sorted_log_files(log_dir: Path) -> list[Path]:
    """Get conversation files sorted by step number."""
    files = list(log_dir.glob("conversation_*_*.txt"))
    def step_num(f):
        match = re.search(r"_(\d+)\.txt$", f.name)
        return int(match.group(1)) if match else 0
    return sorted(files, key=step_num)


def extract_job_url(first_file: Path) -> str:
    """Extract the job URL from the first conversation file's user_request."""
    text = first_file.read_text(errors="replace")
    # Look for the URL in the user request
    match = re.search(r"Go to (https?://[^\s]+)", text)
    if match:
        return match.group(1)
    # Fallback: look for LinkedIn job URL
    match = re.search(r"(https?://(?:www\.)?linkedin\.com/jobs/view/\d+/?)", text)
    if match:
        return match.group(1)
    return ""


def extract_job_title_company(first_file: Path) -> tuple[str, str]:
    """Extract job title and company from the first file or directory name."""
    text = first_file.read_text(errors="replace")
    # Look for @@JOB_APPLIED marker in the task text
    match = re.search(r'"title":\s*"([^"]+)".*?"company":\s*"([^"]+)"', text)
    if match:
        return match.group(1), match.group(2)
    # Fallback: parse from directory name (apply_Company_Title pattern)
    dirname = first_file.parent.name
    if dirname.startswith("apply_"):
        parts = dirname[6:]  # strip "apply_"
        # First word(s) before underscore boundary are company, rest is title
        return parts.replace("_", " "), ""
    return "", ""


def parse_agent_json(text: str) -> dict | None:
    """Extract the JSON response from a conversation file."""
    # The agent's JSON output is at the end of each file
    # Find the last JSON block that has "thinking", "memory", "action" etc.
    # Strategy: find all JSON blocks and take the last valid one
    json_blocks = []
    brace_depth = 0
    start = -1

    for i, ch in enumerate(text):
        if ch == '{':
            if brace_depth == 0:
                start = i
            brace_depth += 1
        elif ch == '}':
            brace_depth -= 1
            if brace_depth == 0 and start >= 0:
                json_blocks.append(text[start:i+1])
                start = -1

    # Try blocks from last to first, looking for the agent output
    for block in reversed(json_blocks):
        try:
            data = json.loads(block)
            if isinstance(data, dict) and ("thinking" in data or "memory" in data or "action" in data):
                return data
        except json.JSONDecodeError:
            continue
    return None


def extract_browser_urls(text: str) -> list[str]:
    """Extract all URLs the browser visited from browser_state sections."""
    urls = set()
    for match in re.finditer(r"Current (?:URL|tab):\s*(https?://[^\s<]+)", text):
        urls.add(match.group(1))
    # Also get URLs from Tab lines
    for match in re.finditer(r"Tab \w+:\s*(https?://[^\s]+)\s*-", text):
        urls.add(match.group(1))
    return list(urls)


def parse_log_directory(log_dir: Path, verbose: bool = False) -> dict:
    """Parse an entire log directory into a structured summary.

    Returns a dict with:
      - job_url, job_title, company
      - success: bool
      - domains_visited: list of domains
      - steps: list of condensed step summaries
      - final_text: the done action's text (if any)
    """
    files = get_sorted_log_files(log_dir)
    if not files:
        return {}

    first_file = files[0]
    last_file = files[-1]

    job_url = extract_job_url(first_file)
    job_title, company = extract_job_title_company(first_file)

    # Parse the last file for success/failure and done text
    last_text = last_file.read_text(errors="replace")
    last_json = parse_agent_json(last_text)

    success = False
    final_text = ""
    if last_json:
        actions = last_json.get("action", [])
        for action in actions:
            if isinstance(action, dict) and "done" in action:
                done_data = action["done"]
                success = done_data.get("success", False)
                final_text = done_data.get("text", "")
                break

    # Collect step summaries from all files
    steps = []
    all_urls = set()

    # Sample files to keep token count manageable: first, last, and every Nth
    sample_indices = set()
    sample_indices.add(0)  # first
    sample_indices.add(len(files) - 1)  # last
    # Every 3rd file for middle
    for i in range(0, len(files), max(1, len(files) // 10)):
        sample_indices.add(i)

    for i in sorted(sample_indices):
        if i >= len(files):
            continue
        f = files[i]
        try:
            text = f.read_text(errors="replace")
        except Exception:
            continue

        # Extract browser URLs
        for url in extract_browser_urls(text):
            all_urls.add(url)

        # Parse agent JSON
        agent_data = parse_agent_json(text)
        if agent_data:
            step_summary = {
                "step": i + 1,
                "eval": (agent_data.get("evaluation_previous_goal") or "")[:200],
                "memory": (agent_data.get("memory") or "")[:300],
                "next_goal": (agent_data.get("next_goal") or "")[:200],
            }
            # Include action types
            actions = agent_data.get("action", [])
            action_types = []
            for a in actions:
                if isinstance(a, dict):
                    action_types.extend(a.keys())
            step_summary["actions"] = action_types
            steps.append(step_summary)

    # Extract domains from all URLs
    domains = set()
    for url in all_urls:
        try:
            from urllib.parse import urlparse
            host = urlparse(url).hostname or ""
            if host.startswith("www."):
                host = host[4:]
            if host and host != "about:blank":
                domains.add(host)
        except Exception:
            pass

    return {
        "dir_name": log_dir.name,
        "job_url": job_url,
        "job_title": job_title,
        "company": company,
        "success": success,
        "total_steps": len(files),
        "domains_visited": sorted(domains),
        "steps": steps,
        "final_text": final_text[:1500],  # truncate to save tokens
    }


# ── LLM-based memory extraction ─────────────────────────────────────────────

def build_batch_prompt(runs: list[dict], primary_domain: str) -> str:
    """Build a prompt for Claude to extract learnings from multiple runs on the same domain."""
    categories_desc = "\n".join(f"- {k}: {v}" for k, v in CATEGORIES.items())

    runs_text = []
    for i, run in enumerate(runs):
        status = "✅ SUCCESSFUL" if run["success"] else "❌ FAILED"
        steps_text = "\n".join(
            f"  Step {s['step']}: eval={s['eval'][:100]} | memo={s['memory'][:150]} | goal={s['next_goal'][:100]} | actions={s['actions']}"
            for s in run["steps"]
        )
        run_block = (
            f"--- Run {i+1}: {run['job_title']} at {run['company']} [{status}] ({run['total_steps']} steps) ---\n"
            f"Job URL: {run['job_url']}\n"
            f"Domains visited: {', '.join(run['domains_visited'])}\n"
            f"Steps:\n{steps_text}\n"
        )
        if run["final_text"]:
            run_block += f"Final output: {run['final_text'][:500]}\n"
        runs_text.append(run_block)

    all_runs = "\n\n".join(runs_text)

    prompt = f"""Analyze these {len(runs)} job application attempts that involved the domain "{primary_domain}".

{all_runs}

MEMORY CATEGORIES:
{categories_desc}

Extract 5-15 SPECIFIC, ACTIONABLE procedural learnings that would help a future AI agent apply to jobs on "{primary_domain}" (and related ATS platforms visited during these runs).

Focus on:
- Navigation patterns: How to get to the application form, what buttons to click, page flow
- UI element interactions: Checkboxes, dropdowns, modals, scrollable areas, shadow DOM elements
- Form structure: How many steps, what each step contains, multi-page flow
- Common pitfalls: What went wrong, what tricky interactions were needed
- ATS-specific patterns: If the application redirected to an external ATS (like ADP, Greenhouse, etc.), include learnings about that ATS
- OTP/verification: If email verification was needed, how to handle it

Rules:
- Each learning must be 1-2 sentences, specific and actionable
- Include the WEBSITE DOMAIN the learning applies to (could be the ATS domain, not just the original job board)
- Do NOT include generic advice — only site-specific observations from the actual run data
- If a run involved multiple domains (e.g. LinkedIn → ADP), generate learnings for EACH relevant domain

Return a JSON array of objects:
[
  {{"domain": "linkedin.com", "category": "navigation", "content": "..."}},
  {{"domain": "myjobs.adp.com", "category": "form_strategy", "content": "..."}},
  ...
]

Return ONLY the JSON array."""

    return prompt


def extract_learnings_from_logs(
    runs: list[dict],
    primary_domain: str,
    verbose: bool = False,
) -> list[dict]:
    """Call Claude to extract learnings from a batch of log runs."""
    prompt = build_batch_prompt(runs, primary_domain)

    if verbose:
        print(f"    📝 Prompt length: {len(prompt)} chars")

    try:
        session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
        bedrock = session.client("bedrock-runtime")

        response = bedrock.invoke_model(
            modelId=MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 3000,
                "temperature": 0.3,
                "messages": [{"role": "user", "content": prompt}],
            }),
        )

        body = json.loads(response["body"].read())
        text = body["content"][0]["text"].strip()

        # Parse JSON array
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            learnings = json.loads(match.group())
            return [
                {
                    "domain": l.get("domain", primary_domain),
                    "category": l.get("category", "form_strategy"),
                    "content": l.get("content", ""),
                }
                for l in learnings
                if isinstance(l, dict) and l.get("content", "").strip()
            ]
    except Exception as e:
        print(f"    ❌ LLM call failed: {e}")

    return []


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Backfill agent memory from historical logs")
    parser.add_argument("--dry-run", action="store_true", help="Parse logs but don't call LLM")
    parser.add_argument("--limit", type=int, help="Max log directories to process")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed progress")
    args = parser.parse_args()

    # Find all apply_* log directories
    log_dirs = sorted([
        d for d in LOGS_DIR.iterdir()
        if d.is_dir() and d.name.startswith("apply_")
    ])

    if args.limit:
        log_dirs = log_dirs[:args.limit]

    if not log_dirs:
        print("No apply_* log directories found in logs/")
        return

    print(f"📂 Found {len(log_dirs)} application log directories\n")

    # Phase 1: Parse all logs
    all_runs = []
    for i, log_dir in enumerate(log_dirs):
        if args.verbose:
            print(f"  [{i+1}/{len(log_dirs)}] Parsing {log_dir.name}...")
        run = parse_log_directory(log_dir, verbose=args.verbose)
        if run and run.get("steps"):
            all_runs.append(run)
            if args.verbose:
                status = "✅" if run["success"] else "❌"
                print(f"    {status} {run['job_title']} at {run['company']} ({run['total_steps']} steps, {len(run['domains_visited'])} domains)")

    print(f"\n📊 Parsed {len(all_runs)} valid runs out of {len(log_dirs)} directories")
    success_count = sum(1 for r in all_runs if r["success"])
    fail_count = len(all_runs) - success_count
    print(f"   ✅ {success_count} successful, ❌ {fail_count} failed")

    # Group runs by primary domain for batch LLM calls
    domain_groups: dict[str, list[dict]] = {}
    for run in all_runs:
        # Primary domain is the first non-linkedin domain, or linkedin itself
        primary = "linkedin.com"
        for d in run["domains_visited"]:
            if "linkedin.com" not in d:
                primary = d
                break
        domain_groups.setdefault(primary, []).append(run)

    print(f"\n🌐 Grouped into {len(domain_groups)} domain batches:")
    for domain, runs in sorted(domain_groups.items(), key=lambda x: -len(x[1])):
        print(f"   {domain}: {len(runs)} runs")

    if args.dry_run:
        print("\n🔒 Dry run — skipping LLM calls and memory storage.")
        print("\nSample parsed run:")
        if all_runs:
            r = all_runs[0]
            print(json.dumps({
                "dir": r["dir_name"],
                "job_url": r["job_url"],
                "title": r["job_title"],
                "company": r["company"],
                "success": r["success"],
                "steps_count": len(r["steps"]),
                "domains": r["domains_visited"],
                "sample_steps": r["steps"][:3],
            }, indent=2))
        return

    # Phase 2: Extract learnings via LLM and store
    store = MemoryStore()
    total_new = 0
    total_reinforced = 0

    from config import refresh_credentials
    refresh_credentials()

    for domain, runs in domain_groups.items():
        print(f"\n🧠 Extracting learnings for {domain} ({len(runs)} runs)...")

        # Batch in groups of 5 to keep prompt size manageable
        for batch_start in range(0, len(runs), 5):
            batch = runs[batch_start:batch_start + 5]
            learnings = extract_learnings_from_logs(batch, domain, verbose=args.verbose)

            if learnings:
                for learning in learnings:
                    is_new = store.add(
                        content=learning["content"],
                        website_domain=learning.get("domain", domain),
                        category=learning.get("category", "form_strategy"),
                        success=True,  # Backfilled learnings are treated as trusted
                        confidence=0.75,  # Slightly lower confidence than live extraction
                        job_url=batch[0].get("job_url", ""),
                    )
                    if is_new:
                        total_new += 1
                    else:
                        total_reinforced += 1

                print(f"    ✅ Extracted {len(learnings)} learnings from batch of {len(batch)} runs")
            else:
                print(f"    ⚠️  No learnings extracted from batch")

    # Summary
    print(f"\n{'='*60}")
    print(f"📊 Backfill Results")
    print(f"{'='*60}")
    print(f"  Logs processed:        {len(all_runs)}")
    print(f"  New memories stored:   {total_new}")
    print(f"  Existing reinforced:   {total_reinforced}")

    stats = store.get_stats()
    print(f"\n🧠 Memory store now has:")
    print(f"  Total memories:  {stats['total_memories']}")
    print(f"  Unique domains:  {stats['unique_domains']}")
    if stats["by_category"]:
        print(f"  By category:")
        for cat, count in sorted(stats["by_category"].items(), key=lambda x: -x[1]):
            print(f"    {cat}: {count}")


if __name__ == "__main__":
    main()
