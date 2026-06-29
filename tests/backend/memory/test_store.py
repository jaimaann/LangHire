"""
Unit tests for backend/memory/store.py — the SQLite-backed MemoryStore.

Each test gets a fresh DB file under ``tmp_path`` so state never leaks
between tests. Nothing touches the network or the real app-data dir.
"""
import sqlite3

import pytest

from memory.store import (
    CATEGORIES,
    DOMAIN_NORMALIZATION,
    MemoryStore,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def store(tmp_path):
    """A MemoryStore backed by a fresh, isolated SQLite file."""
    s = MemoryStore(db_path=tmp_path / "memory_store.db")
    yield s
    s.close()


# ── Static domain / ATS helpers ────────────────────────────────────────────────

@pytest.mark.parametrize(
    "raw, expected",
    [
        ("goodyear.wd1.myworkdayjobs.com", "myworkdayjobs.com"),
        ("acme.myworkdayjobs.com", "myworkdayjobs.com"),
        ("eiqg.fa.us2.oraclecloud.com", "oraclecloud.com"),
        ("foo.oraclecloud.com", "oraclecloud.com"),
        ("career4.successfactors.com", "successfactors.com"),
        ("job-boards.greenhouse.io", "greenhouse.io"),
        ("jobs.lever.co", "lever.co"),
        ("myjobs.adp.com", "adp.com"),
        ("company.icims.com", "icims.com"),
        ("company.smartrecruiters.com", "smartrecruiters.com"),
        ("acme.bamboohr.com", "bamboohr.com"),
        ("jobs.ashbyhq.com", "ashbyhq.com"),
        ("acme.jobvite.com", "jobvite.com"),
        ("acme.taleo.net", "taleo.net"),
        ("acme.paylocity.com", "paylocity.com"),
        ("acme.ultipro.com", "ultipro.com"),
        ("au.indeed.com", "indeed.com"),
        ("indeed.co.uk", "indeed.com"),
        ("www.ziprecruiter.com", "ziprecruiter.com"),
        ("acme.seek.com.au", "seek.com.au"),
        ("acme.seek.co.nz", "seek.co.nz"),
        ("jobs.naukri.com", "naukri.com"),
        ("careers.stepstone.de", "stepstone.de"),
        ("acme.jobs.personio.de", "personio.de"),
        ("acme.teamtailor.com", "teamtailor.com"),
    ],
)
def test_normalize_domain_collapses_subdomains(raw, expected):
    """Company-specific ATS subdomains collapse to their shared platform domain."""
    assert MemoryStore.normalize_domain(raw) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("www.glassdoor.com", "glassdoor.com"),
        ("glassdoor.com", "glassdoor.com"),
        ("www.glassdoor.co.uk", "glassdoor.com"),
        ("glassdoor.co.uk", "glassdoor.com"),
        ("www.glassdoor.ca", "glassdoor.com"),
        ("glassdoor.de", "glassdoor.com"),
    ],
)
def test_normalize_domain_collapses_glassdoor(raw, expected):
    """Glassdoor subdomains and country variants collapse to glassdoor.com (issue #35)."""
    assert MemoryStore.normalize_domain(raw) == expected


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://www.glassdoor.com/job-listing/swe-acme?jl=123", "glassdoor.com"),
        ("https://www.glassdoor.co.uk/Job/jobs.htm?sc.keyword=eng", "glassdoor.com"),
    ],
)
def test_extract_and_detect_glassdoor(url, expected):
    """A Glassdoor URL extracts to glassdoor.com and detects as the glassdoor ATS."""
    domain = MemoryStore.extract_domain(url)
    assert domain == expected
    assert MemoryStore.detect_ats_platform(domain) == "glassdoor"


def test_normalize_domain_passes_through_unknown():
    """Domains without a normalization rule are returned unchanged."""
    assert MemoryStore.normalize_domain("linkedin.com") == "linkedin.com"
    assert MemoryStore.normalize_domain("example.org") == "example.org"


