"""
Resume tailoring engine.
Extracts text from PDF sections, sends to LLM with character-length constraints,
replaces text in-place to preserve layout.
"""
import hashlib
import json
import re
from pathlib import Path
from typing import Optional

import fitz  # pymupdf

try:
    from core.config import get_data_dir, load_settings, load_llm_settings
    from core.llm_factory import create_llm
except ImportError:
    from backend.core.config import get_data_dir, load_settings, load_llm_settings
    from backend.core.llm_factory import create_llm


def _get_tailored_dir() -> Path:
    d = get_data_dir() / "tailored_resumes"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _url_hash(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:12]


_HEADING_RULES = [  # first match wins; order matters ("Academic Projects" is projects, not education)
    ("projects", r"project"),
    ("experience", r"experience|internship|employment|work history|career history|professional background"),
    ("certifications", r"certif|award|achievement|honou?rs?|courses?|training|licen[cs]e"),
    ("skills", r"skill|technolog|tech stack|tools|competenc|expertise"),
    ("overview", r"summary|objective|overview|about me|^profile$|professional profile"),
    ("education", r"education|academic|qualification"),
    ("contact", r"^contact"),
    ("other", r"activit|volunteer|interest|hobb|leadership|publication|languages?|references|extra"),
]

_DEFAULT_TITLES = {"overview": "Summary", "skills": "Skills", "experience": "Experience", "projects": "Projects",
                   "education": "Education", "certifications": "Certifications", "other": "Other"}


def classify_heading(text: str) -> str | None:
    """Section type for a heading line, or None if it doesn't look like a heading."""
    t = " ".join(text.split())
    if not t or len(t) > 45 or len(t.split()) > 6:
        return None
    if t[-1] in ".,;" or "@" in t or any(ch.isdigit() for ch in t):
        return None
    low = t.lower().rstrip(":")
    for stype, rx in _HEADING_RULES:
        if re.search(rx, low):
            return stype
    return None


_BULLET_ONLY = re.compile(r"^[•●▪◦‣·\-–*○]$")
_PAGE_NUMBER = re.compile(r"^(page\s*)?\d{1,2}(\s*(of|/)\s*\d{1,2})?$", re.IGNORECASE)
_ENTRY_START = re.compile(
    r"^\s*((?:[A-Za-z]{3,9}\.?\s+)?\d{4}|present|current|now)\s*[-–—to]+\s*((?:[A-Za-z]{3,9}\.?\s+)?\d{4}|present|current|now)\b",
    re.IGNORECASE,
)


def _rebuild_paragraphs(lines: list[str]) -> str:
    """Turn PDF text lines back into paragraphs.

    PDF text comes out one visual line at a time: a bullet glyph alone on a line,
    sentences split at every wrap, and page numbers mixed in. Lines are grouped
    by PDF block (an empty string marks a block end), wrapped lines are joined,
    lone bullet glyphs are attached to the next paragraph, page numbers dropped,
    and a blank line is put before each dated entry so jobs/projects stay apart.
    """
    paras: list[str] = []
    cur: list[str] = []
    bullet_next = False

    def flush():
        nonlocal cur, bullet_next
        parts = [x.strip() for x in cur if x.strip()]
        cur = []

        def short(x: str) -> bool:
            return len(x.split()) <= 6 and not x.endswith((".", ",", ";", ":"))

        if len(parts) > 1 and len(parts[0].split()) <= 3 and short(parts[0]) and (not short(parts[1]) or "," in parts[1]):
            text = parts[0] + ": " + " ".join(parts[1:])      # "Programming: Python, R, SQL"
        elif len(parts) > 1 and all(short(x) for x in parts):
            text = " · ".join(parts)                          # a column list of courses / tools
        else:
            text = " ".join(parts)
        if not text:
            return
        if _BULLET_ONLY.match(text):
            bullet_next = True
            return
        if _PAGE_NUMBER.match(text):
            return
        prev = paras[-1] if paras else ""
        continues = (prev and not bullet_next and not _ENTRY_START.match(text)
                     and not prev.rstrip().endswith((".", "!", "?", ":"))
                     and (text[0].islower() or text[0] in "(&,/" or prev.rstrip().endswith((",", ";", "&", "/", "-"))))
        if continues:  # a wrapped line that the PDF stored as its own block
            paras[-1] = prev.rstrip() + " " + text
            return
        if bullet_next:
            text = "• " + text.lstrip("•●▪◦‣·-–*○ ")
            bullet_next = False
        if _ENTRY_START.match(text) and paras:
            paras.append("")
        paras.append(text)

    for ln in lines:
        if ln == "":
            flush()
        elif _BULLET_ONLY.match(ln.strip()):
            flush()
            bullet_next = True
        else:
            cur.append(ln)
    flush()
    return re.sub(r"\n{3,}", "\n\n", "\n".join(paras)).strip()


