"""Unit tests for the agent engine (no browser, no LLM, no network)."""
import asyncio
import json
import time

import pytest

from core import db
from engine import ats_fastpath, browsers, matching, memory_packs, prompts
from engine import data as user_data
from engine.events import current_run, emit
from engine.runner import RunManager


# ── matching ────────────────────────────────────────────────────────────────

PROFILE = {
    "target_job_titles": ["Data Analyst", "Business Intelligence Analyst"],
    "skills": ["SQL", "Python", "Tableau", "Excel"],
    "target_locations": ["Austin, TX"],
    "preferred_work_mode": "hybrid",
}


def test_match_score_prefers_relevant_jobs():
    good = {"title": "Senior Data Analyst", "location": "Austin, TX",
            "description": "We need SQL, Python and Tableau dashboards."}
    bad = {"title": "Forklift Operator", "location": "Boston, MA", "description": "Operate forklifts."}
    assert matching.match_score(good, PROFILE) > 70
    assert matching.match_score(bad, PROFILE) < 30


def test_match_score_handles_missing_fields():
    assert 0 <= matching.match_score({}, {}) <= 100


# ── ATS fast path ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("url, ats", [
    ("https://boards.greenhouse.io/acme/jobs/1", "greenhouse"),
    ("https://job-boards.greenhouse.io/acme/jobs/1", "greenhouse"),
    ("https://jobs.lever.co/acme/123/apply", "lever"),
    ("https://jobs.ashbyhq.com/acme/1", "ashby"),
    ("https://acme.wd5.myworkdayjobs.com/x", "workday"),
    ("https://evilgreenhouse.io/x", None),
    ("https://example.com", None),
])
def test_detect_ats(url, ats):
    assert ats_fastpath.detect_ats(url) == ats


def test_build_spec_splits_name_and_uses_ats_selectors():
    spec = ats_fastpath.build_spec("https://boards.greenhouse.io/a/jobs/1",
                                   {"name": "Ada Lovelace King", "email": "ada@x.io", "phone": "5551234",
                                    "phone_country_code": "+1"})
    assert spec["first_name"]["value"] == "Ada"
    assert spec["last_name"]["value"] == "Lovelace King"
    assert spec["first_name"]["selectors"][0] == "#first_name"
    assert spec["phone"]["value"] == "+1 5551234"
    assert "linkedin" not in spec  # empty values are not filled


# ── browser cleanup only matches our profile ───────────────────────────────

def test_profile_args_match(tmp_path):
    prof = tmp_path / "langhire" / "browser_profile"
    assert browsers.profile_args_match(["chrome.exe", f"--user-data-dir={prof}"], prof)
    assert browsers.profile_args_match(["chrome", "--user-data-dir", str(prof)], prof)
    assert not browsers.profile_args_match(["chrome.exe", f"--user-data-dir={tmp_path / 'Chrome' / 'User Data'}"], prof)
    assert not browsers.profile_args_match(["chrome.exe"], prof)  # the user's own Chrome


# ── prompts use the job's source plugin ─────────────────────────────────────

def test_apply_task_uses_source_plugin(data_dir):
    prompts.reset_registry()
    job = {"url": "https://www.indeed.com/viewjob?jk=1", "title": "Analyst", "company": "Acme", "source": "indeed"}
    task = prompts.build_apply_task(job, {}, {}, "/r.pdf", "", has_password=False, gmail_otp=False, blocked=[])
    assert "indeed.com" in task
    assert "linkedin.com/feed" not in task
    assert "mail.google.com" not in task  # Gmail only when the user opts in
    assert "report_application_result" in task


def test_apply_task_manual_job_goes_direct(data_dir):
    prompts.reset_registry()
    job = {"url": "https://jobs.lever.co/acme/1", "title": "Analyst", "company": "Acme", "source": "manual"}
    task = prompts.build_apply_task(job, {}, {}, "/r.pdf", "", has_password=False, gmail_otp=True, blocked=["x.com"])
    assert task.startswith("Go to https://jobs.lever.co/acme/1")
    assert "never invent one" in task
    assert "mail.google.com" in task
    assert "x.com" in task


def test_plugin_for_job_by_host(data_dir):
    prompts.reset_registry()
    p = prompts.plugin_for_job({"url": "https://www.linkedin.com/jobs/view/123/"})
    assert p is not None and p.name == "linkedin"


# ── memory packs ────────────────────────────────────────────────────────────

