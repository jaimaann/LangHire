"""
Unit tests for backend/memory/extractors.py.

The extractors operate on a browser-use ``result`` object whose ``history`` is
a list of items, each with a ``model_output`` carrying ``memory``,
``current_state``, and ``action`` fields. We build lightweight fakes for those
shapes. The LLM-based path is always exercised with a mocked ``llm_call`` — no
network is touched.
"""
import types

import pytest

from memory.extractors import (
    _build_action_summary,
    extract_learnings_from_markers,
    extract_learnings_via_llm,
    store_learnings,
)
from memory.store import MemoryStore


# ── Fake history builders ───────────────────────────────────────────────────────

def _model_output(memory="", eval_prev="", next_goal="", actions=None):
    """Build a fake browser-use model_output object."""
    state = None
    if eval_prev or next_goal:
        state = types.SimpleNamespace(
            evaluation_previous_goal=eval_prev, next_goal=next_goal
        )
    return types.SimpleNamespace(
        memory=memory, current_state=state, action=actions or []
    )


def _result(model_outputs):
    """Wrap a list of model_outputs into a fake result with .history."""
    history = [types.SimpleNamespace(model_output=mo) for mo in model_outputs]
    return types.SimpleNamespace(history=history)


@pytest.fixture
def store(tmp_path):
    s = MemoryStore(db_path=tmp_path / "memory_store.db")
    yield s
    s.close()


# ── Marker-based extraction ──────────────────────────────────────────────────

def test_extract_markers_happy_path():
    """Well-formed @@LEARNING markers are parsed into learning dicts."""
    marker = ('@@LEARNING: {"domain": "linkedin.com", "category": "navigation", '
              '"insight": "Use Easy Apply modal"}')
    result = _result([_model_output(memory=marker)])
    learnings = extract_learnings_from_markers(result)
    assert learnings == [{
        "domain": "linkedin.com",
        "category": "navigation",
        "content": "Use Easy Apply modal",
    }]


def test_extract_markers_dedupes_insights():
    """The same insight emitted twice is only kept once."""
    marker = '@@LEARNING: {"insight": "dup insight", "category": "navigation"}'
    result = _result([_model_output(memory=marker), _model_output(memory=marker)])
    learnings = extract_learnings_from_markers(result)
    assert len(learnings) == 1


def test_extract_markers_defaults_category():
    """Missing category defaults to form_strategy; missing domain to ''."""
    marker = '@@LEARNING: {"insight": "no category here"}'
    result = _result([_model_output(memory=marker)])
    [learning] = extract_learnings_from_markers(result)
    assert learning["category"] == "form_strategy"
    assert learning["domain"] == ""


def test_extract_markers_skips_malformed_json():
    """A malformed JSON payload is skipped without raising."""
    bad = '@@LEARNING: {not valid json}'
    good = '@@LEARNING: {"insight": "valid one"}'
    result = _result([_model_output(memory=bad), _model_output(memory=good)])
    learnings = extract_learnings_from_markers(result)
    assert [l["content"] for l in learnings] == ["valid one"]


def test_extract_markers_skips_empty_insight():
    """A marker with an empty insight string is ignored."""
    marker = '@@LEARNING: {"insight": "   "}'
    result = _result([_model_output(memory=marker)])
    assert extract_learnings_from_markers(result) == []


def test_extract_markers_ignores_items_without_output():
    """History items lacking a model_output are skipped."""
    result = types.SimpleNamespace(
        history=[types.SimpleNamespace(model_output=None)]
    )
    assert extract_learnings_from_markers(result) == []


def test_extract_markers_handles_missing_memory_attr():
    """A model_output without a memory attr yields no learnings, no crash."""
    mo = types.SimpleNamespace(memory=None)  # falls back to "" via `or ""`
    result = _result([mo])
    assert extract_learnings_from_markers(result) == []


def test_extract_markers_empty_history():
    """Empty history → empty result."""
    assert extract_learnings_from_markers(_result([])) == []


# ── Action summary builder ──────────────────────────────────────────────────

def test_build_action_summary_includes_all_parts():
    """Eval, goal, memo, and actions all appear in the per-step summary."""
    mo = _model_output(
        memory="some memory text",
        eval_prev="went well",
        next_goal="click submit",
        actions=["clickElement(1)", "scroll()"],
    )
    summary = _build_action_summary(_result([mo]))
    assert "eval: went well" in summary
    assert "goal: click submit" in summary
    assert "memo: some memory text" in summary
    assert "actions:" in summary
    assert "Step 0:" in summary


def test_build_action_summary_strips_markers_from_memo():
    """@@LEARNING markers are stripped out of the memo text."""
    mo = _model_output(
        memory='real note @@LEARNING: {"insight": "x"} more note'
    )
    summary = _build_action_summary(_result([mo]))
    assert "@@LEARNING" not in summary
    assert "real note" in summary


def test_build_action_summary_limits_actions_to_three():
    """At most 3 actions per step are summarised."""
    mo = _model_output(actions=[f"a{i}()" for i in range(10)])
    summary = _build_action_summary(_result([mo]))
    # Only a0, a1, a2 should appear.
    assert "a0()" in summary and "a2()" in summary
    assert "a3()" not in summary


def test_build_action_summary_keeps_last_30_steps():
    """Only the trailing 30 steps are retained."""
    mos = [_model_output(memory=f"note {i}") for i in range(40)]
    summary = _build_action_summary(_result(mos))
    lines = summary.splitlines()
    assert len(lines) == 30
    assert "note 10" in summary  # step 10 is the first kept
    assert "note 9" not in summary  # step 9 dropped