def _extract_sections(doc: fitz.Document) -> list[dict]:
    """Split a resume PDF into titled sections, in reading order.

    A line starts a new section when it is a short heading that names a known
    section ("Internships", "Academic Projects", "Certifications and Awards"),
    or when it is visibly emphasised (clearly larger than body text) and short.
    Unknown emphasised headings become type "other" and are kept verbatim.
    Headings used to be matched against a fixed list of exact strings, so most
    real resumes collapsed into one or two sections.
    """
    lines: list[dict] = []
    sizes: list[tuple[float, int]] = []
    for page_num in range(len(doc)):
        for block in doc[page_num].get_text("dict")["blocks"]:
            if block.get("type") != 0:
                continue
            block_lines = []
            for line in block.get("lines", []):
                spans = line.get("spans", [])
                text = "".join(sp.get("text", "") for sp in spans).replace("​", "").strip()
                if not text:
                    continue
                size = max((sp.get("size", 0) for sp in spans), default=0)
                bold = any("bold" in (sp.get("font", "") or "").lower() or (sp.get("flags", 0) & 16) for sp in spans)
                sizes.append((size, len(text)))
                block_lines.append({"text": text, "size": size, "bold": bold, "page": page_num,
                                    "bbox": line.get("bbox", block["bbox"])})
            if block_lines:
                block_lines[-1]["end_block"] = True
                lines.extend(block_lines)

    if not lines:
        return []
    # Body size: the size carrying the most characters
    weight: dict[float, int] = {}
    for size, n in sizes:
        weight[round(size, 1)] = weight.get(round(size, 1), 0) + n
    body = max(weight, key=weight.get)

    # If the resume marks its headings with a larger font, trust that and ignore
    # bold sub-lines like "Soft Skills" or a certificate name. Single-font PDFs
    # fall back to keyword matching alone.
    sized_headings = any(classify_heading(ln["text"]) and ln["size"] >= body + 2.5 for ln in lines)

    sections: list[dict] = []
    current: dict | None = None
    for ln in lines:
        stype = classify_heading(ln["text"])
        emphasised = ln["size"] >= body + 2.5
        if sized_headings and not emphasised:
            stype = None
        if stype is None and emphasised and len(ln["text"]) <= 45 and current is not None and                 not any(ch.isdigit() for ch in ln["text"]) and ln["text"][-1:] not in ".,;":
            stype = "other"
        is_heading = stype is not None and (emphasised or ln["bold"] or ln.get("end_block") or len(ln["text"].split()) <= 3)
        if is_heading:
            if current and current["lines"]:
                sections.append(current)
            current = {"section_type": stype, "title": " ".join(ln["text"].split()).rstrip(":"),
                       "page": ln["page"], "lines": [], "bboxes": []}
            continue
        if current is None:
            continue  # name / contact header above the first section
        # A blank line after each PDF text block keeps entries (jobs, projects) apart
        current["lines"].append(ln["text"])
        if ln.get("end_block"):
            current["lines"].append("")
        current["bboxes"].append(ln["bbox"])
    if current and current["lines"]:
        sections.append(current)

    result = []
    for sec in sections:
        text = _rebuild_paragraphs(sec["lines"])
        if not text:
            continue
        bb = sec["bboxes"]
        result.append({
            "page": sec["page"],
            "bbox": (min(b[0] for b in bb), min(b[1] for b in bb), max(b[2] for b in bb), max(b[3] for b in bb)),
            "text": text,
            "char_count": len(text),
            "section_type": sec["section_type"],
            "title": sec["title"],
            "content_blocks": [{"text": t, "bbox": b, "page": sec["page"]}
                               for t, b in zip([x for x in sec["lines"] if x], bb)],
        })
    return result


def _identify_tailorable_sections(sections: list[dict], options: dict) -> list[dict]:
    """Filter sections that match the user's selected tailoring options."""
    tailorable = []
    for s in sections:
        st = s["section_type"]
        if st == "skills" and options.get("skills"):
            tailorable.append(s)
        elif st == "overview" and options.get("overview"):
            tailorable.append(s)
        elif st in ("experience", "projects") and options.get("experience"):
            tailorable.append(s)
    return tailorable


