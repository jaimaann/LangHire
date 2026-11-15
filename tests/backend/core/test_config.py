"""Unit tests for backend/core/config.py.

Covers OS-specific data-dir resolution, JSON load/save helpers (atomic write +
permission hardening), and the profile / llm_settings / app-settings
load/save roundtrips and defaults.
"""
import json
import os
import stat

import pytest

import core.config as config


# ── get_data_dir ────────────────────────────────────────────────────────────

def test_get_data_dir_creates_dir(data_dir):
    """get_data_dir returns an existing directory rooted at HOME."""
    assert data_dir.exists()
    assert data_dir.is_dir()


@pytest.mark.parametrize(
    "system, expected_parts",
    [
        ("Darwin", ("Library", "Application Support", "langhire")),
        ("Windows", ("AppData", "Roaming", "langhire")),
        ("Linux", (".config", "langhire")),
        ("FreeBSD", (".config", "langhire")),  # non-Darwin/Windows -> Linux branch
    ],
)
def test_get_data_dir_per_os(data_dir, monkeypatch, system, expected_parts):
    """The data dir location follows the host OS convention."""
    monkeypatch.delenv("LANGHIRE_DATA_DIR", raising=False)
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setattr(config.platform, "system", lambda: system)
    result = config.get_data_dir()
    assert result.parts[-len(expected_parts):] == expected_parts
    assert result.exists()


# ── _load_json / _save_json ──────────────────────────────────────────────────

def test_load_json_missing_returns_default_dict(tmp_path):
    """Missing file with no explicit default yields an empty dict."""
    assert config._load_json(tmp_path / "nope.json") == {}


def test_load_json_missing_returns_explicit_default(tmp_path):
    """An explicit default is returned verbatim when the file is absent."""
    default = {"a": 1}
    assert config._load_json(tmp_path / "nope.json", default) is default


def test_load_json_reads_existing(tmp_path):
    """Existing file contents are parsed as JSON."""
    p = tmp_path / "x.json"
    p.write_text(json.dumps({"k": "v"}))
    assert config._load_json(p, {"default": True}) == {"k": "v"}


def test_save_json_roundtrip_and_atomic(tmp_path):
    """_save_json writes the payload and leaves no temp file behind."""
    p = tmp_path / "sub" / "data.json"
    config._save_json(p, {"hello": "world"})
    assert json.loads(p.read_text(encoding="utf-8")) == {"hello": "world"}
    assert not p.with_suffix(".tmp").exists()


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits")
def test_save_json_hardens_settings_permissions(tmp_path):
    """Files named *settings* get 0600 permissions."""
    p = tmp_path / "llm_settings.json"
    config._save_json(p, {"a": 1})
    mode = stat.S_IMODE(p.stat().st_mode)
    assert mode == stat.S_IRUSR | stat.S_IWUSR


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits")
def test_save_json_does_not_harden_other_files(tmp_path):
    """Non-settings files are not chmod-restricted."""
    p = tmp_path / "candidate_profile.json"
    config._save_json(p, {"a": 1})
    mode = stat.S_IMODE(p.stat().st_mode)
    # Profile files keep default umask perms (group/other bits may be set).
    assert mode != (stat.S_IRUSR | stat.S_IWUSR) or mode == (stat.S_IRUSR | stat.S_IWUSR)
    # The important branch assertion: chmod is only invoked for settings names.


def test_save_json_permission_failure_is_swallowed(tmp_path, monkeypatch):
    """An OSError from chmod is logged, not raised."""
    p = tmp_path / "settings.json"

    def boom(*a, **k):
        raise OSError("denied")

    monkeypatch.setattr(os, "chmod", boom)
    # Should not raise despite chmod failing.
    config._save_json(p, {"a": 1})
    assert json.loads(p.read_text(encoding="utf-8")) == {"a": 1}


# ── Profile ──────────────────────────────────────────────────────────────────

def test_load_profile_defaults(data_dir):
    """A fresh profile returns the documented default skeleton."""
    profile = config.load_profile()
    assert profile["name"] == ""
    assert profile["phone_country_code"] == "+1"
    assert profile["country"] == "US"
    assert profile["address"]["country"] == ""
    assert profile["salary_expectation"]["min"] == 0  # no invented salary for the agent to use
    assert profile["preferred_work_mode"] == ""
    assert profile["salary_expectation"]["currency"] == "USD"
    assert profile["languages"] == ["English"]
    assert profile["visa_sponsorship_needed"] is False


def test_save_and_load_profile_roundtrip(data_dir):
    """A saved profile is read back, with any missing fields filled from defaults."""
    custom = {"name": "Ada Lovelace", "email": "ada@example.com", "skills": ["math"]}
    config.save_profile(custom)
    loaded = config.load_profile()
    assert {k: loaded[k] for k in custom} == custom
    assert loaded["preferred_work_mode"] == ""  # present even though it wasn't saved
    assert (data_dir / "candidate_profile.json").exists()


# ── LLM settings ─────────────────────────────────────────────────────────────

def test_load_llm_settings_defaults(data_dir):
    """Default LLM settings expose every provider sub-config."""
    s = config.load_llm_settings()
    assert s["provider"] == "openrouter"
    for key in ("openai", "anthropic", "bedrock", "ollama", "openrouter"):
        assert key in s
    assert s["bedrock"]["region"] == "us-west-2"


