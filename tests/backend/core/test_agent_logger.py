"""Unit tests for backend/core/agent_logger.py.

The module is a thin wrapper around a cached, module-level
:class:`logging.Logger` that writes the browser-use agent's reasoning to a
rotating ``agent_verbose.log`` file in the app data dir.

Coverage targets:
  * ``_get_logger``     — lazy singleton creation + handler/formatter config.
  * ``_clean``          — ANSI stripping, whitespace trim, empty/None handling.
  * ``_format_actions`` — model_dump vs str fallback, exceptions, empty input.
  * ``on_step``         — per-step formatting, optional fields, no-output branch.
  * ``on_done``         — run-summary formatting, no-history + error branches.
  * ``log_run_start``   — banner line.

Because ``agent_logger`` caches its logger in a module global, every test gets
a freshly-reset logger via the autouse ``reset_logger`` fixture so file handlers
point at the per-test tmp data dir created by the ``data_dir`` fixture.
"""
import logging
import types
from logging.handlers import RotatingFileHandler

import pytest

import core.agent_logger as agent_logger


def _file_handler(log):
    """Return the module's RotatingFileHandler.

    pytest's logging plugin attaches its own capture handler to every logger,
    so we select by type rather than by position.
    """
    handlers = [h for h in log.handlers if isinstance(h, RotatingFileHandler)]
    assert len(handlers) == 1, f"expected one file handler, got {handlers}"
    return handlers[0]


# ── fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_logger():
    """Reset the cached module-level logger before and after every test.

    The logger is created lazily and memoised in ``agent_logger._logger`` with a
    :class:`RotatingFileHandler` bound to the data dir resolved at creation time.
    Tests must start from a clean slate so the handler targets the current
    ``data_dir`` tmp path, and we close handlers afterwards to release file
    descriptors on the tmp file.
    """
    def _teardown():
        existing = logging.getLogger("agent_verbose")
        for handler in list(existing.handlers):
            handler.close()
            existing.removeHandler(handler)
        agent_logger._logger = None

    _teardown()
    yield
    _teardown()


def _read_log(data_dir):
    """Flush all handlers and return the contents of the verbose log file."""
    for handler in logging.getLogger("agent_verbose").handlers:
        handler.flush()
    log_path = data_dir / "agent_verbose.log"
    if not log_path.exists():
        return ""
    return log_path.read_text()


# ── minimal fakes for the browser-use objects ──────────────────────────────────

class FakeBrowserState:
    """Stub mirroring the ``browser_state`` attrs ``on_step`` reads."""

    def __init__(self, url="", title=""):
        self.url = url
        self.title = title


class FakeAction:
    """Action object exposing ``model_dump`` like a pydantic model."""

    def __init__(self, payload):
        self._payload = payload

    def model_dump(self, exclude_none=True):
        return self._payload


class FakeAgentOutput:
    """Stub mirroring the ``agent_output`` attrs ``on_step`` reads."""

    def __init__(self, **kwargs):
        self.evaluation_previous_goal = kwargs.get("evaluation_previous_goal")
        self.next_goal = kwargs.get("next_goal")
        self.memory = kwargs.get("memory")
        self.thinking = kwargs.get("thinking")
        self.action = kwargs.get("action", [])


class FakeHistory:
    """Stub mirroring the ``history`` interface ``on_done`` consumes."""

    def __init__(self, *, steps=0, done=None, success=None,
                 duration=None, errors=None):
        self.history = list(range(steps))
        self._done = done
        self._success = success
        self._duration = duration
        self._errors = errors if errors is not None else []

    def is_done(self):
        return self._done

    def is_successful(self):
        return self._success

    def total_duration_seconds(self):
        return self._duration

    def errors(self):
        return self._errors


# ── _get_logger ────────────────────────────────────────────────────────────────

def test_get_logger_creates_singleton(data_dir):
    """First call configures the logger; subsequent calls return the same one."""
    log1 = agent_logger._get_logger()
    log2 = agent_logger._get_logger()

    assert log1 is log2
    assert log1 is agent_logger._logger
    assert log1.name == "agent_verbose"
    assert log1.level == logging.DEBUG
    assert log1.propagate is False
    # Exactly one RotatingFileHandler is attached by the module (pytest may add
    # its own capture handler, which is filtered out by _file_handler).
    _file_handler(log1)