def test_normalize_domain_rules_are_nonempty():
    """Sanity-check the rule table is populated (regression guard)."""
    assert len(DOMAIN_NORMALIZATION) > 0


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://www.linkedin.com/jobs/view/123", "linkedin.com"),
        ("https://goodyear.wd1.myworkdayjobs.com/job/123", "myworkdayjobs.com"),
        ("https://eiqg.fa.us2.oraclecloud.com/hcmUI/x", "oraclecloud.com"),
        ("http://example.com/path?q=1", "example.com"),
        ("https://JOBS.LEVER.CO/Acme", "lever.co"),  # case-insensitive
    ],
)
def test_extract_domain(url, expected):
    """URLs are parsed and the host normalized."""
    assert MemoryStore.extract_domain(url) == expected


@pytest.mark.parametrize("bad", ["", "not a url", "   ", "javascript:void(0)"])
def test_extract_domain_handles_garbage(bad):
    """Malformed/unsupported URLs yield an empty domain, never raise."""
    assert MemoryStore.extract_domain(bad) == ""


def test_extract_domain_swallows_exceptions(monkeypatch):
    """If urlparse explodes, extract_domain returns '' rather than raising."""
    import memory.store as store_mod

    def boom(_):
        raise ValueError("nope")

    monkeypatch.setattr(store_mod, "urlparse", boom)
    assert MemoryStore.extract_domain("https://x.com") == ""


@pytest.mark.parametrize(
    "domain, ats",
    [
        ("linkedin.com", "linkedin"),
        ("boards.greenhouse.io", "greenhouse"),
        ("jobs.lever.co", "lever"),
        ("acme.myworkdayjobs.com", "workday"),
        ("unknown-site.xyz", None),
    ],
)
def test_detect_ats_platform(domain, ats):
    """ATS platform detection matches by substring of the domain."""
    assert MemoryStore.detect_ats_platform(domain) == ats


def test_content_hash_is_stable_and_case_insensitive():
    """Hash ignores case/surrounding whitespace and is keyed by domain+category."""
    h1 = MemoryStore._content_hash("Hello World", "x.com", "navigation")
    h2 = MemoryStore._content_hash("  hello world  ", "x.com", "navigation")
    assert h1 == h2
    assert len(h1) == 16
    # Different category → different hash.
    assert MemoryStore._content_hash("hello world", "x.com", "form_strategy") != h1


# ── add() ───────────────────────────────────────────────────────────────────

def test_add_new_memory_returns_true(store):
    """A fresh memory inserts and returns True."""
    assert store.add("Click the apply button", "linkedin.com", "navigation") is True
    rows = store.search(website_domain="linkedin.com")
    assert len(rows) == 1
    assert rows[0]["content"] == "Click the apply button"
    assert rows[0]["ats_platform"] == "linkedin"  # auto-detected


def test_add_blank_content_is_rejected(store):
    """Empty/whitespace-only content is not stored."""
    assert store.add("   ", "linkedin.com", "navigation") is False
    assert store.get_stats()["total_memories"] == 0


def test_add_duplicate_reinforces_and_returns_false(store):
    """Re-adding identical content bumps confidence and access_count, returns False."""
    store.add("Use the modal", "x.com", "navigation", confidence=0.8)
    assert store.add("use the MODAL", "x.com", "navigation") is False  # case-insensitive dup
    rows = store.search(website_domain="x.com", success_only=False)
    assert len(rows) == 1
    assert rows[0]["confidence"] == pytest.approx(0.85)
    assert rows[0]["access_count"] >= 1


def test_add_confidence_caps_at_one(store):
    """Reinforcement cannot push confidence above 1.0."""
    store.add("c", "x.com", "navigation", confidence=0.99)
    for _ in range(10):
        store.add("c", "x.com", "navigation")
    rows = store.search(website_domain="x.com")
    assert rows[0]["confidence"] <= 1.0


def test_add_unknown_category_falls_back(store):
    """An unrecognized category is coerced to the safe default."""
    store.add("content", "x.com", "not_a_real_category")
    rows = store.search(website_domain="x.com")
    assert rows[0]["category"] == "form_strategy"


