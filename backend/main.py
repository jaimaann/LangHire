"""
Python backend for LangHire desktop app.
Runs as a local FastAPI server (sidecar process launched by Tauri).
"""
import json
import signal
import subprocess
import sys
import os
import threading
import uuid
from datetime import datetime
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

try:
    from models import CollectRequest, ApplyRequest, DecayRequest, CleanupRequest
except ImportError:
    from backend.models import CollectRequest, ApplyRequest, DecayRequest, CleanupRequest

from core.config import get_data_dir, load_settings, save_settings, load_profile, save_profile
from core.config import load_llm_settings, save_llm_settings

# Project root for data files
PROJECT_ROOT = Path(__file__).parent.parent
DEFAULT_PORT = 8742
MAX_LOG_LINES = 500
CREDENTIAL_REFRESH_MINUTES = 14


# ── Lifespan ──────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""
    _log.info("Backend starting (build 20260425-v3)...")
    data_dir = get_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    _log.info(f"Data directory: {data_dir}")
    _log.info(f"Token prefix: {_API_TOKEN[:8]}...")
    # Clean up orphaned browser processes from previous crash
    _kill_browser_processes()
    # Reset any jobs stuck in "in_progress" from a previous crash
    _recover_stale_jobs()
    # Clean up old run logs (>30 days)
    _metrics = _get_metrics_store()
    if _metrics:
        cleaned = _metrics.cleanup_old_logs(days=30)
        if cleaned:
            _log.info(f"Cleaned up {cleaned} old log entries")
    # Auto-install Chromium if needed (runs in background so /health is available immediately)
    _ensure_chromium_async()
    # Start parent-process watchdog (self-terminate if Tauri app dies)
    _start_parent_watchdog()
    yield
    # Graceful shutdown: stop running operations
    import traceback
    _log.info(f"Backend shutting down... (trigger: lifespan exit)")
    _log.info(f"Shutdown stack:\n{''.join(traceback.format_stack())}")
    for status_dict in (_collection_status, _apply_status):
        if status_dict.get("running"):
            _force_stop(status_dict)
    # Give workers a moment to clean up, then force-kill browsers
    import time
    time.sleep(2)
    _kill_browser_processes()

app = FastAPI(title="LangHire Backend", version="1.0.0", lifespan=lifespan)

# ── Auth token (generated per-session, written to data dir for frontend) ──
import secrets as _secrets
import logging
from logging.handlers import RotatingFileHandler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        RotatingFileHandler(
            get_data_dir() / "backend.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
        ),
        logging.StreamHandler(),
    ],
)
# Silence noisy low-level loggers but keep browser_use agent logs visible
for _noisy in (
    "browser_use.dom", "browser_use.browser.chrome",
    "browser_use.browser.cdp", "browser_use.browser.session",
    "httpx", "httpcore", "urllib3", "filelock",
    "websockets", "charset_normalizer",
):
    logging.getLogger(_noisy).setLevel(logging.WARNING)
_log = logging.getLogger("backend")

_API_TOKEN = os.environ.get("JOB_APPLICANT_TOKEN") or _secrets.token_hex(32)

# Write token to data dir so the Tauri frontend can read it
import stat as _stat
_token_path = get_data_dir() / ".api_token"
_token_path.parent.mkdir(parents=True, exist_ok=True)
_token_path.write_text(_API_TOKEN)
try:
    os.chmod(_token_path, _stat.S_IRUSR | _stat.S_IWUSR)
except OSError as e:
    _log.warning(f"Could not set restrictive permissions on token file: {e}")
# Verify token was written correctly
_written = _token_path.read_text().strip()
_log.info(f"Token written to {_token_path} (starts with '{_API_TOKEN[:8]}...', verified: {_written == _API_TOKEN})")

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import time as _time

class _RateLimiter:
    """Simple per-path rate limiter using a sliding window."""
    def __init__(self, max_calls: int = 30, window_seconds: int = 60):
        self._max = max_calls
        self._window = window_seconds
        self._calls: dict[str, list[float]] = {}

    def is_allowed(self, path: str) -> bool:
        now = _time.monotonic()
        calls = self._calls.setdefault(path, [])
        calls[:] = [t for t in calls if now - t < self._window]
        if len(calls) >= self._max:
            return False
        calls.append(now)
        return True

_rate_limiter = _RateLimiter(max_calls=60, window_seconds=60)
_rate_limited_prefixes = ("/jobs/collect", "/apply/start", "/apply/stop", "/llm/test", "/auth/login")

_ALLOWED_ORIGINS = {"http://localhost:1420", "tauri://localhost", "http://tauri.localhost", "https://tauri.localhost", "http://127.0.0.1:1420"}

class _AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        _log.info(f"REQ {request.method} {request.url.path} origin='{request.headers.get('Origin', '')}' auth={'yes' if request.headers.get('Authorization') else 'no'}")
        if request.url.path in ("/health", "/chromium/status"):
            return await call_next(request)
        origin = request.headers.get("Origin", "")
        if origin and origin not in _ALLOWED_ORIGINS:
            _log.warning(f"403 blocked origin: '{origin}' not in {_ALLOWED_ORIGINS}")
            return JSONResponse({"error": "forbidden"}, status_code=403)
        auth_header = request.headers.get("Authorization", "")
        token = auth_header.removeprefix("Bearer ").strip()
        if token != _API_TOKEN:
            _log.warning(f"401 {request.method} {request.url.path} | got '{token[:8]}...' expected '{_API_TOKEN[:8]}...'")
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        if any(request.url.path.startswith(p) for p in _rate_limited_prefixes):
            if not _rate_limiter.is_allowed(request.url.path):
                return JSONResponse({"error": "rate limited"}, status_code=429)
        return await call_next(request)

app.add_middleware(_AuthMiddleware)

# Allow frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Helpers ───────────────────────────────────────────────────────────────

def _start_parent_watchdog():
    """Exit if the parent process (Tauri app) dies — prevents orphaned sidecar."""
    parent_pid = os.getppid()
    if parent_pid <= 1:
        _log.info(f"Parent watchdog skipped (ppid={parent_pid}, already orphaned or init)")
        return

    def _watch():
        import time as _time
        try:
            import psutil
            parent = psutil.Process(parent_pid)
        except Exception:
            parent = None

        # Grace period: wait 10s before starting checks.
        _time.sleep(10)
        
        while True:
            _time.sleep(5)
            if parent:
                if not parent.is_running():
                    break
            else:
                # Fallback to os.getppid() if psutil fails
                if os.getppid() != parent_pid:
                    break
        
        _log.info("Parent process died — shutting down backend")
        os.kill(os.getpid(), signal.SIGTERM)

    t = threading.Thread(target=_watch, daemon=True, name="parent-watchdog")
    t.start()
    _log.info(f"Parent watchdog started (monitoring PID {parent_pid})")


