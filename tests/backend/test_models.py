"""Unit tests for backend/models.py (Pydantic request models).

Validates defaults, field constraints (ge/le/gt bounds), Literal choices,
and that out-of-range / wrong-type input raises ValidationError.
"""
import pytest
from pydantic import ValidationError

import models


# ── CollectRequest ───────────────────────────────────────────────────────────

def test_collect_request_defaults():
    """CollectRequest applies documented defaults."""
    r = models.CollectRequest()
    assert r.title is None
    assert r.max_jobs == 0
    assert r.source == "linkedin"
    assert r.filters == {}


def test_collect_request_custom():
    """Custom values are accepted and the filters dict is preserved."""
    r = models.CollectRequest(title="SWE", max_jobs=50, source="indeed", filters={"remote": True})
    assert r.title == "SWE"
    assert r.max_jobs == 50
    assert r.filters == {"remote": True}


def test_collect_request_filters_default_factory_is_independent():
    """Each instance gets its own filters dict (no shared mutable default)."""
    a = models.CollectRequest()
    b = models.CollectRequest()
    a.filters["x"] = 1
    assert b.filters == {}


@pytest.mark.parametrize("bad", [-1, 501, 1000])
def test_collect_request_max_jobs_out_of_range(bad):
    """max_jobs outside [0, 500] is rejected."""
    with pytest.raises(ValidationError):
        models.CollectRequest(max_jobs=bad)


@pytest.mark.parametrize("ok", [0, 1, 250, 500])
def test_collect_request_max_jobs_boundaries(ok):
    """max_jobs accepts the inclusive boundaries."""
    assert models.CollectRequest(max_jobs=ok).max_jobs == ok


# ── ApplyRequest ─────────────────────────────────────────────────────────────

def test_apply_request_defaults():
    """ApplyRequest defaults to easy mode, no limit, single worker."""
    r = models.ApplyRequest()
    assert r.mode == "easy"
    assert r.limit is None
    assert r.workers == 1
    assert r.job_url is None
    assert r.job_urls is None


@pytest.mark.parametrize("mode", ["easy", "external", "all"])
def test_apply_request_valid_modes(mode):
    """All Literal mode values are accepted."""
    assert models.ApplyRequest(mode=mode).mode == mode


def test_apply_request_invalid_mode():
    """A mode outside the Literal set is rejected."""
    with pytest.raises(ValidationError):
        models.ApplyRequest(mode="turbo")


@pytest.mark.parametrize("bad", [0, 501])
def test_apply_request_limit_out_of_range(bad):
    """limit must fall within [1, 500] when provided."""
    with pytest.raises(ValidationError):
        models.ApplyRequest(limit=bad)


def test_apply_request_limit_boundaries():
    """limit accepts its inclusive boundaries."""
    assert models.ApplyRequest(limit=1).limit == 1
    assert models.ApplyRequest(limit=500).limit == 500


@pytest.mark.parametrize("bad", [0, 5, -1])
def test_apply_request_workers_out_of_range(bad):
    """workers must fall within [1, 4]."""
    with pytest.raises(ValidationError):
        models.ApplyRequest(workers=bad)


@pytest.mark.parametrize("ok", [1, 2, 3, 4])
def test_apply_request_workers_boundaries(ok):
    """workers accepts 1 through 4."""
    assert models.ApplyRequest(workers=ok).workers == ok


def test_apply_request_job_urls_list():
    """job_urls accepts a list of strings for batch apply."""
    r = models.ApplyRequest(job_urls=["a", "b"])
    assert r.job_urls == ["a", "b"]


# ── CollectFilters ───────────────────────────────────────────────────────────

def test_collect_filters_default():
    """CollectFilters defaults to an empty filters dict."""
    assert models.CollectFilters().filters == {}


def test_collect_filters_custom():
    """Custom filter values are preserved."""
    assert models.CollectFilters(filters={"k": "v"}).filters == {"k": "v"}


# ── DecayRequest ─────────────────────────────────────────────────────────────

def test_decay_request_defaults():
    """DecayRequest defaults to 30 days / 0.95 factor."""
    r = models.DecayRequest()
    assert r.days == 30
    assert r.factor == 0.95


@pytest.mark.parametrize("days", [0, 366])
def test_decay_request_days_out_of_range(days):
    """days must fall within [1, 365]."""
    with pytest.raises(ValidationError):
        models.DecayRequest(days=days)


@pytest.mark.parametrize("factor", [0, -0.1, 1.01])
def test_decay_request_factor_out_of_range(factor):
    """factor must be in (0, 1.0]."""
    with pytest.raises(ValidationError):
        models.DecayRequest(factor=factor)


def test_decay_request_factor_upper_boundary_inclusive():
    """factor == 1.0 is allowed (le=1.0)."""
    assert models.DecayRequest(factor=1.0).factor == 1.0


# ── CleanupRequest ───────────────────────────────────────────────────────────

def test_cleanup_request_default():
    """CleanupRequest defaults to a 0.3 threshold."""
    assert models.CleanupRequest().threshold == 0.3


@pytest.mark.parametrize("bad", [-0.1, 1.01])
def test_cleanup_request_threshold_out_of_range(bad):
    """threshold must fall within [0, 1.0]."""
    with pytest.raises(ValidationError):
        models.CleanupRequest(threshold=bad)


@pytest.mark.parametrize("ok", [0.0, 0.5, 1.0])
def test_cleanup_request_threshold_boundaries(ok):
    """threshold accepts its inclusive boundaries."""
    assert models.CleanupRequest(threshold=ok).threshold == ok


# ── Plugin requests ──────────────────────────────────────────────────────────

def test_plugin_import_request_requires_file_path():
    """file_path is required for PluginImportRequest."""
    assert models.PluginImportRequest(file_path="/x.yaml").file_path == "/x.yaml"
    with pytest.raises(ValidationError):
        models.PluginImportRequest()


def test_plugin_toggle_request_requires_enabled():
    """enabled is required for PluginToggleRequest."""
    assert models.PluginToggleRequest(enabled=True).enabled is True
    with pytest.raises(ValidationError):
        models.PluginToggleRequest()
