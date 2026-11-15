"""Unit tests for backend/core/shared_config.py.

Focuses on the pure / easily-isolated helpers: SSRF URL validation, question
normalisation, JSON load/save, jobs CRUD with file locking, credential refresh
behaviour, the memory-store singleton, the agent-history extractor, and the
memory-context builder. External boundaries (subprocess, MemoryStore) are
mocked; all file I/O lands in tmp dirs via the ``data_dir`` fixture.
"""
import json
import types

import pytest

from core import shared_config as sc


# ── validate_job_url ─────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "url",
    [
        "https://jobs.example.com/apply",
        "http://careers.acme.io",
        "https://www.linkedin.com/jobs/view/123",
    ],
)
def test_validate_job_url_allows_public_http(url):
    """Public http(s) URLs are accepted."""
    assert sc.validate_job_url(url) is True


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/x",
        "http://127.0.0.1/x",
        "http://10.0.0.5/x",
        "http://192.168.1.1/x",
        "http://172.16.0.1/x",
        "http://169.254.1.1/x",
        "http://0.0.0.0/x",
        "ftp://example.com/x",  # non-http scheme
        "not a url",
        "",
        "https://",  # no host
    ],
)
def test_validate_job_url_rejects_private_or_invalid(url):
    """Private/internal hosts, non-http schemes, and garbage are rejected."""
    assert sc.validate_job_url(url) is False


@pytest.mark.parametrize("url", [
    "https://[::1]/x",                 # IPv6 loopback (was a known gap)
    "http://[fd00::1]/x",              # IPv6 unique-local
    "http://[::ffff:127.0.0.1]/x",     # IPv4-mapped loopback
    "http://2130706433/x",             # 127.0.0.1 in decimal
    "http://0x7f.0.0.1/x",             # hex octet
    "http://foo.localhost/x",
])
def test_validate_job_url_rejects_ip_tricks(url):
    assert sc.validate_job_url(url, resolve=False) is False


def test_validate_job_url_rejects_hostname_resolving_to_private(monkeypatch):
    monkeypatch.setattr(sc.socket, "getaddrinfo", lambda host, port: [(None, None, None, None, ("10.0.0.5", 0))])
    assert sc.validate_job_url("https://intranet.example.com/job") is False


def test_validate_job_url_local_override(monkeypatch):
    monkeypatch.setenv("LANGHIRE_ALLOW_LOCAL_URLS", "1")
    assert sc.validate_job_url("http://127.0.0.1:8000/job") is True


@pytest.mark.parametrize("url, blocked, expected", [
    ("https://jobs.meeboss.com/x", ["meeboss.com"], True),
    ("https://meeboss.com/x", ["meeboss.com"], True),
    ("https://notmeeboss.com/x", ["meeboss.com"], False),   # substring match used to block this
    ("https://example.com/?ref=meeboss.com", ["meeboss.com"], False),
])
def test_is_blocked_domain(url, blocked, expected):
    assert sc.is_blocked_domain(url, blocked) is expected


# ── normalize_question ───────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Hello, World!", "hello world"),
        ("  What's your name?  ", "whats your name"),
        ("Years   of   experience???", "years   of   experience"),
        ("UPPER", "upper"),
        ("", ""),
    ],
)
def test_normalize_question(raw, expected):
    """Punctuation is stripped, case lowered, and edges trimmed."""
    assert sc.normalize_question(raw) == expected


# ── load_json / save_json ────────────────────────────────────────────────────

def test_load_json_missing_default_list(tmp_path):
    """Missing file with no default returns an empty list (not dict)."""
    assert sc.load_json(tmp_path / "x.json") == []


def test_load_json_missing_explicit_default(tmp_path):
    """An explicit default is returned when the file is absent."""
    assert sc.load_json(tmp_path / "x.json", {"a": 1}) == {"a": 1}


def test_save_then_load_json_roundtrip(tmp_path):
    """Saved JSON is read back verbatim and no temp file lingers."""
    p = tmp_path / "nested" / "data.json"
    sc.save_json(p, {"k": [1, 2, 3]})
    assert sc.load_json(p) == {"k": [1, 2, 3]}
    assert not p.with_suffix(".tmp").exists()


# ── jobs CRUD (SQLite-backed) ────────────────────────────────────────────────

@pytest.fixture
def jobs_paths(data_dir):
    return data_dir


def test_read_jobs_empty(jobs_paths):
    assert sc.read_jobs() == {}


def test_write_then_read_jobs(jobs_paths):
    sc.write_jobs({"u1": {"status": "pending", "title": "Eng"}})
    job = sc.read_jobs()["u1"]
    assert job["status"] == "pending" and job["title"] == "Eng" and job["url"] == "u1"


