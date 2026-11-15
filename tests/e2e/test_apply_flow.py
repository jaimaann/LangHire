"""The apply engine end to end: real backend, real browser agent, real Chromium.

The scripted LLM plays the model and the mock ATS plays the employer, so each
test is deterministic and offline. What is checked is what a user relies on:
the job's final status, what reached (or did not reach) the employer, the
application record, token accounting, and the needs-input -> answer -> retry loop.
"""
from __future__ import annotations

import json


def _add(backend, url: str):
    resp = backend.call("POST", "/jobs/add", {"url": url, "title": "", "company": "", "location": "", "description": ""})
    assert resp.get("success"), resp


def _apply(backend, url: str, test_mode: bool) -> dict:
    resp = backend.call("POST", "/apply/start", {"mode": "all", "job_url": url, "test_mode": test_mode})
    assert resp.get("success"), resp
    return backend.wait_idle("apply", timeout=480)


def _job(backend, url: str) -> dict:
    jobs = backend.call("GET", "/jobs")
    items = jobs.get("jobs", jobs) if isinstance(jobs, dict) else jobs
    for j in (items.values() if isinstance(items, dict) else items):
        if j.get("url") == url:
            return j
    raise AssertionError(f"job {url} not found")


def _record(backend, url: str) -> dict:
    recs = backend.call("GET", f"/applications?job_url={url}&limit=1")
    assert recs, f"no application record for {url}"
    return recs[0]


def _submissions(ats, job_id: str) -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in ats["submissions"].glob(f"{job_id}-*.json")]


def test_add_by_url_reads_the_posting(backend, ats):
    url = f"{ats['base']}/jobs/lv-1"
    _add(backend, url)
    job = _job(backend, url)
    assert "Business Intelligence Analyst" in job["title"]      # was "Manually Added" before


def test_test_mode_fills_the_form_clicks_submit_and_sends_nothing(backend, ats):
    url = f"{ats['base']}/jobs/gh-1"
    _add(backend, url)
    status = _apply(backend, url, test_mode=True)
    job = _job(backend, url)
    rec = _record(backend, url)
    assert job["status"] == "test_passed", (job, rec.get("reason"), backend.tail())
    assert rec["outcome"] == "ready_to_submit" and rec["intercepted"] >= 1 and rec["submit_clicks"] >= 1
    assert _submissions(ats, "gh-1") == []                      # nothing reached the employer
    assert rec["prompt_tokens"] > 0 and rec["cached_tokens"] > 0 and rec["completion_tokens"] > 0
    assert rec["llm_model"] == "scripted-agent"
    assert status.get("usage", {}).get("prompt_tokens", 0) >= rec["prompt_tokens"]


def test_real_submit_reaches_the_employer_with_the_resume(backend, ats):
    url = f"{ats['base']}/jobs/lv-1"
    if not _exists(backend, url):
        _add(backend, url)
    _apply(backend, url, test_mode=False)
    job = _job(backend, url)
    assert job["status"] == "applied", (job, _record(backend, url).get("reason"), backend.tail())
    subs = _submissions(ats, "lv-1")
    assert len(subs) == 1
    fields, files = subs[0]["fields"], subs[0]["files"]
    assert fields["email"] == "dana.tester@example.com" and fields["name"] == "Dana Tester"
    assert files["resume"]["is_pdf"]
    assert fields["q_sponsorship"] == "No" and fields["consent"] == "yes"


def test_needs_input_then_answer_requeues_and_the_retry_passes(backend, ats):
    url = f"{ats['base']}/jobs/ni-1"
    _add(backend, url)
    _apply(backend, url, test_mode=True)
    job = _job(backend, url)
    rec = _record(backend, url)
    assert job["status"] == "needs_input", (job, rec.get("reason"), backend.tail())
    assert any("felony" in q.lower() for q in rec["missing_info"])
    assert backend.call("GET", "/qa/stats")["unanswered"] >= 1

    requeued = 0
    for q in backend.call("GET", "/qa?unanswered=true"):
        answer = "No" if "felony" in q["question"].lower() else "USD 70,000"
        requeued += backend.call("PUT", f"/qa/{q['id']}", {"answer": answer}).get("requeued", 0)
    assert requeued == 1
    assert _job(backend, url)["status"] == "pending"

    _apply(backend, url, test_mode=True)
    assert _job(backend, url)["status"] == "test_passed", (_record(backend, url).get("reason"), backend.tail())
    assert _submissions(ats, "ni-1") == []


def _exists(backend, url: str) -> bool:
    try:
        _job(backend, url)
        return True
    except AssertionError:
        return False
