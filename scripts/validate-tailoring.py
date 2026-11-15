"""Validate resume tailoring against real job descriptions.

For each job with a description in a running backend, tailor the resume and
check the output PDF:
  * sections kept   — every section title of the original appears in the tailored PDF
  * fabrication     — numbers / capitalised terms in the tailored text that the original never mentions
  * keyword match   — share of the job description's key terms present, before vs after
  * truncation      — sections ending mid-word
  * pages           — page count of the original vs the tailored PDF
  * used for apply  — get_tailored_resume_path(url) returns the new PDF

    LANGHIRE_PORT=8750 LANGHIRE_API_TOKEN=... python scripts/validate-tailoring.py --resume r.pdf --jobs 5 --out report.json
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from lh import call  # noqa: E402

STOP = set("""a an the and or of to in for with on at by from as is are be will you your we our this that it
their they who what which have has can may must should would able work working team teams role job using use
strong good great excellent experience years year skills skill knowledge ability including etc per new well
also other such more than into across within over about candidate candidates required preferred plus""".split())


def key_terms(jd: str, n: int = 40) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z+#.\-]{1,}", jd)
    freq: dict[str, int] = {}
    for w in words:
        lw = w.lower().strip(".-")
        if lw in STOP or len(lw) < 3:
            continue
        freq[lw] = freq.get(lw, 0) + 1
    return [w for w, _ in sorted(freq.items(), key=lambda kv: -kv[1])[:n]]


def coverage(text: str, terms: list[str]) -> float:
    low = text.lower()
    return round(sum(1 for t in terms if t in low) / max(1, len(terms)), 3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--resume", required=True)
    ap.add_argument("--jobs", type=int, default=5)
    ap.add_argument("--out", default="tailoring-report.json")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    from resume.tailor import _extract_sections, find_fabrications
    orig_doc = pymupdf.open(a.resume)
    original_text = "\n".join(p.get_text() for p in orig_doc)
    original_titles = [s["title"] for s in _extract_sections(orig_doc)]

    jobs = [j for j in call("GET", "/jobs") if (j.get("description") or "").strip()][: a.jobs]
    report = []
    for j in jobs:
        res = call("POST", "/resume/tailor", {"job_urls": [j["url"]]}, timeout=900)
        r = (res.get("results") or [{}])[0] if isinstance(res, dict) else {}
        entry = {"job": f"{j['title']} at {j['company']}", "status": r.get("status"), "message": r.get("message"),
                 "warnings": r.get("warnings", [])}
        if r.get("status") == "done":
            pdf = pymupdf.open(r["path"])
            tailored_text = "\n".join(p.get_text() for p in pdf)
            terms = key_terms(j["description"])
            missing_titles = [t for t in original_titles if t.lower() not in tailored_text.lower()]
            content = r.get("content") or ""
            sections = [blk.split("\n\n", 1)[1] if "\n\n" in blk else "" for blk in content.split("## ")[1:]]
            truncated = [s[-40:] for s in sections if s and s.rstrip()[-1:].isalpha() and not s.rstrip().endswith(
                tuple("abcdefghijklmnopqrstuvwxyz"))]
            entry.update({
                "pages_original": len(orig_doc), "pages_tailored": len(pdf),
                "sections_missing_from_pdf": missing_titles,
                "fabricated_terms": find_fabrications(original_text, content),
                "keyword_coverage_before": coverage(original_text, terms),
                "keyword_coverage_after": coverage(tailored_text, terms),
                "truncated_endings": truncated,
                "chars_original": len(original_text), "chars_tailored": len(tailored_text),
                "content_preview": content[:600],
            })
            out = subprocess.run([sys.executable, "-c",
                                  "import sys; sys.path.insert(0, sys.argv[2]); "
                                  "from resume.tailor import get_tailored_resume_path as g; print(g(sys.argv[1]))",
                                  j["url"], str(ROOT / "backend")], capture_output=True, text=True)
            entry["used_for_apply"] = out.stdout.strip() == r["path"]
        report.append(entry)
        print(json.dumps({k: v for k, v in entry.items() if k != "content_preview"}, ensure_ascii=False))
    Path(a.out).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
