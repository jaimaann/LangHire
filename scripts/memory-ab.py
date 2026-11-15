"""Does the self-learning memory actually help? A/B on the mock ATS, in test mode.

Run 1: no memories (cold).  Run 2: same job, with what run 1 learned.
Run 3: memories wiped again (cold control). Compares steps, time and outcome,
and checks that run 2's prompt really contained the learned memories.

    LANGHIRE_E2E_BASE_URL=... LANGHIRE_E2E_MODEL=... LANGHIRE_E2E_API_KEY=... \
    uv run python scripts/memory-ab.py --resume r.pdf --job gh-1 --out memory-ab.json
"""
import argparse
import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "fixtures" / "ats"))
sys.path.insert(0, str(ROOT / "scripts"))
import server as ats  # noqa: E402

PROFILE = {
    "name": "Jordan Rivera", "email": "jordan.rivera@example.com", "phone": "5125550142", "phone_country_code": "+1",
    "country": "US", "address": {"city": "Austin", "state": "TX", "zip": "78701", "country": "USA"},
    "work_authorization": "US citizen", "visa_sponsorship_needed": False, "years_of_experience": 3,
    "current_role": "Data Analyst", "skills": ["SQL", "Python", "Tableau"], "target_job_titles": ["Data Analyst"],
    "target_locations": ["Austin, TX"], "languages": ["English"],
    "education": {"degree": "B.S. Statistics", "school": "UT Austin", "graduation": "2021"},
}


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--resume", required=True)
    ap.add_argument("--job", default="gh-1")
    ap.add_argument("--out", default="memory-ab.json")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    work = Path(tempfile.mkdtemp(prefix="langhire-memab-"))
    ats_port, api_port, token = free_port(), free_port(), secrets.token_hex(8)
    srv = ats.serve(ats_port, work / "subs")
    env = {**os.environ, "LANGHIRE_DATA_DIR": str(work / "data"), "LANGHIRE_PORT": str(api_port),
           "LANGHIRE_API_TOKEN": token, "LANGHIRE_ALLOW_LOCAL_URLS": "1", "LANGHIRE_NO_WATCHDOG": "1",
           "PYTHONUTF8": "1"}
    key = env.pop("LANGHIRE_E2E_API_KEY")
    log = open(work / "backend.log", "w", encoding="utf-8")
    proc = subprocess.Popen([sys.executable, str(ROOT / "backend" / "main.py")], env=env, stdout=log,
                            stderr=subprocess.STDOUT)
    os.environ["LANGHIRE_PORT"], os.environ["LANGHIRE_API_TOKEN"] = str(api_port), token
    from lh import call
    results = []
    try:
        for _ in range(60):
            try:
                if call("GET", "/health", timeout=3):
                    break
            except Exception:
                time.sleep(1)
        call("PUT", "/settings/llm", {"provider": "openai_compatible", "openai_compatible": {
            "base_url": os.environ["LANGHIRE_E2E_BASE_URL"], "model": os.environ["LANGHIRE_E2E_MODEL"], "api_key": key}})
        call("PUT", "/settings", {"resume_path": str(Path(a.resume).resolve())})
        call("PUT", "/profile", PROFILE)
        url = f"http://127.0.0.1:{ats_port}/jobs/{a.job}"
        call("POST", "/jobs/add", {"url": url, "title": "Data Analyst", "company": "Northwind"})
        for label, wipe in (("cold", False), ("with_memory", False), ("cold_control", True)):
            if wipe:
                call("POST", "/memory/cleanup", {"threshold": 1.0})
            mem_before = call("GET", "/memory/stats").get("total_memories", 0)
            t0 = time.time()
            call("POST", "/apply/start", {"mode": "all", "job_url": url, "test_mode": True})
            time.sleep(3)
            while call("GET", "/apply/status").get("running"):
                time.sleep(10)
            rec = call("GET", f"/applications?job_url={url}")[0]
            injected = sum(1 for line in open(work / "backend.log", encoding="utf-8")
                           if "Injecting" in line and "memories" in line)
            results.append({"run": label, "memories_available": mem_before, "outcome": rec["outcome"],
                            "steps": rec["steps"], "seconds": round(time.time() - t0),
                            "intercepted": rec["intercepted"], "injection_log_lines": injected})
            print(json.dumps(results[-1]))
        mems = call("GET", "/memory/search?q=&limit=100")
        results.append({"memory_stats": call("GET", "/memory/stats"), "sample": mems[:5] if isinstance(mems, list) else []})
    finally:
        proc.terminate()
        srv.shutdown()
    Path(a.out).write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print("work dir:", work)


if __name__ == "__main__":
    main()
