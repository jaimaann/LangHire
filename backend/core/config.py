"""
Configuration management for LangHire.
All settings stored in OS-appropriate app data directory.
No hardcoded values.
"""
import json
import os
import platform
from pathlib import Path
from .fileutil import replace_file


def get_data_dir() -> Path:
    """Get the app data directory.

    ``LANGHIRE_DATA_DIR`` wins (the Tauri host passes it so Rust and Python
    agree on one path; tests and isolated test runs use it too). Otherwise the
    OS default: macOS Application Support, Windows %APPDATA%, Linux ~/.config.
    """
    override = os.environ.get("LANGHIRE_DATA_DIR", "").strip()
    if override:
        base = Path(override).expanduser()
    else:
        system = platform.system()
        if system == "Darwin":
            base = Path.home() / "Library" / "Application Support" / "langhire"
        elif system == "Windows":
            appdata = os.environ.get("APPDATA", "").strip()
            root = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
            base = root / "langhire"
        else:  # Linux: respect XDG_CONFIG_HOME
            xdg = os.environ.get("XDG_CONFIG_HOME", "").strip()
            base = (Path(xdg) if xdg else Path.home() / ".config") / "langhire"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _load_json(path: Path, default=None):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            # A corrupt file must not brick the app: keep a copy, use defaults.
            path.replace(path.with_suffix(path.suffix + ".corrupt"))
    return default if default is not None else {}


def _save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    replace_file(tmp, path)
    if any(s in path.name for s in ("llm_settings", "settings")):
        try:
            import os, stat
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            import logging
            logging.getLogger("config").warning(
                f"Could not set restrictive permissions on {path.name}"
            )


# ── Profile ───────────────────────────────────────────────────────────────

DEFAULT_PROFILE = {
    "name": "",
    "email": "",
    "phone": "",
    "phone_country_code": "+1",
    "country": "US",
    "address": {"street": "", "city": "", "state": "", "zip": "", "country": ""},
    "work_authorization": "",
    "visa_sponsorship_needed": False,
    "willing_to_relocate": False,
    "preferred_work_mode": "",
    "years_of_experience": 0,
    "education": {"degree": "", "school": "", "graduation": ""},
    "current_role": "",
    "target_job_titles": [],
    "target_locations": [],
    "languages": ["English"],
    "skills": [],
    # No made-up numbers: the agent answers salary questions from this
    "salary_expectation": {"min": 0, "max": 0, "currency": "USD", "period": "annual"},
    # Free text ("INR 6,00,000 fixed + 50,000 variable"); forms in India ask for current CTC
    "current_compensation": "",
    "notice_period": "",
    "nationality": "",
    "date_of_birth": "",
    "cover_letter": "",
    "date_format": "MM/DD/YYYY",
    "notes": "",
}


