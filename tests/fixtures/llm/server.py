"""A scripted, OpenAI-compatible "LLM" for end-to-end tests.

The real browser agent (browser-use) sends this server the page it sees, as
indexed elements (`[12]<input name=email ... />`), and expects the next
actions back as JSON. Instead of a model, a few rules decide them, so the
whole apply engine can be tested on every commit, on every OS, without an
API key, network access or flaky model output.

The rules know the local mock ATS (tests/fixtures/ats/server.py):
  posting page            -> click "Apply"
  form appears            -> prefill_standard_fields, upload_resume
  remaining fields        -> answer from rules / the Q&A bank in the system prompt;
                             a required sensitive question with no answer -> needs_input
  everything filled       -> click Submit
  submit result           -> report_application_result, then done

Every response reports token usage (with cached tokens), so token accounting
is tested end to end as well.

    python tests/fixtures/llm/server.py --port 8766
"""
from __future__ import annotations

import argparse
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_EL = re.compile(r"^(?P<indent>\s*)(?:\|SHADOW\([a-z]+\)\|)?\*?\[(?P<idx>\d+)\]<(?P<tag>\w+)(?P<attrs>[^>]*?)/?>\s*$")
_ATTR = re.compile(r"(\w[\w-]*)=((?:\([^)]*\)(?:,\([^)]*\))*)|(?:[^ ]+(?: (?!\w[\w-]*=)[^ ]+)*))")

# Answers for the mock ATS's ordinary questions (by field name)
ANSWERS = {
    "q_work_auth": "Yes",
    "q_sponsorship": "No",
    "q_sql_years": "3",
    "q_why": "I enjoy turning data into decisions and your analytics work matches my SQL and Python skills.",
    "org": "Acme Corp",
}
# Required sensitive questions: answered only from the Q&A bank, else needs_input
SENSITIVE = {"q_felony", "q_current_salary"}
MAX_ACTIONS = 5  # browser-use's max_actions_per_step


def parse_elements(text: str) -> list[dict]:
    """Interactive elements with their label (text on the line before the element)."""
    lines = text.splitlines()
    out = []
    for i, line in enumerate(lines):
        m = _EL.match(line)
        if not m:
            continue
        attrs = {k: v for k, v in _ATTR.findall(m.group("attrs"))}
        label = ""
        for j in range(i - 1, max(i - 3, -1), -1):  # nearest preceding plain-text line
            prev = lines[j].strip()
            if prev and not _EL.match(lines[j]):
                label = prev
                break
        after = lines[i + 1].strip() if i + 1 < len(lines) and not _EL.match(lines[i + 1]) else ""
        out.append({"index": int(m.group("idx")), "tag": m.group("tag").lower(), "attrs": attrs,
                    "label": label, "text": after})
    return out


def profile_answers(system: str) -> dict[str, str]:
    """Contact fields from the CANDIDATE PROFILE block, keyed by common form field names."""
    out: dict[str, str] = {}
    m = re.search(r"^Name: (.+)$", system, re.M)
    if m and m.group(1).strip() != "Not specified":
        full = m.group(1).strip()
        out.update({"name": full, "first_name": full.split()[0], "last_name": full.split()[-1]})
    m = re.search(r"Phone: (\S+)", system)
    if m:
        out["phone"] = m.group(1).strip().rstrip(",")
    return out


def qa_bank(system: str) -> dict[str, str]:
    return {q.strip().lower(): a.strip() for q, a in re.findall(r"^Q: (.+)\nA: (.+)$", system, re.M)}


def _last(tag: str, text: str) -> str:
    found = re.findall(rf"<{tag}>(.*?)</{tag}>", text, re.S)
    return found[-1] if found else ""


def _history(user: str) -> str:
    return _last("agent_history", user)


def _browser(user: str) -> str:
    return _last("browser_state", user) or user


def _step(actions: list[dict], goal: str) -> dict:
    return {"thinking": "scripted", "evaluation_previous_goal": "ok", "memory": goal,
            "next_goal": goal, "action": actions}


def _reported(hist: str) -> dict:
    """The structured result for done(): the app's output schema is ApplicationResult."""
    m = re.search(r"Reported outcome (\w+)|Recorded outcome: (\w+)", hist)
    outcome = (m.group(1) or m.group(2)) if m else "failed"
    return {"outcome": outcome, "reason": "Reported via report_application_result.",
            "confirmation_text": "", "missing_info": []}


# Fields already acted on, per run (a selected <select> or ticked box does not show a value)
_ACTED: dict[str, set] = {}
_ACTED_LOCK = threading.Lock()


def _url(page: str) -> str:
    m = re.search(r"Tab \w+: (\S+)", page)
    return m.group(1) if m else ""