def test_memory_pack_export_is_scrubbed_and_ats_only(data_dir):
    from core import shared_config as sc
    store = sc.get_memory_store()
    store.add(content="Country field is a typeahead; type then wait. Contact ada@x.io or +1 555 123 4567",
              website_domain="acme.wd5.myworkdayjobs.com", category="element_interaction",
              ats_platform="workday", confidence=0.9)
    store.add(content="Acme's careers page hides the button", website_domain="acme.com",
              category="navigation", confidence=0.9)
    pack = memory_packs.export_pack()
    assert pack["format"] == "langhire-memory-pack"
    assert len(pack["memories"]) == 1
    text = pack["memories"][0]["content"]
    assert "ada@x.io" not in text and "555" not in text


def test_memory_pack_import_rejects_garbage(data_dir):
    with pytest.raises(ValueError):
        memory_packs.import_pack({"format": "nope"})
    added = memory_packs.import_pack({"format": "langhire-memory-pack", "memories": [
        {"ats_platform": "lever", "category": "form_strategy", "content": "Lever puts the resume upload first."},
        {"ats_platform": "lever", "category": "qa_pattern", "content": "should be skipped as personal"},
    ]})
    assert added == 1


# ── data export / delete / retention ────────────────────────────────────────

def test_export_has_no_secrets(data_dir):
    from core import config
    config.save_llm_settings({"provider": "openai", "openai": {"api_key": "sk-live-xyz", "model": "m"}})
    config.save_settings({"sensitive_data": {"email": "a@b.co", "password": "pw-123"}})
    dump = json.dumps(user_data.export_all())
    assert "sk-live-xyz" not in dump and "pw-123" not in dump


def test_delete_all_removes_data_and_secrets(data_dir):
    from core import config, secrets
    config.save_llm_settings({"provider": "openai", "openai": {"api_key": "sk-live-xyz", "model": "m"}})
    db.add_jobs([{"url": "https://a.co/1", "title": "T"}])
    removed = user_data.delete_all()
    assert "langhire.db" in removed
    assert secrets.get_secret("llm.openai.api_key") == ""
    assert db.read_jobs() == {}


def test_prune_logs(data_dir):
    logs = data_dir / "logs"
    logs.mkdir()
    old, new = logs / "old.json", logs / "new.json"
    old.write_text("x")
    new.write_text("y")
    past = time.time() - 40 * 86400
    import os
    os.utime(old, (past, past))
    assert user_data.prune_logs(30) == 1
    assert new.exists() and not old.exists()


# ── db: application records and caps ────────────────────────────────────────

def test_applications_today_and_ats_rates(data_dir):
    db.add_application({"job_url": "u1", "outcome": "submitted", "source": "indeed", "ats": "greenhouse", "cost_usd": 0.2})
    db.add_application({"job_url": "u2", "outcome": "failed", "source": "indeed", "ats": "greenhouse", "cost_usd": 0.1})
    assert db.applications_today("indeed") == 1
    rates = {r["ats"]: r for r in db.ats_success_rates()}
    assert rates["greenhouse"]["attempts"] == 2
    assert rates["greenhouse"]["success_rate"] == 0.5


# ── events + run manager ────────────────────────────────────────────────────

def test_run_manager_runs_and_records_events(data_dir):
    mgr = RunManager()

    async def factory(ctx):
        emit("job_found", "found one", job_url="https://a.co/1")
        ctx.counters["collected"] = 1
        return {"collected": 1}

    st = mgr.start("collect", factory, {"title": "x"})
    for _ in range(400):  # up to 20 s: generous for a loaded CI machine
        if not st.running:
            break
        time.sleep(0.05)
    status = mgr.status("collect")
    assert status["running"] is False and status["error"] is None
    assert status["collected"] == 1
    assert any("found one" in line for line in status["log"])
    types = [e["type"] for e in db.list_events(st.ctx.run_id)]
    assert types[0] == "run_started" and "job_found" in types and types[-1] == "run_finished"
    assert db.list_runs(kind="collect")[0]["status"] == "succeeded"


def test_run_manager_cancel(data_dir):
    mgr = RunManager()

    async def factory(ctx):
        await asyncio.sleep(30)

    st = mgr.start("apply", factory, {})
    with pytest.raises(RuntimeError):
        mgr.start("apply", factory, {})  # one apply run at a time
    assert mgr.cancel("apply") is True
    for _ in range(400):  # up to 20 s: generous for a loaded CI machine
        if not st.running:
            break
        time.sleep(0.05)
    assert mgr.status("apply")["error"] == "cancelled"
    assert db.list_runs(kind="apply")[0]["status"] == "cancelled"