def _deep_merge(defaults: dict, stored: dict) -> dict:
    out = _copy(defaults)
    for k, v in (stored or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = {**out[k], **v}
        elif v is not None:
            out[k] = v
    return out


def load_profile() -> dict:
    """The candidate profile, with every field present (missing ones from defaults).

    A profile missing any field used to crash every application with a bare KeyError.
    """
    return _deep_merge(DEFAULT_PROFILE, _load_json(get_data_dir() / "candidate_profile.json", {}))


def save_profile(profile: dict):
    _save_json(get_data_dir() / "candidate_profile.json", profile)


# ── LLM Settings ──────────────────────────────────────────────────────────

def load_llm_settings() -> dict:
    """LLM settings with secrets filled in from the OS keychain.

    Plaintext keys left over from older versions are moved into the keychain
    the first time they are read.
    """
    from . import secrets
    path = get_data_dir() / "llm_settings.json"
    settings = _load_json(path, _default_llm_settings())
    if secrets.llm_secret_names(settings) and any(
        settings[p].get(k) for p, k in secrets.llm_secret_names(settings)
    ):
        _save_json(path, secrets.split_llm_secrets(settings))  # migrate plaintext
    return secrets.merge_llm_secrets(settings)


def _default_llm_settings() -> dict:
    return _copy({
        "provider": "openrouter",
        "openai": {"api_key": "", "model": "gpt-4o"},
        "anthropic": {"api_key": "", "model": "claude-sonnet-4-5"},
        "bedrock": {"access_key": "", "secret_key": "", "region": "us-west-2", "model": "us.anthropic.claude-sonnet-4-6"},
        "gemini": {"api_key": "", "model": "gemini-2.5-pro"},
        "ollama": {"base_url": "http://localhost:11434", "model": ""},
        "openrouter": {"api_key": "", "model": "qwen/qwen3.6-plus"},
    })


def _copy(d: dict) -> dict:
    return json.loads(json.dumps(d))


def save_llm_settings(settings: dict):
    from . import secrets
    _save_json(get_data_dir() / "llm_settings.json", secrets.split_llm_secrets(settings))


# ── App Settings ──────────────────────────────────────────────────────────

DEFAULT_SETTINGS = {
    "resume_path": "",
    "blocked_domains": [],
    "sensitive_data": {"email": "", "password": ""},
    "max_failures": 8,
    "stagger_delay": 5,
    "telemetry_enabled": False,       # opt-in only
    "theme": "system",
    "log_retention_days": 14,         # 0 = don't keep agent conversation logs
    "daily_apply_cap": 25,            # max applications per job source per day
    "max_run_cost_usd": 5.0,          # stop starting new applications past this LLM spend
    "browser_cdp_url": "",            # e.g. http://127.0.0.1:9222 to drive your own Chrome
    "email_otp_via_gmail": False,     # let the agent read Gmail for verification codes
    "test_mode": False,               # click Submit but intercept the request: nothing is sent
}


def load_settings() -> dict:
    """App settings merged over defaults; the site password comes from the keychain."""
    from . import secrets
    path = get_data_dir() / "settings.json"
    stored = _load_json(path, {})
    settings = {**_copy(DEFAULT_SETTINGS), **stored}
    settings["data_dir"] = str(get_data_dir())
    sd = dict(settings.get("sensitive_data") or {})
    if sd.get("password"):  # migrate a plaintext password from older versions
        secrets.set_secret("site.password", sd["password"])
        stored["sensitive_data"] = {**sd, "password": ""}
        _save_json(path, stored)
    sd["password"] = secrets.get_secret("site.password")
    sd.setdefault("email", "")
    settings["sensitive_data"] = sd
    return settings


def save_settings(settings: dict):
    from . import secrets
    settings = dict(settings)
    settings.pop("data_dir", None)  # derived, never persisted
    if isinstance(settings.get("sensitive_data"), dict):
        sd = dict(settings["sensitive_data"])
        if "password" in sd:
            secrets.set_secret("site.password", str(sd.get("password") or ""))
            sd["password"] = ""
        settings["sensitive_data"] = sd
    if "log_retention_days" in settings:
        settings["log_retention_days"] = max(0, min(int(settings["log_retention_days"]), 365))
    if "daily_apply_cap" in settings:
        settings["daily_apply_cap"] = max(0, min(int(settings["daily_apply_cap"]), 500))
    if "max_run_cost_usd" in settings:
        settings["max_run_cost_usd"] = max(0.0, min(float(settings["max_run_cost_usd"]), 1000.0))
    if "max_failures" in settings:
        settings["max_failures"] = max(1, min(int(settings["max_failures"]), 50))
    if "stagger_delay" in settings:
        settings["stagger_delay"] = max(0, min(int(settings["stagger_delay"]), 300))
    if "blocked_domains" in settings:
        settings["blocked_domains"] = [
            str(d).strip() for d in settings["blocked_domains"]
            if isinstance(d, str) and d.strip()
        ]
    _save_json(get_data_dir() / "settings.json", settings)

