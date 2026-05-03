"""Shared config, utilities, and credential management."""
import asyncio
import json
import re
import subprocess
import sys
import threading
from pathlib import Path

import boto3
from filelock import FileLock
from browser_use.llm import ChatAWSBedrock

try:
    from core.config import get_data_dir
    from memory import MemoryStore
except ImportError:
    from backend.core.config import get_data_dir
    from backend.memory import MemoryStore

_SOURCE_DIR = Path(__file__).resolve().parent.parent.parent  # project root (or temp dir if frozen)

DATA_DIR = get_data_dir()

# When frozen (PyInstaller), BASE_DIR would be a temp dir — use DATA_DIR instead
BASE_DIR = DATA_DIR if getattr(sys, 'frozen', False) else _SOURCE_DIR

# Use OS data dir for settings/profile (written by UI), project root for jobs/logs
JOBS_FILE = DATA_DIR / "jobs.json"
JOBS_LOCK = DATA_DIR / "jobs.json.lock"
QA_FILE = DATA_DIR / "qa_repository.json"
CANDIDATE_PROFILE = DATA_DIR / "candidate_profile.json"
LOGS_DIR = BASE_DIR / "logs"
RESUMES_DIR = BASE_DIR / "resumes"

# Browser profile ALWAYS in OS data dir (must match backend/main.py login endpoint)
BROWSER_PROFILE_DIR = DATA_DIR / "browser_profile"

AWS_PROFILE = "default"
AWS_REGION = "us-west-2"
MODEL_ID = "us.anthropic.claude-sonnet-4-6"
ADA_CMD: tuple[str, ...] = ()  # Only needed for Amazon internal credential refresh

# Load settings from OS data dir (written by desktop app UI) if available
_settings_file = DATA_DIR / "settings.json"
_ui_settings = json.loads(_settings_file.read_text()) if _settings_file.exists() else {}
SENSITIVE_DATA = _ui_settings.get("sensitive_data", {"email": "", "password": ""})

# Fall back to profile email if sensitive_data email is blank
if not SENSITIVE_DATA.get("email", "").strip():
    _profile_file = DATA_DIR / "candidate_profile.json"
    if _profile_file.exists():
        _profile_data = json.loads(_profile_file.read_text())
        _profile_email = _profile_data.get("email", "").strip()
        if _profile_email:
            SENSITIVE_DATA["email"] = _profile_email

RESUME_PATH = _ui_settings.get("resume_path", "")
BLOCKED_DOMAINS = _ui_settings.get("blocked_domains", ["meeboss.com"])

_PRIVATE_IP_PREFIXES = ("127.", "10.", "192.168.", "172.16.", "172.17.", "172.18.",
                        "172.19.", "172.20.", "172.21.", "172.22.", "172.23.",
                        "172.24.", "172.25.", "172.26.", "172.27.", "172.28.",
                        "172.29.", "172.30.", "172.31.", "0.", "169.254.")

def validate_job_url(url: str) -> bool:
    """Reject URLs pointing to private/internal networks (SSRF prevention)."""
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if not host or not parsed.scheme.startswith("http"):
            return False
        if host in ("localhost", "0.0.0.0", "[::]", "[::1]"):
            return False
        if any(host.startswith(p) for p in _PRIVATE_IP_PREFIXES):
            return False
        return True
    except Exception:
        return False

# ── Singleton memory store ────────────────────────────────────────────────────
_memory_store: MemoryStore | None = None


def get_memory_store() -> MemoryStore:
    """Get or create the singleton memory store instance."""
    global _memory_store
    if _memory_store is None:
        _memory_store = MemoryStore()
    return _memory_store


def load_json(path: Path, default=None):
    if path.exists():
        return json.loads(path.read_text())
    return default if default is not None else []


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.replace(path)


def read_jobs() -> dict:
    """Read jobs.json with cross-process lock."""
    with FileLock(JOBS_LOCK):
        return load_json(JOBS_FILE, {})


def write_jobs(jobs: dict):
    """Write jobs.json with cross-process lock."""
    with FileLock(JOBS_LOCK):
        save_json(JOBS_FILE, jobs)


def update_job(url: str, **fields):
    """Atomically update a single job entry."""
    with FileLock(JOBS_LOCK):
        jobs = load_json(JOBS_FILE, {})
        if url in jobs:
            jobs[url].update(fields)
            save_json(JOBS_FILE, jobs)


_claim_lock = threading.Lock()


def claim_job(url: str) -> bool:
    """Atomically claim a pending job. Returns True if claimed, False if already taken.
    Uses both FileLock (cross-process) and threading lock (in-process workers)."""
    with _claim_lock:
        with FileLock(JOBS_LOCK):
            jobs = load_json(JOBS_FILE, {})
            if url in jobs and jobs[url].get("status") == "pending":
                jobs[url]["status"] = "in_progress"
                save_json(JOBS_FILE, jobs)
                return True
            return False


def refresh_credentials():
    """Run ada credentials update and return True on success."""
    if not ADA_CMD:
        # No credential refresh command configured — skip silently
        # Users should configure AWS credentials via the Settings UI or aws cli
        return True
    print("🔑 Refreshing AWS credentials...")
    try:
        subprocess.run(ADA_CMD, check=True, timeout=30)
        print("✅ Credentials refreshed")
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        print(f"❌ Credential refresh failed: {e}", file=sys.stderr)
        return False


