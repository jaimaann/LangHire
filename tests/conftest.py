"""
Shared pytest fixtures for the LangHire backend test suite.

The backend modules import each other with a `backend/`-rooted style
(e.g. `from core.config import ...`), so we put `backend/` on sys.path here.
We also isolate every test from the real OS app-data directory by pointing
HOME at a per-test temporary directory.
"""
import sys
from pathlib import Path

import pytest

# ── Make `backend/` importable as a top-level package root ──────────────────
# Modules do `from core.config import ...`, so the *backend* dir must be on path.
ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
for p in (str(ROOT), str(BACKEND)):
    if p not in sys.path:
        sys.path.insert(0, p)


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """
    Redirect the app data directory to an isolated tmp dir for the test.

    `core.config.get_data_dir()` derives its location from `Path.home()`, so
    pointing HOME (and the macOS/Windows equivalents) at tmp_path gives each
    test a clean, writable, throwaway config root.
    """
    home = tmp_path / "home"
    home.mkdir()
    data = home / "langhire-data"
    monkeypatch.setenv("LANGHIRE_DATA_DIR", str(data))
    monkeypatch.setenv("LANGHIRE_SECRETS_BACKEND", "file")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))  # Windows
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

    # Return the resolved data dir so tests can assert on files directly.
    import core.config as config
    return config.get_data_dir()


@pytest.fixture(autouse=True)
def _no_real_data_dir(tmp_path_factory, monkeypatch):
    """Every test gets a throwaway data dir, even ones that don't ask for one."""
    import os
    if not os.environ.get("LANGHIRE_DATA_DIR") or "pytest" not in os.environ.get("LANGHIRE_DATA_DIR", ""):
        d = tmp_path_factory.mktemp("lhdata")
        monkeypatch.setenv("LANGHIRE_DATA_DIR", str(d))
        monkeypatch.setenv("LANGHIRE_SECRETS_BACKEND", "file")
