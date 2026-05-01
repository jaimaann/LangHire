"""
Verbose agent logger.

Logs the browser-use agent's thinking, goals, memory, and actions
to a dedicated rotating log file (agent_verbose.log).
"""

import logging
import re
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

try:
    from core.config import get_data_dir
except ImportError:
    from backend.core.config import get_data_dir

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

_logger: logging.Logger | None = None


def _get_logger() -> logging.Logger:
    global _logger
    if _logger is None:
        _logger = logging.getLogger("agent_verbose")
        _logger.setLevel(logging.DEBUG)
        _logger.propagate = False
        handler = RotatingFileHandler(
            get_data_dir() / "agent_verbose.log",
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
        )
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        _logger.addHandler(handler)
    return _logger


def _clean(text: str | None) -> str:
    if not text:
        return ""
    return _ANSI_RE.sub("", text).strip()


def _format_actions(actions) -> str:
    if not actions:
        return "  (none)"
    lines = []
    for i, act in enumerate(actions):
        try:
            d = act.model_dump(exclude_none=True) if hasattr(act, "model_dump") else str(act)
        except Exception:
            d = str(act)
        lines.append(f"  [{i+1}] {d}")
    return "\n".join(lines)


def on_step(browser_state, agent_output, step_num: int) -> None:
    """Callback for register_new_step_callback. Logs agent reasoning per step."""
    log = _get_logger()
    if not agent_output:
        log.debug(f"Step {step_num}: (no agent output)")
        return

    url = getattr(browser_state, "url", "") if browser_state else ""
    title = getattr(browser_state, "title", "") if browser_state else ""

    evaluation = _clean(getattr(agent_output, "evaluation_previous_goal", None))
    next_goal = _clean(getattr(agent_output, "next_goal", None))
    memory = _clean(getattr(agent_output, "memory", None))
    thinking = _clean(getattr(agent_output, "thinking", None))
    actions = getattr(agent_output, "action", []) or []

    parts = [f"Step {step_num} | {url}"]
    if title:
        parts[0] += f" — {title}"
    if thinking:
        parts.append(f"  Thinking: {thinking}")
    if evaluation:
        parts.append(f"  Eval prev goal: {evaluation}")
    if next_goal:
        parts.append(f"  Next goal: {next_goal}")
    if memory:
        parts.append(f"  Memory: {memory}")
    parts.append(f"  Actions:\n{_format_actions(actions)}")

    log.info("\n".join(parts))


def on_done(history) -> None:
    """Callback for register_done_callback. Logs a run summary."""
    log = _get_logger()
    if not history:
        log.info("Run complete (no history)")
        return

    steps = len(history.history) if hasattr(history, "history") else 0
    done = history.is_done() if hasattr(history, "is_done") else None
    success = history.is_successful() if hasattr(history, "is_successful") else None
    duration = history.total_duration_seconds() if hasattr(history, "total_duration_seconds") else None
    errors = [e for e in (history.errors() if hasattr(history, "errors") else []) if e]

    parts = [
        "── Run Summary ──",
        f"  Steps: {steps}",
        f"  Done: {done}  Success: {success}",
    ]
    if duration is not None:
        parts.append(f"  Duration: {duration:.1f}s")
    if errors:
        parts.append(f"  Errors ({len(errors)}):")
        for e in errors[-5:]:
            parts.append(f"    - {str(e)[:200]}")
    parts.append("── End Summary ──")

    log.info("\n".join(parts))


def log_run_start(run_type: str, label: str) -> None:
    """Log the start of a collect or apply run."""
    log = _get_logger()
    log.info(f"{'='*60}\nRun started: {run_type} — {label}\n{'='*60}")