def trim_to_limit(text: str, limit: int) -> str:
    """Shorten to `limit` chars at a line or sentence boundary, never mid-word."""
    text = text.strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    for sep in ("\n", ". ", "; ", ", "):
        pos = cut.rfind(sep)
        if pos >= limit * 0.6:
            return cut[: pos + (1 if sep.startswith(".") else 0)].rstrip(" ,;")
    pos = cut.rfind(" ")
    return (cut[:pos] if pos > 0 else cut).rstrip(" ,;")


_FACT_TOKEN = re.compile(r"\b(?:\d[\d.,%+]*|[A-Z][A-Za-z0-9+#.\-]{1,}|[a-z]+[A-Z][A-Za-z0-9]*)\b")
_COMMON_CAPS = {
    "The", "A", "An", "And", "Or", "For", "With", "In", "On", "At", "To", "Of", "By", "From", "As", "Using", "Used",
    "Built", "Led", "Developed", "Designed", "Created", "Managed", "Analyzed", "Analysed", "Improved", "Delivered",
    "Implemented", "Performed", "Conducted", "Collaborated", "Worked", "Applied", "Automated", "Reduced",
    "Increased", "Optimized", "Optimised", "Presented", "Prepared", "Cleaned", "Visualized", "Visualised",
    "Extracted", "Downloaded", "Identified", "Generated", "Leveraged", "Utilized", "Utilised", "Strong",
    "Proficient", "Experienced", "Skilled", "Data", "Analysis", "Analyst", "Skills", "Experience", "Summary",
    "Projects", "Project", "Tools", "Programming", "Visualization", "Visualisation", "Database", "Databases",
    "Soft", "Technical", "Key", "Core", "Results", "Team", "Teams", "Business", "Reports", "Reporting",
    "Dashboards", "Dashboard", "Insights", "Communication", "Detail", "Oriented", "Problem", "Solving",
}


def find_fabrications(original_resume: str, tailored: str) -> list[str]:
    """Numbers, names and skills in the tailored text that the original resume never mentions.

    The prompt tells the model not to invent experience; this checks it. Any
    number (years, %, counts) or capitalised / camel-case term (tools, employers,
    certifications) must already appear somewhere in the original resume.
    """
    known = original_resume.lower()
    known_compact = re.sub(r"[^a-z0-9]", "", known)

    def is_known(word: str) -> bool:
        low = word.lower()
        variants = {low, low.rstrip("s"), low[:-2] if low.endswith("es") else low, re.sub(r"[^a-z0-9]", "", low)}
        return any(v and (v in known or v in known_compact) for v in variants)

    found = []
    for m in _FACT_TOKEN.finditer(tailored):
        t = m.group(0).strip(".,")
        if not t or t in _COMMON_CAPS or t.upper() in _GENERIC_ACRONYMS:
            continue
        if is_known(t) or all(is_known(p) for p in t.split("-") if p):
            continue
        is_number = t[0].isdigit()
        is_tool = t.lower() in _TECH_TERMS
        acronym_or_camel = sum(ch.isupper() for ch in t) > 1
        start = tailored[max(0, m.start() - 3):m.start()]
        sentence_initial = m.start() == 0 or bool(re.search(r"(^|[\n.:•;!?]\s*|^\s*)$", start))
        # An ordinary capitalised word opening a sentence or bullet ("Partnered", "Exported")
        # is style, not a claim; tools, acronyms, numbers and mid-sentence names are claims.
        if sentence_initial and t[0].isupper() and t[1:].islower() and not is_tool:
            continue
        if is_number or is_tool or acronym_or_camel or (t[0].isupper() and not sentence_initial):
            found.append(t)
    return sorted(set(found))


# Generic business acronyms that describe work, not claimed tools or credentials
_GENERIC_ACRONYMS = {"KPI", "KPIS", "ROI", "ETL", "BI", "QA", "UI", "UX", "API", "APIS", "CRM", "ERP", "SLA", "SLAS",
                     "OKR", "OKRS", "B2B", "B2C", "CSV", "PDF", "MOM", "YOY", "QOQ", "EDA", "AI", "ML", "IT", "HR"}