def test_add_respects_explicit_ats_platform(store):
    """An explicit ats_platform overrides auto-detection."""
    store.add("c", "linkedin.com", "navigation", ats_platform="custom_ats")
    rows = store.search(website_domain="linkedin.com")
    assert rows[0]["ats_platform"] == "custom_ats"


def test_add_failure_memory(store):
    """success=False is persisted as 0 and filtered out of success_only search."""
    store.add("failed thing", "x.com", "failure_recovery", success=False)
    assert store.search(website_domain="x.com", success_only=True) == []
    rows = store.search(website_domain="x.com", success_only=False)
    assert rows[0]["success"] == 0


# ── search() ──────────────────────────────────────────────────────────────────

def test_search_orders_by_confidence_then_access(store):
    """Higher-confidence memories come first."""
    store.add("low", "x.com", "navigation", confidence=0.4)
    store.add("high", "x.com", "navigation", confidence=0.9)
    rows = store.search(website_domain="x.com")
    assert [r["content"] for r in rows] == ["high", "low"]


def test_search_filters_by_category_and_ats(store):
    """Category and ats_platform filters narrow results."""
    store.add("nav", "x.com", "navigation", ats_platform="atsA")
    store.add("strat", "x.com", "form_strategy", ats_platform="atsB")
    assert len(store.search(category="navigation")) == 1
    assert len(store.search(ats_platform="atsB")) == 1


def test_search_respects_limit(store):
    """The limit caps the number of returned rows."""
    for i in range(5):
        store.add(f"item {i}", "x.com", "navigation")
    assert len(store.search(website_domain="x.com", limit=3)) == 3


def test_search_no_filters_returns_all(store):
    """No filters + success_only=False returns everything."""
    store.add("a", "x.com", "navigation")
    store.add("b", "y.com", "navigation", success=False)
    assert len(store.search(success_only=False)) == 2


def test_search_increments_access_count(store):
    """Searching a row bumps its access_count (side effect)."""
    store.add("a", "x.com", "navigation")
    before = store.search(website_domain="x.com")[0]["access_count"]
    store.search(website_domain="x.com")
    after = store.search(website_domain="x.com")[0]["access_count"]
    assert after > before


def test_search_empty_db(store):
    """Search on an empty store returns an empty list, no error."""
    assert store.search(website_domain="nothing.com") == []


# ── get_domain_memories() ──────────────────────────────────────────────────────

def test_get_domain_memories_combines_domain_and_ats(store):
    """Pulls domain-specific memories plus same-ATS memories from other domains."""
    # Two greenhouse domains.
    store.add("boards memory", "boards.greenhouse.io", "navigation",
              ats_platform="greenhouse")
    store.add("other gh memory", "job-boards.greenhouse.io", "navigation",
              ats_platform="greenhouse")
    mems = store.get_domain_memories("https://boards.greenhouse.io/acme/jobs/1")
    contents = {m["content"] for m in mems}
    assert "boards memory" in contents
    assert "other gh memory" in contents


def test_get_domain_memories_dedups_by_id(store):
    """The same row is never returned twice when domain == ATS source."""
    store.add("only memory", "linkedin.com", "navigation")
    mems = store.get_domain_memories("https://www.linkedin.com/jobs/view/1")
    ids = [m["id"] for m in mems]
    assert len(ids) == len(set(ids))


def test_get_domain_memories_empty_for_bad_url(store):
    """An unparseable URL yields no memories."""
    assert store.get_domain_memories("not a url") == []


# ── Reporting / aggregation ────────────────────────────────────────────────────

def test_get_all_domains_aggregates(store):
    """Per-domain summary counts successes and failures and averages confidence."""
    store.add("a", "x.com", "navigation", success=True, confidence=0.8)
    store.add("b", "x.com", "form_strategy", success=False, confidence=0.6)
    store.add("c", "y.com", "navigation", success=True, confidence=1.0)
    summary = {d["website_domain"]: d for d in store.get_all_domains()}
    assert summary["x.com"]["count"] == 2
    assert summary["x.com"]["success_count"] == 1
    assert summary["x.com"]["failure_count"] == 1
    assert summary["x.com"]["avg_confidence"] == pytest.approx(0.7)
    # Ordered by count DESC — x.com (2) before y.com (1).
    assert store.get_all_domains()[0]["website_domain"] == "x.com"