def _recover_stale_jobs():
    """Reset jobs stuck in 'in_progress' back to 'pending' (crash recovery)."""
    try:
        from core.shared_config import read_jobs, write_jobs
    except ImportError:
        from backend.core.shared_config import read_jobs, write_jobs
    jobs = read_jobs()
    recovered = 0
    for url, job in jobs.items():
        if job.get("status") == "in_progress":
            job["status"] = "pending"
            recovered += 1
    if recovered:
        write_jobs(jobs)
        _log.info(f"Recovered {recovered} stale in_progress jobs back to pending")


def _api_error(code: str, message: str, status_code: int = 400) -> JSONResponse:
    """Return a structured error response."""
    return JSONResponse(
        {"ok": False, "error": {"code": code, "message": message}},
        status_code=status_code,
    )


def _get_jobs_file() -> Path:
    """Find jobs.json — try data dir first, then project root."""
    data_dir = get_data_dir()
    if (data_dir / "jobs.json").exists():
        return data_dir / "jobs.json"
    if (PROJECT_ROOT / "jobs.json").exists():
        return PROJECT_ROOT / "jobs.json"
    return data_dir / "jobs.json"


def _load_jobs() -> dict:
    path = _get_jobs_file()
    if path.exists():
        return json.loads(path.read_text())
    return {}


def _get_memory_store():
    """Get the memory store, falling back gracefully."""
    try:
        from memory.store import MemoryStore
        return MemoryStore()
    except (ImportError, FileNotFoundError, OSError) as e:
        _log.warning(f"Memory store unavailable: {e}")
        return None


def _get_metrics_store():
    """Get the metrics store, falling back gracefully."""
    try:
        from memory.metrics import MetricsStore
        return MetricsStore()
    except (ImportError, FileNotFoundError, OSError) as e:
        _log.warning(f"Metrics store unavailable: {e}")
        return None


# ── Playwright Chromium Discovery ─────────────────────────────────────────
def _find_playwright_chromium() -> str | None:
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
_chromium_status: dict = {"state": "checking", "message": "Checking for Chromium..."}


def _get_playwright_install_cmd() -> list[str] | None:
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


def _ensure_chromium_async():
    """Check if Playwright Chromium is installed, install in background if not.
    Updates _chromium_status so the frontend can poll progress."""
    global _chromium_status

    if _find_playwright_chromium() is not None:
        _chromium_status = {"state": "ready", "message": "Chromium found"}
        _log.info("Chromium found")
        return

    _chromium_status = {"state": "installing", "message": "Installing Chromium (one-time download, ~400MB)..."}
    _log.info("Chromium not found — installing in background")

    def _install():
        global _chromium_status
        try:
            cmd = _get_playwright_install_cmd()
            if not cmd:
                _chromium_status = {"state": "failed", "message": "Could not find Playwright installer. Please reinstall the application."}
                _log.error("No working Playwright install command found")
                return
            _log.info(f"Chromium install command: {cmd}")
            _chromium_status = {"state": "installing", "message": "Downloading Chromium browser (~162 MB). This may take a few minutes, please don't close the app..."}

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
                        _chromium_status = {"state": "installing", "message": f"Downloading Chromium... {mb:.0f} MB downloaded. Please don't close the app."}
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
                _chromium_status = {"state": "ready", "message": "Chromium installed successfully"}
                _log.info("Chromium installed successfully")
            else:
                cur_msg = _chromium_status.get("message", "Unknown error")
                _chromium_status = {"state": "failed", "message": f"Install failed: {cur_msg}"}
                _log.error(f"Chromium install failed (code {proc.returncode}): {cur_msg}")
        except Exception as e:
            msg = str(e)
            _chromium_status = {"state": "failed", "message": f"Install failed: {msg[:200]}"}
            _log.error(f"Chromium install error: {e}")

    threading.Thread(target=_install, daemon=True, name="chromium-install").start()


@app.get("/chromium/status")
async def chromium_status():
    return _chromium_status


# ── Health ────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    db_ok = False
    try:
        store = _get_memory_store()
        if store:
            store.get_stats()
            db_ok = True
    except Exception:
        pass

    chromium_ok = _chromium_status.get("state") == "ready"
    chromium_installing = _chromium_status.get("state") == "installing"
    if not chromium_ok and not chromium_installing:
        try:
            chromium_ok = _find_playwright_chromium() is not None
        except Exception:
            pass

    llm_configured = bool(load_llm_settings().get("provider"))
    worker_running = _collection_status.get("running") or _apply_status.get("running")

    all_ok = db_ok and chromium_ok and llm_configured
    return {
        "status": "ok" if all_ok else "degraded",
        "version": "1.0.0",
        "frozen": getattr(sys, 'frozen', False),
        "checks": {
            "database": db_ok,
            "chromium": chromium_ok,
            "chromium_installing": chromium_installing,
            "llm_configured": llm_configured,
            "worker_running": bool(worker_running),
        },
    }


# ── Profile ───────────────────────────────────────────────────────────────
@app.get("/profile")
async def get_profile():
    return load_profile()

@app.put("/profile")
async def update_profile(profile: dict):
    save_profile(profile)
    return {"success": True}


# ── LLM Settings ──────────────────────────────────────────────────────────
@app.get("/settings/llm")
async def get_llm():
    return load_llm_settings()

@app.put("/settings/llm")
async def update_llm(settings: dict):
    save_llm_settings(settings)
    return {"success": True}

@app.post("/llm/test")
async def test_llm(settings: dict):
    """Test LLM connection with given settings."""
    try:
        from core.llm_factory import create_llm, test_connection
        llm = create_llm(settings)
        result = await test_connection(llm)
        return {"success": True, "message": result}
    except Exception as e:
        msg = str(e)
        if "api_key" in msg.lower() or "unauthorized" in msg.lower() or "401" in msg:
            return {"success": False, "message": "Invalid API key or unauthorized. Check your credentials."}
        if "timeout" in msg.lower() or "connect" in msg.lower():
            return {"success": False, "message": "Connection failed. Check your network and provider settings (is your local LLM server running?)"}
        
        from browser_use.llm.exceptions import ModelProviderError
        if isinstance(e, ModelProviderError):
            return {"success": False, "message": f"LLM Provider Error: {msg}"}
            
        _log.error(f"LLM test failed: {e}", exc_info=True)
        return {"success": False, "message": f"LLM test failed: {msg}"}