def test_emit_without_run_does_not_fail():
    assert current_run.get() is None
    emit("log", "no run")  # just logs


# ── vision detection ────────────────────────────────────────────────────────

def test_image_rejection_patterns():
    from engine import vision
    assert vision.is_image_rejection("{'code': '1210', 'message': \"messages.content.type is invalid, allowed values: ['text']\"}")
    assert vision.is_image_rejection("This model does not support image input")
    assert not vision.is_image_rejection("rate limit exceeded")


def test_text_only_model_is_remembered(data_dir):
    from core import config
    from engine import vision
    config.save_llm_settings({"provider": "openai_compatible", "openai_compatible": {"model": "glm-5.3", "base_url": "x"}})
    assert vision.use_vision() is True
    vision.remember_text_only()
    assert vision.use_vision() is False
    config.save_llm_settings({"provider": "openai_compatible", "use_vision": "on",
                              "openai_compatible": {"model": "glm-5.3", "base_url": "x"}})
    assert vision.use_vision() is True


def test_parallel_workers_get_separate_profiles(data_dir):
    main = browsers.browser_profile_dir()
    (main / "Default" / "Network").mkdir(parents=True)
    (main / "Default" / "Network" / "Cookies").write_text("c")
    (main / "SingletonLock").write_text("lock")
    assert browsers.worker_profile_dir(1) == main
    w2 = browsers.worker_profile_dir(2)
    assert w2 != main
    assert (w2 / "Default" / "Network" / "Cookies").exists()   # logins carried over
    assert not (w2 / "SingletonLock").exists()                 # Chrome's lock is not copied


def test_delete_all_works_while_other_threads_hold_the_db(data_dir):
    """Windows can't unlink an open SQLite file; delete_all must still remove the data."""
    import threading
    db.add_jobs([{"url": "https://a.co/1", "title": "T"}])
    ready, done = threading.Event(), threading.Event()

    def hold():
        db.read_jobs()  # opens this thread's own connection and keeps it
        ready.set()
        done.wait(10)

    t = threading.Thread(target=hold)
    t.start()
    # Under heavy load the helper thread could start late; without this the test would
    # race delete_all against the thread's first connection instead of testing a held one.
    assert ready.wait(60), "helper thread never opened its connection"
    try:
        user_data.delete_all()
        assert db.read_jobs() == {}
    finally:
        done.set()
        t.join()


def test_linkedin_url_normalization_handles_slug_urls():
    from engine.collect import _normalize_url as n
    assert n("https://in.linkedin.com/jobs/view/senior-data-analyst-at-azilen-4490713768?position=1") \
        == "https://www.linkedin.com/jobs/view/4490713768/"
    assert n("https://www.linkedin.com/jobs/search/?currentJobId=4356842209") \
        == "https://www.linkedin.com/jobs/view/4356842209/"


def test_outcome_written_as_text_is_recovered():
    from engine.apply import parse_outcome_text
    text = ("report_application_result:\noutcome=needs_input\n"
            "missing_info=['Log in to LinkedIn in LangHire Settings, Job site logins']\nJOB: Senior Data Analyst")
    outcome, reason, missing = parse_outcome_text(text)
    assert outcome == "needs_input"
    assert missing == ["Log in to LinkedIn in LangHire Settings, Job site logins"]
    assert parse_outcome_text("I could not finish") is None


def test_rate_limit_detection():
    from engine.apply import is_rate_limited
    assert is_rate_limited("Error code: 429 - Rate limit reached for requests")
    assert not is_rate_limited("Could not find the application form")


def test_outcome_text_with_words_between():
    from engine.apply import parse_outcome_text
    text = "OUTCOME (had report_application_result been callable): needs_input — form is mostly filled"
    assert parse_outcome_text(text)[0] == "needs_input"


def test_agent_kwargs_we_pass_exist_in_browser_use():
    """browser-use accepts **kwargs, so a misspelt option is silently ignored
    (llm_call_timeout was, for months). Every option we pass must be a real one."""
    import inspect
    import re
    from pathlib import Path
    from browser_use import Agent
    params = set(inspect.signature(Agent.__init__).parameters)
    root = Path(__file__).resolve().parents[3] / "backend" / "engine"
    for f in ("apply.py", "collect.py"):
        src = (root / f).read_text(encoding="utf-8")
        for call in re.findall(r"Agent\((.*?)\n\s*\)", src, re.S):
            for kw in re.findall(r"^\s*(\w+)=", call, re.M) + re.findall(r",\s*(\w+)=", call):
                assert kw in params, f"{f}: Agent({kw}=...) is not a browser-use option"