def decide(system: str, user: str) -> dict:
    """The next agent step for the page in `user`."""
    hist = _history(user)
    task = re.search(r"Go to (\S+)", user)
    key = task.group(1) if task else "default"
    with _ACTED_LOCK:
        if hist.count("<step") <= 1:  # a new run for this job
            _ACTED[key] = set()
        acted = _ACTED.setdefault(key, set())
    page = _browser(user)
    els = parse_elements(page)
    fields = [e for e in els if e["tag"] in ("input", "select", "textarea")]

    if "Recorded outcome" in hist or "Reported outcome" in hist:
        return _step([{"done": {"success": True, "data": _reported(hist)}}], "Finish")
    if ("passed validation" in hist or "was intercepted" in hist
            or re.search(r"Application received|Thank you for applying|was received", page)):
        return _step([{"report_application_result": {
            "outcome": "ready_to_submit" if "TEST MODE" in hist else "submitted",
            "reason": "The form was accepted.", "confirmation_text": "", "missing_info": []}}],
            "Report the result")
    if hist.count("no application request was sent") >= 2:
        return _step([{"report_application_result": {
            "outcome": "failed", "reason": "Submit did not send the form twice.", "missing_info": []}}],
            "Give up")

    if not fields:
        link = next((e for e in els if e["tag"] in ("a", "button")
                     and re.search(r"apply", e["text"] + e["attrs"].get("id", ""), re.I)), None)
        if link:
            return _step([{"click": {"index": link["index"]}}], "Open the application form")
        return _step([{"report_application_result": {
            "outcome": "failed", "reason": "No application form found.", "missing_info": []}}], "Give up")

    actions: list[dict] = []
    if "Prefilled" not in hist and "No known ATS fields" not in hist:
        actions.append({"prefill_standard_fields": {}})
    if any(e["attrs"].get("type") == "file" for e in fields) and "Resume " not in hist:
        actions.append({"upload_resume": {}})
    if actions:
        return _step(actions, "Fill the standard fields and attach the resume")

    bank = qa_bank(system)
    prof = profile_answers(system)
    missing = []
    planned: list[tuple[tuple, dict]] = []  # (mark, action)
    for e in fields:
        name = e["attrs"].get("name", "") or e["attrs"].get("id", "")
        typ = e["attrs"].get("type", "")
        mark = (_url(page), e["index"])
        if mark in acted:
            continue
        if typ == "checkbox":
            if e["attrs"].get("checked") != "true" and (e["attrs"].get("required") == "true" or name == "consent"):
                planned.append((mark, {"click": {"index": e["index"]}}))
            continue
        if typ == "file" or "value" in e["attrs"]:
            continue
        answer = ANSWERS.get(name) or prof.get(name)
        if name in SENSITIVE:
            answer = bank.get(e["label"].lower().rstrip(" *"))
            if answer is None:
                missing.append(e["label"].rstrip(" *"))
                continue
        if answer is None:
            continue  # optional or unknown: leave blank
        kind = "select_dropdown" if e["tag"] == "select" else "input"
        planned.append((mark, {kind: {"index": e["index"], "text": answer}}))
    # browser-use runs at most 5 actions per step and drops the rest silently
    for mark, action in planned[:MAX_ACTIONS]:
        acted.add(mark)
        actions.append(action)
    if missing:
        return _step([{"report_application_result": {
            "outcome": "needs_input", "reason": "Required questions are not answered in the profile or Q&A bank.",
            "missing_info": missing}}], "Ask the candidate")
    if actions:
        return _step(actions, "Answer the remaining questions")
    below = re.search(r"([\d.]+) pages below", page)
    if below and float(below.group(1)) > 0:  # more of the form is below the fold
        return _step([{"scroll": {"down": True, "pages": 1}}], "Scroll to the rest of the form")
    submit = next((e for e in els if e["tag"] == "button"
                   and re.search(r"submit|continue", e["text"] + e["attrs"].get("type", ""), re.I)), None)
    if submit:
        return _step([{"click": {"index": submit["index"]}}], "Submit the application")
    return _step([{"report_application_result": {
        "outcome": "failed", "reason": "No submit button.", "missing_info": []}}], "Give up")


class State:
    def __init__(self):
        self.lock = threading.Lock()
        self.calls = 0


def make_handler(state: State):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def _json(self, code: int, obj):
            data = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path.rstrip("/").endswith("/models"):
                return self._json(200, {"object": "list", "data": [{"id": "scripted-agent", "object": "model"}]})
            if self.path == "/stats":
                return self._json(200, {"calls": state.calls})
            self._json(404, {"error": "not found"})

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
            msgs = body.get("messages", [])

            def text(m):
                c = m.get("content")
                if isinstance(c, list):
                    return "\n".join(p.get("text", "") for p in c if isinstance(p, dict))
                return c or ""
            system = "\n".join(text(m) for m in msgs if m.get("role") == "system")
            # the page can come in any user message (browser-use may add notes after it)
            user = "\n".join(text(m) for m in msgs if m.get("role") == "user")
            with state.lock:
                state.calls += 1
            if body.get("response_format") and "<browser_state>" in user + system:
                content = json.dumps(decide(system, user))
            elif body.get("response_format"):
                content = json.dumps({})
            else:
                content = "[]"  # plain-text calls (memory extraction): nothing to learn
            prompt_tokens = max(1, len(json.dumps(msgs)) // 4)
            self._json(200, {
                "id": f"chatcmpl-{state.calls}", "object": "chat.completion", "created": 0,
                "model": body.get("model", "scripted-agent"),
                "choices": [{"index": 0, "finish_reason": "stop",
                             "message": {"role": "assistant", "content": content}}],
                "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": max(1, len(content) // 4),
                          "total_tokens": prompt_tokens + len(content) // 4,
                          "prompt_tokens_details": {"cached_tokens": prompt_tokens // 2}},
            })
    return Handler


def serve(port: int = 0) -> tuple[ThreadingHTTPServer, State]:
    state = State()
    httpd = ThreadingHTTPServer(("127.0.0.1", port), make_handler(state))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, state


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8766)
    a = ap.parse_args()
    srv, _ = serve(a.port)
    print(f"scripted LLM on http://127.0.0.1:{srv.server_address[1]}/v1", flush=True)
    threading.Event().wait()
