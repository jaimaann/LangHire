"""Add real postings from public Greenhouse / Lever boards to a running backend, with descriptions.

Used for real-site testing in test mode (nothing is submitted). Each spec is
"greenhouse:<board token>:<job id>" or "lever:<company>:<posting id>".

    python scripts/add-board-jobs.py greenhouse:gitlab:8922013002 lever:paytm:99417427-...
"""
import html
import json
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lh import call  # noqa: E402


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=30) as r:
        return json.loads(r.read())


def text(h: str) -> str:
    h = html.unescape(h or "")
    h = re.sub(r"<(br|/p|/li|/h\d)[^>]*>", "\n", h)
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"<[^>]+>", "", html.unescape(h))).strip()


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    for spec in sys.argv[1:]:
        kind, board, jid = spec.split(":", 2)
        if kind == "greenhouse":
            j = get(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{jid}")
            body = {"url": j["absolute_url"], "title": j["title"], "company": board,
                    "location": (j.get("location") or {}).get("name", ""), "description": text(j.get("content")),
                    "source": "manual"}
        else:
            j = get(f"https://api.lever.co/v0/postings/{board}/{jid}")
            desc = j.get("descriptionPlain", "") + "\n" + "\n".join(
                f"{x.get('text', '')}\n{text(x.get('content', ''))}" for x in j.get("lists", []))
            body = {"url": j["hostedUrl"], "title": j["text"], "company": board,
                    "location": (j.get("categories") or {}).get("location", ""), "description": desc.strip(),
                    "source": "manual"}
        r = call("POST", "/jobs/add", body)
        print(spec, "->", body["url"], r.get("success") if isinstance(r, dict) else r)


if __name__ == "__main__":
    main()
