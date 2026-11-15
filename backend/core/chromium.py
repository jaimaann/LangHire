"""Finding and installing the Chromium build the agent drives."""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
from pathlib import Path

_log = logging.getLogger("backend")

# ── Playwright Chromium Discovery ─────────────────────────────────────────
def find_playwright_chromium() -> str | None:
    """Find the Playwright-installed Chromium/Chrome binary.

    Handles both old and new Playwright naming conventions:
      Old: chromium-*/chrome-mac/Chromium.app/.../Chromium
      New: chromium-*/chrome-mac-arm64/Google Chrome for Testing.app/.../Google Chrome for Testing
    Searches in the correct OS-specific Playwright cache directory.
    """
    import glob as _glob

    home = Path.home()

    # Playwright browser cache directories (OS-specific)
    cache_dirs = []
    if sys.platform == "darwin":
        cache_dirs.append(home / "Library" / "Caches" / "ms-playwright")
    elif sys.platform == "win32":
        local_app = os.environ.get("LOCALAPPDATA", str(home / "AppData" / "Local"))
        cache_dirs.append(Path(local_app) / "ms-playwright")
    cache_dirs.append(home / ".cache" / "ms-playwright")

    # Also check inside the venv's playwright package
    try:
        import importlib
        pw_module = importlib.import_module("playwright")
        venv_browsers = Path(pw_module.__file__).parent / "driver" / "package" / ".local-browsers"
        if venv_browsers.exists():
            cache_dirs.insert(0, venv_browsers)
    except (ImportError, AttributeError):
        pass

    # macOS executable patterns (both old and new Playwright naming)
    mac_patterns = [
        # New Playwright (v1.40+): Google Chrome for Testing
        "chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
        "chrome-mac/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
        # Old Playwright: Chromium
        "chrome-mac/Chromium.app/Contents/MacOS/Chromium",
        "chrome-mac-arm64/Chromium.app/Contents/MacOS/Chromium",
    ]

    for cache_dir in cache_dirs:
        if not cache_dir.exists():
            continue
        # Sort chromium dirs by version number descending (newest first)
        chromium_dirs = sorted(cache_dir.glob("chromium-*"), reverse=True)
        for chromium_dir in chromium_dirs:
            if sys.platform == "darwin":
                for pattern in mac_patterns:
                    exe = chromium_dir / pattern
                    if exe.exists():
                        return str(exe)
            elif sys.platform == "win32":
                for pattern in ["chrome-win/chrome.exe", "chrome-win64/chrome.exe"]:
                    exe = chromium_dir / pattern
                    if exe.exists():
                        return str(exe)
            else:  # Linux
                for pattern in ["chrome-linux/chrome", "chrome-linux64/chrome"]:
                    exe = chromium_dir / pattern
                    if exe.exists():
                        return str(exe)

    return None


# ── Chromium Auto-Install ─────────────────────────────────────────────────
chromium_status: dict = {"state": "checking", "message": "Checking for Chromium..."}


def get_playwright_install_cmd() -> list[str] | None:
    """Build the command to run `playwright install chromium`.
    Works in both frozen (PyInstaller) and development modes."""
    # Use the bundled Playwright driver (node + cli.js)
    try:
        from playwright._impl._driver import compute_driver_executable
        result = compute_driver_executable()
        if isinstance(result, tuple):
            node_bin, cli_js = result
            if os.path.exists(node_bin) and os.path.exists(cli_js):
                return [str(node_bin), str(cli_js), "install", "chromium"]
        elif os.path.exists(str(result)):
            return [str(result), "install", "chromium"]
    except (ImportError, Exception) as e:
        _log.warning(f"Bundled Playwright driver not usable: {e}")

    # Fallback: try system playwright
    import shutil
    if shutil.which("playwright"):
        return ["playwright", "install", "chromium"]
    for python in ["python3", "python"]:
        if shutil.which(python):
            try:
                r = subprocess.run([python, "-m", "playwright", "--version"],
                                   capture_output=True, text=True, timeout=10)
                if r.returncode == 0:
                    return [python, "-m", "playwright", "install", "chromium"]
            except Exception:
                pass
    return None


def ensure_chromium_async():
    """Check if Playwright Chromium is installed, install in background if not.
    Updates chromium_status so the frontend can poll progress."""
    global chromium_status

    if find_playwright_chromium() is not None:
        chromium_status = {"state": "ready", "message": "Chromium found"}
        _log.info("Chromium found")
        return

    chromium_status = {"state": "installing", "message": "Installing Chromium (one-time download, ~400MB)..."}
    _log.info("Chromium not found — installing in background")

    def _install():
        global chromium_status
        try:
            cmd = get_playwright_install_cmd()
            if not cmd:
                chromium_status = {"state": "failed", "message": "Could not find Playwright installer. Please reinstall the application."}
                _log.error("No working Playwright install command found")
                return
            _log.info(f"Chromium install command: {cmd}")
            chromium_status = {"state": "installing", "message": "Downloading Chromium browser (~162 MB). This may take a few minutes, please don't close the app..."}

            # Monitor the download directory for progress instead of parsing stdout
            # (Playwright suppresses progress bars when stdout is not a TTY)
            import re as _re
            cache_dir = Path.home() / "Library" / "Caches" / "ms-playwright"
            if sys.platform == "win32":
                local_app = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
                cache_dir = Path(local_app) / "ms-playwright"
            elif sys.platform != "darwin":
                cache_dir = Path.home() / ".cache" / "ms-playwright"

            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            )

            # Poll the download directory size while process runs
            while proc.poll() is None:
                import time as _t
                _t.sleep(3)
                # Check for partial download files
                try:
                    total_bytes = 0
                    for f in cache_dir.rglob("*"):
                        if f.is_file():
                            total_bytes += f.stat().st_size
                    mb = total_bytes / (1024 * 1024)
                    if mb > 1:
                        chromium_status = {"state": "installing", "message": f"Downloading Chromium... {mb:.0f} MB downloaded. Please don't close the app."}
                except Exception:
                    pass

            # Read any remaining output
            out = proc.stdout.read()
            if out:
                text = out.decode("utf-8", errors="replace").strip()
                clean = _re.sub(r'\x1b\[[0-9;]*m', '', text)
                for line in clean.splitlines():
                    if line.strip():
                        _log.info(f"Chromium: {line.strip()}")
            if proc.returncode == 0:
                chromium_status = {"state": "ready", "message": "Chromium installed successfully"}
                _log.info("Chromium installed successfully")
            else:
                cur_msg = chromium_status.get("message", "Unknown error")
                chromium_status = {"state": "failed", "message": f"Install failed: {cur_msg}"}
                _log.error(f"Chromium install failed (code {proc.returncode}): {cur_msg}")
        except Exception as e:
            msg = str(e)
            chromium_status = {"state": "failed", "message": f"Install failed: {msg[:200]}"}
            _log.error(f"Chromium install error: {e}")

    threading.Thread(target=_install, daemon=True, name="chromium-install").start()