# Tools and platforms a rewrite is most likely to invent (flagged wherever they appear)
_TECH_TERMS = {
    "snowflake", "redshift", "bigquery", "databricks", "spark", "pyspark", "hadoop", "hive", "airflow", "dbt",
    "looker", "qlik", "qlikview", "alteryx", "sas", "spss", "stata", "matlab", "aws", "azure", "gcp", "kubernetes",
    "docker", "java", "scala", "go", "rust", "javascript", "typescript", "react", "node", "tensorflow", "pytorch",
    "keras", "scikit-learn", "sklearn", "salesforce", "sap", "oracle", "postgresql", "postgres", "mongodb",
    "kafka", "excel", "tableau", "powerbi", "jira", "git", "github", "linux",
}


_STOP = {"and", "the", "for", "with", "from", "that", "this", "using", "used", "into", "over", "our", "your",
         "you", "are", "was", "were", "will", "have", "has", "had", "not", "but", "all", "any", "can", "its",
         "their", "they", "them", "who", "what", "which", "when", "where", "about", "work", "working", "team",
         "role", "years", "year", "experience", "skills", "ability", "strong", "good", "including", "across"}


def _terms(text: str) -> set[str]:
    words = (w.strip(".") for w in re.findall(r"[a-z][a-z0-9+#.]{2,}", (text or "").lower()))
    return {w for w in words if len(w) >= 3 and w not in _STOP}


_GENERIC = {"build", "built", "show", "more", "how", "company", "perform", "remove", "make", "made", "help",
             "new", "well", "also", "other", "such", "than", "within", "per", "etc", "able", "must", "should",
             "would", "may", "need", "needs", "based", "like", "high", "time", "day", "days", "end", "get", "use"}


def _jd_keywords(job_description: str, n: int = 30) -> set[str]:
    """The job description's most frequent content words: what a recruiter's keyword search looks for."""
    freq: dict[str, int] = {}
    for w in re.findall(r"[a-z][a-z0-9+#.]{2,}", (job_description or "").lower()):
        w = w.strip(".")
        if len(w) >= 3 and w not in _STOP and w not in _GENERIC:
            freq[w] = freq.get(w, 0) + 1
    return {w for w, _ in sorted(freq.items(), key=lambda kv: -kv[1])[:n]}


def find_dropped_terms(original_section: str, tailored: str, job_description: str) -> list[str]:
    """Top job keywords the original section had and the rewrite lost (tailoring should add, not remove)."""
    relevant = _terms(original_section) & _jd_keywords(job_description)
    return sorted(relevant - _terms(tailored))


async def _generate_tailored_text(
    sections: list[dict],
    job_description: str,
    options: dict,
    refinement: str = "",
) -> dict[int, str]:
    """Call LLM to generate tailored text for each section within char limits."""
    llm_settings = load_llm_settings()
    if not llm_settings.get("provider"):
        raise ValueError("No LLM configured")

    llm = create_llm(llm_settings)

    section_prompts = []
    for i, s in enumerate(sections):
        max_chars = s["char_count"]
        section_prompts.append(
            f"SECTION {i} ({s['section_type']}, max {max_chars} characters):\n"
            f"ORIGINAL: \"{s['text']}\"\n"
            f"→ Rewrite for the target job. MUST be {max_chars} characters or fewer.\n"
        )

    refinement_note = ""
    if refinement:
        refinement_note = f"\nADDITIONAL INSTRUCTION: {refinement}\n"

    prompt = (
        "You are a resume tailoring expert. Rewrite the following resume sections "
        "to better match the target job description.\n\n"
        "CRITICAL RULES:\n"
        "- Each section's output MUST NOT exceed its character limit\n"
        "- Keep the same general structure and formatting style\n"
        "- Keep EVERY entry, bullet and fact of the original: reword and reorder, never drop content. "
        "Use most of each character limit; a shorter rewrite loses keywords recruiters search for\n"
        "- Emphasize skills and experience relevant to the job\n"
        "- Do NOT fabricate experience the candidate doesn't have\n"
        "- Do NOT add skills not present in the original resume\n"
        "- Reorder and rephrase to highlight what matters for this role\n"
        f"{refinement_note}\n"
        f"TARGET JOB DESCRIPTION:\n{job_description[:3000]}\n\n"
        + "\n".join(section_prompts) + "\n\n"
        "Return ONLY a JSON object with section indices as keys and tailored text as values:\n"
        '{"0": "tailored text for section 0", "1": "tailored text for section 1", ...}\n'
    )

    from core.llm_factory import ainvoke_text
    response = await ainvoke_text(llm, prompt, timeout=300)
    if hasattr(response, "completion"):
        text = response.completion
    elif hasattr(response, "content") and isinstance(response.content, str):
        text = response.content
    else:
        text = str(response)

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("LLM did not return valid JSON")

    result = json.loads(match.group())

    tailored = {}
    for i, s in enumerate(sections):
        key = str(i)
        if key in result:
            new_text = str(result[key]).strip()
            # Over-long output used to be cut mid-word ("...built dashbo"); cut at a boundary instead
            tailored[i] = trim_to_limit(new_text, s["char_count"])

    return tailored