def test_write_jobs_replaces_set(jobs_paths):
    sc.write_jobs({"u1": {"status": "pending"}, "u2": {"status": "pending"}})
    sc.write_jobs({"u2": {"status": "applied"}})
    assert list(sc.read_jobs()) == ["u2"]


def test_update_job_existing_keeps_extra_fields(jobs_paths):
    sc.write_jobs({"u1": {"status": "pending", "title": "Eng"}})
    sc.update_job("u1", status="applied", company="Acme", tailored_resume_path="/r.pdf")
    job = sc.read_jobs()["u1"]
    assert (job["status"], job["title"], job["company"], job["tailored_resume_path"]) == ("applied", "Eng", "Acme", "/r.pdf")


def test_update_job_missing_is_noop(jobs_paths):
    sc.write_jobs({"u1": {"status": "pending"}})
    sc.update_job("ghost", status="done")
    assert list(sc.read_jobs()) == ["u1"]


def test_claim_job_success(jobs_paths):
    sc.write_jobs({"u1": {"status": "pending"}})
    assert sc.claim_job("u1") is True
    assert sc.read_jobs()["u1"]["status"] == "in_progress"


def test_claim_job_already_taken(jobs_paths):
    sc.write_jobs({"u1": {"status": "in_progress"}})
    assert sc.claim_job("u1") is False


def test_claim_job_unknown(jobs_paths):
    assert sc.claim_job("nope") is False


def test_legacy_jobs_json_is_imported(data_dir):
    import json as _json
    from core import db
    db.close_all()
    (data_dir / "jobs.json").write_text(_json.dumps({"https://a.co/j": {"title": "T", "status": "applied"}}),
                                        encoding="utf-8")
    jobs = sc.read_jobs()
    assert jobs["https://a.co/j"]["status"] == "applied"
    assert (data_dir / "jobs.json.migrated").exists() and not (data_dir / "jobs.json").exists()


# ── get_memory_store singleton ───────────────────────────────────────────────

def test_get_memory_store_is_singleton(data_dir):
    sc._memory_store = None
    first = sc.get_memory_store()
    assert first is sc.get_memory_store()
    assert str(first.db_path).startswith(str(data_dir))


# ── extract_from_history ─────────────────────────────────────────────────────

def _history_item(memory_text):
    """Build a fake agent-history item exposing model_output.memory."""
    model_output = types.SimpleNamespace(memory=memory_text)
    return types.SimpleNamespace(model_output=model_output)


def _result(items):
    return types.SimpleNamespace(history=items)


def test_extract_from_history_jobs_and_questions():
    """Tagged JOB_APPLIED and QUESTION markers are parsed out."""
    mem = (
        '@@JOB_APPLIED: {"title": "Engineer", "company": "Acme", "location": "NYC"}\n'
        '@@QUESTION: {"question": "Visa?", "answer": "No", "type": "radio"}'
    )
    jobs, questions = sc.extract_from_history(_result([_history_item(mem)]))
    assert jobs == ["Engineer at Acme - NYC"]
    assert questions == {"Visa?": "No"}


def test_extract_from_history_dedupes_questions():
    """Questions that normalise identically are deduplicated."""
    mem = (
        '@@QUESTION: {"question": "Your Name?", "answer": "A"}\n'
        '@@QUESTION: {"question": "your name", "answer": "B"}'
    )
    _, questions = sc.extract_from_history(_result([_history_item(mem)]))
    assert questions == {"Your Name?": "A"}


def test_extract_from_history_skips_empty_and_bad_json():
    """Items with no output and malformed JSON are ignored gracefully."""
    items = [
        types.SimpleNamespace(model_output=None),
        _history_item('@@JOB_APPLIED: {bad json}'),
        _history_item('no markers here'),
    ]
    jobs, questions = sc.extract_from_history(_result(items))
    assert jobs == []
    assert questions == {}


def test_extract_from_history_fallback_phrase():
    """Free-text 'applied to X via' is captured when no JSON marker exists."""
    mem = "Successfully applied to Senior Dev via the company site."
    jobs, _ = sc.extract_from_history(_result([_history_item(mem)]))
    assert jobs == ["Senior Dev"]


def test_extract_from_history_deduplicates_jobs():
    """Duplicate job strings collapse to one (order preserved)."""
    mem = (
        '@@JOB_APPLIED: {"title": "X", "company": "Y", "location": "Z"}\n'
        '@@JOB_APPLIED: {"title": "X", "company": "Y", "location": "Z"}'
    )
    jobs, _ = sc.extract_from_history(_result([_history_item(mem)]))
    assert jobs == ["X at Y - Z"]


# ── build_memory_context ─────────────────────────────────────────────────────

