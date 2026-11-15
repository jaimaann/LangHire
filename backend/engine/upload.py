"""Deterministic resume upload that works across shadow DOM and cross-origin iframes.

The agent's generic upload action fails on two common layouts seen in real runs:
  * a careers page that embeds the ATS form in a cross-origin iframe
    (Stripe, Airbnb on Greenhouse): "No node found for given backend id";
  * React widgets that hide the <input type=file>: the agent typed the file
    path into it, the widget re-rendered, and the input vanished.

This walks every page/iframe target over the root CDP connection, finds the
best resume file input (shadow roots included), sets the file on it, and then
checks that the page shows the file name.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os

_log = logging.getLogger("engine")

# Scores each file input; the resume field wins over cover letter / other attachments.
_FIND_JS = r"""(() => {
  const all = [];
  const walk = (root) => {
    root.querySelectorAll('input[type=file]').forEach(el => all.push(el));
    root.querySelectorAll('*').forEach(el => { if (el.shadowRoot) walk(el.shadowRoot); });
  };
  walk(document);
  const text = (el) => {
    let t = [el.id, el.name, el.getAttribute('aria-label'), el.getAttribute('data-qa'), el.accept].join(' ');
    if (el.id) { const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`); if (l) t += ' ' + l.innerText; }
    let p = el.parentElement;
    for (let i = 0; p && i < 4; i++, p = p.parentElement) t += ' ' + (p.getAttribute('aria-label') || '') + ' ' + (p.id || '');
    const box = el.closest('fieldset, .field, .application-question, [class*=upload], [class*=field]');
    if (box) t += ' ' + (box.innerText || '').slice(0, 200);
    return t.toLowerCase();
  };
  let best = null, bestScore = -1e9;
  all.forEach((el, i) => {
    if (el.disabled) return;
    const t = text(el);
    let s = 0;
    if (/resume|cv\b|curriculum/.test(t)) s += 10;
    if (/cover|letter|transcript|portfolio|photo|avatar|image/.test(t)) s -= 8;
    if (/pdf|doc/.test(el.accept || '')) s += 1;
    if (s > bestScore) { bestScore = s; best = el; }
  });
  if (!best) return null;
  window.__lhResumeInput = best;
  return JSON.stringify({count: all.length, score: bestScore, id: best.id || best.name || ''});
})()"""


async def _targets(root) -> list[dict]:
    res = await root.send.Target.getTargets()
    return [t for t in res.get("targetInfos", []) if t.get("type") in ("page", "iframe")
            and t.get("url", "").startswith("http")]


async def upload_resume_any_frame(browser_session, path: str) -> str:
    """Attach `path` to the best resume input on the current page or its iframes. Returns a status line."""
    if not path or not os.path.isfile(path):
        return "No resume file is configured."
    root = getattr(browser_session, "_cdp_client_root", None)
    if root is None:
        return "Browser not ready."
    focus = getattr(browser_session, "agent_focus_target_id", None)
    targets = await _targets(root)
    # the focused tab first, then its iframes (OOPIFs have their own targets)
    targets.sort(key=lambda t: (t.get("targetId") != focus, t.get("type") != "page"))
    if focus:
        targets = [t for t in targets if t.get("targetId") == focus or t.get("type") == "iframe"]
    candidates: list[tuple] = []
    sessions: list[str] = []
    try:
        return await _upload(root, targets, candidates, sessions, path)
    finally:
        for sid in sessions:
            try:
                await root.send.Target.detachFromTarget(params={"sessionId": sid})
            except Exception:
                pass


async def _upload(root, targets, candidates, sessions, path) -> str:
    for t in targets:
        try:
            att = await root.send.Target.attachToTarget(params={"targetId": t["targetId"], "flatten": True})
            sid = att["sessionId"]
            sessions.append(sid)
            r = await root.send.Runtime.evaluate(params={"expression": _FIND_JS, "returnByValue": True},
                                                 session_id=sid)
            val = (r.get("result") or {}).get("value")
            if val:
                info = json.loads(val)
                candidates.append((info["score"], t, sid, info))
        except Exception as e:
            _log.debug(f"upload: target {t.get('url', '')[:60]} skipped: {e}")
    if not candidates:
        return "No file upload field found on this page or its frames."
    candidates.sort(key=lambda c: -c[0])
    score, target, sid, info = candidates[0]
    r = await root.send.Runtime.evaluate(params={"expression": "window.__lhResumeInput"}, session_id=sid)
    oid = (r.get("result") or {}).get("objectId")
    if not oid:
        return "The upload field disappeared before it could be used."
    await root.send.DOM.enable(session_id=sid)
    await root.send.DOM.setFileInputFiles(params={"files": [os.path.abspath(path)], "objectId": oid},
                                          session_id=sid)
    name = os.path.basename(path)
    shown = False
    for _ in range(8):  # widgets upload to storage first; wait for the file name to show
        await asyncio.sleep(1)
        try:
            r = await root.send.Runtime.evaluate(
                params={"expression": f"document.body.innerText.includes({json.dumps(name)})",
                        "returnByValue": True}, session_id=sid)
            if (r.get("result") or {}).get("value"):
                shown = True
                break
        except Exception:
            break
    where = "an embedded form" if target.get("type") == "iframe" else "the page"
    _log.info(f"upload: resume set on {where} ({target.get('url', '')[:80]}), field={info.get('id')!r}, "
              f"shown={shown}")
    if shown:
        return f"Resume {name} attached to the resume field on {where}; the page shows the file name."
    return (f"Resume {name} was set on the resume field on {where}, but the page does not show the file name yet. "
            "Look at the field: if it is still empty, report it in your final reason.")
