"""Shareable ATS memory packs.

The per-ATS procedural memory ("Workday: the country field is a typeahead —
type, then wait for the list") is the part of LangHire that gets better with
use. A memory pack exports only that ATS-level knowledge, scrubbed of anything
personal, so users can share packs (or a maintainer can publish curated ones)
without sharing a single detail about themselves.

Excluded: site-specific memories with no ATS, Q&A patterns, job URLs, and any
text that looks like an email, phone number, URL query or long number.
"""
from __future__ import annotations

import re

try:
    from core import db
    from core import shared_config as sc
except ImportError:
    from backend.core import db
    from backend.core import shared_config as sc

PACK_FORMAT = "langhire-memory-pack"
SHAREABLE_CATEGORIES = {"navigation", "form_strategy", "element_interaction", "failure_recovery", "site_structure"}

_SCRUB = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "<email>"),
    (re.compile(r"\+?\d[\d\s().-]{7,}\d"), "<number>"),
    (re.compile(r"https?://\S+"), "<url>"),
    (re.compile(r"\b\d{5,}\b"), "<number>"),
]


def scrub(text: str) -> str:
    for rx, repl in _SCRUB:
        text = rx.sub(repl, text)
    return text.strip()


def export_pack(min_confidence: float = 0.6) -> dict:
    store = sc.get_memory_store()
    out, seen = [], set()
    for m in store.export_all():
        ats = m.get("ats_platform")
        if not ats or m.get("category") not in SHAREABLE_CATEGORIES:
            continue
        if float(m.get("confidence") or 0) < min_confidence:
            continue
        content = scrub(m.get("content") or "")
        if len(content) < 15 or (ats, content) in seen:
            continue
        seen.add((ats, content))
        out.append({"ats_platform": ats, "category": m["category"], "content": content,
                    "confidence": round(float(m.get("confidence") or 0.8), 2)})
    return {"format": PACK_FORMAT, "version": 1, "created_at": db.now_iso(), "memories": out}


def import_pack(pack: dict) -> int:
    if not isinstance(pack, dict) or pack.get("format") != PACK_FORMAT:
        raise ValueError("Not a LangHire memory pack")
    store = sc.get_memory_store()
    added = 0
    for m in pack.get("memories") or []:
        if not isinstance(m, dict):
            continue
        ats = str(m.get("ats_platform") or "").strip()[:64]
        category = m.get("category")
        content = scrub(str(m.get("content") or ""))[:1000]
        if not ats or category not in SHAREABLE_CATEGORIES or len(content) < 15:
            continue
        # Imported knowledge starts below locally learned knowledge
        conf = min(float(m.get("confidence") or 0.7), 0.75)
        if store.add(content=content, website_domain=ats, category=category, success=True,
                     confidence=conf, job_url="", ats_platform=ats):
            added += 1
    return added
