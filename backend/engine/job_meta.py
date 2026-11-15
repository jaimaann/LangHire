"""Title, company, location and description of a job posting, from its URL.

A job added by URL used to show as "Manually Added · Unknown" with a 10%
match, because nothing was known about it. Most career pages (Greenhouse,
Lever, Workday, company sites) publish schema.org JobPosting JSON-LD for
search engines; that is read first, then OpenGraph tags and <title>.

Plain HTTP, no browser: fast, and pages that need JavaScript just fall back
to what the user typed. Every redirect target is re-checked against the
SSRF guard.
"""
from __future__ import annotations

import html
import json
import logging
import re

import httpx

from core.shared_config import validate_job_url

_log = logging.getLogger("engine")
_UA = "Mozilla/5.0 (compatible; LangHire job details fetcher)"
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"[ \t\r\f\v]+")


def _text(s: str) -> str:
    s = html.unescape(s or "")  # JSON-LD descriptions are often entity-escaped HTML
    s = re.sub(r"(?i)<br\s*/?>|</p>|</li>|</h\d>", "\n", s)
    s = html.unescape(_TAG.sub(" ", s))
    lines = [_WS.sub(" ", ln).strip() for ln in s.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def _iter_ld(node):
    if isinstance(node, list):
        for n in node:
            yield from _iter_ld(n)
    elif isinstance(node, dict):
        yield node
        for key in ("@graph", "itemListElement"):
            if key in node:
                yield from _iter_ld(node[key])


def _location(loc) -> str:
    for item in loc if isinstance(loc, list) else [loc]:
        addr = (item or {}).get("address") if isinstance(item, dict) else None
        if isinstance(addr, dict):
            parts = [addr.get(k) for k in ("addressLocality", "addressRegion", "addressCountry")]
            parts = [p.get("name") if isinstance(p, dict) else p for p in parts]
            text = ", ".join(str(p) for p in parts if p)
            if text:
                return text
        if isinstance(addr, str) and addr.strip():
            return addr.strip()
    return ""


def parse_job_html(page: str) -> dict:
    """Pull job metadata out of a posting's HTML. Empty strings for what isn't there."""
    out = {"title": "", "company": "", "location": "", "description": ""}
    for m in re.finditer(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', page, re.S | re.I):
        try:
            data = json.loads(m.group(1).strip())
        except (ValueError, TypeError):
            continue
        for node in _iter_ld(data):
            types = node.get("@type")
            if "JobPosting" not in (types if isinstance(types, list) else [types]):
                continue
            org = node.get("hiringOrganization")
            out["title"] = _text(str(node.get("title") or ""))
            out["company"] = _text(str(org.get("name") if isinstance(org, dict) else org or ""))
            out["location"] = _location(node.get("jobLocation"))
            if not out["location"] and str(node.get("jobLocationType", "")).upper() == "TELECOMMUTE":
                out["location"] = "Remote"
            out["description"] = _text(str(node.get("description") or ""))
            return out

    def meta(prop: str) -> str:
        mm = re.search(rf'<meta[^>]+(?:property|name)=["\']{prop}["\'][^>]+content=["\']([^"\']*)', page, re.I) \
            or re.search(rf'<meta[^>]+content=["\']([^"\']*)["\'][^>]+(?:property|name)=["\']{prop}["\']', page, re.I)
        return html.unescape(mm.group(1)).strip() if mm else ""

    title = meta("og:title")
    if not title:
        tm = re.search(r"<title[^>]*>(.*?)</title>", page, re.S | re.I)
        title = _text(tm.group(1)) if tm else ""
    out["title"] = title
    out["company"] = meta("og:site_name")
    out["description"] = meta("og:description") or meta("description")
    return out


_GH = re.compile(r"^https?://(?:job-boards|boards)(?:\.eu)?\.greenhouse\.io/(?:embed/)?([\w-]+)/jobs/(\d+)", re.I)


def greenhouse_api_url(url: str) -> str | None:
    """Greenhouse's newer job pages carry no JSON-LD; its public job board API has everything."""
    m = _GH.match(url)
    return f"https://boards-api.greenhouse.io/v1/boards/{m.group(1)}/jobs/{m.group(2)}" if m else None


def parse_greenhouse_api(data: dict) -> dict:
    return {
        "title": _text(str(data.get("title") or "")),
        "company": _text(str(data.get("company_name") or "")),
        "location": _text(str((data.get("location") or {}).get("name") or "")),
        "description": _text(str(data.get("content") or "")),
    }


async def fetch_job_meta(url: str, timeout: float = 10.0) -> dict:
    """Best-effort metadata for a job URL. Never raises; returns {} when nothing could be read."""
    async def _guard(request: httpx.Request):
        if not validate_job_url(str(request.url)):
            raise httpx.RequestError("redirect to a private address blocked", request=request)

    try:
        async with httpx.AsyncClient(follow_redirects=True, max_redirects=5, timeout=timeout,
                                     headers={"User-Agent": _UA, "Accept": "text/html"},
                                     event_hooks={"request": [_guard]}) as client:
            api = greenhouse_api_url(url)
            if api:
                ra = await client.get(api, headers={"Accept": "application/json"})
                if ra.status_code == 200:
                    meta = parse_greenhouse_api(ra.json())
                    meta["description"] = meta["description"][:20000]
                    return {k: v for k, v in meta.items() if v}
            r = await client.get(url)
        if r.status_code >= 400 or "html" not in r.headers.get("content-type", "html"):
            return {}
        meta = parse_job_html(r.text[:3_000_000])
        meta["description"] = meta["description"][:20000]
        return {k: v for k, v in meta.items() if v}
    except Exception as e:  # network, TLS, blocked redirect: the user's own fields still apply
        _log.info(f"job details fetch failed for {url[:80]}: {e}")
        return {}
