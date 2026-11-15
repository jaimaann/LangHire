"""Browser sessions for the agent, and cleanup that only touches our browsers.

The old cleanup matched the POSIX string ``langhire/browser_profile`` (never
true on Windows, where paths use backslashes) and, without psutil, fell back to
``taskkill /IM chrome.exe`` — which closes every Chrome window the user has.
Here we match the exact ``--user-data-dir`` of our profile, normalised for the
OS, and never kill anything else.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from core.config import load_settings
from core.shared_config import browser_profile_dir

_log = logging.getLogger("engine")


def _norm(p: str) -> str:
    return os.path.normcase(os.path.normpath(os.path.abspath(p.strip().strip('"'))))


def profile_args_match(cmdline: list[str], profile_dir: Path) -> bool:
    """True when a process command line uses exactly our --user-data-dir."""
    target = _norm(str(profile_dir))
    args = list(cmdline)
    for i, arg in enumerate(args):
        value = None
        if arg.startswith("--user-data-dir="):
            value = arg.split("=", 1)[1]
        elif arg == "--user-data-dir" and i + 1 < len(args):
            value = args[i + 1]
        if value is not None and _norm(value) == target:
            return True
    return False


def kill_profile_browsers(profile_dir: Path | None = None, timeout: float = 3.0) -> int:
    """Terminate Chromium processes using our profile dir. Returns how many."""
    try:
        import psutil
    except ImportError:  # psutil is a declared dependency; never fall back to killing all Chrome
        _log.warning("psutil missing; skipping browser cleanup")
        return 0
    profile_dir = profile_dir or browser_profile_dir()
    procs = []
    for proc in psutil.process_iter(["pid", "cmdline"]):
        try:
            cmd = proc.info.get("cmdline") or []
            if cmd and profile_args_match(cmd, profile_dir):
                procs.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    for proc in procs:
        try:
            proc.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    _, alive = psutil.wait_procs(procs, timeout=timeout)
    for proc in alive:
        try:
            proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    if procs:
        _log.info(f"Closed {len(procs)} leftover browser process(es)")
    return len(procs)


def make_browser_session(**overrides):
    """A browser-use session: the user's own Chrome over CDP if configured, else our profile."""
    from browser_use import BrowserSession
    settings = load_settings()
    cdp_url = (settings.get("browser_cdp_url") or "").strip()
    if cdp_url:
        return BrowserSession(cdp_url=cdp_url, **overrides)
    kwargs: dict = {
        "user_data_dir": str(browser_profile_dir()),
        "chromium_sandbox": sys.platform != "linux",
    }
    kwargs.update(overrides)
    return BrowserSession(**kwargs)  # type: ignore[call-overload]


def uses_own_chrome() -> bool:
    return bool((load_settings().get("browser_cdp_url") or "").strip())


async def close_session(browser) -> None:
    """Close a session we opened.

    browser-use's ``close()`` is an alias of ``stop()``, which leaves the Chromium
    process running — the old code leaked one browser per job. ``kill()`` ends
    it. With the user's own Chrome (CDP) we only disconnect.
    """
    try:
        if uses_own_chrome():
            await browser.stop()
        else:
            await browser.kill()
    except Exception as e:
        _log.info(f"browser close: {e}")