# ── PDF layout constants ─────────────────────────────────────────────────────
_PAGE_WIDTH = 612          # US Letter
_PAGE_HEIGHT = 792
_MARGIN_LEFT = 36
_MARGIN_RIGHT = 576
_TOP_MARGIN = 50
_BOTTOM_MARGIN = 50        # usable area ends at _PAGE_HEIGHT - _BOTTOM_MARGIN
_TEXT_WIDTH = _MARGIN_RIGHT - _MARGIN_LEFT
_BULLET_INDENT = 15        # x-offset for bullet glyph
_HANGING_INDENT = 27       # x-offset for wrapped bullet continuation lines
_BODY_SIZE = 9
_LINE_GAP = 3              # extra spacing added to fontsize for line-height
_ENTRY_GAP = 10            # consistent vertical gap between experience entries

# Bullet glyphs we treat as list markers (beyond the original ·/-).
_BULLET_CHARS = ("·", "-", "•", "*", "–", "—", "‣", "●", "▪", "◦", "○")
# Numbered bullets like "1." / "12)" / "a." / "iv)".
_NUMBERED_RE = re.compile(r"^\(?\s*([0-9]+|[a-zA-Z]|[ivxIVX]+)\s*[.)]\s+")
# A leading date range, e.g. "2019 - 2022", "Jan 2019 – Present", "2020-Now".
_DATE_RANGE_RE = re.compile(
    r"^\s*((?:[A-Za-z]{3,9}\.?\s+)?\d{4}|present|current|now)\s*[-–—to]+\s*"
    r"((?:[A-Za-z]{3,9}\.?\s+)?\d{4}|present|current|now)\b",
    re.IGNORECASE,
)
# "Title — Company" / "Title @ Company" / "Title at Company" style header.
_TITLE_COMPANY_RE = re.compile(r".+\s+(?:[–—@|]|\bat\b)\s+.+")


def _is_bullet(line: str) -> bool:
    """Return True if ``line`` looks like a list bullet of any common style."""
    s = line.lstrip()
    if not s:
        return False
    if s[0] in _BULLET_CHARS:
        return True
    return bool(_NUMBERED_RE.match(s))


def _strip_bullet(line: str) -> str:
    """Remove a leading bullet marker, returning the bullet text only."""
    s = line.lstrip()
    if s and s[0] in _BULLET_CHARS:
        return s[1:].lstrip()
    m = _NUMBERED_RE.match(s)
    if m:
        return s[m.end():].lstrip()
    return s


def _is_entry_header(line: str) -> bool:
    """Heuristic: a non-bullet line that begins a new experience entry.

    Catches lines with a leading date range or a "Title — Company" pattern even
    when the resume uses no explicit bullets.
    """
    s = line.strip()
    if not s or _is_bullet(s):
        return False
    return bool(_DATE_RANGE_RE.match(s) or _TITLE_COMPANY_RE.match(s))


def _split_entries(content: str) -> list[list[str]]:
    """Split experience-section text into a list of entries (each a line list).

    An entry boundary is a blank line, OR a new non-bullet header line that
    follows lines already containing bullets, OR a detected entry-header line.
    """
    entries: list[list[str]] = []
    current: list[str] = []
    for raw in content.split("\n"):
        stripped = raw.strip()
        if not stripped:
            if current:
                entries.append(current)
                current = []
            continue
        start_new = False
        if current:
            has_bullets = any(_is_bullet(l) for l in current)
            if not _is_bullet(stripped) and has_bullets:
                start_new = True
            elif _is_entry_header(stripped) and not _is_bullet(stripped):
                # A new header (date range / Title — Company) starts a fresh entry.
                start_new = True
        if start_new:
            entries.append(current)
            current = []
        current.append(stripped)
    if current:
        entries.append(current)
    return entries