@app.post("/llm/ollama-models")
async def list_ollama_models(body: dict):
    """Fetch available models from an Ollama server."""
    import httpx
    base_url = body.get("base_url", "http://localhost:11434").rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{base_url}/api/tags")
            resp.raise_for_status()
            data = resp.json()
            models = [m["name"] for m in data.get("models", [])]
            return {"success": True, "models": models}
    except Exception as e:
        return {"success": False, "models": [], "message": str(e)}


# ── App Settings ──────────────────────────────────────────────────────────
@app.get("/settings")
async def get_settings():
    return load_settings()

@app.put("/settings")
async def update_settings(settings: dict):
    save_settings(settings)
    return {"success": True}


# ── In-process task runner ────────────────────────────────────────────────
import asyncio
import io
import contextlib


class _LogCapture(io.StringIO):
    """Captures print output and appends to a status log list + persists to DB."""
    _ansi_re = __import__("re").compile(r"\x1b\[[0-9;]*m")

    def __init__(self, log_list: list, status_dict: dict = None,
                 max_lines: int = MAX_LOG_LINES, metrics_store=None, run_id: str = ""):
        super().__init__()
        self._log = log_list
        self._status = status_dict
        self._max = max_lines
        self._metrics = metrics_store
        self._run_id = run_id

    def write(self, s):
        import re as _re
        for line in s.splitlines():
            line = self._ansi_re.sub("", line).strip()
            if line:
                with _status_lock:
                    self._log.append(line)
                    if len(self._log) > self._max:
                        del self._log[:len(self._log) - self._max // 2]
                    if self._status is not None and "💾" in line:
                        m = _re.search(r"total this title:\s*(\d+)", line)
                        if m:
                            self._status["collected"] = int(m.group(1))
                if self._metrics and self._run_id:
                    try:
                        level = "ERROR" if "❌" in line else "WARNING" if "⚠️" in line else "INFO"
                        self._metrics.log(self._run_id, line, level=level)
                    except Exception:
                        pass
        return len(s)

    def flush(self):
        pass


def _run_async_in_thread(coro_factory, status_dict):
    """Run an async function in a new thread with its own event loop, capturing stdout and logs."""
    run_id = status_dict.get("run_id", "")
    metrics = _get_metrics_store()

    def _worker():
        capture = _LogCapture(status_dict["log"], status_dict=status_dict,
                              metrics_store=metrics, run_id=run_id)

        class _ListHandler(logging.Handler):
            _noise = {"httpx", "httpcore", "urllib3", "filelock", "websockets",
                       "charset_normalizer", "botocore", "boto3", "s3transfer"}
            _collected_re = __import__("re").compile(r"(\d+)\s+jobs?\s+collected", __import__("re").IGNORECASE)
            _ansi_re = __import__("re").compile(r"\x1b\[[0-9;]*m")
            def emit(self, record):
                if record.name.split(".")[0] in self._noise:
                    return
                msg = self._ansi_re.sub("", record.getMessage()).strip()
                if msg and not msg.startswith("🌎"):
                    with _status_lock:
                        status_dict["log"].append(msg)
                        if len(status_dict["log"]) > MAX_LOG_LINES:
                            del status_dict["log"][:MAX_LOG_LINES // 2]
                        if "collected" in status_dict:
                            m = self._collected_re.search(msg)
                            if m:
                                status_dict["collected"] = max(status_dict.get("collected", 0), int(m.group(1)))
                    if metrics and run_id:
                        try:
                            level = record.levelname
                            metrics.log(run_id, msg, level=level)
                        except Exception:
                            pass

        log_handler = _ListHandler()
        log_handler.setLevel(logging.INFO)
        logging.getLogger().addHandler(log_handler)

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            status_dict["_loop"] = loop
            with contextlib.redirect_stdout(capture), contextlib.redirect_stderr(capture):
                loop.run_until_complete(coro_factory())
            with _status_lock:
                if status_dict.get("cancel_requested"):
                    status_dict["log"].append("🛑 Stopped by user")
                    status_dict["error"] = "cancelled"
                else:
                    status_dict["log"].append("✅ Finished successfully")
                    status_dict["error"] = None
        except asyncio.CancelledError:
            with _status_lock:
                status_dict["log"].append("🛑 Stopped by user")
                status_dict["error"] = "cancelled"
        except Exception as e:
            _log.error(f"Worker thread error: {e}", exc_info=True)
            with _status_lock:
                status_dict["log"].append(f"❌ Error: {e}")
                status_dict["error"] = str(e)
        finally:
            logging.getLogger().removeHandler(log_handler)
            loop.close()
            with _status_lock:
                status_dict["running"] = False
                status_dict["cancel_requested"] = False
                status_dict["finished_at"] = datetime.now().isoformat()
            status_dict.pop("_loop", None)

    run_id = str(uuid.uuid4())[:8]
    status_dict["run_id"] = run_id
    status_dict["running"] = True
    status_dict["cancel_requested"] = False
    status_dict["error"] = None
    status_dict["finished_at"] = None
    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    return t


def _kill_browser_processes():
    """Kill any Chromium processes using the shared browser profile.
    Uses psutil for cross-platform support (macOS, Linux, Windows)."""
    try:
        import psutil
        target = "langhire/browser_profile"
        procs_to_kill = []
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                cmdline = proc.info.get("cmdline") or []
                if any(target in arg for arg in cmdline):
                    procs_to_kill.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        for proc in procs_to_kill:
            try:
                proc.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        _, alive = psutil.wait_procs(procs_to_kill, timeout=3)
        for proc in alive:
            try:
                proc.kill()
                _log.warning(f"Force-killed browser process {proc.pid}")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except ImportError:
        import subprocess
        try:
            if sys.platform == "win32":
                subprocess.run(
                    ["taskkill", "/F", "/FI", "IMAGENAME eq chrome.exe"],
                    timeout=5, capture_output=True,
                )
                subprocess.run(
                    ["taskkill", "/F", "/FI", "IMAGENAME eq chromium.exe"],
                    timeout=5, capture_output=True,
                )
            else:
                subprocess.run(
                    ["pkill", "-f", "user-data-dir=.*langhire/browser_profile"],
                    timeout=3, capture_output=True,
                )
        except Exception:
            pass


def _force_stop(status_dict):
    """Force-stop a running operation: cancel async tasks and kill browser processes."""
    with _status_lock:
        status_dict["cancel_requested"] = True

    # Cancel all tasks in the worker's event loop
    loop = status_dict.get("_loop")
    if loop and loop.is_running():
        for task in asyncio.all_tasks(loop):
            loop.call_soon_threadsafe(task.cancel)

    _kill_browser_processes()
    with _status_lock:
        status_dict["log"].append("🛑 Force stopped")


# ── Thread-safe status access ─────────────────────────────────────────────
_status_lock = threading.Lock()


# ── Job Collection ────────────────────────────────────────────────────────
_collection_status: dict = {"running": False, "title": None, "log": []}
_collection_thread: threading.Thread | None = None


@app.post("/jobs/collect")
async def start_collection(body: CollectRequest):
    """Start job collection in-process (no subprocess, no external Python needed)."""
    global _collection_thread, _collection_status

    if _collection_status["running"]:
        return {"success": False, "message": "Collection already running"}

    # Kill any leftover browser processes from previous runs
    _kill_browser_processes()

    title = body.title
    max_jobs = body.max_jobs
    _collection_status = {"running": True, "title": title or "all titles", "log": ["Starting collection... This may take several minutes per job title."], "collected": 0, "max_jobs": max_jobs}

    async def _do_collect():
        """Run collection logic directly, bypassing argparse."""
        from core.shared_config import LOGS_DIR, read_jobs, refresh_credentials, credential_refresh_loop
        from cli import collect_jobs
        import core.shared_config as _config

        # Override config.get_llm with the user's UI-configured LLM
        llm_settings = load_llm_settings()
        if llm_settings.get("provider"):
            from core.llm_factory import create_llm
            _config.get_llm = lambda: create_llm(llm_settings)
            print(f"🤖 Using {llm_settings['provider']} LLM from settings")

        # Load profile from the app data dir (set via UI), not the project root
        profile = load_profile()
        jobs = read_jobs()
        LOGS_DIR.mkdir(exist_ok=True)

        titles = [title] if title else profile.get("target_job_titles", [])
        cred_task = asyncio.create_task(credential_refresh_loop(CREDENTIAL_REFRESH_MINUTES))

        for i, t in enumerate(titles):
            if _collection_status.get("cancel_requested"):
                print("🛑 Stop requested — halting collection")
                break
            print(f"\n{'='*60}")
            print(f"[{i+1}/{len(titles)}] Collecting: {t}")
            print(f"{'='*60}")
            try:
                found = await collect_jobs.collect_for_title(t, jobs, profile, max_jobs=max_jobs)
                jobs = read_jobs()
                _collection_status["collected"] = _collection_status.get("collected", 0) + len(found)
                print(f"  Found {len(found)} new jobs (total: {len(jobs)})")
            except Exception as e:
                print(f"  Error: {e}")

        cred_task.cancel()

        # Summary
        jobs = read_jobs()
        easy = sum(1 for j in jobs.values() if j.get("easy_apply"))
        pending = sum(1 for j in jobs.values() if j.get("status") == "pending")
        print(f"\nCollection complete! Total: {len(jobs)} (Easy Apply: {easy}), Pending: {pending}")

    def make_coro():
        return _do_collect()

    _collection_thread = _run_async_in_thread(make_coro, _collection_status)
    return {"success": True, "message": f"Collection started for {title or 'all titles'}"}


@app.post("/jobs/collect/stop")
async def stop_collection():
    _force_stop(_collection_status)
    return {"success": True}


@app.get("/jobs/collect/status")
async def collection_status():
    with _status_lock:
        return {
            "running": _collection_status.get("running", False),
            "title": _collection_status.get("title"),
            "log": list(_collection_status.get("log", [])[-100:]),
            "collected": _collection_status.get("collected", 0),
            "max_jobs": _collection_status.get("max_jobs", 0),
            "error": _collection_status.get("error"),
            "finished_at": _collection_status.get("finished_at"),
            "run_id": _collection_status.get("run_id"),
        }


# ── Application Control ──────────────────────────────────────────────────
_apply_status: dict = {"running": False, "mode": None, "workers": 1, "log": []}
_apply_thread: threading.Thread | None = None


@app.post("/apply/start")
async def start_applying(body: ApplyRequest):
    """Start job application in-process."""
    global _apply_thread, _apply_status

    if _apply_status["running"]:
        return {"success": False, "message": "Application already running"}

    # Kill any leftover browser processes from previous runs
    _kill_browser_processes()

    workers = body.workers
    mode = body.mode
    limit = body.limit
    target_job_url = body.job_url

    if target_job_url:
        _apply_status = {"running": True, "mode": mode, "workers": 1, "log": [f"Applying to single job..."]}
    else:
        _apply_status = {"running": True, "mode": mode, "workers": workers, "log": [f"Starting {mode} apply with {workers} worker(s)..."]}

    # mode="all" applies to all pending jobs regardless of easy_apply status
    easy_apply_filter = None if mode == "all" else (mode != "external")

    async def _do_apply():
        """Run apply logic directly, bypassing argparse."""
        from core.shared_config import JOBS_FILE, CANDIDATE_PROFILE, QA_FILE, LOGS_DIR, load_json, credential_refresh_loop, get_memory_store
        from cli import apply_jobs
        import core.shared_config as _config

        # Override config.get_llm with the user's UI-configured LLM
        llm_settings = load_llm_settings()
        if llm_settings.get("provider"):
            from core.llm_factory import create_llm
            _config.get_llm = lambda: create_llm(llm_settings)
            print(f"🤖 Using {llm_settings['provider']} LLM from settings")

        jobs = load_json(JOBS_FILE, {})
        profile = load_json(CANDIDATE_PROFILE, {})
        qa = load_json(QA_FILE, {})
        LOGS_DIR.mkdir(exist_ok=True)

        if target_job_url:
            target = jobs.get(target_job_url)
            if not target:
                print("Job not found.")
                return
            if target.get("status") not in ("pending", "failed"):
                print(f"Job is already {target.get('status')}.")
                return
            # Reset to pending so the worker can claim it
            from core.shared_config import update_job as _update_job
            _update_job(target_job_url, status="pending", error=None)
            target["status"] = "pending"
            pending = [target]
        elif easy_apply_filter is None:
            pending = [j for j in jobs.values() if j.get("status") == "pending"]
        else:
            pending = [
                j for j in jobs.values()
                if j.get("status") == "pending"
                and (j.get("easy_apply") is True) == easy_apply_filter
            ]
        if limit and not target_job_url:
            pending = pending[:limit]

        if not pending:
            print("No pending jobs to apply to.")
            return

        applied_labels = [
            f"{j.get('title','')} at {j.get('company','')}"
            for j in jobs.values() if j.get("status") == "applied"
        ]

        label = "All" if easy_apply_filter is None else ("Easy Apply" if easy_apply_filter else "Non-Easy Apply")
        print(f"Applying to {len(pending)} {label} jobs with {workers} worker(s)\n")

        queue = asyncio.Queue()
        for job in pending:
            queue.put_nowait(job)

        stats = {}
        num_workers = min(workers, len(pending))
        cred_task = asyncio.create_task(credential_refresh_loop(CREDENTIAL_REFRESH_MINUTES))

        # For mode="all", pass True for easy_apply (agent handles both types via the job URL)
        worker_easy_apply = True if easy_apply_filter is None else easy_apply_filter
        tasks = []
        for i in range(num_workers):
            if i > 0:
                await asyncio.sleep(5)
            tasks.append(asyncio.create_task(
                apply_jobs.worker(f"W{i+1}", i+1, queue, profile, qa, applied_labels, worker_easy_apply, stats, cancel_flag=_apply_status)
            ))
        await asyncio.gather(*tasks)
        cred_task.cancel()

        print(f"\nResults: {stats}")
        total_applied = sum(1 for j in load_json(JOBS_FILE, {}).values() if j.get("status") == "applied")
        print(f"Total applied: {total_applied}")

    def make_coro():
        return _do_apply()

    _apply_thread = _run_async_in_thread(make_coro, _apply_status)
    return {"success": True, "message": f"Started {mode} apply with {workers} worker(s)"}


@app.post("/apply/stop")
async def stop_applying():
    _force_stop(_apply_status)
    return {"success": True}


@app.get("/apply/status")
async def apply_status():
    with _status_lock:
        return {
            "running": _apply_status.get("running", False),
            "mode": _apply_status.get("mode"),
            "workers": _apply_status.get("workers", 1),
            "log": list(_apply_status.get("log", [])[-100:]),
            "error": _apply_status.get("error"),
            "finished_at": _apply_status.get("finished_at"),
            "run_id": _apply_status.get("run_id"),
        }


# ── Jobs ──────────────────────────────────────────────────────────────────
@app.get("/jobs")
async def get_jobs(
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(500),
):
    """Get all jobs, optionally filtered by status and search."""
    jobs = _load_jobs()
    result = []
    for url, job in jobs.items():
        job["url"] = url
        if status and job.get("status") != status:
            continue
        if search:
            q = search.lower()
            if q not in (job.get("title", "") or "").lower() and \
               q not in (job.get("company", "") or "").lower():
                continue
        result.append(job)
    # Sort by collected_at desc
    result.sort(key=lambda j: j.get("collected_at", ""), reverse=True)
    return result[:limit]


@app.get("/jobs/stats")
async def get_job_stats():
    jobs = _load_jobs()
    stats = {"total": len(jobs), "pending": 0, "applied": 0, "failed": 0, "blocked": 0, "in_progress": 0}
    for j in jobs.values():
        s = j.get("status", "pending")
        if s in stats:
            stats[s] += 1
    return stats


# ── Auth / Login Sessions ─────────────────────────────────────────────────
_login_browser_process = None  # track the login browser subprocess

def _get_browser_profile_dir() -> str:
    """Get the shared browser profile directory. Migrates from old per-worker profiles if needed."""
    data_dir = get_data_dir()
    profile = data_dir / "browser_profile"
    profile.mkdir(parents=True, exist_ok=True)

    # Auto-migrate: if shared profile has no cookies but an old one does, copy it
    if not (profile / "Default" / "Cookies").exists():
        import shutil
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


@app.get("/auth/status")
async def auth_status():
    """Check if LinkedIn and Gmail sessions are valid by inspecting cookies."""
    import sqlite3
    profile_dir = _get_browser_profile_dir()
    cookies_db = Path(profile_dir) / "Default" / "Cookies"

    result = {"linkedin": {"logged_in": False}, "gmail": {"logged_in": False}}

    if not cookies_db.exists():
        return result

    try:
        import shutil, tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir) / "Cookies"
            shutil.copy2(cookies_db, tmp)

            conn = sqlite3.connect(str(tmp))
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT COUNT(*) FROM cookies WHERE host_key LIKE '%linkedin.com' AND name = 'li_at'"
                )
                li_count = cursor.fetchone()[0]
                result["linkedin"]["logged_in"] = li_count > 0

                cursor.execute(
                    "SELECT COUNT(*) FROM cookies WHERE host_key LIKE '%google.com' AND name IN ('SID', 'SSID', 'HSID')"
                )
                gmail_count = cursor.fetchone()[0]
                result["gmail"]["logged_in"] = gmail_count >= 2
            finally:
                conn.close()
    except Exception as e:
        _log.warning(f"Cookie check failed: {e}")

    return result