def test_submit_guard_blocks_unreadable_same_site_writes():
    from engine.submit_guard import SubmitInterceptor, _same_site
    g = SubmitInterceptor(None, {"email": "a@b.co"})
    same = {"url": "https://jobs.lever.co/acme/1/apply", "hasPostData": True,
            "headers": {"Content-Type": "multipart/form-data; boundary=x", "Origin": "https://jobs.lever.co"}}
    s3 = {"url": "https://bucket.s3.amazonaws.com/upload", "hasPostData": True,
          "headers": {"Content-Type": "multipart/form-data; boundary=x", "Origin": "https://jobs.lever.co"}}
    assert _same_site(same) and not _same_site(s3)
    assert g._block_reason("POST", same) == "unreadable body to the site itself"
    assert g._block_reason("POST", s3) is None          # third-party resume upload is allowed
    g.arm()
    assert g._block_reason("POST", s3) == "after submit click"


def test_submit_guard_lets_captcha_through_and_ignores_trackers():
    """Blocking CAPTCHA traffic stops the real request from ever firing; beacons are not the application."""
    import time

    from engine.submit_guard import Intercepted, SubmitInterceptor, is_captcha, is_tracker
    g = SubmitInterceptor(None, {"email": "a@b.co"})
    g.arm()
    cap = {"url": "https://api.hcaptcha.com/getcaptcha/x", "postData": "v=1"}
    assert g._block_reason("POST", cap) is None
    leak = {"url": "https://api.hcaptcha.com/getcaptcha/x", "postData": "email=a@b.co"}
    assert g._block_reason("POST", leak) == "contains candidate details"
    assert g._block_reason("POST", {"url": "https://jobs.lever.co/x/1/apply", "postData": "a=1"}) == "after submit click"
    assert is_captcha("https://www.recaptcha.net/recaptcha/enterprise/reload")
    for u in ("https://www.linkedin.com/li/track", "https://r.stripe.com/0", "https://www.google.com/pagead/form-data/1",
              "https://www.okta.com/cdn-cgi/rum?", "https://www.facebook.com/tr/"):
        assert is_tracker(u), u
    for u in ("https://boards.greenhouse.io/gitlab/jobs/1", "https://jobs.lever.co/paytm/1/apply",
              "https://www.linkedin.com/voyager/api/voyagerJobsDashOnsiteApplyApplication"):
        assert not is_tracker(u), u
    t = time.time() - 1
    g.blocked = [Intercepted("https://r.stripe.com/0", "POST", "after submit click", 0, application=False)]
    assert g.blocked_since(t) == []  # a tracker beacon alone is not a passed submission


def test_upload_resume_registered_and_file_inputs_guarded():
    import asyncio
    from types import SimpleNamespace

    from engine.tools import AgentReport, build_apply_tools
    tools = build_apply_tools(AgentReport(), {}, "/tmp/r.pdf")
    actions = tools.registry.registry.actions
    assert "upload_resume" in actions

    file_node = SimpleNamespace(tag_name="input", attributes={"type": "file"})
    session = SimpleNamespace(get_element_by_index=lambda i: asyncio.sleep(0, result=file_node))
    params = SimpleNamespace(index=3, text="C:/r.pdf")
    res = asyncio.run(actions["input"].function(params=params, browser_session=session))
    assert res.error and "upload_resume" in res.error  # typing a path into a file field is refused


def test_engine_rules_mention_upload_resume_and_captcha():
    from engine.prompts import engine_rules
    rules = engine_rules(has_password=False, gmail_otp=False, blocked=[])
    assert "upload_resume" in rules and "CAPTCHA" in rules


def test_cost_unknown_for_unpriced_models():
    from types import SimpleNamespace

    from engine.apply import _cost_unknown
    priced = SimpleNamespace(usage=SimpleNamespace(total_tokens=5000, total_cost=0.02))
    unpriced = SimpleNamespace(usage=SimpleNamespace(total_tokens=5000, total_cost=0.0))
    unused = SimpleNamespace(usage=SimpleNamespace(total_tokens=0, total_cost=0.0))
    assert not _cost_unknown(priced)
    assert _cost_unknown(unpriced)  # shown as unknown, not as free
    assert not _cost_unknown(unused)