def test_get_all_domains_empty(store):
    """Empty DB → empty summary list."""
    assert store.get_all_domains() == []


def test_get_stats(store):
    """Overall stats report totals, distinct domains, and category breakdown."""
    store.add("a", "x.com", "navigation")
    store.add("b", "x.com", "navigation")
    store.add("c", "y.com", "form_strategy")
    stats = store.get_stats()
    assert stats["total_memories"] == 3
    assert stats["unique_domains"] == 2
    assert stats["by_category"]["navigation"] == 2
    assert stats["by_category"]["form_strategy"] == 1


def test_get_stats_empty(store):
    """Stats on empty DB return zeros and an empty category dict."""
    stats = store.get_stats()
    assert stats == {"total_memories": 0, "unique_domains": 0, "by_category": {}}


# ── Maintenance ────────────────────────────────────────────────────────────────

def test_decay_confidence_only_affects_stale(store):
    """Stale memories decay; freshly-added ones are untouched."""
    store.add("fresh", "x.com", "navigation", confidence=0.9)
    # Force one row to look old by rewriting its updated_at.
    conn = store._get_conn()
    conn.execute("INSERT INTO memories "
                 "(website_domain, category, content, content_hash, success, "
                 " confidence, created_at, updated_at) "
                 "VALUES ('x.com','navigation','old','hashold',1,0.9,"
                 "'2000-01-01T00:00:00+00:00','2000-01-01T00:00:00+00:00')")
    conn.commit()
    affected = store.decay_confidence(days_old=30, decay_factor=0.5)
    assert affected == 1
    rows = {r["content"]: r["confidence"] for r in store.search(website_domain="x.com")}
    assert rows["fresh"] == pytest.approx(0.9)
    assert rows["old"] == pytest.approx(0.45)


def test_decay_confidence_floor(store):
    """Decay never pushes confidence below the 0.3 floor."""
    conn = store._get_conn()
    conn.execute("INSERT INTO memories "
                 "(website_domain, category, content, content_hash, success, "
                 " confidence, created_at, updated_at) "
                 "VALUES ('x.com','navigation','old','hashold',1,0.31,"
                 "'2000-01-01T00:00:00+00:00','2000-01-01T00:00:00+00:00')")
    conn.commit()
    store.decay_confidence(days_old=1, decay_factor=0.1)
    rows = store.search(website_domain="x.com")
    assert rows[0]["confidence"] == pytest.approx(0.3)


def test_delete_low_confidence(store):
    """Memories below the threshold are removed."""
    store.add("keep", "x.com", "navigation", confidence=0.8)
    store.add("drop", "x.com", "form_strategy", confidence=0.2)
    removed = store.delete_low_confidence(threshold=0.3)
    assert removed == 1
    remaining = [r["content"] for r in store.search(website_domain="x.com")]
    assert remaining == ["keep"]


def test_delete_low_confidence_none_match(store):
    """Returns 0 when nothing is below threshold."""
    store.add("keep", "x.com", "navigation", confidence=0.8)
    assert store.delete_low_confidence(threshold=0.3) == 0


def test_consolidate_domains_migrates_and_dedups(store):
    """Subdomain memories migrate to the normalized domain and duplicates collapse."""
    # Two company subdomains on Workday with identical content → after migration,
    # they share a domain and should dedup down to one.
    store.add("apply via modal", "acme.wd1.myworkdayjobs.com", "navigation")
    store.add("apply via modal", "beta.wd5.myworkdayjobs.com", "navigation")
    migrations = store.consolidate_domains()
    # Both old domains were migrated.
    assert any("acme.wd1.myworkdayjobs.com" in k for k in migrations)
    assert migrations.get("_duplicates_removed", 0) == 1
    rows = store.search(website_domain="myworkdayjobs.com")
    assert len(rows) == 1
    assert rows[0]["ats_platform"] == "workday"