_login_running = False

@app.post("/auth/login/{service}")
async def auth_login(service: str):
    """Launch a Playwright persistent browser context for login.
    Uses the exact same mechanism as BrowserSession so cookies are compatible with collection/apply."""
    global _login_running

    if service not in ("linkedin", "gmail"):
        return {"success": False, "message": f"Unknown service: {service}"}

    if _login_running:
        return {"success": False, "message": "A login browser is already open. Please use it or close it first."}

    urls = {
        "linkedin": "https://www.linkedin.com/login",
        "gmail": "https://accounts.google.com/signin/v2/identifier?service=mail",
    }

    profile_dir = _get_browser_profile_dir()

    def _run_login_browser():
        """Run Playwright persistent context in a thread (blocks until browser closes)."""
        global _login_running
        _login_running = True
        try:
            _log.info(f"Launching Playwright login browser for {service} with profile: {profile_dir}")
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                _log.info("Playwright started, launching persistent context...")
                # Find actual Chromium binary (critical for frozen/PyInstaller builds)
                chromium_path = _find_playwright_chromium()
                launch_kwargs = {
                    "user_data_dir": profile_dir,
                    "headless": False,
                    "args": ["--no-first-run", "--no-default-browser-check"],
                    "ignore_default_args": ["--enable-automation"],
                }
                if chromium_path:
                    launch_kwargs["executable_path"] = chromium_path
                    _log.info(f"Using Chromium at: {chromium_path}")
                context = p.chromium.launch_persistent_context(**launch_kwargs)
                _log.info(f"Browser launched with {len(context.pages)} pages")
                # Navigate existing page or create new one
                if context.pages:
                    page = context.pages[0]
                else:
                    page = context.new_page()
                page.goto(urls[service], wait_until="domcontentloaded")
                _log.info(f"Navigated to {urls[service]}")
                # Keep browser open until user closes all pages
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
                _log.info("Login browser closed by user")
        except Exception as e:
            _log.error(f"Login browser error: {e}", exc_info=True)
        finally:
            _login_running = False

    try:
        import threading
        t = threading.Thread(target=_run_login_browser, daemon=True)
        t.start()
        return {"success": True, "message": f"Browser opened for {service} login. Please log in and close the browser when done."}
    except Exception as e:
        _login_running = False
        _log.error(f"Failed to launch login browser: {e}")
        return {"success": False, "message": f"Failed to launch browser: {e}"}