def _generate_fresh_pdf(
    sections: list[dict],
    tailored: dict[int, str],
    profile_name: str,
    contact_info: str,
    education_text: str,
    output_path: Path,
):
    """Generate a professional PDF matching the user's resume style.

    Uses real font metrics for wrapping and tracks a y-cursor with page-overflow
    handling so no text is ever drawn below the usable area.
    """
    doc = fitz.open()
    page = doc.new_page(width=_PAGE_WIDTH, height=_PAGE_HEIGHT)
    usable_bottom = _PAGE_HEIGHT - _BOTTOM_MARGIN

    # Colors
    header_color = (0.09, 0.09, 0.40)  # dark blue for section headers
    body_color = (0.19, 0.19, 0.19)    # dark gray for body
    light_color = (0.40, 0.40, 0.40)   # lighter gray for dates/secondary

    state = {"page": page, "y": _TOP_MARGIN}

    def ensure_space(needed: float):
        """Start a new page if drawing ``needed`` points would overflow."""
        if state["y"] + needed > usable_bottom:
            state["page"] = doc.new_page(width=_PAGE_WIDTH, height=_PAGE_HEIGHT)
            state["y"] = _TOP_MARGIN

    def draw_line_text(text: str, *, x: float, fontsize: float, fontname: str,
                       color: tuple, line_height: float, baseline_pad: float):
        ensure_space(line_height)
        state["page"].insert_text(
            fitz.Point(x, state["y"] + baseline_pad),
            text, fontsize=fontsize, fontname=fontname, color=color,
        )
        state["y"] += line_height

    def draw_wrapped(text: str, *, x: float, hang_x: float, width: float,
                     fontsize: float, fontname: str, color: tuple):
        line_height = fontsize + _LINE_GAP
        wrapped = _wrap_text(text, width, fontsize) or [""]
        for i, wl in enumerate(wrapped):
            draw_line_text(
                wl, x=(x if i == 0 else hang_x), fontsize=fontsize,
                fontname=fontname, color=color, line_height=line_height,
                baseline_pad=fontsize,
            )

    def draw_section_header(title: str):
        ensure_space(28)
        state["page"].insert_text(
            fitz.Point(_MARGIN_LEFT, state["y"] + 12), title,
            fontsize=12, fontname="helvetica-bold", color=header_color,
        )
        state["y"] += 18
        state["page"].draw_line(
            fitz.Point(_MARGIN_LEFT, state["y"]),
            fitz.Point(_MARGIN_RIGHT, state["y"]),
            color=(0.8, 0.8, 0.8), width=0.5,
        )
        state["y"] += 12

    # ─── Name ───
    ensure_space(42)
    state["page"].insert_text(
        fitz.Point(_MARGIN_LEFT, state["y"] + 30),
        profile_name.upper() if profile_name else "",
        fontsize=28, fontname="helvetica-bold", color=(0, 0, 0),
    )
    state["y"] += 42
    state["page"].draw_line(
        fitz.Point(_MARGIN_LEFT, state["y"]), fitz.Point(_MARGIN_RIGHT, state["y"]),
        color=(0.85, 0.20, 0.35), width=2,
    )
    state["y"] += 20

    # ─── Contact info (below name) ───
    for line in contact_info.split("\n"):
        if line.strip():
            draw_line_text(line.strip(), x=_MARGIN_LEFT, fontsize=_BODY_SIZE,
                           fontname="helv", color=body_color,
                           line_height=14, baseline_pad=10)
    state["y"] += 10

    def draw_entries(content: str):
        for entry in _split_entries(content):
            # Lines before the first bullet are the entry header (title / org / dates)
            first_bullet_idx = next((i for i, l in enumerate(entry) if _is_bullet(l)), len(entry))
            for ei, eline in enumerate(entry):
                if _is_bullet(eline):
                    draw_wrapped("• " + _strip_bullet(eline), x=_MARGIN_LEFT + _BULLET_INDENT,
                                 hang_x=_MARGIN_LEFT + _HANGING_INDENT, width=_TEXT_WIDTH - _BULLET_INDENT,
                                 fontsize=_BODY_SIZE, fontname="helv", color=body_color)
                elif ei == 0 and ei < first_bullet_idx:
                    draw_wrapped(eline, x=_MARGIN_LEFT, hang_x=_MARGIN_LEFT, width=_TEXT_WIDTH,
                                 fontsize=9.5, fontname="helvetica-bold", color=body_color)
                elif ei == 1 and ei < first_bullet_idx:
                    draw_wrapped(eline, x=_MARGIN_LEFT, hang_x=_MARGIN_LEFT, width=_TEXT_WIDTH,
                                 fontsize=_BODY_SIZE, fontname="helv", color=body_color)
                else:
                    draw_wrapped(eline, x=_MARGIN_LEFT, hang_x=_MARGIN_LEFT, width=_TEXT_WIDTH,
                                 fontsize=_BODY_SIZE, fontname="helv",
                                 color=light_color if ei < first_bullet_idx else body_color)
            state["y"] += _ENTRY_GAP

    def draw_lines(content: str):
        for line in content.split("\n"):
            if line.strip():
                draw_wrapped(line.strip(), x=_MARGIN_LEFT, hang_x=_MARGIN_LEFT, width=_TEXT_WIDTH,
                             fontsize=_BODY_SIZE, fontname="helv", color=body_color)
        state["y"] += 10

    # ─── Every section, in the resume's own order, under its own title ───
    # (The old layout drew only Skills, Experience and Education: summaries were
    # tailored but never drawn, and projects / certifications / awards vanished.)
    has_education = False
    for idx, s in enumerate(sections):
        stype = s.get("section_type", "other")
        if stype == "contact":
            continue
        has_education = has_education or stype == "education"
        title = s.get("title") or _DEFAULT_TITLES.get(stype, stype.replace("_", " ").title())
        content = tailored.get(idx, s["text"])
        if not content.strip():
            continue
        draw_section_header(title)
        if stype in ("experience", "projects"):
            draw_entries(content)
        else:
            draw_lines(content)

    if education_text and not has_education:
        draw_section_header("Education")
        draw_lines(education_text)

    doc.save(str(output_path))
    doc.close()