def test_build_action_summary_empty_for_no_output():
    """No model_output anywhere → empty summary."""
    result = _result([_model_output()])  # nothing meaningful
    assert _build_action_summary(result) == ""


# ── LLM-based extraction ─────────────────────────────────────────────────────

def _result_with_content():
    """A result that produces a non-empty action summary."""
    return _result([_model_output(memory="did a thing", next_goal="finish")])


def test_extract_via_llm_none_callable_returns_empty():
    """Without an llm_call, extraction is a no-op."""
    assert extract_learnings_via_llm(
        _result_with_content(), "https://x.com", "Engineer", True, llm_call=None
    ) == []


def test_extract_via_llm_empty_summary_returns_empty():
    """If there are no actions to summarise, no LLM call is made."""
    calls = []
    extract_learnings_via_llm(
        _result([_model_output()]), "https://x.com", "Eng", True,
        llm_call=lambda p: calls.append(p) or "[]",
    )
    assert calls == []  # short-circuited before calling the LLM


def test_extract_via_llm_parses_json_array():
    """A JSON array embedded in LLM output is parsed into learnings."""
    def fake_llm(prompt):
        # Prompt should mention the resolved domain.
        assert "linkedin.com" in prompt
        return ('Sure, here you go:\n'
                '[{"category": "navigation", "content": "Use the modal"},'
                ' {"category": "site_structure", "content": "3 steps"}]')

    learnings = extract_learnings_via_llm(
        _result_with_content(),
        "https://www.linkedin.com/jobs/view/1",
        "Engineer", True, llm_call=fake_llm,
    )
    assert len(learnings) == 2
    assert all(l["domain"] == "linkedin.com" for l in learnings)
    assert learnings[0]["content"] == "Use the modal"


def test_extract_via_llm_failure_prompt_wording():
    """A failed run prompts for what went wrong (FAILED keyword present)."""
    captured = {}

    def fake_llm(prompt):
        captured["prompt"] = prompt
        return "[]"

    extract_learnings_via_llm(
        _result_with_content(), "https://x.com", "Eng", False, llm_call=fake_llm
    )
    assert "FAILED" in captured["prompt"]
    assert "went wrong" in captured["prompt"]


def test_extract_via_llm_filters_blank_and_nondict():
    """Entries that aren't dicts or have blank content are filtered out."""
    def fake_llm(_):
        return '["a string", {"content": "   "}, {"content": "keep me"}]'

    learnings = extract_learnings_via_llm(
        _result_with_content(), "https://x.com", "Eng", True, llm_call=fake_llm
    )
    assert [l["content"] for l in learnings] == ["keep me"]


def test_extract_via_llm_no_json_array_returns_empty():
    """Output without a JSON array yields no learnings."""
    learnings = extract_learnings_via_llm(
        _result_with_content(), "https://x.com", "Eng", True,
        llm_call=lambda _: "I could not produce anything useful.",
    )
    assert learnings == []


def test_extract_via_llm_swallows_llm_exception(capsys):
    """An exception inside llm_call is caught and reported, not raised."""
    def boom(_):
        raise RuntimeError("model down")

    learnings = extract_learnings_via_llm(
        _result_with_content(), "https://x.com", "Eng", True, llm_call=boom
    )
    assert learnings == []
    assert "LLM call failed" in capsys.readouterr().out


def test_extract_via_llm_malformed_json_returns_empty():
    """A JSON array that fails to parse yields no learnings."""
    learnings = extract_learnings_via_llm(
        _result_with_content(), "https://x.com", "Eng", True,
        llm_call=lambda _: "[ {broken json ]",
    )
    assert learnings == []


# ── store_learnings() ─────────────────────────────────────────────────────────

def test_store_learnings_counts_new_and_reinforced(store, capsys):
    """New learnings count as new; re-stored ones count as reinforced."""
    learnings = [
        {"domain": "linkedin.com", "category": "navigation", "content": "A"},
        {"domain": "linkedin.com", "category": "navigation", "content": "B"},
    ]
    new, reinforced = store_learnings(
        store, learnings, "https://www.linkedin.com/jobs/1", success=True
    )
    assert (new, reinforced) == (2, 0)

    # Re-store the same → both reinforced.
    new2, reinforced2 = store_learnings(
        store, learnings, "https://www.linkedin.com/jobs/1", success=True
    )
    assert (new2, reinforced2) == (0, 2)
    # The success/confidence on a successful run is 0.85.
    rows = store.search(website_domain="linkedin.com")
    assert all(r["success"] == 1 for r in rows)


def test_store_learnings_uses_url_domain_when_missing(store):
    """A learning without its own domain falls back to the job_url's domain."""
    learnings = [{"category": "navigation", "content": "X"}]  # no domain key
    store_learnings(store, learnings, "https://www.linkedin.com/jobs/1", success=True)
    rows = store.search(website_domain="linkedin.com")
    assert len(rows) == 1


def test_store_learnings_failure_confidence(store):
    """Failed runs are stored with lower (0.5) confidence and success=0."""
    learnings = [{"domain": "x.com", "category": "failure_recovery", "content": "Y"}]
    store_learnings(store, learnings, "https://x.com/jobs/1", success=False)
    rows = store.search(website_domain="x.com", success_only=False)
    assert rows[0]["confidence"] == pytest.approx(0.5)
    assert rows[0]["success"] == 0


def test_store_learnings_empty_list(store):
    """An empty learnings list stores nothing and returns zeros."""
    assert store_learnings(store, [], "https://x.com/1", success=True) == (0, 0)