# ── Memory ────────────────────────────────────────────────────────────────
@app.get("/memory/stats")
async def get_memory_stats():
    store = _get_memory_store()
    if store:
        return store.get_stats()
    return {"total_memories": 0, "unique_domains": 0, "by_category": {}}


@app.get("/memory/domains")
async def get_memory_domains():
    store = _get_memory_store()
    if store:
        return store.get_all_domains()
    return []


@app.get("/memory/domain/{domain}")
async def get_memories_for_domain(domain: str, limit: int = Query(50)):
    store = _get_memory_store()
    if store:
        return store.search(website_domain=domain, success_only=False, limit=limit)
    return []


@app.get("/memory/search")
async def search_memories(q: str = Query(""), limit: int = Query(50)):
    store = _get_memory_store()
    if not store or not q:
        return []
    # Simple text search across all memories
    all_mems = store.export_all()
    q_lower = q.lower()
    results = [m for m in all_mems if q_lower in m.get("content", "").lower() or q_lower in m.get("website_domain", "").lower()]
    return results[:limit]


@app.post("/memory/decay")
async def decay_memories(body: DecayRequest):
    store = _get_memory_store()
    if store:
        affected = store.decay_confidence(days_old=body.days, decay_factor=body.factor)
        return {"success": True, "affected": affected}
    return {"success": False, "message": "Memory store not available"}


