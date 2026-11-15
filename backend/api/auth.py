"""Job-site login sessions in the shared browser profile.

Previously only LinkedIn and Gmail were supported. Any source plugin that
declares ``login_url`` (and ``auth_cookies`` for the status check) now works.
"""
from __future__ import annotations

import logging
import shutil
import sqlite3
import sys
import tempfile
import threading
from pathlib import Path

from fastapi import APIRouter

from core import chromium
from core.config import get_data_dir

from .common import plugin_registry

router = APIRouter()
_log = logging.getLogger("backend")

GMAIL = {"login_url": "https://accounts.google.com/signin/v2/identifier?service=mail",
         "cookies": [("google.com", ("SID", "SSID", "HSID"), 2)]}

_login_running = False


def browser_profile_dir() -> str:
    """The shared browser profile. Migrates old per-worker profiles once."""
    data_dir = get_data_dir()
    profile = data_dir / "browser_profile"
    profile.mkdir(parents=True, exist_ok=True)
    if not (profile / "Default" / "Cookies").exists():
        for old_name in ["browser_profile_w1", "browser_profile_collect"]:
            old = data_dir / old_name
            if (old / "Default" / "Cookies").exists():
                for item in old.iterdir():
                    dest = profile / item.name
                    if not dest.exists():
                        if item.is_dir():
                            shutil.copytree(item, dest)
                        else:
                            shutil.copy2(item, dest)
                _log.info(f"Migrated browser profile from {old_name}")
                break
    return str(profile)


def _services() -> dict[str, dict]:
    """service name -> {login_url, cookies: [(host suffix, names, min count)]}"""
    out: dict[str, dict] = {}
    for p in plugin_registry().get_all():
        if p.login_url:
            cookies = [(c.domain.lstrip("."), (c.name,), 1) for c in p.auth_cookies]
            out[p.name] = {"login_url": p.login_url, "cookies": cookies, "display_name": p.display_name}
    out["gmail"] = {**GMAIL, "display_name": "Gmail"}
    return out


def _cookie_db(profile_dir: str) -> Path | None:
    for rel in (("Default", "Network", "Cookies"), ("Default", "Cookies")):
        p = Path(profile_dir).joinpath(*rel)
        if p.exists():
            return p
    return None


@router.get("/auth/status")
async def auth_status():
    services = _services()
    result = {name: {"logged_in": False, "display_name": s["display_name"]} for name, s in services.items()}
    cookies_db = _cookie_db(browser_profile_dir())
    if cookies_db is None:
        return result
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir) / "Cookies"
            shutil.copy2(cookies_db, tmp)
            conn = sqlite3.connect(str(tmp))
            try:
                for name, svc in services.items():
                    if not svc["cookies"]:
                        continue
                    ok = True
                    for host, names, minimum in svc["cookies"]:
                        marks = ",".join("?" for _ in names)
                        n = conn.execute(
                            f"SELECT COUNT(*) FROM cookies WHERE (host_key = ? OR host_key LIKE ?) AND name IN ({marks})",
                            (host, f"%.{host}", *names),
                        ).fetchone()[0]
                        ok = ok and n >= minimum
                    result[name]["logged_in"] = ok
            finally:
                conn.close()
    except Exception as e:
        _log.warning(f"Cookie check failed: {e}")
    return result


@router.post("/auth/login/{service}")
async def auth_login(service: str):
    """Open a visible browser on the service's login page, using the agent's profile."""
    global _login_running
    services = _services()
    if service not in services:
        return {"success": False, "message": f"Unknown service: {service}"}
    if _login_running:
        return {"success": False, "message": "A login browser is already open. Please use it or close it first."}
    url = services[service]["login_url"]
    profile_dir = browser_profile_dir()

    def _run():
        global _login_running
        _login_running = True
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                args = ["--no-first-run", "--no-default-browser-check"]
                if sys.platform == "linux":
                    args.append("--no-sandbox")
                kwargs = {"user_data_dir": profile_dir, "headless": False, "args": args,
                          "ignore_default_args": ["--enable-automation"]}
                exe = chromium.find_playwright_chromium()
                if exe:
                    kwargs["executable_path"] = exe
                context = p.chromium.launch_persistent_context(**kwargs)
                page = context.pages[0] if context.pages else context.new_page()
                page.goto(url, wait_until="domcontentloaded")
                try:
                    while len(context.pages) > 0:
                        context.pages[0].wait_for_event("close", timeout=300000)
                except Exception:
                    pass
                finally:
                    try:
                        context.close()
                    except Exception:
                        pass
        except Exception as e:
            _log.error(f"Login browser error: {e}", exc_info=True)
        finally:
            _login_running = False

    threading.Thread(target=_run, daemon=True, name=f"login-{service}").start()
    return {"success": True, "message": f"Browser opened for {services[service]['display_name']} login. "
                                        "Log in, then close the browser window."}
