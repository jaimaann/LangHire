"""User data lifecycle: retention, export and delete-everything.

* Agent conversation logs (screenshots, page text, typed answers) are pruned
  after ``log_retention_days``; 0 means they are not written at all.
* ``export_all`` returns one JSON document with everything LangHire stores
  about the user (secrets excluded).
* ``delete_all`` removes the data dir contents and the keychain entries.
"""
from __future__ import annotations

import logging
import shutil
import time
from pathlib import Path

from core import db, secrets
from core.config import get_data_dir, load_llm_settings, load_profile, load_settings
from core import shared_config as sc

_log = logging.getLogger("engine")


def prune_logs(days: int | None = None) -> int:
    """Delete conversation logs and run events older than `days`. Returns files removed."""
    if days is None:
        days = int(load_settings().get("log_retention_days", 14) or 0)
    cutoff = time.time() - max(days, 0) * 86400
    removed = 0
    logs = get_data_dir() / "logs"
    if logs.exists():
        for p in logs.rglob("*"):
            try:
                if p.is_file() and (days == 0 or p.stat().st_mtime < cutoff):
                    p.unlink()
                    removed += 1
            except OSError:
                pass
    try:
        db.prune_events(max(days, 1))
    except Exception as e:
        _log.warning(f"event prune failed: {e}")
    return removed


def _strip_secrets(llm: dict) -> dict:
    out = {}
    for k, v in llm.items():
        if isinstance(v, dict):
            out[k] = {kk: ("" if kk in secrets.LLM_SECRET_KEYS else vv) for kk, vv in v.items()}
        else:
            out[k] = v
    return out


def export_all() -> dict:
    settings = load_settings()
    settings["sensitive_data"] = {"email": settings.get("sensitive_data", {}).get("email", ""), "password": ""}
    store = sc.get_memory_store()
    return {
        "format": "langhire-export",
        "version": 1,
        "exported_at": db.now_iso(),
        "profile": load_profile(),
        "settings": settings,
        "llm_settings": _strip_secrets(load_llm_settings()),
        "jobs": list(db.read_jobs().values()),
        "applications": db.list_applications(limit=100000),
        "runs": db.list_runs(limit=100000),
        "qa": store.qa_list(),
        "memories": store.export_all(),
    }


def delete_all() -> list[str]:
    """Delete everything LangHire stored. Returns the top-level names removed."""
    names = secrets.all_secret_names(load_llm_settings())
    secrets.delete_all(names)
    # Empty every table first. On Windows a database file can't be deleted while
    # any thread (the engine loop, the metrics logger) still has it open, and
    # the old version silently left all jobs and memories in place.
    for path in (get_data_dir() / "langhire.db", get_data_dir() / "memory_store.db"):
        _wipe_sqlite(path)
    db.close_all()
    try:
        sc.get_memory_store().close()
    except Exception:
        pass
    sc._memory_store = None
    # Release the agent log file so Windows lets us delete it
    for h in list(logging.getLogger("agent_verbose").handlers):
        try:
            h.close()
        finally:
            logging.getLogger("agent_verbose").removeHandler(h)
    from core import agent_logger
    agent_logger._logger = None
    root = get_data_dir()
    removed = []
    for p in sorted(root.iterdir()):
        if p.name in ("backend.log", "backend.log.1", "backend.log.2", "backend.log.3", ".api_token"):
            continue  # the running backend holds these open; they hold no personal data
        try:
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
            else:
                p.unlink()
            removed.append(p.name)
        except OSError as e:
            _log.warning(f"could not delete {p.name}: {e}")
    return removed


def _wipe_sqlite(path: Path) -> None:
    """Delete all rows from every table (schema kept) and checkpoint the WAL."""
    if not path.exists():
        return
    import sqlite3
    try:
        conn = sqlite3.connect(str(path), timeout=30)
        try:
            tables = [r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name != 'schema_version'")]
            with conn:
                for t in tables:
                    conn.execute(f'DELETE FROM "{t}"')
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.execute("VACUUM")
        finally:
            conn.close()
    except sqlite3.Error as e:
        _log.warning(f"could not wipe {path.name}: {e}")