@app.post("/memory/cleanup")
async def cleanup_memories(body: CleanupRequest):
    store = _get_memory_store()
    if store:
        deleted = store.delete_low_confidence(threshold=body.threshold)
        return {"success": True, "deleted": deleted}
    return {"success": False, "message": "Memory store not available"}


@app.get("/memory/export")
async def export_memories():
    store = _get_memory_store()
    if store:
        return store.export_all()
    return []


# ── Profile: Parse Resume ─────────────────────────────────────────────────
@app.post("/profile/parse-resume")
async def parse_resume_to_profile():
    """Read the user's resume PDF and use the configured LLM to extract profile fields."""
    import re as _re

    settings = load_settings()
    resume_path = settings.get("resume_path", "").strip()
    if not resume_path:
        return {"success": False, "message": "No resume path configured. Set it in Settings first."}

    resume_file = Path(resume_path).resolve()
    if not resume_file.exists():
        return {"success": False, "message": f"Resume file not found: {resume_path}"}
    if resume_file.suffix.lower() != ".pdf":
        return {"success": False, "message": "Resume must be a PDF file."}
    home = Path.home()
    if not (str(resume_file).startswith(str(home)) or str(resume_file).startswith("/tmp")):
        return {"success": False, "message": "Resume path must be within your home directory."}

    try:
        import fitz  # pymupdf
        doc = fitz.open(str(resume_file))
        resume_text = ""
        for page in doc:
            resume_text += page.get_text()
        doc.close()
        resume_text = resume_text.strip()
        if not resume_text:
            return {"success": False, "message": "Could not extract any text from the resume PDF."}
    except Exception as e:
        return {"success": False, "message": f"Failed to read resume PDF: {e}"}

    # 2. Send to LLM for structured extraction
    llm_settings = load_llm_settings()
    if not llm_settings.get("provider"):
        return {"success": False, "message": "No LLM provider configured. Set it in LLM Settings first."}

    try:
        from core.llm_factory import create_llm
        llm = create_llm(llm_settings)
    except Exception as e:
        return {"success": False, "message": f"Failed to create LLM: {e}"}

    prompt = f"""Extract candidate profile information from this resume text. Return ONLY a valid JSON object with these fields (use empty string "" for missing text fields, 0 for missing numbers, empty array [] for missing lists, false for missing booleans):

{{
  "name": "Full Name",
  "email": "email@example.com",
  "phone": "phone number",
  "address": {{"street": "", "city": "City", "state": "State", "zip": "ZIP", "country": "USA"}},
  "work_authorization": "Authorized to work in the US",
  "visa_sponsorship_needed": false,
  "willing_to_relocate": false,
  "preferred_work_mode": "hybrid",
  "years_of_experience": 0,
  "education": {{"degree": "Degree Name", "school": "University Name", "graduation": "Year or Date"}},
  "current_role": "Current or Most Recent Job Title",
  "target_job_titles": ["Job Title 1", "Job Title 2"],
  "target_locations": ["City, State"],
  "languages": ["English"],
  "skills": ["Skill 1", "Skill 2"],
  "salary_expectation": {{"min": 50000, "max": 100000, "currency": "USD"}},
  "notes": ""
}}

Rules:
- Extract the MOST RECENT job title as current_role
- For target_job_titles, infer 2-4 relevant titles based on their experience and skills
- For target_locations, use the candidate's current city/state if mentioned
- For skills, extract ALL mentioned technical and soft skills
- For years_of_experience, calculate from work history dates if possible
- For education, use the highest degree
- Return ONLY the JSON object, no other text

RESUME TEXT:
{resume_text[:6000]}"""

    try:
        from browser_use.llm.messages import UserMessage
        response = await llm.ainvoke([UserMessage(content=prompt)])
        response_text = response.completion if hasattr(response, 'completion') else (response.content if hasattr(response, 'content') else str(response))

        # Parse JSON from response
        match = _re.search(r"\{.*\}", response_text, _re.DOTALL)
        if not match:
            return {"success": False, "message": "LLM did not return valid JSON. Try again."}

        parsed_profile = json.loads(match.group())

        # Merge with existing profile (don't overwrite fields the user already set)
        existing = load_profile()
        for key, value in parsed_profile.items():
            if key in existing:
                existing_val = existing[key]
                # Only overwrite if existing is empty/default
                if isinstance(existing_val, str) and not existing_val.strip():
                    existing[key] = value
                elif isinstance(existing_val, list) and not existing_val:
                    existing[key] = value
                elif isinstance(existing_val, dict):
                    # Merge nested dicts
                    for sub_key, sub_val in value.items():
                        if sub_key in existing_val:
                            if isinstance(existing_val[sub_key], str) and not existing_val[sub_key].strip():
                                existing_val[sub_key] = sub_val
                            elif isinstance(existing_val[sub_key], (int, float)) and existing_val[sub_key] == 0:
                                existing_val[sub_key] = sub_val
                elif isinstance(existing_val, (int, float)) and existing_val == 0:
                    existing[key] = value
                elif isinstance(existing_val, bool) and not existing_val:
                    existing[key] = value

        # Save the merged profile
        save_profile(existing)

        # Count how many fields were filled
        filled_count = 0
        for key, value in parsed_profile.items():
            if isinstance(value, str) and value.strip():
                filled_count += 1
            elif isinstance(value, list) and value:
                filled_count += 1
            elif isinstance(value, dict):
                for sv in value.values():
                    if isinstance(sv, str) and sv.strip():
                        filled_count += 1
                        break
            elif isinstance(value, (int, float)) and value > 0:
                filled_count += 1

        return {
            "success": True,
            "message": f"Extracted {filled_count} fields from your resume!",
            "profile": existing,
            "fields_filled": filled_count,
        }

    except json.JSONDecodeError:
        return {"success": False, "message": "LLM returned invalid JSON. Try again."}
    except Exception as e:
        return {"success": False, "message": f"LLM parsing failed: {e}"}


