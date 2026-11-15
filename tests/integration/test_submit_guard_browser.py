"""The submit-intercept test mode must never let an application reach the server.

Real Chromium against the local mock ATS, which records every submission it
receives. Opt-in: LANGHIRE_BROWSER_TESTS=1.
"""
import asyncio
import json
import os
import socket
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "fixtures" / "ats"))

pytestmark = pytest.mark.skipif(os.environ.get("LANGHIRE_BROWSER_TESTS") != "1",
                                reason="set LANGHIRE_BROWSER_TESTS=1 to run real-browser tests")

PROFILE = {"name": "Jordan Rivera", "email": "jordan.rivera@example.com", "phone": "5125550142"}

FILL_JS = """(doc) => {
  const d = doc || document;
  const set = (sel, v) => { const el = d.querySelector(sel); if (el) { el.value = v; } };
  set('#first_name', 'Jordan'); set('#last_name', 'Rivera'); set('#email', 'jordan.rivera@example.com');
  set('#phone', '5125550142'); set('[name=q_sql_years]', '3'); set('[name=q_why]', 'Because data.');
  for (const s of d.querySelectorAll('select[required]')) s.value = s.options[1].value;
  const c = d.querySelector('[name=consent]'); if (c) c.checked = true;
  const f = d.querySelector('input[type=file]');
  if (f) { const dt = new DataTransfer(); dt.items.add(new File(['%PDF-1.4 test'], 'r.pdf', {type: 'application/pdf'})); f.files = dt.files; }
  return 'ok';
}"""


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture
def ats(tmp_path):
    import server as ats_server
    port = _free_port()
    out = tmp_path / "subs"
    srv = ats_server.serve(port, out)
    yield f"http://127.0.0.1:{port}", out
    srv.shutdown()


async def _run(url: str, how: str, tmp_path) -> tuple[list, int]:
    from browser_use import BrowserSession
    from engine.submit_guard import SubmitInterceptor
    session = BrowserSession(headless=True, user_data_dir=str(tmp_path / "p"))
    await session.start()
    guard = SubmitInterceptor(session, PROFILE)
    assert await guard.install()
    try:
        page = await session.get_current_page() or await session.new_page(url)
        await page.goto(url)
        await asyncio.sleep(1.5)
        if how == "iframe":
            # fill + submit inside the cross-origin frame, on its own CDP target
            root = session._cdp_client_root
            targets = (await root.send.Target.getTargets())["targetInfos"]
            frames = [t for t in targets if t["type"] == "iframe"]
            assert frames, f"expected an out-of-process iframe target, got {[t['type'] for t in targets]}"
            att = await root.send.Target.attachToTarget(params={"targetId": frames[0]["targetId"], "flatten": True})
            expr = f"({FILL_JS})(document); document.querySelector('button[type=submit]').click(); 'ok'"
            guard.arm()
            await root.send.Runtime.evaluate(params={"expression": expr}, session_id=att["sessionId"])
        else:
            await page.evaluate(FILL_JS)
            if how == "button":
                guard.arm()
                await page.evaluate("() => { document.querySelector('button[type=submit]').click(); return 'ok'; }")
            else:  # Enter-key style submit, guard NOT armed: must be caught by the body check
                await page.evaluate("() => { document.querySelector('form').requestSubmit ? "
                                    "HTMLFormElement.prototype.requestSubmit.call(document.querySelector('form')) : "
                                    "document.querySelector('form').submit(); return 'ok'; }")
        await asyncio.sleep(4)
        return guard.blocked, 0
    finally:
        await session.kill()


@pytest.mark.parametrize("how,path", [("button", "/jobs/gh-1/apply"), ("enter", "/jobs/gh-1/apply"),
                                      ("iframe", "/embed/gh-1")])
def test_application_never_reaches_server(ats, tmp_path, how, path):
    base, out = ats
    blocked, _ = asyncio.run(_run(base + path, how, tmp_path))
    received = list(out.glob("*.json")) if out.exists() else []
    assert received == [], f"submission leaked: {[json.loads(p.read_text()) for p in received]}"
    assert blocked, "the guard should have intercepted the application request"
