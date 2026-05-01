"""
Configuration management for LangHire.
All settings stored in OS-appropriate app data directory.
No hardcoded values.
"""
import json
import platform
from pathlib import Path


def get_data_dir() -> Path:
    """Get OS-appropriate data directory for the app."""
    system = platform.system()
    if system == "Darwin":
        base = Path.home() / "Library" / "Application Support" / "langhire"
    elif system == "Windows":
        base = Path.home() / "AppData" / "Roaming" / "langhire"
    else:  # Linux
        base = Path.home() / ".config" / "langhire"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _load_json(path: Path, default=None):
    if path.exists():
        return json.loads(path.read_text())
    return default if default is not None else {}


def _save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.replace(path)
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

def load_profile() -> dict:
    return _load_json(get_data_dir() / "candidate_profile.json", {
        "name": "",
        "email": "",
        "phone": "",
        "address": {"street": "", "city": "", "state": "", "zip": "", "country": "USA"},
        "work_authorization": "Authorized to work in the US",
        "visa_sponsorship_needed": False,
        "willing_to_relocate": False,
        "preferred_work_mode": "hybrid",
        "years_of_experience": 0,
        "education": {"degree": "", "school": "", "graduation": ""},
        "current_role": "",
        "target_job_titles": [],
        "target_locations": [],
        "languages": ["English"],
        "skills": [],
        "salary_expectation": {"min": 50000, "max": 100000, "currency": "USD"},
        "notes": "",
    })


def save_profile(profile: dict):
    _save_json(get_data_dir() / "candidate_profile.json", profile)


# ── LLM Settings ──────────────────────────────────────────────────────────

def load_llm_settings() -> dict:
    return _load_json(get_data_dir() / "llm_settings.json", {
        "provider": "openai",
        "openai": {"api_key": "", "model": "gpt-4o"},
        "anthropic": {"api_key": "", "model": "claude-sonnet-4-20250514"},
        "bedrock": {"access_key": "", "secret_key": "", "region": "us-west-2", "model": "us.anthropic.claude-sonnet-4-6"},
        "ollama": {"base_url": "http://localhost:11434", "model": ""},
    })


def save_llm_settings(settings: dict):
    _save_json(get_data_dir() / "llm_settings.json", settings)


# ── App Settings ──────────────────────────────────────────────────────────

def load_settings() -> dict:
    return _load_json(get_data_dir() / "settings.json", {
        "resume_path": "",
        "blocked_domains": [],
        "sensitive_data": {"email": "", "password": ""},
        "max_failures": 8,
        "stagger_delay": 5,
        "data_dir": str(get_data_dir()),
    })


def save_settings(settings: dict):
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

