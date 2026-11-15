"""Helpers shared by the routers."""
from __future__ import annotations

import logging

from fastapi.responses import JSONResponse

_log = logging.getLogger("backend")


def api_error(code: str, message: str, status_code: int = 400) -> JSONResponse:
    return JSONResponse({"ok": False, "error": {"code": code, "message": message}}, status_code=status_code)


def get_memory_store():
    """The shared memory store (None if it can't be opened)."""
    try:
        from core import shared_config
        return shared_config.get_memory_store()
    except (ImportError, OSError) as e:
        _log.warning(f"Memory store unavailable: {e}")
        return None


def get_metrics_store():
    try:
        from memory.metrics import MetricsStore
        return MetricsStore()
    except (ImportError, OSError) as e:
        _log.warning(f"Metrics store unavailable: {e}")
        return None


def plugin_registry():
    from engine import prompts
    return prompts.registry()


def llm_text(response) -> str:
    """Text of a browser-use chat completion (it has .completion, not .content)."""
    for attr in ("completion", "content", "text"):
        v = getattr(response, attr, None)
        if isinstance(v, str):
            return v
    return str(response)