def test_get_logger_handler_config(data_dir):
    """The handler is a RotatingFileHandler with the expected rotation policy."""
    log = agent_logger._get_logger()
    handler = _file_handler(log)

    assert handler.maxBytes == 10 * 1024 * 1024
    assert handler.backupCount == 5
    # Handler writes into the per-test tmp data dir.
    assert handler.baseFilename == str(data_dir / "agent_verbose.log")


def test_get_logger_formatter(data_dir):
    """Formatter emits the documented '<time> [<level>] <message>' layout."""
    log = agent_logger._get_logger()
    formatter = _file_handler(log).formatter
    record = logging.LogRecord(
        "agent_verbose", logging.INFO, __file__, 1, "hello", None, None
    )
    formatted = formatter.format(record)
    assert formatted.endswith("[INFO] hello")
    # Timestamp prefix matches the configured datefmt (YYYY-MM-DD HH:MM:SS).
    assert formatted[:4].isdigit()


def test_get_logger_writes_file(data_dir):
    """Logging through the configured logger creates the verbose log file."""
    log = agent_logger._get_logger()
    log.info("first line")
    assert "first line" in _read_log(data_dir)


# ── _clean ──────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "raw, expected",
    [
        (None, ""),
        ("", ""),
        ("   ", ""),
        ("plain text", "plain text"),
        ("  padded  ", "padded"),
        ("\x1b[31mred\x1b[0m", "red"),
        ("\x1b[1;32mbold green\x1b[0m text", "bold green text"),
        ("\x1b[31m  spaced  \x1b[0m", "spaced"),
    ],
)
def test_clean(raw, expected):
    """ANSI escape codes are stripped and surrounding whitespace trimmed."""
    assert agent_logger._clean(raw) == expected


def test_clean_falsy_zero_like():
    """Falsy non-string inputs short-circuit to empty string."""
    assert agent_logger._clean(0) == ""


# ── _format_actions ─────────────────────────────────────────────────────────────

def test_format_actions_empty():
    """Empty/None action lists yield the '(none)' placeholder."""
    assert agent_logger._format_actions([]) == "  (none)"
    assert agent_logger._format_actions(None) == "  (none)"


def test_format_actions_with_model_dump():
    """Pydantic-style actions are rendered via model_dump and numbered."""
    actions = [FakeAction({"click": 1}), FakeAction({"type": "hi"})]
    result = agent_logger._format_actions(actions)
    lines = result.split("\n")

    assert lines[0] == "  [1] {'click': 1}"
    assert lines[1] == "  [2] {'type': 'hi'}"


def test_format_actions_without_model_dump():
    """Actions lacking model_dump fall back to str()."""
    result = agent_logger._format_actions(["raw-action"])
    assert result == "  [1] raw-action"


def test_format_actions_model_dump_raises():
    """If model_dump raises, the action falls back to str() without erroring."""

    class Boom:
        def model_dump(self, exclude_none=True):
            raise ValueError("nope")

        def __str__(self):
            return "boom-repr"

    result = agent_logger._format_actions([Boom()])
    assert result == "  [1] boom-repr"


# ── on_step ──────────────────────────────────────────────────────────────────────

def test_on_step_no_agent_output(data_dir):
    """A falsy agent_output logs the '(no agent output)' debug line and returns."""
    agent_logger.on_step(FakeBrowserState(url="http://x"), None, 7)
    contents = _read_log(data_dir)
    assert "Step 7: (no agent output)" in contents


def test_on_step_full(data_dir):
    """All optional fields render when present, in the documented order."""
    state = FakeBrowserState(url="https://jobs.example/apply", title="Apply Now")
    output = FakeAgentOutput(
        evaluation_previous_goal="\x1b[32mwent well\x1b[0m",
        next_goal="click submit",
        memory="filled email field",
        thinking="need to submit the form",
        action=[FakeAction({"click_element": {"index": 3}})],
    )
    agent_logger.on_step(state, output, 2)
    contents = _read_log(data_dir)

    assert "Step 2 | https://jobs.example/apply — Apply Now" in contents
    assert "Thinking: need to submit the form" in contents
    assert "Eval prev goal: went well" in contents  # ANSI stripped
    assert "Next goal: click submit" in contents
    assert "Memory: filled email field" in contents
    assert "[1] {'click_element': {'index': 3}}" in contents