# ── Setup Status ──────────────────────────────────────────────────────────
@app.get("/setup/status")
async def get_setup_status():
    """Check which onboarding steps are complete."""
    profile = load_profile()
    llm = load_llm_settings()
    settings = load_settings()

    profile_done = bool(profile.get("name", "").strip())
    llm_done = False
    provider = llm.get("provider", "")
    if provider == "openai":
        llm_done = bool((llm.get("openai") or {}).get("api_key", "").strip())
    elif provider == "anthropic":
        llm_done = bool((llm.get("anthropic") or {}).get("api_key", "").strip())
    elif provider == "bedrock":
        bedrock = llm.get("bedrock") or {}
        if bedrock.get("auth_mode") == "keys":
            llm_done = bool(bedrock.get("access_key", "").strip() and bedrock.get("secret_key", "").strip())
        else:
            # Profile mode — considered configured even with default profile
            llm_done = True
    elif provider == "ollama":
        ollama = llm.get("ollama") or {}
        llm_done = bool(ollama.get("base_url", "").strip())

    resume_done = bool(settings.get("resume_path", "").strip())
    onboarding_completed = settings.get("onboarding_completed", False)

    # Check Chromium
    chromium_done = _find_playwright_chromium() is not None

    # Check login status
    auth = await auth_status()
    linkedin_done = auth.get("linkedin", {}).get("logged_in", False)
    gmail_done = auth.get("gmail", {}).get("logged_in", False)

    return {
        "profile": profile_done,
        "llm": llm_done,
        "resume": resume_done,
        "chromium": chromium_done,
        "linkedin": linkedin_done,
        "gmail": gmail_done,
        "onboarding_completed": onboarding_completed,
        "all_required_done": profile_done and llm_done and resume_done and linkedin_done,
    }


@app.post("/setup/complete-onboarding")
async def complete_onboarding():
    """Mark the onboarding wizard as completed."""
    settings = load_settings()
    settings["onboarding_completed"] = True
    save_settings(settings)
    return {"success": True}


# ── Metrics / Dashboard ───────────────────────────────────────────────────
@app.get("/dashboard")
async def get_dashboard():
    stats = await get_job_stats()
    mem_stats = await get_memory_stats()

    # Try to get metrics data
    metrics_data = {}
    metrics = _get_metrics_store()
    if metrics:
        try:
            metrics_data = {
                "overall": metrics.get_overall_stats(),
                "memory_impact": metrics.get_memory_impact(),
                "domain_stats": metrics.get_domain_stats(),
                "trend": metrics.get_trend(window_size=5),
                "recent_runs": metrics.get_all_runs(limit=10),
            }
        except (OSError, ValueError) as e:
            _log.warning(f"Failed to load metrics: {e}")

    return {
        "jobs": stats,
        "memory": mem_stats,
        "metrics": metrics_data,
    }


@app.get("/metrics/runs")
async def get_metric_runs(limit: int = Query(50)):
    metrics = _get_metrics_store()
    if metrics:
        return metrics.get_all_runs(limit=limit)
    return []


@app.get("/metrics/domains")
async def get_metric_domains():
    metrics = _get_metrics_store()
    if metrics:
        return metrics.get_domain_stats()
    return []


# ── Logs ──────────────────────────────────────────────────────────────────
@app.get("/logs/runs/{run_id}")
async def get_run_logs(run_id: str, limit: int = Query(500)):
    metrics = _get_metrics_store()
    if metrics:
        return metrics.get_run_logs(run_id, limit=limit)
    return []


@app.get("/logs/recent")
async def get_recent_logs(limit: int = Query(100)):
    metrics = _get_metrics_store()
    if metrics:
        return metrics.get_recent_logs(limit=limit)
    return []


@app.get("/logs/runs")
async def get_runs_with_logs(limit: int = Query(50)):
    metrics = _get_metrics_store()
    if metrics:
        return metrics.get_runs_with_logs(limit=limit)
    return []


# ── Q&A Repository ────────────────────────────────────────────────────────

@app.get("/qa")
async def get_qa(search: str = Query(""), unanswered: bool = Query(False)):
    store = _get_memory_store()
    if not store:
        return []
    return store.qa_list(search=search, unanswered_only=unanswered)