def test_strip_leaked_json_from_typed_text():
    from engine.tools import strip_leaked_json
    assert strip_leaked_json("1}}, {") == "1"
    assert strip_leaked_json('Python, SQL"}, {"click": {"index": 4}}') == "Python, SQL"
    assert strip_leaked_json('Ahmedabad {"input": {"index": 9') == "Ahmedabad"
    for ok in ("INR 3,60,000 fixed", "Built dashboards (Tableau) for {region} teams", "C++ / C#", "a}b"):
        assert strip_leaked_json(ok) == ok


def test_only_the_application_counts_as_intercepted():
    """Seen live: an armed click also blocked LinkedIn's apply widget, the S3 resume upload,
    Snowplow and ad pixels. None of those is the application."""
    from engine.submit_guard import is_application
    gh = "https://boards.greenhouse.io"
    swept = [
        {"url": "https://www.linkedin.com/talentwidgets/apply-with-linkedin", "headers": {"Origin": "https://jobs.lever.co"}},
        {"url": "https://grnhse-prod-jben-us-west-2.s3.us-west-2.amazonaws.com/", "headers": {"Origin": gh}},
        {"url": "https://c.spl.greenhouse.io/com.snowplowanalytics.snowplow/tp2", "headers": {"Origin": gh}},
        {"url": "https://q.stripe.com/csp-report", "headers": {"Origin": "https://stripe.com"}},
        {"url": "https://alb.reddit.com/rp?id=x", "headers": {"Origin": "https://stripe.com"}},
    ]
    for req in swept:
        assert not is_application("after submit click", req), req["url"]
    real = {"url": "https://boards.greenhouse.io/gitlab/jobs/1", "headers": {"Origin": gh}}
    assert is_application("after submit click", real)
    assert is_application("contains candidate details", swept[0])


def test_detect_ats_recognises_embedded_greenhouse():
    from engine.ats_fastpath import detect_ats
    assert detect_ats("https://stripe.com/jobs/search?gh_jid=8190059") == "greenhouse"
    assert detect_ats("https://www.okta.com/company/careers/opportunity/7626222?gh_jid=7626222") == "greenhouse"
    assert detect_ats("https://example.com/jobs/1") is None


def test_token_usage_recorded_per_application_and_run(data_dir):
    from types import SimpleNamespace

    from core import db as cdb
    from engine.apply import add_run_usage, usage_tokens
    from engine.events import RunContext
    usage = SimpleNamespace(total_prompt_tokens=12000, total_prompt_cached_tokens=9000,
                            total_completion_tokens=600, by_model={"glm-5.3-flash": {}})
    tokens = usage_tokens(SimpleNamespace(usage=usage))
    assert tokens == {"prompt_tokens": 12000, "cached_tokens": 9000, "completion_tokens": 600,
                      "llm_model": "glm-5.3-flash"}
    assert usage_tokens(None)["prompt_tokens"] == 0

    ctx = RunContext(run_id="r1", kind="apply")
    add_run_usage(ctx, tokens)
    add_run_usage(ctx, tokens)
    assert ctx.counters["usage"]["prompt_tokens"] == 24000 and ctx.counters["usage"]["cached_tokens"] == 18000

    cdb.add_application({"job_url": "https://a.co/1", "outcome": "failed", "cost_usd": None, **tokens})
    cdb.add_application({"job_url": "https://a.co/2", "outcome": "failed", "cost_usd": 0.02, **tokens})
    rows = {r["job_url"]: r for r in cdb.list_applications()}
    assert rows["https://a.co/1"]["cost_usd"] is None      # unknown price stays unknown, not $0
    assert rows["https://a.co/2"]["cost_usd"] == 0.02
    assert rows["https://a.co/1"]["cached_tokens"] == 9000 and rows["https://a.co/1"]["llm_model"] == "glm-5.3-flash"


def test_provider_errors_get_plain_sentences():
    from engine.apply import friendly_error
    assert "screenshots" in friendly_error("Error code: 400 - {'error': {'message': 'content.type is invalid'}}")
    assert "API key" in friendly_error("Error code: 401 - Unauthorized")
    assert "credit" in friendly_error("openai.APIStatusError: Insufficient balance or no resource package")
    assert "model name" in friendly_error("Error code: 404 - model_not_found")
    assert "too slow" in friendly_error("The AI provider did not answer within 300 seconds.")
    assert friendly_error("Plain reason the agent gave") == "Plain reason the agent gave"
    # agent reasons that merely contain these numbers or words are left alone
    assert friendly_error("Job 4021 posting does not exist any more") == "Job 4021 posting does not exist any more"