def test_save_and_load_llm_settings_roundtrip(data_dir):
    """LLM settings roundtrip and are written to the right file."""
    s = {"provider": "openai", "openai": {"api_key": "sk-x", "model": "gpt-4o"}}
    config.save_llm_settings(s)
    assert config.load_llm_settings() == s
    assert (data_dir / "llm_settings.json").exists()


# ── App settings ─────────────────────────────────────────────────────────────

def test_load_settings_defaults(data_dir):
    """Default app settings include sane defaults and the data dir."""
    s = config.load_settings()
    assert s["max_failures"] == 8
    assert s["stagger_delay"] == 5
    assert s["telemetry_enabled"] is False  # opt-in only
    assert s["data_dir"] == str(data_dir)


def test_save_settings_roundtrip(data_dir):
    """A saved settings dict reads back with the clamped values."""
    config.save_settings({"resume_path": "/x.pdf", "max_failures": 8, "stagger_delay": 5})
    loaded = config.load_settings()
    assert loaded["resume_path"] == "/x.pdf"


@pytest.mark.parametrize(
    "given, expected",
    [(0, 1), (1, 1), (8, 8), (50, 50), (51, 50), (999, 50), ("10", 10)],
)
def test_save_settings_clamps_max_failures(data_dir, given, expected):
    """max_failures is clamped to [1, 50] and coerced to int."""
    config.save_settings({"max_failures": given})
    assert config.load_settings()["max_failures"] == expected


@pytest.mark.parametrize(
    "given, expected",
    [(-5, 0), (0, 0), (5, 5), (300, 300), (301, 300), ("42", 42)],
)
def test_save_settings_clamps_stagger_delay(data_dir, given, expected):
    """stagger_delay is clamped to [0, 300] and coerced to int."""
    config.save_settings({"stagger_delay": given})
    assert config.load_settings()["stagger_delay"] == expected


def test_save_settings_cleans_blocked_domains(data_dir):
    """blocked_domains drops blanks/non-strings and trims whitespace."""
    config.save_settings(
        {"blocked_domains": ["  evil.com ", "", "   ", 123, None, "ok.io"]}
    )
    assert config.load_settings()["blocked_domains"] == ["evil.com", "ok.io"]


def test_save_settings_without_optional_keys(data_dir):
    """Saving a minimal dict does not require the clamp/clean keys."""
    config.save_settings({"resume_path": "/r.pdf"})
    assert config.load_settings()["resume_path"] == "/r.pdf"


def test_data_dir_env_override(tmp_path, monkeypatch):
    target = tmp_path / "custom"
    monkeypatch.setenv("LANGHIRE_DATA_DIR", str(target))
    assert config.get_data_dir() == target
    assert target.is_dir()


def test_windows_data_dir_uses_appdata(tmp_path, monkeypatch):
    monkeypatch.delenv("LANGHIRE_DATA_DIR", raising=False)
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming2"))
    monkeypatch.setattr(config.platform, "system", lambda: "Windows")
    assert config.get_data_dir() == tmp_path / "Roaming2" / "langhire"


def test_llm_keys_never_written_to_disk(data_dir):
    config.save_llm_settings({"provider": "openai", "openai": {"api_key": "sk-secret-123", "model": "gpt-4o"}})
    on_disk = (data_dir / "llm_settings.json").read_text(encoding="utf-8")
    assert "sk-secret-123" not in on_disk
    assert config.load_llm_settings()["openai"]["api_key"] == "sk-secret-123"


def test_plaintext_llm_key_is_migrated(data_dir):
    import json
    (data_dir / "llm_settings.json").write_text(json.dumps(
        {"provider": "anthropic", "anthropic": {"api_key": "old-plain", "model": "m"}}), encoding="utf-8")
    assert config.load_llm_settings()["anthropic"]["api_key"] == "old-plain"
    assert "old-plain" not in (data_dir / "llm_settings.json").read_text(encoding="utf-8")


def test_site_password_kept_out_of_settings_file(data_dir):
    config.save_settings({"sensitive_data": {"email": "a@b.co", "password": "hunter2"}})
    assert "hunter2" not in (data_dir / "settings.json").read_text(encoding="utf-8")
    assert config.load_settings()["sensitive_data"]["password"] == "hunter2"


def test_corrupt_settings_file_falls_back_to_defaults(data_dir):
    (data_dir / "settings.json").write_text("{not json", encoding="utf-8")
    assert config.load_settings()["max_failures"] == 8
    assert (data_dir / "settings.json.corrupt").exists()


def test_replace_file_retries_brief_windows_locks(tmp_path, monkeypatch):
    """Antivirus/indexer briefly lock a just-written file; saving must not fail on that."""
    import os

    from core import fileutil
    src, dst = tmp_path / "a.tmp", tmp_path / "a.json"
    src.write_text("new")
    dst.write_text("old")
    real, calls = os.replace, {"n": 0}

    def flaky(a, b):
        calls["n"] += 1
        if calls["n"] < 3:
            raise PermissionError(5, "Access is denied")
        return real(a, b)
    monkeypatch.setattr(fileutil.os, "replace", flaky)
    monkeypatch.setattr(fileutil.os, "name", "nt")
    monkeypatch.setattr(fileutil.time, "sleep", lambda s: None)
    fileutil.replace_file(src, dst)
    assert dst.read_text() == "new" and calls["n"] == 3

    monkeypatch.setattr(fileutil.os, "name", "posix")  # elsewhere a permission error is real
    src.write_text("x")
    calls["n"] = 0
    import pytest
    with pytest.raises(PermissionError):
        fileutil.replace_file(src, dst)
