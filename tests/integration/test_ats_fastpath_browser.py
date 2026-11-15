"""Browser test for the ATS fast path against the local mock ATS (no LLM, no network).

Runs only when a Chromium is available and LANGHIRE_BROWSER_TESTS=1, because it
launches a real browser:

    LANGHIRE_BROWSER_TESTS=1 uv run pytest tests/integration -q
"""
import asyncio
import os
import socket
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "fixtures" / "ats"))

pytestmark = pytest.mark.skipif(os.environ.get("LANGHIRE_BROWSER_TESTS") != "1",
                                reason="set LANGHIRE_BROWSER_TESTS=1 to run real-browser tests")

PROFILE = {"name": "Jordan Rivera", "email": "jordan.rivera@example.com", "phone": "5125550142",
           "phone_country_code": "+1", "current_company": "Acme Data", "linkedin_url": "https://linkedin.com/in/jr"}


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture
def ats_server(tmp_path):
    import server as ats
    port = _free_port()
    srv = ats.serve(port, tmp_path / "subs")
    yield f"http://127.0.0.1:{port}"
    srv.shutdown()


async def _fill(url: str, spec_url: str, tmp_path) -> dict:
    from browser_use import BrowserSession
    from engine import ats_fastpath
    session = BrowserSession(headless=True, user_data_dir=str(tmp_path / "profile"))
    await session.start()
    try:
        page = await session.get_current_page() or await session.new_page(url)
        await page.goto(url)
        await asyncio.sleep(1)
        import json
        spec = ats_fastpath.build_spec(spec_url, PROFILE)
        filled = json.loads(await page.evaluate(ats_fastpath._FILL_JS, spec))
        values = json.loads(await page.evaluate(
            "() => JSON.stringify(Object.fromEntries([...document.querySelectorAll('input')]"
            ".filter(i => i.name).map(i => [i.name, i.value])))"))
        return {"filled": filled, "values": values}
    finally:
        await session.kill()


def test_greenhouse_form_prefill(ats_server, tmp_path):
    out = asyncio.run(_fill(f"{ats_server}/jobs/gh-1/apply", "https://boards.greenhouse.io/x/jobs/1", tmp_path))
    assert set(out["filled"]) >= {"first_name", "last_name", "email", "phone"}
    assert out["values"]["first_name"] == "Jordan"
    assert out["values"]["last_name"] == "Rivera"
    assert out["values"]["email"] == "jordan.rivera@example.com"


def test_lever_form_prefill(ats_server, tmp_path):
    out = asyncio.run(_fill(f"{ats_server}/jobs/lv-1/apply", "https://jobs.lever.co/x/1/apply", tmp_path))
    assert out["values"]["name"] == "Jordan Rivera"
    assert out["values"]["org"] == "Acme Data"
    assert out["values"]["urls[LinkedIn]"] == "https://linkedin.com/in/jr"


def test_generic_autocomplete_prefill(ats_server, tmp_path):
    # An unknown host: only the standard autocomplete/type selectors apply
    out = asyncio.run(_fill(f"{ats_server}/jobs/gh-1/apply", "https://careers.example.com/apply", tmp_path))
    assert out["values"]["first_name"] == "Jordan"
    assert out["values"]["email"] == "jordan.rivera@example.com"
