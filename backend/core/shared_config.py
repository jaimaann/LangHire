"""Shared helpers for the agent engine: paths, job storage, URL safety, prompt context.

Nothing here reads settings at import time — every value is looked up when it
is used, so changes made in the UI apply to the next run without a restart.
"""
import ipaddress
import logging
import json
import os
import re
import socket
from pathlib import Path

try:
    from core.config import get_data_dir, load_settings, load_llm_settings
    from core import db
    from memory import MemoryStore
except ImportError:
    from backend.core.config import get_data_dir, load_settings, load_llm_settings
    from backend.core import db
    from backend.memory import MemoryStore

_SOURCE_DIR = Path(__file__).resolve().parent.parent.parent  # project root (or temp dir if frozen)


# ── Paths (resolved on every call) ──────────────────────────────────────────

def data_dir() -> Path:
    return get_data_dir()


def logs_dir() -> Path:
    d = get_data_dir() / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def resumes_dir() -> Path:
    d = get_data_dir() / "resumes"
    d.mkdir(parents=True, exist_ok=True)
    return d


def browser_profile_dir() -> Path:
    return get_data_dir() / "browser_profile"


_LEGACY_PATHS = {
    "DATA_DIR": lambda: get_data_dir(),
    "BASE_DIR": lambda: get_data_dir(),
    "JOBS_FILE": lambda: get_data_dir() / "jobs.json",
    "QA_FILE": lambda: get_data_dir() / "qa_repository.json",
    "CANDIDATE_PROFILE": lambda: get_data_dir() / "candidate_profile.json",
    "LOGS_DIR": logs_dir,
    "RESUMES_DIR": resumes_dir,
    "BROWSER_PROFILE_DIR": browser_profile_dir,
}


def __getattr__(name):  # PEP 562: old constant names, resolved lazily
    if name in _LEGACY_PATHS:
        return _LEGACY_PATHS[name]()
    raise AttributeError(name)


# ── Settings accessors ──────────────────────────────────────────────────────

def sensitive_data() -> dict:
    """Login credentials for job sites. The form email falls back to the profile email."""
    sd = dict(load_settings().get("sensitive_data") or {})
    if not (sd.get("email") or "").strip():
        try:
            from core.config import load_profile
        except ImportError:
            from backend.core.config import load_profile
        sd["email"] = (load_profile().get("email") or "").strip()
    return {"email": sd.get("email", ""), "password": sd.get("password", "")}


def resume_path() -> str:
    return load_settings().get("resume_path", "") or ""


def blocked_domains() -> list[str]:
    return list(load_settings().get("blocked_domains") or [])


def is_blocked_domain(url: str, blocked: list[str] | None = None) -> bool:
    """True when the URL's host is a blocked domain or a subdomain of one."""
    from urllib.parse import urlparse
    host = (urlparse(url).hostname or "").lower().rstrip(".")
    for d in blocked if blocked is not None else blocked_domains():
        d = d.lower().strip().lstrip("*.").rstrip(".")
        if d and (host == d or host.endswith("." + d)):
            return True
    return False


def get_llm():
    """A fresh LLM client from the settings the user saved in the UI."""
    try:
        from core.llm_factory import create_llm
    except ImportError:
        from backend.core.llm_factory import create_llm
    return create_llm(load_llm_settings())


# ── URL safety ──────────────────────────────────────────────────────────────

def _is_public_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip.split("%", 1)[0])
    except ValueError:
        return False
    if getattr(addr, "ipv4_mapped", None):
        addr = addr.ipv4_mapped
    return not (
        addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_multicast
        or addr.is_reserved or addr.is_unspecified
    )


def validate_job_url(url: str, resolve: bool = True) -> bool:
    """Reject URLs that point at this machine or a private network (SSRF guard).

    Literal IPs in any notation (IPv6, decimal, hex) are checked with
    ``ipaddress``; hostnames are resolved and every address must be public.
    ``LANGHIRE_ALLOW_LOCAL_URLS=1`` disables the check for local test harnesses.
    """
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower().rstrip(".")
        if not host or parsed.scheme not in ("http", "https"):
            return False
        if os.environ.get("LANGHIRE_ALLOW_LOCAL_URLS") == "1":
            return True
        if host == "localhost" or host.endswith(".localhost") or host.endswith(".local"):
            return False
        # Literal IP (inet_aton also accepts decimal/hex/short forms like 2130706433)
        literal = None
        try:
            literal = str(ipaddress.ip_address(host))
        except ValueError:
            try:
                literal = socket.inet_ntoa(socket.inet_aton(host)) if re.fullmatch(r"[0-9a-fx.]+", host) else None
            except OSError:
                literal = None
        if literal is not None:
            return _is_public_ip(literal)
        if not resolve:
            return True
        try:
            infos = socket.getaddrinfo(host, None)
        except OSError:
            return True  # can't resolve now (offline); the browser will fail on its own
        return all(_is_public_ip(info[4][0]) for info in infos)
    except Exception:
        return False


