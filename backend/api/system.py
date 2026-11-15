"""Health, setup status, countries, and the user's data (export / delete)."""
from __future__ import annotations

import os
import sys

from fastapi import APIRouter

from core import chromium, secrets
from core.config import load_llm_settings, load_profile, load_settings, save_settings
from core.country_config import COUNTRY_CONFIGS, NOTICE_PERIOD_OPTIONS
from engine import data as user_data
from engine.runner import manager
from models import DataDeleteRequest

from .auth import auth_status
from .common import api_error, get_memory_store

router = APIRouter()

APP_VERSION = os.environ.get("LANGHIRE_APP_VERSION", "1.0.0")


@router.get("/chromium/status")
async def chromium_status():
    return chromium.chromium_status


@router.get("/health")
async def health():
    db_ok = False
    try:
        store = get_memory_store()
        if store:
            store.get_stats()
            db_ok = True
    except Exception:
        pass
    state = chromium.chromium_status.get("state")
    chromium_ok = state == "ready"
    chromium_installing = state == "installing"
    if not chromium_ok and not chromium_installing:
        try:
            chromium_ok = chromium.find_playwright_chromium() is not None
        except Exception:
            pass
    llm_ok = llm_configured(load_llm_settings())
    worker_running = manager.is_running("collect") or manager.is_running("apply")
    all_ok = db_ok and chromium_ok and llm_ok
    return {
        "status": "ok" if all_ok else "degraded",
        "version": APP_VERSION,
        "frozen": getattr(sys, "frozen", False),
        "secrets_backend": secrets.backend(),
        "checks": {
            "database": db_ok,
            "chromium": chromium_ok,
            "chromium_installing": chromium_installing,
            "llm_configured": llm_ok,
            "worker_running": bool(worker_running),
        },
    }


def llm_configured(llm: dict) -> bool:
    provider = llm.get("provider", "")
    cfg = llm.get(provider) or {}
    if provider == "bedrock":
        if cfg.get("auth_mode") == "keys":
            return bool(cfg.get("access_key", "").strip() and cfg.get("secret_key", "").strip())
        return True  # AWS profile mode
    if provider in ("ollama", "openai_compatible"):
        return bool((cfg.get("base_url") or "").strip())
    if provider in ("openai", "anthropic", "openrouter", "gemini", "zai", "xai"):
        return bool((cfg.get("api_key") or "").strip())
    return False


@router.get("/setup/status")
async def get_setup_status():
    profile = load_profile()
    settings = load_settings()
    profile_done = bool(profile.get("name", "").strip())
    llm_done = llm_configured(load_llm_settings())
    resume_done = bool(settings.get("resume_path", "").strip())
    chromium_done = chromium.find_playwright_chromium() is not None or bool(settings.get("browser_cdp_url"))
    auth = await auth_status()
    linkedin_done = auth.get("linkedin", {}).get("logged_in", False)
    gmail_done = auth.get("gmail", {}).get("logged_in", False)
    return {
        "profile": profile_done,
        "llm": llm_done,
        "resume": resume_done,
        "chromium": chromium_done,
        "linkedin": linkedin_done,
        "gmail": gmail_done,
        "onboarding_completed": settings.get("onboarding_completed", False),
        # Logging in to a job board is optional: jobs can be added by URL, and
        # most sources work without an account.
        "all_required_done": profile_done and llm_done and resume_done,
    }


@router.post("/setup/complete-onboarding")
async def complete_onboarding():
    settings = load_settings()
    settings["onboarding_completed"] = True
    save_settings(settings)
    return {"success": True}


@router.get("/countries")
async def get_countries():
    return {"success": True, "countries": COUNTRY_CONFIGS, "notice_period_options": NOTICE_PERIOD_OPTIONS}


@router.get("/countries/{code}")
async def get_country(code: str):
    if code not in COUNTRY_CONFIGS:
        return api_error("not_found", f"Country code '{code}' not supported", 404)
    return {"success": True, "config": COUNTRY_CONFIGS[code]}


# ── Your data ──────────────────────────────────────────────────────────────

@router.get("/data/export")
async def export_data():
    """Everything LangHire stores about you, as one JSON document (no secrets)."""
    return user_data.export_all()


@router.post("/data/delete")
async def delete_data(body: DataDeleteRequest):
    """Delete all local data and keychain entries. Stops any running work first."""
    manager.cancel_all()
    from engine.browsers import kill_profile_browsers
    kill_profile_browsers()
    deleted = user_data.delete_all()
    return {"ok": True, "deleted": deleted}


@router.post("/data/prune-logs")
async def prune_logs():
    return {"ok": True, "removed": user_data.prune_logs()}