@app.get("/qa/stats")
async def get_qa_stats():
    store = _get_memory_store()
    if not store:
        return {"total": 0, "answered": 0, "unanswered": 0}
    return store.qa_stats()

@app.put("/qa/{qa_id}")
async def update_qa(qa_id: int, body: dict):
    store = _get_memory_store()
    if not store:
        return _api_error("no_store", "Memory store not available")
    answer = body.get("answer", "")
    store.qa_update(qa_id, answer)
    return {"success": True}

@app.delete("/qa/{qa_id}")
async def delete_qa(qa_id: int):
    store = _get_memory_store()
    if not store:
        return _api_error("no_store", "Memory store not available")
    store.qa_delete(qa_id)
    return {"success": True}

@app.post("/qa/{source_id}/merge/{target_id}")
async def merge_qa(source_id: int, target_id: int):
    store = _get_memory_store()
    if not store:
        return _api_error("no_store", "Memory store not available")
    store.qa_merge(source_id, target_id)
    return {"success": True}

@app.post("/qa/auto-squash")
async def auto_squash_qa():
    store = _get_memory_store()
    if not store:
        return _api_error("no_store", "Memory store not available")
    merged = store.qa_auto_squash()
    return {"success": True, "merged": merged}

@app.post("/qa/smart-squash")
async def smart_squash_qa():
    """LLM-based semantic deduplication of Q&A questions."""
    store = _get_memory_store()
    if not store:
        return _api_error("no_store", "Memory store not available")
    questions = store.qa_list()
    if len(questions) < 2:
        return {"success": True, "merged": 0}

    from core.llm_factory import create_llm
    llm_settings = load_llm_settings()
    if not llm_settings.get("provider"):
        return _api_error("no_llm", "No LLM configured. Set up an LLM provider in Settings first.")

    llm = create_llm(llm_settings)
    q_list = "\n".join(f"[{q['id']}] {q['question']}" for q in questions)
    prompt = (
        "Below is a numbered list of screening questions from job applications. "
        "Find groups of questions that ask the same thing in different words. "
        "Return ONLY a JSON array of merge instructions: [{\"keep\": <id_to_keep>, \"merge\": [<ids_to_merge>]}, ...]. "
        "Only group questions that are truly semantically identical. If no duplicates exist, return [].\n\n"
        f"{q_list}"
    )
    try:
        response = await llm.ainvoke(prompt)
        import json as _json
        text = response.content if hasattr(response, "content") else str(response)
        # Extract JSON from response
        import re as _re_mod
        match = _re_mod.search(r"\[.*\]", text, _re_mod.DOTALL)
        if not match:
            return {"success": True, "merged": 0}
        groups = _json.loads(match.group(0))
        merged_count = 0
        for group in groups:
            keep_id = group.get("keep")
            merge_ids = group.get("merge", [])
            for mid in merge_ids:
                store.qa_merge(mid, keep_id)
                merged_count += 1
        return {"success": True, "merged": merged_count}
    except Exception as e:
        return _api_error("llm_error", f"Smart squash failed: {str(e)}", 500)


# ── Main ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    def _handle_sigterm(signum, frame):
        _log.info(f"Received signal {signum} — cleaning up and exiting")
        _kill_browser_processes()
        sys.exit(0)

    # Register SIGTERM handler AFTER uvicorn starts (uvicorn installs its own)
    # signal.signal(signal.SIGTERM, _handle_sigterm)  — disabled, let uvicorn handle signals

    port = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT
    _log.info(f"Starting uvicorn on port {port} (pid={os.getpid()}, ppid={os.getppid()})")

    # Use Server directly instead of uvicorn.run() — the latter fails in
    # PyInstaller frozen builds because it can't manage the event loop properly
    # Check if port is already in use (stale process from previous run)
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", port))
        sock.close()
        _log.info(f"Port {port} is available")
    except OSError as e:
        _log.error(f"Port {port} already in use: {e}. Killing stale process...")
        sock.close()
        try:
            import subprocess as _sp
            result = _sp.run(["lsof", "-ti", f":{port}"], capture_output=True, text=True, timeout=5)
            if result.stdout.strip():
                for pid in result.stdout.strip().split("\n"):
                    _log.info(f"Killing stale process on port {port}: PID {pid}")
                    try:
                        os.kill(int(pid), signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                import time
                time.sleep(1)
        except Exception as kill_err:
            _log.warning(f"Could not kill stale process: {kill_err}")

    # Ignore SIGHUP — Tauri sidecar may receive it when parent process group changes
    if sys.platform != "win32":
        signal.signal(signal.SIGHUP, signal.SIG_IGN)

    import asyncio

    if getattr(sys, 'frozen', False):
        # In PyInstaller frozen builds, uvicorn's signal handling and lifespan
        # protocol break. Use a minimal approach: disable lifespan protocol
        # and manage signals ourselves.
        _log.info("Frozen build detected — using uvicorn with lifespan=off")
        config = uvicorn.Config(
            app, host="127.0.0.1", port=port, log_level="info",
            lifespan="off",
        )
        # Fix: uvicorn 0.30+ requires config.load() to be called to initialize 
        # internal attributes like ssl, http_protocol_class, etc. when not using run().
        config.load()
        server = uvicorn.Server(config)
        from uvicorn.lifespan.off import LifespanOff
        server.lifespan = LifespanOff(config)
        
        server.install_signal_handlers = lambda: None
        import contextlib as _ctxlib
        server.capture_signals = _ctxlib.contextmanager(lambda: (yield))

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def _run():
            async with lifespan(app):
                _log.info("Lifespan started, launching server...")
                # Run startup and log the result
                await server.startup()
                _log.info(f"After startup: should_exit={server.should_exit} started={server.started}")
                if server.should_exit:
                    _log.warning("Uvicorn wants to exit — forcing main_loop anyway")
                    server.should_exit = False
                if not server.started:
                    _log.error("Server failed to start!")
                    return
                _log.info("Entering main_loop...")
                await server.main_loop()
                _log.info("main_loop exited, shutting down...")
                await server.shutdown()

        try:
            loop.run_until_complete(_run())
        except (KeyboardInterrupt, SystemExit):
            _log.info("Server stopped")
        finally:
            loop.close()
            _log.info("Uvicorn exited")
    else:
        # Development mode — standard uvicorn.run() works fine
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
