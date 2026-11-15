"""Job-to-profile match score (0-100), computed without an LLM.

Used to sort the queue (best matches first) and shown in the jobs list so
users stop spending tokens on poor fits. Deliberately simple and explainable:
title similarity to the target titles, skill coverage in the description, and
location / remote fit.
"""
from __future__ import annotations

import re

_WORD = re.compile(r"[a-z0-9+#.]+")
_STOP = {"and", "or", "the", "a", "an", "of", "to", "in", "for", "with", "senior", "junior", "sr", "jr",
         "i", "ii", "iii", "lead", "staff", "principal", "remote", "hybrid"}


def _tokens(text: str) -> set[str]:
    return {t.strip(".") for t in _WORD.findall((text or "").lower()) if t.strip(".") and t not in _STOP}


def _title_score(title: str, targets: list[str]) -> float:
    tt = _tokens(title)
    if not tt or not targets:
        return 0.5 if not targets else 0.0
    best = 0.0
    for target in targets:
        tg = _tokens(target)
        if tg:
            best = max(best, len(tt & tg) / len(tg))
    return best


def _skill_score(text: str, skills: list[str]) -> float | None:
    if not skills or not text:
        return None
    low = (text or "").lower()
    hits = 0
    for s in skills:
        s = s.strip().lower()
        if s and re.search(r"(?<![a-z0-9])" + re.escape(s) + r"(?![a-z0-9])", low):
            hits += 1
    # Matching a third of your skills is already a strong signal
    return min(1.0, hits / max(1, min(len(skills), 9)) * 1.5) if skills else None


def _location_score(job: dict, profile: dict) -> float:
    loc = (job.get("location") or "").lower()
    if not loc:
        return 0.7
    if "remote" in loc:
        return 1.0 if profile.get("preferred_work_mode") in ("remote", "hybrid", "any", None, "") else 0.8
    targets = [t.lower() for t in profile.get("target_locations") or []]
    if not targets:
        return 0.7
    for t in targets:
        first = t.split(",")[0].strip()
        if first and first in loc:
            return 1.0
    return 0.4


def match_score(job: dict, profile: dict) -> int:
    title = _title_score(job.get("title", ""), list(profile.get("target_job_titles") or []))
    skills = _skill_score(job.get("description", "") + " " + job.get("title", ""), list(profile.get("skills") or []))
    loc = _location_score(job, profile)
    if skills is None:
        score = 0.65 * title + 0.35 * loc
    else:
        score = 0.45 * title + 0.4 * skills + 0.15 * loc
    return int(round(100 * max(0.0, min(1.0, score))))