def test_on_step_minimal_fields_omitted(data_dir):
    """Empty optional fields are omitted; only the header + Actions appear."""
    state = FakeBrowserState(url="http://only-url")
    output = FakeAgentOutput()  # everything None/empty
    agent_logger.on_step(state, output, 1)
    contents = _read_log(data_dir)

    assert "Step 1 | http://only-url" in contents
    # No title separator, no optional sections.
    assert "—" not in contents
    assert "Thinking:" not in contents
    assert "Eval prev goal:" not in contents
    assert "Next goal:" not in contents
    assert "Memory:" not in contents
    assert "Actions:\n  (none)" in contents


def test_on_step_none_browser_state(data_dir):
    """A None browser_state degrades to an empty url/title without raising."""
    output = FakeAgentOutput(next_goal="proceed")
    agent_logger.on_step(None, output, 5)
    contents = _read_log(data_dir)

    assert "Step 5 | " in contents
    assert "Next goal: proceed" in contents


def test_on_step_action_none_coerced(data_dir):
    """An explicit None action attr is coerced to an empty list -> '(none)'."""
    state = FakeBrowserState(url="http://x")
    output = FakeAgentOutput()
    output.action = None  # the `or []` guard must handle this
    agent_logger.on_step(state, output, 3)
    assert "Actions:\n  (none)" in _read_log(data_dir)


# ── on_done ──────────────────────────────────────────────────────────────────────

def test_on_done_no_history(data_dir):
    """A falsy history logs the 'no history' line and returns early."""
    agent_logger.on_done(None)
    assert "Run complete (no history)" in _read_log(data_dir)


def test_on_done_full_summary(data_dir):
    """A complete history renders steps, status, duration, and trimmed errors."""
    history = FakeHistory(
        steps=4,
        done=True,
        success=True,
        duration=12.34,
        errors=["boom", "", "kaboom"],  # falsy entries filtered out
    )
    agent_logger.on_done(history)
    contents = _read_log(data_dir)

    assert "── Run Summary ──" in contents
    assert "Steps: 4" in contents
    assert "Done: True  Success: True" in contents
    assert "Duration: 12.3s" in contents
    assert "Errors (2):" in contents  # empty string filtered
    assert "- boom" in contents
    assert "- kaboom" in contents
    assert "── End Summary ──" in contents


def test_on_done_no_duration_no_errors(data_dir):
    """When duration is None and there are no errors, those sections are omitted."""
    history = FakeHistory(steps=1, done=False, success=False,
                          duration=None, errors=[])
    agent_logger.on_done(history)
    contents = _read_log(data_dir)

    assert "Steps: 1" in contents
    assert "Done: False  Success: False" in contents
    assert "Duration:" not in contents
    assert "Errors (" not in contents


def test_on_done_long_error_truncated(data_dir):
    """Individual error strings are truncated to 200 chars."""
    long_err = "x" * 500
    history = FakeHistory(steps=1, errors=[long_err])
    agent_logger.on_done(history)
    contents = _read_log(data_dir)

    assert "x" * 200 in contents
    assert "x" * 201 not in contents


def test_on_done_caps_at_five_errors(data_dir):
    """Only the last five errors are emitted even when more occurred."""
    errors = [f"err{i}" for i in range(8)]
    history = FakeHistory(steps=1, errors=errors)
    agent_logger.on_done(history)
    contents = _read_log(data_dir)

    assert "Errors (8):" in contents       # count reflects total
    assert "- err0" not in contents         # earliest dropped (only last 5 shown)
    assert "- err2" not in contents
    assert "- err3" in contents             # first of the last five
    assert "- err7" in contents


def test_on_done_missing_optional_methods(data_dir):
    """A history object lacking the optional methods uses the hasattr fallbacks."""
    bare = types.SimpleNamespace()  # truthy but no history/is_done/etc.
    agent_logger.on_done(bare)
    contents = _read_log(data_dir)

    assert "Steps: 0" in contents
    assert "Done: None  Success: None" in contents
    assert "Duration:" not in contents
    assert "Errors (" not in contents


# ── log_run_start ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "run_type, label",
    [
        ("collect", "Software Engineer"),
        ("apply", "Acme Corp"),
        ("", ""),  # edge: empty inputs still produce a banner
    ],
)
def test_log_run_start(data_dir, run_type, label):
    """A run-start banner with the type and label is written to the log."""
    agent_logger.log_run_start(run_type, label)
    contents = _read_log(data_dir)

    assert f"Run started: {run_type} — {label}" in contents
    assert "=" * 60 in contents
