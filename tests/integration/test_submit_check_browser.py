"""Real applications: a success page over a failed submit must not count as applied (#89).

The repro from the issue: the form POSTs, the server answers 500 and records
nothing, and the page shows "Application submitted!" anyway. The observer
(SubmitInterceptor in observe mode) must let the request through and report
the 500. Opt-in: LANGHIRE_BROWSER_TESTS=1.
"""
import asyncio
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

pytestmark = pytest.mark.skipif(os.environ.get("LANGHIRE_BROWSER_TESTS") != "1",
                                reason="set LANGHIRE_BROWSER_TESTS=1 to run real-browser tests")

PROFILE = {"name": "Jane Doe", "email": "jane.doe@example.com"}

PAGE = """<!doctype html><html><body><form id=f>
<input name=name value="Jane Doe"><input name=email value="jane.doe@example.com">
<button type=submit>Submit application</button></form><p id=ok></p>
<script>document.getElementById('f').onsubmit=async e=>{e.preventDefault();
 try{await fetch('/apply-submit?mode=MODE',{method:'POST',body:new URLSearchParams(new FormData(e.target))})}catch{}
 document.getElementById('ok').textContent='Application submitted!';};</script></body></html>"""


@pytest.fixture
def site():
    received = []

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            mode = "fail" if "fail" in self.path else "ok"
            body = PAGE.replace("MODE", mode).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            n = int(self.headers.get("Content-Length") or 0)
            data = self.rfile.read(n)
            if "mode=fail" in self.path:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(b"internal error")
                return
            received.append(data)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", received
    srv.shutdown()


async def _submit(url: str, tmp_path):
    from browser_use import BrowserSession
    from engine.submit_guard import SubmitInterceptor
    session = BrowserSession(headless=True, user_data_dir=str(tmp_path / "p"))
    await session.start()
    observer = SubmitInterceptor(session, PROFILE, observe=True)
    assert await observer.install()
    try:
        page = await session.get_current_page() or await session.new_page(url)
        await page.goto(url)
        await asyncio.sleep(1.5)
        observer.arm()
        await page.evaluate("() => { document.querySelector('button[type=submit]').click(); return 'ok'; }")
        await asyncio.sleep(3)
        shown = await page.evaluate("() => document.getElementById('ok').textContent")
        return observer, shown
    finally:
        await session.kill()


@pytest.mark.parametrize("mode,verdict,status", [("fail", "rejected", 500), ("ok", "confirmed", 200)])
def test_observer_reports_the_sites_answer(site, tmp_path, mode, verdict, status):
    base, received = site
    observer, shown = asyncio.run(_submit(f"{base}/apply?mode={mode}", tmp_path))
    assert shown == "Application submitted!"  # the page claims success either way
    got, resp = observer.submission_verdict()
    assert got == verdict and resp is not None and resp.status == status
    assert len(received) == (1 if mode == "ok" else 0)  # observe mode never blocks the request
