"""Secret storage for API keys and passwords.

Secrets live in the OS keychain (macOS Keychain, Windows Credential Manager,
Linux Secret Service) through the ``keyring`` package. The JSON settings files
on disk only ever hold an empty string where a secret used to be.

When no usable keychain backend exists (headless Linux, CI, some sandboxes),
secrets fall back to ``secrets.json`` in the data dir with owner-only
permissions, and ``backend()`` reports ``"file"`` so the UI can say so.

Set ``LANGHIRE_SECRETS_BACKEND=file`` to force the file fallback (tests use it).
"""
from __future__ import annotations

import json
import logging
import os
import stat
import threading
from pathlib import Path

_log = logging.getLogger("secrets")
SERVICE = "langhire"
_lock = threading.Lock()
_keyring = None  # resolved lazily
_keyring_checked = False


def _data_dir() -> Path:
    from .config import get_data_dir  # local import: config imports us
    return get_data_dir()


def _get_keyring():
    """Return the keyring module if a real (non-fail, non-plaintext) backend exists."""
    global _keyring, _keyring_checked
    if os.environ.get("LANGHIRE_SECRETS_BACKEND", "").lower() == "file":
        return None
    if _keyring_checked:
        return _keyring
    _keyring_checked = True
    try:
        import keyring
        from keyring.backends import fail
        kr = keyring.get_keyring()
        name = type(kr).__module__ + "." + type(kr).__name__
        if isinstance(kr, fail.Keyring) or "plaintext" in name.lower() or "null" in name.lower():
            _log.warning(f"No secure keyring backend ({name}); using file fallback")
            _keyring = None
        else:
            # Probe it: e.g. Windows services / sandboxed sessions have no
            # credential store (WinError 1312) even though the backend loads.
            kr.get_password(SERVICE, "__probe__")
            _keyring = keyring
    except Exception as e:  # ImportError or backend init failure
        _log.warning(f"Keyring unavailable ({e}); using file fallback")
        _keyring = None
    return _keyring


def backend() -> str:
    return "keychain" if _get_keyring() else "file"


def _file_path() -> Path:
    return _data_dir() / "secrets.json"


def _read_file() -> dict:
    p = _file_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _write_file(data: dict) -> None:
    p = _file_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    try:
        os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass
    tmp.replace(p)


def get_secret(name: str) -> str:
    kr = _get_keyring()
    if kr:
        try:
            value = kr.get_password(SERVICE, name)
            if value:
                return value
        except Exception as e:
            _log.warning(f"keyring read failed for {name}: {type(e).__name__}")
    with _lock:  # also covers values written to the fallback after a keyring failure
        return _read_file().get(name, "")


def set_secret(name: str, value: str) -> None:
    kr = _get_keyring()
    if kr:
        try:
            if value:
                kr.set_password(SERVICE, name, value)
            else:
                try:
                    kr.delete_password(SERVICE, name)
                except Exception:
                    pass
            return
        except Exception as e:
            _log.warning(f"keyring write failed for {name}: {type(e).__name__}; using file")
    with _lock:
        data = _read_file()
        if value:
            data[name] = value
        else:
            data.pop(name, None)
        _write_file(data)


def delete_all(names: list[str]) -> None:
    for n in names:
        set_secret(n, "")
    p = _file_path()
    if p.exists():
        p.unlink()


# ── Which settings fields are secrets ───────────────────────────────────────
LLM_SECRET_KEYS = {"api_key", "access_key", "secret_key", "session_token"}


def llm_secret_names(settings: dict) -> list[tuple[str, str]]:
    """(provider, key) pairs in an LLM settings dict that are secrets."""
    out = []
    for provider, cfg in settings.items():
        if isinstance(cfg, dict):
            for k in cfg:
                if k in LLM_SECRET_KEYS:
                    out.append((provider, k))
    return out


def split_llm_secrets(settings: dict) -> dict:
    """Store secrets from an LLM settings dict; return a copy with them blanked."""
    clean = json.loads(json.dumps(settings))
    for provider, key in llm_secret_names(settings):
        value = str(settings[provider].get(key) or "")
        set_secret(f"llm.{provider}.{key}", value)
        clean[provider][key] = ""
    return clean


def merge_llm_secrets(settings: dict) -> dict:
    """Fill blank secret fields of an LLM settings dict from secret storage."""
    for provider, key in llm_secret_names(settings):
        if not settings[provider].get(key):
            settings[provider][key] = get_secret(f"llm.{provider}.{key}")
    return settings


def all_secret_names(llm_settings: dict) -> list[str]:
    names = [f"llm.{p}.{k}" for p, k in llm_secret_names(llm_settings)]
    names.append("site.password")
    return names
