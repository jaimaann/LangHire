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


def _our_profile_dirs() -> list[Path]:
    main = browser_profile_dir()
    return [main, *sorted(main.parent.glob("browser_profile_w*"))]


def kill_profile_browsers(profile_dir: Path | None = None, timeout: float = 3.0) -> int:
    """Terminate Chromium processes using one of our profile dirs. Returns how many."""
    try:
        import psutil
    except ImportError:  # psutil is a declared dependency; never fall back to killing all Chrome
        _log.warning("psutil missing; skipping browser cleanup")
        return 0
    dirs = [profile_dir] if profile_dir else _our_profile_dirs()
    procs = []
    for proc in psutil.process_iter(["pid", "cmdline"]):
        try:
            cmd = proc.info.get("cmdline") or []
            if cmd and any(profile_args_match(cmd, d) for d in dirs):
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


_CLONE_SKIP = ("Cache", "Code Cache", "GPUCache", "Service Worker", "ShaderCache", "GrShaderCache",
               "Crashpad", "SingletonLock", "SingletonCookie", "SingletonSocket", "lockfile")


def worker_profile_dir(worker_id: int) -> Path:
    """Chrome locks a profile directory, so parallel workers can't share one.

    Worker 1 uses the main profile (where the user logged in); workers 2+ get a
    copy of it (logins included, caches and lock files skipped), refreshed when
    the main profile is newer.
    """
    main = browser_profile_dir()
    if worker_id <= 1:
        return main
    clone = main.parent / f"browser_profile_w{worker_id}"
    main.mkdir(parents=True, exist_ok=True)
    stamp = clone / ".cloned_at"
    main_mtime = max((p.stat().st_mtime for p in main.glob("Default/**/Cookies")), default=0.0)
    if not stamp.exists() or float(stamp.read_text() or 0) < main_mtime:
        import shutil
        shutil.rmtree(clone, ignore_errors=True)
        shutil.copytree(main, clone, ignore=shutil.ignore_patterns(*_CLONE_SKIP), dirs_exist_ok=True)
        stamp.write_text(str(main_mtime))
    return clone


def make_browser_session(worker_id: int = 1, **overrides):
    """A browser-use session: the user's own Chrome over CDP if configured, else our profile."""
    from browser_use import BrowserSession
    settings = load_settings()
    cdp_url = (settings.get("browser_cdp_url") or "").strip()
    if cdp_url:
        return BrowserSession(cdp_url=cdp_url, **overrides)
    kwargs: dict = {
        "user_data_dir": str(worker_profile_dir(worker_id)),
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
