"""Deterministic fast path for the most common applicant tracking systems.

Filling name / email / phone through the LLM costs several vision steps per
application. For ATSs with stable markup (Greenhouse, Lever, Ashby, Workable)
plus any form that uses standard ``autocomplete`` attributes, one JavaScript
call fills those fields directly, the way a password manager would. The agent
still handles the resume upload, custom questions and submit.
"""
from __future__ import annotations

import json
import logging
import re
from urllib.parse import urlparse

_log = logging.getLogger("engine")

ATS_HOSTS = {
    "greenhouse": ("greenhouse.io",),
    "lever": ("lever.co",),
    "ashby": ("ashbyhq.com",),
    "workable": ("workable.com",),
    "workday": ("myworkdayjobs.com", "workday.com"),
    "smartrecruiters": ("smartrecruiters.com",),
}

# field -> CSS selectors, most specific first
SELECTORS: dict[str, dict[str, list[str]]] = {
    "greenhouse": {
        "first_name": ["#first_name", "input[name='job_application[first_name]']"],
        "last_name": ["#last_name", "input[name='job_application[last_name]']"],
        "email": ["#email", "input[name='job_application[email]']"],
        "phone": ["#phone", "input[name='job_application[phone]']"],
    },
    "lever": {
        "full_name": ["input[name='name']"],
        "email": ["input[name='email']"],
        "phone": ["input[name='phone']"],
        "current_company": ["input[name='org']"],
        "linkedin": ["input[name='urls[LinkedIn]']"],
        "github": ["input[name='urls[GitHub]']"],
        "website": ["input[name='urls[Portfolio]']", "input[name='urls[Other]']"],
    },
    "ashby": {
        "full_name": ["#_systemfield_name", "input[name='_systemfield_name']"],
        "email": ["#_systemfield_email", "input[name='_systemfield_email']"],
        "phone": ["#_systemfield_phone", "input[name='_systemfield_phone']"],
    },
    "workable": {
        "first_name": ["input[name='firstname']"],
        "last_name": ["input[name='lastname']"],
        "email": ["input[name='email']"],
        "phone": ["input[name='phone']"],
    },
    # Any site: standard autocomplete tokens
    "generic": {
        "first_name": ["input[autocomplete='given-name']"],
        "last_name": ["input[autocomplete='family-name']"],
        "full_name": ["input[autocomplete='name']"],
        "email": ["input[autocomplete='email']", "input[type='email']"],
        "phone": ["input[autocomplete='tel']", "input[type='tel']"],
    },
}

# Sets the value through the native setter and fires input/change so React,
# Vue and Angular forms register it. Never overwrites a field the user filled.
_FILL_JS = r"""(spec) => {
  const out = [];
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
  for (const [field, info] of Object.entries(spec)) {
    if (!info.value) continue;
    for (const sel of info.selectors) {
      let el = null;
      try { el = document.querySelector(sel); } catch (e) { continue; }
      if (!el || el.disabled || el.readOnly || el.type === 'hidden') continue;
      if (el.value && el.value.trim()) { break; }
      el.focus();
      setter.call(el, info.value);
      el.dispatchEvent(new Event('input', {bubbles: true}));
      el.dispatchEvent(new Event('change', {bubbles: true}));
      el.blur();
      out.push(field);
      break;
    }
  }
  return JSON.stringify(out);
}"""


def detect_ats(url: str) -> str | None:
    host = (urlparse(url).hostname or "").lower()
    for ats, suffixes in ATS_HOSTS.items():
        if any(host == s or host.endswith("." + s) for s in suffixes):
            return ats
    return None


def profile_values(profile: dict) -> dict[str, str]:
    name = (profile.get("name") or "").strip()
    parts = name.split()
    first = parts[0] if parts else ""
    last = " ".join(parts[1:]) if len(parts) > 1 else ""
    phone = (profile.get("phone") or "").strip()
    cc = (profile.get("phone_country_code") or "").strip()
    if phone and cc and not phone.startswith("+"):
        phone = f"{cc} {phone}"
    return {
        "first_name": first,
        "last_name": last,
        "full_name": name,
        "email": (profile.get("email") or "").strip(),
        "phone": phone,
        "current_company": (profile.get("current_company") or "").strip(),
        "linkedin": (profile.get("linkedin_url") or "").strip(),
        "github": (profile.get("github_url") or "").strip(),
        "website": (profile.get("website") or profile.get("portfolio_url") or "").strip(),
    }


def build_spec(url: str, profile: dict) -> dict:
    values = profile_values(profile)
    ats = detect_ats(url)
    selectors: dict[str, list[str]] = {}
    for source in ([ats] if ats in SELECTORS else []) + ["generic"]:
        for field, sels in SELECTORS[source].items():
            selectors.setdefault(field, [])
            selectors[field] += [s for s in sels if s not in selectors[field]]
    return {f: {"value": values.get(f, ""), "selectors": s} for f, s in selectors.items() if values.get(f)}


async def prefill_page(browser_session, profile: dict) -> list[str]:
    """Fill known fields on the current page. Returns the field names filled."""
    try:
        page = await browser_session.get_current_page()
        if page is None:
            return []
        url = await browser_session.get_current_page_url()
        spec = build_spec(url, profile)
        if not spec:
            return []
        raw = await page.evaluate(_FILL_JS, spec)
        filled = json.loads(raw) if isinstance(raw, str) and raw.startswith("[") else []
        return [str(f) for f in filled if re.fullmatch(r"[a-z_]+", str(f))]
    except Exception as e:
        _log.info(f"ATS prefill skipped: {e}")
        return []