# Shared font used for both measuring and rendering so wrapping matches output.
# "helv" maps to Helvetica, the same base-14 font used by insert_text below.
_MEASURE_FONT = fitz.Font("helv")


def _wrap_text(text: str, max_width: float, fontsize: float) -> list[str]:
    """Word-wrap ``text`` so each line renders within ``max_width`` points.

    Uses real font metrics (fitz.Font.text_length) rather than an approximate
    character-width estimate, so wrapped lines match the actually-rendered width.
    A single word that is wider than ``max_width`` cannot be split and is emitted
    on its own line.
    """
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        test = f"{current} {word}" if current else word
        if current and _MEASURE_FONT.text_length(test, fontsize) > max_width:
            lines.append(current)
            current = word
        else:
            current = test
    if current:
        lines.append(current)
    return lines


def _draw_wrapped(page, x: float, y: float, text: str, max_width: float, fontsize: float, fontname: str, color: tuple):
    """Draw text with word wrap. Returns the new y-cursor after drawing."""
    lines = _wrap_text(text, max_width, fontsize)
    for line in lines:
        page.insert_text(fitz.Point(x, y + 8), line, fontsize=fontsize, fontname=fontname, color=color)
        y += fontsize + 2
    return y


async def tailor_resume(
    job_url: str,
    job_description: str,
    options: dict,
    refinement: str = "",
) -> dict:
    """Generate a tailored resume PDF for a specific job. Returns path and content."""
    settings = load_settings()
    resume_path = settings.get("resume_path", "")
    if not resume_path or not Path(resume_path).exists():
        raise FileNotFoundError("No resume PDF configured or file not found")
    if Path(resume_path).suffix.lower() != ".pdf":
        # Tailoring rewrites sections inside the PDF's own layout; Word files are used as-is.
        raise ValueError("Resume tailoring works on PDF resumes. Export your Word resume as PDF to tailor it; "
                         "applications still use the Word file.")

    doc = fitz.open(resume_path)
    sections = _extract_sections(doc)
    tailorable = _identify_tailorable_sections(sections, options)

    if not tailorable:
        doc.close()
        raise ValueError("No tailorable sections found in resume matching selected options")

    tailored_text = await _generate_tailored_text(tailorable, job_description, options, refinement=refinement)

    # Fabrication guard: a rewritten section may only use facts already in the resume
    original_resume = "\n".join(page.get_text() for page in doc)
    warnings: list[str] = []
    for ti, text in list(tailored_text.items()):
        invented = find_fabrications(original_resume, text)
        if invented:
            title = tailorable[ti].get("title") or tailorable[ti]["section_type"]
            warnings.append(f"Kept the original {title}: the rewrite added terms not in your resume "
                            f"({', '.join(invented[:6])})")
            del tailored_text[ti]
            continue
        dropped = find_dropped_terms(tailorable[ti]["text"], text, job_description)
        if len(dropped) >= 2:
            title = tailorable[ti].get("title") or tailorable[ti]["section_type"]
            warnings.append(f"Kept the original {title}: the rewrite dropped job keywords you already had "
                            f"({', '.join(dropped[:6])})")
            del tailored_text[ti]

    if not tailored_text and not warnings:
        doc.close()
        raise ValueError("LLM could not tailor any sections within character limits")

    url_hash = _url_hash(job_url)
    output_pdf = _get_tailored_dir() / f"{url_hash}.pdf"
    output_md = _get_tailored_dir() / f"{url_hash}.md"

    # Extract name, contact, and education from the original resume/profile
    try:
        from core.config import load_profile
        profile = load_profile()
        profile_name = profile.get("name", "")
        contact_parts = []
        if profile.get("email"):
            contact_parts.append(profile["email"])
        if profile.get("phone"):
            contact_parts.append(f"{profile.get('phone_country_code', '')}{profile['phone']}")
        addr = profile.get("address", {})
        if addr.get("city"):
            contact_parts.append(f"{addr['city']}, {addr.get('state', '')} {addr.get('country', '')}")
        contact_info = "\n".join(contact_parts)
    except Exception:
        profile_name = ""
        contact_info = ""

    # Get education from the extracted sections (not tailored)
    education_text = ""
    for s in sections:
        if s["section_type"] == "education":
            education_text = s["text"]
            break
    if not education_text:
        try:
            edu = profile.get("education", {})
            if edu.get("degree"):
                education_text = f"{edu.get('school', '')} | {edu['degree']}\nGraduation: {edu.get('graduation', '')}"
        except Exception:
            pass

    # Pass ALL sections to the PDF (not just tailored ones)
    # Map tailored indices back to full section list
    all_sections_for_pdf = [s for s in sections if s["section_type"] != "contact"]
    # Build a tailored_text map using full section indices
    full_tailored = {}
    for i, s in enumerate(all_sections_for_pdf):
        # Find if this section was tailored
        for ti, ts in enumerate(tailorable):
            if ts["text"] == s["text"] and ts["section_type"] == s["section_type"]:
                if ti in tailored_text:
                    full_tailored[i] = tailored_text[ti]
                break

    _generate_fresh_pdf(all_sections_for_pdf, full_tailored, profile_name, contact_info, education_text, output_pdf)
    doc.close()

    content_parts = []
    for i, s in enumerate(tailorable):
        section_type = s["section_type"].upper()
        original = s["text"]
        tailored = tailored_text.get(i, original)
        content_parts.append(f"## {s.get('title') or section_type}\n\n{tailored}")

    content = "\n\n".join(content_parts)
    output_md.write_text(content, encoding="utf-8")

    return {
        "path": str(output_pdf),
        "content": content,
        "sections_tailored": len(tailored_text),
        "sections_total": len(tailorable),
        "warnings": warnings,
    }


