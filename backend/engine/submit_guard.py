"""Submit-intercept test mode: click the real Submit button, never send the application.

Forms often reveal missing or invalid fields only when Submit is clicked, so
stopping before Submit under-measures failures. In this mode the agent does
click Submit; client-side validation runs exactly as for a real applicant. If
validation passes, the browser then sends the application request — and this
guard cancels it at the Chrome DevTools Fetch layer, on the root connection so
that every tab and cross-site iframe is covered. A cancelled request carrying
the application counts as "would have been submitted".

Blocking rules (fail closed):
  * POST/PUT/PATCH requests while "armed" (just after a submit-like click),
  * any write request whose body contains the candidate's email, phone or name,
  * any write request with a body the guard cannot read (multipart, large),
    when it isn't a plain file upload done before any submit click.
Everything else (page loads, assets, GETs) passes through.

Limits: server-side-only rejections (duplicate application, server CAPTCHA
checks) can't be observed, because the request never reaches the server.
"""
from __future__ import annotations

import asyncio
import base64
import logging
import re
import time
from dataclasses import dataclass, field

_log = logging.getLogger("engine")

WRITE_METHODS = {"POST", "PUT", "PATCH"}
ARM_SECONDS = 25.0


@dataclass
class Intercepted:
    url: str
    method: str
    reason: str
    size: int
    at: float = field(default_factory=time.time)


class SubmitInterceptor:
    def __init__(self, browser_session, profile: dict):
        self.session = browser_session
        self.armed_until = 0.0
        self.blocked: list[Intercepted] = []
        self.passed_writes = 0
        self.installed = False
        self._tasks: set[asyncio.Task] = set()
        needles = []
        email = (profile.get("email") or "").strip().lower()
        if email:
            needles += [email, email.replace("@", "%40")]
        phone_digits = re.sub(r"\D", "", profile.get("phone") or "")
        if len(phone_digits) >= 7:
            needles.append(phone_digits[-7:])
        name = (profile.get("name") or "").strip().lower()
        if len(name) >= 5:
            needles += [name, name.replace(" ", "+"), name.replace(" ", "%20")]
        self.needles = [n for n in needles if n]

    # ── lifecycle ────────────────────────────────────────────────────────
    async def install(self) -> bool:
        root = getattr(self.session, "_cdp_client_root", None)
        if root is None:
            await self.session.start()
            root = getattr(self.session, "_cdp_client_root", None)
        if root is None:
            return False
        root.register.Fetch.requestPaused(self._on_paused)
        await root.send.Fetch.enable(params={"patterns": [{"urlPattern": "*", "requestStage": "Request"}]})
        self.installed = True
        return True

    def arm(self, seconds: float = ARM_SECONDS) -> None:
        self.armed_until = time.time() + seconds

    def blocked_since(self, t: float) -> list[Intercepted]:
        return [b for b in self.blocked if b.at >= t]

    # ── CDP handler ──────────────────────────────────────────────────────
    def _on_paused(self, event, session_id=None):
        task = asyncio.ensure_future(self._handle(event, session_id))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _handle(self, event, session_id):
        root = self.session._cdp_client_root
        req = event.get("request", {})
        rid = event["requestId"]
        method = (req.get("method") or "GET").upper()
        try:
            reason = self._block_reason(method, req) if method in WRITE_METHODS else None
            if reason:
                body = req.get("postData") or ""
                self.blocked.append(Intercepted(req.get("url", ""), method, reason, len(body)))
                _log.info(f"test mode: blocked {method} {req.get('url', '')[:120]} ({reason})")
                await root.send.Fetch.failRequest(params={"requestId": rid, "errorReason": "BlockedByClient"},
                                                  session_id=session_id)
            else:
                if method in WRITE_METHODS:
                    self.passed_writes += 1
                await root.send.Fetch.continueRequest(params={"requestId": rid}, session_id=session_id)
        except Exception as e:  # the target may be gone; never leave a request hanging silently
            _log.debug(f"test mode: fetch handling failed: {e}")

    def _body_text(self, req: dict) -> str | None:
        body = req.get("postData")
        if body is None:
            entries = req.get("postDataEntries") or []
            parts = []
            for e in entries:
                b = e.get("bytes")
                if b:
                    try:
                        parts.append(base64.b64decode(b).decode("utf-8", "ignore"))
                    except Exception:
                        return None
            body = "".join(parts) if parts else None
        return body

    def _block_reason(self, method: str, req: dict) -> str | None:
        if time.time() < self.armed_until:
            return "after submit click"
        body = self._body_text(req)
        if body is None:
            if req.get("hasPostData"):
                ctype = (req.get("headers") or {}).get("Content-Type", "") or (req.get("headers") or {}).get("content-type", "")
                if "multipart" in ctype.lower() and not _same_site(req):
                    return None  # a file upload to a third party (S3, a CDN) before any submit click
                return "unreadable body to the site itself"
            return None
        low = body.lower()
        for n in self.needles:
            if n and n in low:
                return "contains candidate details"
        return None