def test_consolidate_domains_noop_when_already_normalized(store):
    """Domains with no normalization rule produce no migrations."""
    store.add("a", "linkedin.com", "navigation")
    assert store.consolidate_domains() == {}


# ── Export / import round-trip ──────────────────────────────────────────────────

def test_export_import_round_trip(store, tmp_path):
    """Exported memories can be re-imported into a fresh store."""
    store.add("a", "x.com", "navigation", confidence=0.9)
    store.add("b", "y.com", "form_strategy", success=False, confidence=0.5)
    exported = store.export_all()
    assert len(exported) == 2

    fresh = MemoryStore(db_path=tmp_path / "fresh.db")
    try:
        added = fresh.import_memories(exported)
        assert added == 2
        assert fresh.get_stats()["total_memories"] == 2
        # Importing again imports nothing new (dedup).
        assert fresh.import_memories(exported) == 0
    finally:
        fresh.close()


def test_import_skips_blank_content(store):
    """Records with blank content are silently skipped on import."""
    added = store.import_memories([
        {"content": "", "website_domain": "x.com", "category": "navigation"},
        {"content": "real", "website_domain": "x.com", "category": "navigation"},
    ])
    assert added == 1


# ── Prompt formatting ──────────────────────────────────────────────────────────

def test_format_for_prompt_groups_by_category(store):
    """Memories are grouped under human-readable category labels."""
    mems = [
        {"category": "navigation", "content": "click X"},
        {"category": "navigation", "content": "scroll Y"},
        {"category": "form_strategy", "content": "do Z"},
    ]
    out = store.format_for_prompt(mems)
    assert CATEGORIES["navigation"] in out
    assert "click X" in out and "scroll Y" in out and "do Z" in out


def test_format_for_prompt_empty(store):
    """No memories → empty string."""
    assert store.format_for_prompt([]) == ""


def test_format_for_prompt_unknown_category_label(store):
    """An unknown category is title-cased rather than dropped."""
    out = store.format_for_prompt([{"category": "weird_cat", "content": "hi"}])
    assert "Weird Cat" in out
    assert "hi" in out


# ── Q&A repository ──────────────────────────────────────────────────────────────

def test_qa_add_new_returns_dict(store):
    """A new question returns its row dict."""
    row = store.qa_add("What is your name?", answer="Jai", source_domain="x.com")
    assert row is not None
    assert row["question"] == "What is your name?"
    assert row["answer"] == "Jai"
    assert row["times_seen"] == 1


def test_qa_add_exact_duplicate_increments(store):
    """An exact (normalized) duplicate returns None and bumps times_seen."""
    store.qa_add("What is your name?")
    assert store.qa_add("what is your NAME???") is None
    rows = store.qa_list()
    assert len(rows) == 1
    assert rows[0]["times_seen"] == 2


def test_qa_add_fuzzy_duplicate_increments(store):
    """A high token-overlap question is treated as a duplicate."""
    store.qa_add("How many years of Python experience do you have")
    # Same tokens, reordered/extra punctuation → overlap > 0.85.
    assert store.qa_add("How many years of Python experience do you have?") is None
    assert len(store.qa_list()) == 1


def test_qa_list_search_and_unanswered(store):
    """qa_list supports text search and unanswered-only filtering."""
    store.qa_add("Salary expectation?", answer="100k")
    store.qa_add("Visa status?", answer="")
    assert len(store.qa_list(search="salary")) == 1
    unanswered = store.qa_list(unanswered_only=True)
    assert len(unanswered) == 1
    assert unanswered[0]["question"] == "Visa status?"


def test_qa_stats(store):
    """qa_stats counts answered vs unanswered canonical questions."""
    store.qa_add("Q1", answer="A")
    store.qa_add("Q2", answer="")
    stats = store.qa_stats()
    assert stats == {"total": 2, "answered": 1, "unanswered": 1}


def test_qa_update(store):
    """qa_update sets the answer and reports success."""
    row = store.qa_add("Q?")
    assert store.qa_update(row["id"], "the answer") is True
    assert store.qa_list()[0]["answer"] == "the answer"


