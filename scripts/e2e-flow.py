"""End-to-end flow test: real backend + real browser + real LLM, against the local mock ATS.

Drives the backend over HTTP the way the desktop UI does. No application is
ever sent to a real employer: every job points at tests/fixtures/ats/server.py.

    LANGHIRE_E2E_BASE_URL=https://api.example.com/v1 \
    LANGHIRE_E2E_MODEL=some-model LANGHIRE_E2E_API_KEY=... \
    uv run python scripts/e2e-flow.py --resume path/to/resume.pdf --out e2e-report.json

Steps can be limited with --steps (comma list). The report is JSON: one entry
per step with ok, seconds and details. Also used by the nightly canary.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "fixtures" / "ats"))
import server as ats  # noqa: E402

ALL_STEPS = ["health", "llm", "resume", "profile", "setup", "plugins", "jobs", "cover_letter", "tailor",
             "apply_gh", "apply_needs_input", "apply_batch", "records", "qa", "dashboard", "caps",
             "collect", "export", "memory_pack", "delete"]


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class Api:
    def __init__(self, base: str, token: str):
        self.base, self.token = base, token

    def call(self, method: str, path: str, body=None, timeout: float = 300):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method)
        req.add_header("Authorization", f"Bearer {self.token}")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
                ctype = r.headers.get("Content-Type", "")
                return r.status, (json.loads(raw) if "json" in ctype else raw.decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            raw = e.read()
            try:
                return e.code, json.loads(raw)
            except ValueError:
                return e.code, raw.decode("utf-8", "replace")

    def get(self, path, **kw):
        return self.call("GET", path, **kw)

    def post(self, path, body=None, **kw):
        return self.call("POST", path, body if body is not None else {}, **kw)

    def put(self, path, body, **kw):
        return self.call("PUT", path, body, **kw)


class EventTap(threading.Thread):
    """Collects SSE events from /events in the background."""

    def __init__(self, api: Api):
        super().__init__(daemon=True)
        self.api, self.events, self.error = api, [], None

    def run(self):
        req = urllib.request.Request(self.api.base + "/events")
        req.add_header("Authorization", f"Bearer {self.api.token}")
        try:
            with urllib.request.urlopen(req, timeout=3600) as r:
                for line in r:
                    line = line.decode("utf-8", "replace").strip()
                    if line.startswith("data: "):
                        self.events.append(json.loads(line[6:]))
        except Exception as e:  # noqa: BLE001
            self.error = str(e)


def wait_run(api: Api, kind: str, timeout: float) -> dict:
    path = "/apply/status" if kind == "apply" else "/jobs/collect/status"
    t0 = time.time()
    time.sleep(2)
    while time.time() - t0 < timeout:
        _, st = api.get(path)
        if isinstance(st, dict) and not st.get("running"):
            return st
        time.sleep(5)
    api.post("/apply/stop" if kind == "apply" else "/jobs/collect/stop")
    return {"timeout": True}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--resume", required=True)
    ap.add_argument("--out", default="e2e-report.json")
    ap.add_argument("--steps", default=",".join(ALL_STEPS))
    ap.add_argument("--data-dir", default="")
    ap.add_argument("--collect-source", default="reed")
    ap.add_argument("--apply-timeout", type=float, default=900)
    ap.add_argument("--test-mode", action="store_true",
                    help="click Submit but intercept the request; the mock ATS must receive nothing")
    a = ap.parse_args()
    steps = [s.strip() for s in a.steps.split(",") if s.strip()]
    base_url = os.environ["LANGHIRE_E2E_BASE_URL"]
    model = os.environ["LANGHIRE_E2E_MODEL"]
    key = os.environ["LANGHIRE_E2E_API_KEY"]

    work = Path(a.data_dir or tempfile.mkdtemp(prefix="langhire-e2e-"))
    data_dir = work / "data"
    subs = work / "submissions"
    ats_port, api_port = free_port(), free_port()
    ats_srv = ats.serve(ats_port, subs)
    ats_base = f"http://127.0.0.1:{ats_port}"
    token = secrets.token_hex(16)
    env = {**os.environ, "LANGHIRE_DATA_DIR": str(data_dir), "LANGHIRE_PORT": str(api_port),
           "LANGHIRE_API_TOKEN": token, "LANGHIRE_ALLOW_LOCAL_URLS": "1", "LANGHIRE_NO_WATCHDOG": "1",
           "PYTHONUTF8": "1"}
    env.pop("LANGHIRE_E2E_API_KEY", None)
    backend_log = open(work / "backend-stdout.log", "w", encoding="utf-8")
    proc = subprocess.Popen([sys.executable, str(ROOT / "backend" / "main.py")], env=env, cwd=str(ROOT),
                            stdout=backend_log, stderr=subprocess.STDOUT)
    api = Api(f"http://127.0.0.1:{api_port}", token)
    report: list[dict] = []

    def step(name: str, fn):
        if name not in steps:
            return None
        t0 = time.time()
        try:
            details = fn()
            ok = True
        except AssertionError as e:
            ok, details = False, {"assertion": str(e)}
        except Exception as e:  # noqa: BLE001
            ok, details = False, {"error": f"{type(e).__name__}: {e}"}
        report.append({"step": name, "ok": ok, "seconds": round(time.time() - t0, 1), "details": details})
        print(f"[{'PASS' if ok else 'FAIL'}] {name} ({report[-1]['seconds']}s)", flush=True)
        Path(a.out).write_text(json.dumps({"model": model, "work_dir": str(work), "steps": report}, indent=2,
                                          default=str), encoding="utf-8")
        return details

    try:
        for _ in range(90):
            try:
                if api.get("/health", timeout=3)[0] == 200:
                    break
            except Exception:  # noqa: BLE001
                time.sleep(1)
        tap = EventTap(api)
        tap.start()

        def s_health():
            code, h = api.get("/health")
            assert code == 200, h
            return h
        step("health", s_health)

        def s_llm():
            cfg = {"provider": "openai_compatible", "openai_compatible": {"base_url": base_url, "model": model,
                                                                          "api_key": key}}
            code, r = api.put("/settings/llm", cfg)
            assert code == 200, r
            on_disk = (data_dir / "llm_settings.json").read_text(encoding="utf-8")
            assert key not in on_disk, "API key written to llm_settings.json in plaintext"
            code, t = api.post("/llm/test", cfg, timeout=120)
            assert t.get("success"), t
            return {"test": t}
        step("llm", s_llm)

        def s_resume():
            code, r = api.put("/settings", {"resume_path": str(Path(a.resume).resolve())})
            assert code == 200, r
            code, r = api.post("/profile/parse-resume", timeout=300)
            assert r.get("success"), r
            return {"fields_filled": r.get("fields_filled"), "profile": r.get("profile")}
        step("resume", s_resume)

        def s_profile():
            _, p = api.get("/profile")
            assert p.get("name"), "no name parsed"
            # Make the profile complete enough to apply, as a user would in the Profile page
            p.setdefault("address", {})
            p["address"].update({"city": p["address"].get("city") or "Austin", "state": p["address"].get("state") or "TX",
                                 "country": p["address"].get("country") or "USA"})
            p["work_authorization"] = p.get("work_authorization") or "Authorized to work in the US"
            p["visa_sponsorship_needed"] = False
            p["phone"] = p.get("phone") or "5125550142"
            p["email"] = "e2e.candidate@example.com"  # never a real person's inbox
            p["target_job_titles"] = p.get("target_job_titles") or ["Data Analyst"]
            p["target_locations"] = ["Austin, TX"]
            code, r = api.put("/profile", p)
            assert code == 200, r
            return {"name": p["name"], "skills": p.get("skills", [])[:10], "titles": p["target_job_titles"]}
        step("profile", s_profile)

        def s_setup():
            _, s = api.get("/setup/status")
            assert s["profile"] and s["llm"] and s["resume"], s
            return s
        step("setup", s_setup)

        def s_plugins():
            _, r = api.get("/plugins")
            names = [p["name"] for p in r["plugins"]]
            assert "linkedin" in names and "indeed" in names
            _, auth = api.get("/auth/status")
            return {"plugins": names, "auth": auth}
        step("plugins", s_plugins)

        def s_jobs():
            added = []
            for jid, j in ats.JOBS.items():
                code, r = api.post("/jobs/add", {"url": f"{ats_base}/jobs/{jid}", "title": j["title"],
                                                  "company": j["company"], "location": j["location"]})
                assert code == 200, r
                added.append(jid)
            code, dup = api.post("/jobs/add", {"url": f"{ats_base}/jobs/gh-1"})
            assert code == 409, dup
            _, jobs = api.get("/jobs")
            _, stats = api.get("/jobs/stats")
            return {"added": added, "stats": stats,
                    "scores": {j["title"]: j.get("match_score") for j in jobs}}
        step("jobs", s_jobs)

        def s_cover():
            code, r = api.post("/cover-letter/generate", {"job_description": "Data analyst: SQL, Python, Tableau.",
                                                            "job_title": "Data Analyst", "company": "Northwind"},
                               timeout=300)
            assert r.get("success"), r
            letter = r["cover_letter"]
            assert "ChatInvokeCompletion" not in letter and "completion=" not in letter, letter[:200]
            assert len(letter) > 200, letter
            return {"chars": len(letter), "start": letter[:160]}
        step("cover_letter", s_cover)

        def s_tailor():
            code, r = api.post("/resume/tailor", {"job_urls": [f"{ats_base}/jobs/gh-1"]}, timeout=600)
            res = (r.get("results") or [{}])[0] if isinstance(r, dict) else {}
            assert res.get("status") == "done", r
            return {"path": res.get("path"), "chars": len(res.get("content") or "")}
        step("tailor", s_tailor)

        def apply_one(jid: str) -> dict:
            code, r = api.post("/apply/start", {"mode": "all", "job_url": f"{ats_base}/jobs/{jid}",
                                                 "test_mode": a.test_mode})
            assert r.get("success"), r
            st = wait_run(api, "apply", a.apply_timeout)
            _, jobs = api.get("/jobs")
            job = next(j for j in jobs if j["url"].endswith(f"/jobs/{jid}"))
            _, recs = api.get(f"/applications?job_url={ats_base}/jobs/{jid}")
            subs_for = sorted(subs.glob(f"{jid}-*.json"))
            return {"status": job["status"], "error": job.get("error"), "run_error": st.get("error"),
                    "cost_usd": st.get("cost_usd"), "log_tail": (st.get("log") or [])[-15:],
                    "record": recs[0] if recs else None,
                    "submission": json.loads(subs_for[-1].read_text(encoding="utf-8")) if subs_for else None}

        def s_apply_gh():
            out = apply_one("gh-1")
            if a.test_mode:
                assert out["submission"] is None, "TEST MODE LEAK: the mock ATS received an application"
                assert out["status"] == "test_passed", out["status"]
                rec = out["record"] or {}
                assert rec.get("intercepted", 0) >= 1, rec
                return out
            assert out["submission"] is not None, "no submission reached the mock ATS"
            assert out["status"] == "applied", out["status"]
            f = out["submission"]["fields"]
            assert f.get("email") == "e2e.candidate@example.com", f.get("email")
            assert out["submission"]["files"].get("resume", {}).get("is_pdf"), "resume not uploaded as PDF"
            return out
        step("apply_gh", s_apply_gh)

        def s_needs_input():
            out = apply_one("ni-1")
            assert out["status"] == "needs_input", f"expected needs_input, got {out['status']}"
            assert out["submission"] is None, "agent submitted a form with an unanswerable required question"
            return out
        step("apply_needs_input", s_needs_input)

        def s_batch():
            urls = [f"{ats_base}/jobs/lv-1", f"{ats_base}/jobs/ms-1"]
            code, r = api.post("/apply/start", {"mode": "all", "job_urls": urls, "workers": 2,
                                                 "test_mode": a.test_mode})
            assert r.get("success"), r
            st = wait_run(api, "apply", a.apply_timeout * 2)
            _, jobs = api.get("/jobs")
            res = {j["url"].rsplit("/", 1)[-1]: (j["status"], j.get("error")) for j in jobs if j["url"] in urls}
            got = {p.stem.split("-")[0] + "-" + p.stem.split("-")[1] for p in subs.glob("*.json")}
            if a.test_mode:
                assert not got, f"TEST MODE LEAK: {got}"
                assert all(s == "test_passed" for s, _ in res.values()), res
            else:
                assert all(s == "applied" for s, _ in res.values()), res
            return {"jobs": res, "submissions": sorted(got), "cost_usd": st.get("cost_usd"),
                    "log_tail": (st.get("log") or [])[-10:]}
        step("apply_batch", s_batch)

        def s_records():
            _, recs = api.get("/applications")
            _, ats_rates = api.get("/applications/ats")
            assert recs, "no application records"
            return {"count": len(recs), "outcomes": [r["outcome"] for r in recs], "ats": ats_rates,
                    "screenshots": [bool(r.get("screenshot_path")) for r in recs],
                    "answers_per_record": [len(r.get("answers") or []) for r in recs]}
        step("records", s_records)

        def s_qa():
            _, qa = api.get("/qa")
            _, stats = api.get("/qa/stats")
            return {"stats": stats, "unanswered": [q["question"] for q in qa if not q.get("answer")][:10]}
        step("qa", s_qa)

        def s_dashboard():
            _, d = api.get("/dashboard")
            _, runs = api.get("/runs")
            _, logs = api.get("/logs/runs")
            return {"jobs": d.get("jobs"), "memory": d.get("memory"), "ats": d.get("metrics", {}).get("ats"),
                    "cost_7d": d.get("metrics", {}).get("cost_7d_usd"), "runs": [(r["kind"], r["status"]) for r in runs],
                    "log_runs": len(logs), "sse_events": len(tap.events), "sse_error": tap.error,
                    "sse_types": sorted({e["type"] for e in tap.events})}
        step("dashboard", s_dashboard)

        def s_caps():
            api.put("/settings", {"daily_apply_cap": 1})
            api.post("/jobs/add", {"url": f"{ats_base}/jobs/gh-1?ref=cap", "title": "Cap test", "company": "Northwind"})
            api.post("/apply/start", {"mode": "all", "job_urls": [f"{ats_base}/jobs/gh-1?ref=cap"]})
            st = wait_run(api, "apply", 120)
            api.put("/settings", {"daily_apply_cap": 25})
            _, jobs = api.get("/jobs")
            j = next(j for j in jobs if j["url"].endswith("ref=cap"))
            assert j["status"] == "pending", f"cap ignored: {j['status']}"
            return {"log_tail": (st.get("log") or [])[-5:]}
        step("caps", s_caps)

        def s_collect():
            code, r = api.post("/jobs/collect", {"title": "Data Analyst", "max_jobs": 3, "source": a.collect_source})
            assert r.get("success"), r
            st = wait_run(api, "collect", 900)
            _, jobs = api.get("/jobs")
            real = [j for j in jobs if j.get("source") == a.collect_source]
            return {"collected": st.get("collected"), "error": st.get("error"), "cost_usd": st.get("cost_usd"),
                    "jobs": [(j["title"], j["company"], j.get("match_score"), bool(j.get("description"))) for j in real],
                    "log_tail": (st.get("log") or [])[-12:]}
        step("collect", s_collect)

        def s_export():
            _, dump = api.get("/data/export")
            text = json.dumps(dump)
            assert key not in text, "API key leaked into data export"
            return {"keys": sorted(dump.keys()), "jobs": len(dump.get("jobs", [])), "bytes": len(text)}
        step("export", s_export)

        def s_pack():
            _, pack = api.get("/memory/packs/export")
            _, mem = api.get("/memory/stats")
            return {"pack_memories": len(pack.get("memories", [])), "memory_stats": mem,
                    "sample": pack.get("memories", [])[:3]}
        step("memory_pack", s_pack)

        def s_delete():
            code, r = api.post("/data/delete", {"confirm": True})
            assert code == 200 and r.get("ok"), r
            _, jobs = api.get("/jobs")
            _, llm = api.get("/settings/llm")
            assert jobs == [], "jobs survived delete"
            leftover = (llm.get("openai_compatible") or {}).get("api_key")
            assert not leftover, "API key survived delete"
            return {"deleted": r.get("deleted")}
        step("delete", s_delete)
    finally:
        proc.terminate()
        try:
            proc.wait(10)
        except subprocess.TimeoutExpired:
            proc.kill()
        ats_srv.shutdown()
    passed = sum(1 for r in report if r["ok"])
    print(f"\n{passed}/{len(report)} steps passed. Report: {a.out}. Work dir: {work}")
    sys.exit(0 if passed == len(report) else 1)


if __name__ == "__main__":
    main()
