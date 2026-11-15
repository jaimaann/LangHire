"""Whether to send screenshots to the model.

The agent used ``use_vision=True`` unconditionally, so a text-only model (for
example Z.ai's ``glm-5.3``) failed every step with an opaque provider error.
LLM settings now carry ``use_vision``: "on", "off" or "auto" (default). In auto
mode a model that rejects images is remembered and the job is retried once
without screenshots.
"""
from __future__ import annotations

import re

from core.config import load_llm_settings, load_settings, save_settings

_IMAGE_REJECTED = re.compile(
    r"(content\.type is invalid|allowed values: \['text'\]|image.*not supported|does not support (image|vision)"
    r"|vision is not supported|image_url.*(invalid|unsupported)|unsupported content type)",
    re.IGNORECASE,
)


def model_key() -> str:
    llm = load_llm_settings()
    provider = llm.get("provider", "")
    return f"{provider}:{(llm.get(provider) or {}).get('model', '')}"


def use_vision() -> bool:
    llm = load_llm_settings()
    mode = str(llm.get("use_vision", "auto")).lower()
    if mode in ("off", "false", "0"):
        return False
    if mode in ("on", "true", "1"):
        return True
    return model_key() not in (load_settings().get("non_vision_models") or [])


def is_image_rejection(text: str) -> bool:
    return bool(_IMAGE_REJECTED.search(text or ""))


def remember_text_only() -> None:
    settings = load_settings()
    models = list(settings.get("non_vision_models") or [])
    key = model_key()
    if key not in models:
        models.append(key)
        settings["non_vision_models"] = models
        save_settings(settings)


def history_rejected_images(history) -> bool:
    try:
        return any(is_image_rejection(e or "") for e in history.errors())
    except Exception:
        return False