def _site(host: str) -> str:
    """Registrable domain, approximately: last two labels (three for co.uk-style suffixes)."""
    parts = [p for p in (host or "").lower().split(".") if p]
    if len(parts) >= 3 and parts[-2] in ("co", "com", "org", "net", "ac", "gov", "edu") and len(parts[-1]) == 2:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def _same_site(req: dict) -> bool:
    """Is this request going to the same site as the page that made it?"""
    from urllib.parse import urlparse
    headers = {k.lower(): v for k, v in (req.get("headers") or {}).items()}
    origin = headers.get("origin") or headers.get("referer") or ""
    target = urlparse(req.get("url", "")).hostname or ""
    source = urlparse(origin).hostname or ""
    return not source or _site(source) == _site(target)


_WEAK_SUBMIT = re.compile(r"\bapply(\s+now)?\b|\bsend\b|\bcomplete\b|\bconfirm\b", re.IGNORECASE)


def install_click_hook(tools, interceptor: SubmitInterceptor, report) -> None:
    """Arm the interceptor before submit-like clicks and report what happened after."""
    from browser_use.agent.views import ActionResult

    from .dryrun import element_label, looks_like_final_submit

    actions = tools.registry.registry.actions
    click = actions.get("click")
    if click is None:
        return
    original = click.function

    async def hooked_click(*args, **kwargs):
        params = kwargs.get("params") or (args[0] if args else None)
        session = kwargs.get("browser_session")
        index = getattr(params, "index", None)
        if index is None:
            return ActionResult(error="TEST MODE: click elements by index, not coordinates.")
        try:
            node = await session.get_element_by_index(index) if session else None
        except Exception:
            node = None
        label = element_label(node) if node is not None else ""
        if not looks_like_final_submit(label):
            if _WEAK_SUBMIT.search(label or ""):
                # 'Apply' may open a form or send one: arm silently, and only speak up
                # if an application request actually got intercepted.
                started = time.time()
                interceptor.arm()
                result = await original(*args, **kwargs)
                await asyncio.sleep(4)
                if interceptor.blocked_since(started) and isinstance(result, ActionResult):
                    report.intercepted += len(interceptor.blocked_since(started))
                    note = ("TEST MODE: that click sent the application, which was intercepted (nothing was sent). "
                            "Call report_application_result with outcome=ready_to_submit, then done.")
                    result.extracted_content = ((result.extracted_content or "") + " " + note).strip()
                    result.long_term_memory = note
                return result
            return await original(*args, **kwargs)
        report.submit_clicks += 1
        started = time.time()
        interceptor.arm()
        result = await original(*args, **kwargs)
        await asyncio.sleep(6)  # let validation run and the request (if any) fire
        caught = interceptor.blocked_since(started)
        if caught:
            report.intercepted += len(caught)
            note = ("TEST MODE: the form passed validation and the application request was intercepted "
                    "(nothing was sent). Call report_application_result with outcome=ready_to_submit, then done.")
        else:
            note = ("TEST MODE: Submit was clicked but no application request was sent. The page most likely "
                    "shows validation errors or a further step: look for them, fix them, and try again.")
        if isinstance(result, ActionResult):
            result.extracted_content = ((result.extracted_content or "") + "\n" + note).strip()
            result.long_term_memory = note
            return result
        return ActionResult(extracted_content=note, long_term_memory=note)

    click.function = hooked_click
