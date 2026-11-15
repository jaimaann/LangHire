"""End-to-end test stack: the real backend, the real browser agent, the built UI.

Everything runs locally and offline, so the suite can run on every commit on
Linux, Windows and macOS with no API keys:

  * mock ATS       tests/fixtures/ats/server.py   job postings + application forms
  * scripted LLM   tests/fixtures/llm/server.py   OpenAI-compatible, rule-based "agent"
  * backend        backend/main.py (or a built binary via LANGHIRE_E2E_BACKEND)
  * UI             dist/ (npm run build), served statically and driven by Playwright;
                   the Tauri host is replaced by a stub that hands over port + token

Enable with LANGHIRE_E2E=1 (the tests are skipped otherwise, so `pytest tests/`
in the unit-test job stays fast).
"""
from __future__ import annotations

import functools
import http.server
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

TOKEN = "e2e-token"


def pytest_collection_modifyitems(config, items):
    if os.environ.get("LANGHIRE_E2E") == "1":
        return
    skip = pytest.mark.skip(reason="end-to-end tests: set LANGHIRE_E2E=1")
    for item in items:
        if "tests/e2e" in str(item.fspath).replace("\\", "/"):
            item.add_marker(skip)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Backend:
    def __init__(self, port: int, data_dir: Path, proc: subprocess.Popen, log: Path):
        self.port, self.data_dir, self.proc, self.log = port, data_dir, proc, log
        self.base = f"http://127.0.0.1:{port}"

    def call(self, method: str, path: str, body=None, timeout: float = 60):
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(self.base + path, data=data, method=method, headers={
            "Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read() or b"null")
        except urllib.error.HTTPError as e:
            return json.loads(e.read() or b"null")

    def wait_idle(self, kind: str = "apply", timeout: float = 600) -> dict:
        path = "/apply/status" if kind == "apply" else "/jobs/collect/status"
        end = time.time() + timeout
        status: dict = {}
        while time.time() < end:
            status = self.call("GET", path)
            if not status.get("running"):
                return status
            time.sleep(2)
        raise AssertionError(f"{kind} run still going after {timeout}s; log tail:\n{self.tail()}")

    def tail(self, n: int = 60) -> str:
        try:
            return "\n".join(self.log.read_text(encoding="utf-8", errors="replace").splitlines()[-n:])
        except OSError:
            return ""


def _make_resume(path: Path) -> Path:
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page()
    text = ("Dana Tester\ndana.tester@example.com | +1 512 555 0142 | Austin, TX\n\n"
            "EXPERIENCE\nData Analyst, Acme Corp (2021-2024)\n- Built Tableau dashboards and SQL reports\n"
            "- Automated weekly reporting with Python\n\nSKILLS\nSQL, Python, Tableau, Excel\n\n"
            "EDUCATION\nB.S. Statistics, University of Texas (2021)\n")
    page.insert_text((56, 72), text, fontsize=11)
    doc.save(str(path))
    return path


def _load(name: str, rel: str):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="session")
def ats(tmp_path_factory):
    out = tmp_path_factory.mktemp("submissions")
    httpd = _load("mock_ats", "tests/fixtures/ats/server.py").serve(_free_port(), out)
    yield {"base": f"http://127.0.0.1:{httpd.server_address[1]}", "submissions": out}
    httpd.shutdown()


@pytest.fixture(scope="module")
def llm():
    httpd, state = _load("scripted_llm", "tests/fixtures/llm/server.py").serve(0)
    yield {"base_url": f"http://127.0.0.1:{httpd.server_address[1]}/v1", "state": state}
    httpd.shutdown()


@pytest.fixture(scope="module")
def backend(tmp_path_factory, llm):
    """A fresh backend (and data folder) per test module, so modules don't depend on each other."""
    data = tmp_path_factory.mktemp("langhire-data")
    port = _free_port()
    log = data.parent / "backend.out"
    env = {**os.environ,
           "LANGHIRE_DATA_DIR": str(data), "LANGHIRE_API_TOKEN": TOKEN, "LANGHIRE_PORT": str(port),
           "LANGHIRE_NO_WATCHDOG": "1", "LANGHIRE_ALLOW_LOCAL_URLS": "1", "LANGHIRE_SECRETS_BACKEND": "file",
           "PYTHONUTF8": "1", "ANONYMIZED_TELEMETRY": "false", "LANGHIRE_HEADLESS": "1", "BROWSER_USE_SETUP_LOGGING": "false"}
    binary = os.environ.get("LANGHIRE_E2E_BACKEND")
    cmd = [binary] if binary else [sys.executable, str(ROOT / "backend" / "main.py")]
    fh = open(log, "w", encoding="utf-8")
    proc = subprocess.Popen(cmd, cwd=str(ROOT), env=env, stdout=fh, stderr=subprocess.STDOUT)
    be = Backend(port, data, proc, log)
    end = time.time() + 120
    while time.time() < end:
        if proc.poll() is not None:
            raise AssertionError(f"backend exited with {proc.returncode}:\n{be.tail()}")
        try:
            with urllib.request.urlopen(be.base + "/health", timeout=2):
                break
        except OSError:
            time.sleep(0.5)
    else:
        raise AssertionError(f"backend did not start:\n{be.tail()}")

    resume = _make_resume(data.parent / "resume.pdf")
    be.call("PUT", "/settings/llm", {"provider": "openai_compatible", "openai_compatible": {
        "base_url": llm["base_url"], "model": "scripted-agent", "api_key": "not-needed"}})
    profile = be.call("GET", "/profile")
    profile.update({"name": "Dana Tester", "email": "dana.tester@example.com", "phone": "5125550142",
                    "phone_country_code": "+1", "country": "US", "work_authorization": "US Citizen",
                    "years_of_experience": 3, "skills": ["SQL", "Python", "Tableau"],
                    "target_job_titles": ["Data Analyst"], "target_locations": ["Austin, TX"]})
    be.call("PUT", "/profile", profile)
    settings = be.call("GET", "/settings")
    settings.update({"resume_path": str(resume), "onboarding_completed": True, "daily_apply_cap": 100,
                     "stagger_delay": 0})
    be.call("PUT", "/settings", settings)
    yield be
    proc.terminate()
    try:
        proc.wait(timeout=20)
    except subprocess.TimeoutExpired:
        proc.kill()
    fh.close()


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass


@pytest.fixture(scope="session")
def ui():
    """The production UI bundle (dist/), served statically. Build it first: npm run build."""
    dist = ROOT / "dist"
    if not (dist / "index.html").exists():
        pytest.skip("dist/ not built: run `npm run build` first")
    # The backend only answers its own app's origins (CORS + an origin check); 127.0.0.1:1420
    # is the allowed dev origin, so the UI is served from exactly there.
    try:
        httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 1420),
                                                functools.partial(_QuietHandler, directory=str(dist)))
    except OSError as e:
        pytest.fail(f"port 1420 is busy (is `npm run dev` running?): {e}")
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


# Replaces the Tauri host: the UI asks it for the backend's port and token.
TAURI_STUB = """
window.__TAURI_INTERNALS__ = {
  metadata: {currentWindow: {label: 'main'}, currentWebview: {label: 'main', windowLabel: 'main'}},
  transformCallback: (cb) => { const id = Math.random(); window['_' + id] = cb; return id; },
  invoke: async (cmd, args) => {
    if (cmd === 'get_backend_info') return {port: %d, token: '%s', managed: false, status: 'running'};
    if (cmd && cmd.startsWith('plugin:')) return null;
    return null;
  },
  convertFileSrc: (p) => p,
};
"""


@pytest.fixture
def page(ui, backend):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=os.environ.get("LANGHIRE_E2E_HEADED") != "1")
        context = browser.new_context(viewport={"width": 1280, "height": 860})
        context.add_init_script(TAURI_STUB % (backend.port, TOKEN))
        pg = context.new_page()
        errors: list[str] = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.errors = errors  # type: ignore[attr-defined]
        pg.goto(ui)
        yield pg
        context.close()
        browser.close()