# ── Singleton memory store ──────────────────────────────────────────────────
_memory_store: MemoryStore | None = None


def get_memory_store() -> MemoryStore:
    """Get or create the singleton memory store instance."""
    global _memory_store
    if _memory_store is None or Path(_memory_store.db_path).parent != get_data_dir():
        _memory_store = MemoryStore()
    return _memory_store


def load_json(path: Path, default=None):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default if default is not None else []


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


# ── Jobs (SQLite-backed; see core/db.py) ────────────────────────────────────

def read_jobs() -> dict:
    return db.read_jobs()


def write_jobs(jobs: dict):
    db.write_jobs(jobs)


def update_job(url: str, **fields):
    db.update_job(url, **fields)


def claim_job(url: str) -> bool:
    """Atomically claim a pending job. Returns True if claimed."""
    return db.claim_job(url)


def normalize_question(q: str) -> str:
    return re.sub(r"[^\w\s]", "", q.lower()).strip()


def build_memory_context(
    profile: dict,
    qa: dict,
    applied_labels: list[str] | None = None,
    job_url: str | None = None,
    include_tracking: bool = True,
) -> str:
    """Build the system message context with candidate profile, Q&A bank, and per-website learnings."""
    parts = []

    # Salary formatting (country-aware)
    sal = profile.get('salary_expectation', {})
    sal_currency = sal.get('currency', 'USD') or 'USD'
    sal_min = sal.get('min', 0) or 0
    sal_max = sal.get('max', 0) or 0
    sal_period = sal.get('period', 'annual')
    salary_str = f"{sal_currency} {sal_min:,}-{sal_max:,} ({sal_period})" if sal_min else "Not specified"

    # Country-aware date format
    date_format = profile.get('date_format', '') or 'MM/DD/YYYY'

    profile_lines = [
        "CANDIDATE PROFILE:",
        f"Name: {profile['name']}",
        f"Email: {profile['email']}, Phone: {profile.get('phone_country_code', '')}{profile['phone']}",
        f"Location: {profile['address']['city']}, {profile['address']['state']} {profile['address']['zip']} {profile['address'].get('country', '')}".strip(),
        f"Work Authorization: {profile['work_authorization']}, Visa Sponsorship Needed: {profile['visa_sponsorship_needed']}",
        f"Willing to Relocate: {profile['willing_to_relocate']}, Preferred Work Mode: {profile['preferred_work_mode']}",
        f"Years of Experience: {profile['years_of_experience']}",
        f"Education: {profile['education']['degree']} from {profile['education']['school']} ({profile['education']['graduation']})",
        f"Current Role: {profile['current_role']}",
        f"Target Locations: {', '.join(profile['target_locations'])}",
        f"Languages: {', '.join(profile['languages'])}",
        f"Skills: {', '.join(profile['skills'])}",
        f"Salary: {salary_str}",
    ]
    if profile.get('notice_period'):
        profile_lines.append(f"Notice Period: {profile['notice_period']}")
    if profile.get('nationality'):
        profile_lines.append(f"Nationality: {profile['nationality']}")
    if profile.get('notes'):
        profile_lines.append(f"Notes: {profile['notes']}")

    parts.append("\n".join(profile_lines))

    # Country-specific instructions for the agent
    country_instructions = []
    country_instructions.append(f"DATE FORMAT: When filling date fields, use {date_format} format.")
    if profile.get('notice_period'):
        country_instructions.append(f"NOTICE PERIOD: If asked about notice period or availability, answer: {profile['notice_period']}")
    if profile.get('nationality'):
        country_instructions.append(f"NATIONALITY: If asked about nationality, answer: {profile['nationality']}")
    if profile.get('cover_letter'):
        country_instructions.append(f"COVER LETTER: If a cover letter is requested, use:\n{profile['cover_letter']}")
    if country_instructions:
        parts.append("COUNTRY-SPECIFIC INSTRUCTIONS:\n" + "\n".join(country_instructions))

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
            logging.getLogger("engine").info(f"Injecting {mem_count} memories for {domain}")
            parts.append(store.format_for_prompt(memories))

    if include_tracking:
        parts.append(_TRACKING_INSTRUCTIONS)
    return "\n\n".join(parts)


_TRACKING_INSTRUCTIONS = (
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