@pytest.fixture
def base_profile():
    """A minimal-but-complete profile satisfying build_memory_context."""
    return {
        "name": "Ada Lovelace",
        "email": "ada@example.com",
        "phone": "5551234",
        "phone_country_code": "+1",
        "address": {"city": "London", "state": "", "zip": "", "country": "UK"},
        "work_authorization": "Citizen",
        "visa_sponsorship_needed": False,
        "willing_to_relocate": True,
        "preferred_work_mode": "remote",
        "years_of_experience": 5,
        "education": {"degree": "BSc", "school": "Cambridge", "graduation": "1850"},
        "current_role": "Mathematician",
        "target_locations": ["London", "Remote"],
        "languages": ["English"],
        "skills": ["Python", "Math"],
        "salary_expectation": {"min": 80000, "max": 120000, "currency": "GBP", "period": "annual"},
        "notice_period": "1 month",
        "nationality": "British",
        "cover_letter": "Dear Hiring Manager",
        "notes": "Pioneer",
        "date_format": "DD/MM/YYYY",
    }


@pytest.fixture
def no_op_store(monkeypatch):
    """Stub the memory store so build_memory_context skips DB/website memory."""
    class FakeStore:
        def qa_get_all_for_prompt(self):
            return {}

        def get_domain_memories(self, url, limit=20):
            return []

        def extract_domain(self, url):
            return "example.com"

        def format_for_prompt(self, memories):
            return "MEM"

    monkeypatch.setattr(sc, "get_memory_store", lambda: FakeStore())
    return FakeStore


def test_build_memory_context_basic(base_profile, no_op_store):
    """The context includes profile, salary, country instructions, and tracking."""
    ctx = sc.build_memory_context(base_profile, qa={})
    assert "CANDIDATE PROFILE:" in ctx
    assert "Name: Ada Lovelace" in ctx
    assert "GBP 80,000-120,000 (annual)" in ctx
    assert "DATE FORMAT: When filling date fields, use DD/MM/YYYY" in ctx
    assert "NOTICE PERIOD: If asked about notice period" in ctx
    assert "NATIONALITY:" in ctx
    assert "COVER LETTER:" in ctx
    assert "TRACKING INSTRUCTIONS:" in ctx


def test_build_memory_context_includes_qa(base_profile, no_op_store):
    """A passed-in Q&A dict (with answers) is rendered into the prompt."""
    ctx = sc.build_memory_context(base_profile, qa={"Q1": "A1", "blank": ""})
    assert "Q: Q1\nA: A1" in ctx
    assert "blank" not in ctx  # empty answers are filtered out


def test_build_memory_context_applied_labels(base_profile, no_op_store):
    """applied_labels produce a SKIP section."""
    ctx = sc.build_memory_context(base_profile, qa={}, applied_labels=["Job A", "Job B"])
    assert "Already applied — SKIP:" in ctx
    assert "- Job A" in ctx


def test_build_memory_context_no_salary(base_profile, no_op_store):
    """A zero salary minimum renders 'Not specified'."""
    base_profile["salary_expectation"]["min"] = 0
    ctx = sc.build_memory_context(base_profile, qa={})
    assert "Salary: Not specified" in ctx


def test_build_memory_context_default_date_format(base_profile, no_op_store):
    """A blank date_format falls back to MM/DD/YYYY."""
    base_profile["date_format"] = ""
    ctx = sc.build_memory_context(base_profile, qa={})
    assert "use MM/DD/YYYY format" in ctx


def test_build_memory_context_injects_website_memory(base_profile, monkeypatch):
    """When a job_url is given, per-website memories are appended."""
    class FakeStore:
        def qa_get_all_for_prompt(self):
            return {}

        def get_domain_memories(self, url, limit=20):
            return ["m1", "m2"]

        def extract_domain(self, url):
            return "acme.io"

        def format_for_prompt(self, memories):
            return "WEBSITE-MEMORY-BLOCK"

    monkeypatch.setattr(sc, "get_memory_store", lambda: FakeStore())
    ctx = sc.build_memory_context(base_profile, qa={}, job_url="https://acme.io/job")
    assert "WEBSITE-MEMORY-BLOCK" in ctx


def test_build_memory_context_qa_db_overrides_passed_in(base_profile, monkeypatch):
    """SQLite Q&A takes precedence over the passed-in qa dict."""
    class FakeStore:
        def qa_get_all_for_prompt(self):
            return {"DBQ": "DBA"}

        def get_domain_memories(self, url, limit=20):
            return []

        def extract_domain(self, url):
            return "x"

        def format_for_prompt(self, m):
            return ""

    monkeypatch.setattr(sc, "get_memory_store", lambda: FakeStore())
    ctx = sc.build_memory_context(base_profile, qa={"OLDQ": "OLDA"})
    assert "Q: DBQ\nA: DBA" in ctx
    assert "OLDQ" not in ctx