async def credential_refresh_loop(interval_minutes: int = 14):
    """Background task that refreshes credentials on a timer. Cancels with parent."""
    while True:
        await asyncio.sleep(interval_minutes * 60)
        refresh_credentials()


def get_llm() -> ChatAWSBedrock:
    """Create a fresh LLM client with current credentials."""
    session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
    return ChatAWSBedrock(model=MODEL_ID, session=session)


def normalize_question(q: str) -> str:
    return re.sub(r"[^\w\s]", "", q.lower()).strip()


def build_memory_context(
    profile: dict,
    qa: dict,
    applied_labels: list[str] | None = None,
    job_url: str | None = None,
) -> str:
    """Build the system message context with candidate profile, Q&A bank, and per-website learnings."""
    parts = []
    parts.append(
        "CANDIDATE PROFILE:\n"
        f"Name: {profile['name']}\n"
        f"Email: {profile['email']}, Phone: {profile['phone']}\n"
        f"Location: {profile['address']['city']}, {profile['address']['state']} {profile['address']['zip']}\n"
        f"Work Authorization: {profile['work_authorization']}, Visa Sponsorship Needed: {profile['visa_sponsorship_needed']}\n"
        f"Willing to Relocate: {profile['willing_to_relocate']}, Preferred Work Mode: {profile['preferred_work_mode']}\n"
        f"Years of Experience: {profile['years_of_experience']}\n"
        f"Education: {profile['education']['degree']} from {profile['education']['school']} ({profile['education']['graduation']})\n"
        f"Current Role: {profile['current_role']}\n"
        f"Target Locations: {', '.join(profile['target_locations'])}\n"
        f"Languages: {', '.join(profile['languages'])}\n"
        f"Skills: {', '.join(profile['skills'])}\n"
        f"Salary: ${profile['salary_expectation']['min']:,}-${profile['salary_expectation']['max']:,}\n"
        f"Notes: {profile['notes']}"
    )

    if applied_labels:
        parts.append("Already applied — SKIP:\n" + "\n".join(f"- {j}" for j in applied_labels))

    # Try SQLite Q&A first, fall back to passed-in dict
    qa_for_prompt = qa
    try:
        store = get_memory_store()
        if store:
            db_qa = store.qa_get_all_for_prompt()
            if db_qa:
                qa_for_prompt = db_qa
    except Exception:
        pass
    if qa_for_prompt:
        qa_list = "\n".join(f'Q: {q}\nA: {a}' for q, a in qa_for_prompt.items() if a)
        if qa_list:
            parts.append(f"Pre-filled answers for application questions:\n{qa_list}")

    # ── Per-website memory injection ──────────────────────────────────────
    if job_url:
        store = get_memory_store()
        memories = store.get_domain_memories(job_url, limit=20)
        if memories:
            domain = store.extract_domain(job_url)
            mem_count = len(memories)
            print(f"    🧠 Injecting {mem_count} memories for {domain}")
            parts.append(store.format_for_prompt(memories))

    parts.append(
        "TRACKING INSTRUCTIONS:\n"
        "After each successful application: @@JOB_APPLIED: {\"title\": \"...\", \"company\": \"...\", \"location\": \"...\"}\n"
        "For each form question encountered: @@QUESTION: {\"question\": \"...\", \"answer\": \"...\", \"type\": \"text|dropdown|radio|checkbox\"}\n\n"
        "SELF-LEARNING — report observations about THIS WEBSITE's UI/flow as you navigate:\n"
        "@@LEARNING: {\"domain\": \"<website domain>\", \"category\": \"navigation|form_strategy|element_interaction|failure_recovery|site_structure|qa_pattern\", \"insight\": \"<specific actionable observation>\"}\n"
        "Examples of good learnings:\n"
        "- Navigation: 'Easy Apply opens a modal overlay, don't navigate away from the page'\n"
        "- Element interaction: 'The checkbox is inside a scrollable div, must scroll to find it'\n"
        "- Form strategy: 'This ATS splits the form into 4 steps: Personal → Resume → Questions → Review'\n"
        "Report at least 2-3 learnings per application run."
    )
    return "\n\n".join(parts)


def extract_from_history(result):
    """Extract applied jobs and questions from agent history."""
    jobs, questions, seen = [], {}, set()
    for item in result.history:
        if not item.model_output:
            continue
        memory = item.model_output.memory or ""
        for m in re.finditer(r"@@JOB_APPLIED:\s*(\{[^}]{1,2000}\})", memory):
            try:
                j = json.loads(m.group(1))
                jobs.append(f"{j.get('title','')} at {j.get('company','')} - {j.get('location','')}")
            except json.JSONDecodeError:
                pass
        for m in re.finditer(r"@@QUESTION:\s*(\{[^}]{1,2000}\})", memory):
            try:
                q = json.loads(m.group(1))
                qtext, ans = q.get("question", "").strip(), q.get("answer", "").strip()
                norm = normalize_question(qtext)
                if qtext and norm not in seen:
                    seen.add(norm)
                    questions[qtext] = ans
            except json.JSONDecodeError:
                pass
        # Fallback
        if not jobs and any(kw in memory.lower() for kw in ["application submitted", "successfully applied"]):
            for pat in [r"applied to (.+?) via", r"Application submitted for (.+?) via"]:
                match = re.search(pat, memory, re.IGNORECASE)
                if match:
                    jobs.append(match.group(1).strip())
                    break
    return list(dict.fromkeys(jobs)), questions
