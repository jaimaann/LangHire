"""
LangHire backend: a local FastAPI server, run as a sidecar by the Tauri app.

The Tauri host picks a free port and an API token and passes them in
``LANGHIRE_PORT`` / ``LANGHIRE_API_TOKEN`` (plus ``LANGHIRE_DATA_DIR``). Run by
hand in development, it falls back to port 8743 and writes the token to
``<data dir>/.api_token`` for the dev frontend to read.

Routes live in ``api/``; the agent engine lives in ``engine/``.
"""
import asyncio
import hmac
import logging
import os
import secrets as _secrets
import signal
import stat
import sys
import threading
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler

# Windows consoles default to cp1252; emoji in log lines must not crash the server.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except Exception:
        pass

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from starlette.middleware.base import BaseHTTPMiddleware  # noqa: E402
from starlette.responses import JSONResponse  # noqa: E402
import uvicorn  # noqa: E402

from core.config import get_data_dir  # noqa: E402

DEFAULT_PORT = 8743
APP_VERSION = os.environ.get("LANGHIRE_APP_VERSION", "1.0.0")

# ── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        RotatingFileHandler(get_data_dir() / "backend.log", maxBytes=5 * 1024 * 1024,
                            backupCount=3, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
for _noisy in ("browser_use.dom", "browser_use.browser.chrome", "browser_use.browser.cdp",
               "browser_use.browser.session", "httpx", "httpcore", "urllib3", "filelock",
               "websockets", "charset_normalizer"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)
_log = logging.getLogger("backend")

# ── API token ──────────────────────────────────────────────────────────────
_ENV_TOKEN = os.environ.get("LANGHIRE_API_TOKEN") or os.environ.get("JOB_APPLICANT_TOKEN")
_API_TOKEN = _ENV_TOKEN or _secrets.token_hex(32)
_token_path = get_data_dir() / ".api_token"
if _ENV_TOKEN and os.environ.get("LANGHIRE_API_TOKEN"):
    # The host handed us the token: no file needed. Remove a stale one.
    try:
        _token_path.unlink(missing_ok=True)
    except OSError:
        pass
