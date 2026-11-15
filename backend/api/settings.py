"""Profile, app settings and LLM settings."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter

from core.llm_factory import ainvoke_text

from core.config import (load_llm_settings, load_profile, load_settings, save_llm_settings,
                         save_profile, save_settings)
from models import LLMSettingsBody, OllamaModelsRequest, ProfileBody, SettingsBody

from .common import llm_text

router = APIRouter()
_log = logging.getLogger("backend")


@router.get("/profile")
async def get_profile():
    return load_profile()


@router.put("/profile")
async def update_profile(profile: ProfileBody):
    save_profile(profile.model_dump())
    return {"success": True}


@router.get("/settings/llm")
async def get_llm():
    return load_llm_settings()


@router.put("/settings/llm")
async def update_llm(settings: LLMSettingsBody):
    save_llm_settings(settings.model_dump())
    return {"success": True}


@router.post("/llm/test")
async def test_llm(settings: LLMSettingsBody):
    """Test an LLM connection with the given (unsaved) settings."""
    try:
        from core.llm_factory import create_llm, test_connection
        llm = create_llm(settings.model_dump())
        result = await test_connection(llm)
        return {"success": True, "message": result}
    except Exception as e:
        msg = str(e)
        if "api_key" in msg.lower() or "unauthorized" in msg.lower() or "401" in msg:
            return {"success": False, "message": "Invalid API key or unauthorized. Check your credentials."}
        if "timeout" in msg.lower() or "connect" in msg.lower():
            return {"success": False, "message": "Connection failed. Check your network and provider settings (is your local LLM server running?)"}
        from browser_use.llm.exceptions import ModelProviderError
        if isinstance(e, ModelProviderError):
            return {"success": False, "message": f"LLM Provider Error: {msg}"}
        _log.error(f"LLM test failed: {e}", exc_info=True)
        return {"success": False, "message": f"LLM test failed: {msg}"}


@router.post("/llm/ollama-models")
async def list_ollama_models(body: OllamaModelsRequest):
    import httpx
    base_url = body.base_url.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{base_url}/api/tags")
            resp.raise_for_status()
            models = [m["name"] for m in resp.json().get("models", [])]
            return {"success": True, "models": models}
    except Exception as e:
        return {"success": False, "models": [], "message": str(e)}


@router.get("/settings")
async def get_settings():
    return load_settings()


@router.put("/settings")
async def update_settings(settings: SettingsBody):
    # Merge over what is stored so a partial update never drops other keys
    merged = {**load_settings(), **settings.model_dump(exclude_unset=True)}
    if "sensitive_data" in settings.model_fields_set:
        merged["sensitive_data"] = settings.sensitive_data.model_dump()
    save_settings(merged)
    return {"success": True}


@router.post("/profile/parse-resume")
async def parse_resume_to_profile():
    """Read the user's resume PDF and use the configured LLM to extract profile fields."""
    import re as _re

    settings = load_settings()
    resume_path = settings.get("resume_path", "").strip()
    if not resume_path:
        return {"success": False, "message": "No resume path configured. Set it in Settings first."}

    resume_file = Path(resume_path).resolve()
    if not resume_file.exists():
        return {"success": False, "message": f"Resume file not found: {resume_path}"}
    if resume_file.suffix.lower() != ".pdf":
        return {"success": False, "message": "Resume must be a PDF file."}

    try:
        import fitz  # pymupdf
        doc = fitz.open(str(resume_file))
        resume_text = ""
        for page in doc:
            resume_text += page.get_text()
        doc.close()
        resume_text = resume_text.strip()
        if not resume_text:
            return {"success": False, "message": "Could not extract any text from the resume PDF."}
    except Exception as e:
        return {"success": False, "message": f"Failed to read resume PDF: {e}"}

    # 2. Send to LLM for structured extraction
    llm_settings = load_llm_settings()
    if not llm_settings.get("provider"):
        return {"success": False, "message": "No LLM provider configured. Set it in LLM Settings first."}

    try:
        from core.llm_factory import create_llm
        llm = create_llm(llm_settings)
    except Exception as e:
        return {"success": False, "message": f"Failed to create LLM: {e}"}

    prompt = f"""Extract candidate profile information from this resume text. Return ONLY a valid JSON object with these fields (use empty string "" for missing text fields, 0 for missing numbers, empty array [] for missing lists, false for missing booleans):

{{
  "name": "Full Name",
  "email": "email@example.com",
  "phone": "phone number",
  "address": {{"street": "", "city": "City", "state": "State", "zip": "ZIP", "country": "Country name"}},
  "work_authorization": "",
  "visa_sponsorship_needed": false,
  "willing_to_relocate": false,
  "preferred_work_mode": "",
  "years_of_experience": 0,
  "education": {{"degree": "Degree Name", "school": "University Name", "graduation": "Year or Date"}},
  "current_role": "Current or Most Recent Job Title",
  "target_job_titles": ["Job Title 1", "Job Title 2"],
  "target_locations": ["City, State"],
  "languages": ["English"],
  "skills": ["Skill 1", "Skill 2"],
  "salary_expectation": {{"min": 0, "max": 0, "currency": ""}},
  "notes": ""
}}

Rules:
- Extract the MOST RECENT job title as current_role
- For target_job_titles, infer 2-4 relevant titles based on their experience and skills
- For target_locations, use the candidate's current city/state if mentioned
- For skills, extract ALL mentioned technical and soft skills
- For years_of_experience, calculate from work history dates if possible
- For education, use the highest degree
- Only fill work_authorization, visa_sponsorship_needed, preferred_work_mode and salary_expectation when the
  resume states them explicitly; otherwise leave them empty / 0 / false. Never guess these.
- The values above are placeholders showing the format, not defaults to copy
- Return ONLY the JSON object, no other text

RESUME TEXT:
{resume_text[:6000]}"""

    try:
        response = await ainvoke_text(llm, prompt)
        response_text = llm_text(response)

        # Parse JSON from response
        match = _re.search(r"\{.*\}", response_text, _re.DOTALL)
        if not match:
            return {"success": False, "message": "LLM did not return valid JSON. Try again."}

        parsed_profile = json.loads(match.group())

        # Normalize skills: LLM sometimes returns {technical_skills: [...], soft_skills: [...]}
        if isinstance(parsed_profile.get("skills"), dict):
            skills_dict = parsed_profile["skills"]
            flat_skills = []
            for v in skills_dict.values():
                if isinstance(v, list):
                    flat_skills.extend(v)
                elif isinstance(v, str) and v.strip():
                    flat_skills.append(v)
            parsed_profile["skills"] = flat_skills

        # The country picker drives date format, currency and work-authorization options;
        # it used to stay at the default "US" even for a resume with an Indian address.
        inferred = infer_country_code(parsed_profile)
        if inferred:
            from core.country_config import COUNTRY_CONFIGS
            cfg = COUNTRY_CONFIGS[inferred]
            parsed_profile["country"] = inferred
            parsed_profile.setdefault("date_format", cfg.get("date_format", ""))
            sal = parsed_profile.get("salary_expectation")
            if isinstance(sal, dict) and cfg.get("currency"):
                sal["currency"] = cfg["currency"]

        # Merge with existing profile — overwrite with parsed values when they're non-empty
        existing = load_profile()
        for key, value in parsed_profile.items():
            if key not in existing:
                existing[key] = value
                continue
            if isinstance(value, str) and value.strip():
                existing[key] = value
            elif isinstance(value, list) and value:
                existing[key] = value
            elif isinstance(value, dict):
                if key not in existing or not isinstance(existing[key], dict):
                    existing[key] = value
                else:
                    for sub_key, sub_val in value.items():
                        if isinstance(sub_val, str) and sub_val.strip():
                            existing[key][sub_key] = sub_val
                        elif isinstance(sub_val, (int, float)) and sub_val > 0:
                            existing[key][sub_key] = sub_val
            elif isinstance(value, (int, float)) and value > 0:
                existing[key] = value

        # Save the merged profile
        save_profile(existing)

        # Count how many fields were filled
        filled_count = 0
        for key, value in parsed_profile.items():
            if isinstance(value, str) and value.strip():
                filled_count += 1
            elif isinstance(value, list) and value:
                filled_count += 1
            elif isinstance(value, dict):
                for sv in value.values():
                    if isinstance(sv, str) and sv.strip():
                        filled_count += 1
                        break
            elif isinstance(value, (int, float)) and value > 0:
                filled_count += 1

        return {
            "success": True,
            "message": f"Extracted {filled_count} fields from your resume!",
            "profile": existing,
            "fields_filled": filled_count,
        }

    except json.JSONDecodeError:
        return {"success": False, "message": "LLM returned invalid JSON. Try again."}
    except Exception as e:
        return {"success": False, "message": f"LLM parsing failed: {e}"}


_COUNTRY_ALIASES = {"usa": "US", "united states of america": "US", "u.s.": "US", "u.s.a.": "US", "uk": "GB",
                    "england": "GB", "scotland": "GB", "great britain": "GB", "uae": "AE", "deutschland": "DE"}


def infer_country_code(parsed: dict) -> str | None:
    """Country code from a parsed resume's address (name, alias or ISO code)."""
    from core.country_config import COUNTRY_CONFIGS
    raw = str((parsed.get("address") or {}).get("country") or parsed.get("country") or "").strip()
    if not raw:
        return None
    low = raw.lower()
    if raw.upper() in COUNTRY_CONFIGS:
        return raw.upper()
    if low in _COUNTRY_ALIASES:
        return _COUNTRY_ALIASES[low]
    for code, cfg in COUNTRY_CONFIGS.items():
        if cfg.get("name", "").lower() == low:
            return code
    return None