async def refine_resume(job_url: str, job_description: str, instruction: str, options: dict) -> dict:
    """Refine an existing tailored resume with additional instructions."""
    return await tailor_resume(job_url, job_description, options, refinement=instruction)


def get_tailored_content(job_url: str) -> Optional[dict]:
    """Get the tailored resume content for a job (if it exists)."""
    url_hash = _url_hash(job_url)
    md_path = _get_tailored_dir() / f"{url_hash}.md"
    pdf_path = _get_tailored_dir() / f"{url_hash}.pdf"

    if not md_path.exists():
        return None

    return {
        "content": md_path.read_text(encoding="utf-8"),
        "path": str(pdf_path) if pdf_path.exists() else None,
    }


def delete_tailored_resume(job_url: str) -> bool:
    """Delete the tailored resume files for a job."""
    url_hash = _url_hash(job_url)
    md_path = _get_tailored_dir() / f"{url_hash}.md"
    pdf_path = _get_tailored_dir() / f"{url_hash}.pdf"

    deleted = False
    if md_path.exists():
        md_path.unlink()
        deleted = True
    if pdf_path.exists():
        pdf_path.unlink()
        deleted = True
    return deleted


def get_tailored_resume_path(job_url: str) -> Optional[str]:
    """Get the path to the tailored PDF for a job, or None if it doesn't exist."""
    url_hash = _url_hash(job_url)
    pdf_path = _get_tailored_dir() / f"{url_hash}.pdf"
    if pdf_path.exists():
        return str(pdf_path)
    return None
