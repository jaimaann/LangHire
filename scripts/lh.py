"""Tiny CLI client for a running LangHire backend (manual and scripted testing).

    python scripts/lh.py GET /jobs/stats
    python scripts/lh.py PUT /settings '{"daily_apply_cap": 30}'
    python scripts/lh.py wait apply            # block until the apply run finishes, then print its status

Reads LANGHIRE_PORT (default 8743) and LANGHIRE_API_TOKEN (or <data dir>/.api_token).
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def token() -> str:
    t = os.environ.get("LANGHIRE_API_TOKEN")
    if t:
        return t
    base = Path(os.environ.get("APPDATA", Path.home() / ".config")) / "langhire" / ".api_token"
    return base.read_text().strip()


def call(method: str, path: str, body=None, timeout: float = 600):
    port = os.environ.get("LANGHIRE_PORT", "8743")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data, method=method)
    req.add_header("Authorization", f"Bearer {token()}")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
    try:
        return json.loads(raw)
    except ValueError:
        return raw


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if sys.argv[1] == "wait":
        kind = sys.argv[2]
        path = "/apply/status" if kind == "apply" else "/jobs/collect/status"
        while True:
            st = call("GET", path)
            if isinstance(st, dict) and not st.get("running"):
                print(json.dumps(st, indent=1, ensure_ascii=False)[:6000])
                return
            time.sleep(15)
    method, path = sys.argv[1], sys.argv[2]
    body = json.loads(sys.argv[3]) if len(sys.argv) > 3 else ({} if method in ("POST", "PUT") else None)
    print(json.dumps(call(method, path, body), indent=1, ensure_ascii=False)[:20000])


if __name__ == "__main__":
    main()