else:
    # Development: the dev frontend reads the token from this file.
    _token_path.parent.mkdir(parents=True, exist_ok=True)
    _token_path.write_text(_API_TOKEN, encoding="utf-8")
    try:
        os.chmod(_token_path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass

# ── Imports that need logging configured first ────────────────────────────
from api import auth as auth_api, content, jobs, memory as memory_api, plugins, runs  # noqa: E402
from api import settings as settings_api, system  # noqa: E402
from core import chromium, db  # noqa: E402
from engine.browsers import kill_profile_browsers  # noqa: E402
from engine.data import prune_logs  # noqa: E402
from engine.runner import manager  # noqa: E402


# ── Lifespan ───────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    _log.info(f"Backend {APP_VERSION} starting; data dir {get_data_dir()}")
    kill_profile_browsers()  # leftovers from a crash
    try:
        recovered = db.recover_stale_jobs()
        if recovered:
            _log.info(f"Recovered {recovered} stale in_progress jobs back to pending")
        db.mark_interrupted_runs()
    except Exception as e:
        _log.error(f"Database startup failed: {e}", exc_info=True)
    try:
        prune_logs()
    except Exception as e:
        _log.warning(f"Log pruning failed: {e}")
    chromium.ensure_chromium_async()
    _start_parent_watchdog()
    yield
    _log.info("Backend shutting down")
    manager.cancel_all()
    kill_profile_browsers()


app = FastAPI(title="LangHire Backend", version=APP_VERSION, lifespan=lifespan)

_rate_limited_prefixes = ("/jobs/collect", "/apply/start", "/apply/stop", "/llm/test", "/auth/login")
_ALLOWED_ORIGINS = ["http://localhost:1420", "http://127.0.0.1:1420", "tauri://localhost",
                    "http://tauri.localhost", "https://tauri.localhost"]
_PUBLIC_PATHS = ("/health", "/chromium/status")


class _RateLimiter:
    """Per-path sliding window."""
    def __init__(self, max_calls: int = 60, window_seconds: int = 60):
        import time
        self._now = time.monotonic
        self._max, self._window = max_calls, window_seconds
        self._calls: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def is_allowed(self, path: str) -> bool:
        now = self._now()
        with self._lock:
            calls = [t for t in self._calls.get(path, []) if now - t < self._window]
            if len(calls) >= self._max:
                self._calls[path] = calls
                return False
            calls.append(now)
            self._calls[path] = calls
            return True


_rate_limiter = _RateLimiter()


class _AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path
        if request.method == "OPTIONS" or path in _PUBLIC_PATHS:
            return await call_next(request)
        origin = request.headers.get("Origin", "")
        if origin and origin not in _ALLOWED_ORIGINS:
            _log.warning(f"403 blocked origin {origin!r} for {path}")
            return JSONResponse({"error": "forbidden"}, status_code=403)
        token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        if not hmac.compare_digest(token.encode(), _API_TOKEN.encode()):
            _log.warning(f"401 {request.method} {path}")  # never log token material
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        if path.startswith(_rate_limited_prefixes) and not _rate_limiter.is_allowed(path):
            return JSONResponse({"error": "rate limited"}, status_code=429)
        return await call_next(request)


app.add_middleware(_AuthMiddleware)
# CORS runs first (added last). One allowlist, shared with the origin check above.
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

from fastapi.exceptions import RequestValidationError  # noqa: E402


@app.exception_handler(RequestValidationError)
async def _validation_error(request, exc: RequestValidationError):
    """Invalid request bodies get the API's usual error shape (400), not FastAPI's 422."""
    first = exc.errors()[0] if exc.errors() else {}
    where = ".".join(str(x) for x in first.get("loc", []) if x != "body")
    message = f"{where}: {first.get('msg', 'invalid value')}" if where else first.get("msg", "Invalid request")
    return JSONResponse({"ok": False, "error": {"code": "invalid_request", "message": message}}, status_code=400)


for _router in (system.router, settings_api.router, jobs.router, runs.router, auth_api.router,
                memory_api.router, content.router, plugins.router):
    app.include_router(_router)


# ── Parent watchdog ────────────────────────────────────────────────────────
def _start_parent_watchdog():
    """Exit if the Tauri host dies, so the sidecar is never orphaned."""
    parent_pid = os.getppid()
    if parent_pid <= 1 or os.environ.get("LANGHIRE_NO_WATCHDOG") == "1":
        return

    def _watch():
        import time
        try:
            import psutil
            parent = psutil.Process(parent_pid)
        except Exception:
            parent = None
        time.sleep(10)
        while True:
            time.sleep(5)
            alive = parent.is_running() if parent else os.getppid() == parent_pid
            if not alive:
                break
        _log.info("Parent process died — shutting down backend")
        manager.cancel_all()
        kill_profile_browsers()
        os._exit(0)

    threading.Thread(target=_watch, daemon=True, name="parent-watchdog").start()


def _resolve_port() -> int:
    for value in (os.environ.get("LANGHIRE_PORT"), sys.argv[1] if len(sys.argv) > 1 else None):
        if value and value.isdigit():
            return int(value)
    return DEFAULT_PORT


# ── Main ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if sys.platform != "win32":
        signal.signal(signal.SIGHUP, signal.SIG_IGN)
    port = _resolve_port()
    _log.info(f"Starting server on 127.0.0.1:{port} (pid={os.getpid()})")

    if getattr(sys, "frozen", False):
        # PyInstaller: uvicorn's own signal and lifespan handling break, so run
        # the server loop ourselves inside our lifespan.
        config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="info", lifespan="off")
        config.load()
        server = uvicorn.Server(config)
        from uvicorn.lifespan.off import LifespanOff
        server.lifespan = LifespanOff(config)  # startup() expects it; serve() normally sets it
        server.install_signal_handlers = lambda: None  # type: ignore[method-assign]

        async def _run():
            async with lifespan(app):
                await server.startup()
                if not server.started:
                    _log.error("Server failed to start (is the port taken?)")
                    return
                await server.main_loop()
                await server.shutdown()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_run())
        except (KeyboardInterrupt, SystemExit):
            pass
        finally:
            loop.close()
    else:
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