def test_qa_delete(store):
    """qa_delete removes a question (and any merged into it)."""
    row = store.qa_add("Q?")
    assert store.qa_delete(row["id"]) is True
    assert store.qa_list() == []


def test_qa_delete_missing_id_does_not_remove_rows(store):
    """Deleting a non-existent id leaves real rows intact.

    Note: qa_delete returns ``conn.total_changes`` (a connection-lifetime
    cumulative counter, not per-statement), so its boolean return is not a
    reliable "row existed" signal. We assert on observable state instead.
    """
    row = store.qa_add("keep me")
    before = len(store.qa_list())
    store.qa_delete(999)  # no matching row
    assert len(store.qa_list()) == before
    # The real row is still present and deletable.
    assert store.qa_delete(row["id"]) is True
    assert store.qa_list() == []


def test_qa_merge(store):
    """Merging folds source times_seen into target and hides the source."""
    a = store.qa_add("Question A")
    b = store.qa_add("Totally different B")
    store.qa_add("Question A")  # bump A → times_seen 2
    assert store.qa_merge(a["id"], b["id"]) is True
    listed = store.qa_list()
    # A is now merged into B, so only B is canonical.
    assert len(listed) == 1
    assert listed[0]["id"] == b["id"]
    assert listed[0]["times_seen"] == 1 + 2  # b's 1 + a's 2


def test_qa_merge_missing_source(store):
    """Merging a missing source id returns False."""
    b = store.qa_add("B")
    assert store.qa_merge(123456, b["id"]) is False


def test_qa_auto_squash(store):
    """Auto-squash collapses near-duplicate questions, returning the merge count."""
    store.qa_add("How many years of experience do you have")
    # Insert a near-duplicate directly so qa_add's own fuzzy guard doesn't pre-merge.
    conn = store._get_conn()
    conn.execute(
        "INSERT INTO qa_repository (question, normalized, answer, created_at, updated_at) "
        "VALUES (?, ?, '', '2020-01-01', '2020-01-01')",
        ("How many years of experience do you have?",
         store._normalize_qa("How many years of experience do you have extra")),
    )
    conn.commit()
    merges = store.qa_auto_squash()
    assert merges >= 1
    # After squash only one canonical question remains.
    assert len(store.qa_list()) == 1


def test_qa_get_all_for_prompt(store):
    """Only answered canonical questions are surfaced for prompt injection."""
    store.qa_add("Q1", answer="A1")
    store.qa_add("Q2", answer="")  # unanswered, excluded
    out = store.qa_get_all_for_prompt()
    assert out == {"Q1": "A1"}


def test_token_overlap_edge_cases():
    """Token overlap returns 0 for empty inputs and 1 for identical sets."""
    assert MemoryStore._token_overlap("", "a b") == 0.0
    assert MemoryStore._token_overlap("a b", "") == 0.0
    assert MemoryStore._token_overlap("a b c", "a b c") == 1.0
    assert MemoryStore._token_overlap("a b", "a c") == pytest.approx(0.5)


def test_normalize_qa_strips_punctuation():
    """Q&A normalization lowercases and strips punctuation."""
    assert MemoryStore._normalize_qa("  Hello, World!?  ") == "hello world"


# ── Connection / lifecycle ──────────────────────────────────────────────────────

def test_close_is_idempotent(store):
    """close() can be called repeatedly without error."""
    store.close()
    store.close()  # no-op second time
    # Reopens lazily on next use.
    assert store.get_stats()["total_memories"] == 0


def test_separate_stores_have_isolated_dbs(tmp_path):
    """Two stores on different paths do not share data."""
    a = MemoryStore(db_path=tmp_path / "a.db")
    b = MemoryStore(db_path=tmp_path / "b.db")
    try:
        a.add("only in a", "x.com", "navigation")
        assert b.get_stats()["total_memories"] == 0
        assert a.get_stats()["total_memories"] == 1
    finally:
        a.close()
        b.close()


def test_schema_version_recorded(store):
    """Migrations advance schema_version to 2 (qa_repository present)."""
    conn = store._get_conn()
    version = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
    assert version == 2
    # qa_repository table exists.
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert "qa_repository" in tables and "memories" in tables
