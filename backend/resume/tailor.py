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


def _extract_sections(doc: fitz.Document) -> list[dict]:
    """Extract text blocks from the PDF grouped into logical sections.

    Groups a section header block with all content blocks that follow it
    until the next section header.
    """
    SECTION_HEADERS = {
        "skills": "skills",
        "technologies": "skills",
        "tech stack": "skills",
        "tools": "skills",
        "summary": "overview",
        "objective": "overview",
        "overview": "overview",
        "about me": "overview",
        "profile": "overview",
        "work experience": "experience",
        "experience": "experience",
        "employment": "experience",
        "professional experience": "experience",
        "volunteer experience": "experience",
        "education": "education",
        "contact": "contact",
    }

    all_blocks = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            if block["type"] != 0:
                continue
            text = ""
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text += span.get("text", "")
                text += "\n"
            text = text.strip()
            if not text:
                continue
            all_blocks.append({
                "page": page_num,
                "bbox": block["bbox"],
                "text": text,
            })

    # Identify which blocks are section headers
    sections = []
    current_section = None

    for block in all_blocks:
        lower = block["text"].lower().strip()
        section_type = SECTION_HEADERS.get(lower)

        if section_type:
            # This block is a header — start a new section
            if current_section and current_section["content_blocks"]:
                sections.append(current_section)
            current_section = {
                "section_type": section_type,
                "header_block": block,
                "content_blocks": [],
                "page": block["page"],
            }
        elif current_section:
            # This block is content under the current header
            current_section["content_blocks"].append(block)

    if current_section and current_section["content_blocks"]:
        sections.append(current_section)

    # Build final section objects with combined text and bounding boxes
    result = []
    for section in sections:
        content_text = "\n".join(b["text"] for b in section["content_blocks"])
        if not content_text.strip():
            continue
        # Compute bounding box that covers all content blocks
        all_bboxes = [b["bbox"] for b in section["content_blocks"]]
        combined_bbox = (
            min(b[0] for b in all_bboxes),
            min(b[1] for b in all_bboxes),
            max(b[2] for b in all_bboxes),
            max(b[3] for b in all_bboxes),
        )
        result.append({
            "page": section["page"],
            "bbox": combined_bbox,
            "text": content_text,
            "char_count": len(content_text),
            "section_type": section["section_type"],
            "content_blocks": section["content_blocks"],
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
        elif st == "experience" and options.get("experience"):
            tailorable.append(s)
    return tailorable


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

    from browser_use.llm.messages import UserMessage
    response = await llm.ainvoke([UserMessage(content=prompt)])
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
            new_text = result[key].strip()
            if len(new_text) <= s["char_count"]:
                tailored[i] = new_text
            else:
                tailored[i] = new_text[:s["char_count"]]

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

    # ─── Skills Section ───
    skills_section = next(
        ((i, s) for i, s in enumerate(sections) if s["section_type"] == "skills"),
        None,
    )
    if skills_section:
        idx, s = skills_section
        draw_section_header("Skills")
        content = tailored.get(idx, s["text"])
        for line in content.split("\n"):
            if line.strip():
                draw_wrapped(line.strip(), x=_MARGIN_LEFT, hang_x=_MARGIN_LEFT,
                             width=_TEXT_WIDTH, fontsize=_BODY_SIZE,
                             fontname="helv", color=body_color)
        state["y"] += 10

    # ─── Experience Section ───
    experience_sections = [
        (i, s) for i, s in enumerate(sections) if s["section_type"] == "experience"
    ]
    if experience_sections:
        draw_section_header("Experience")
        for idx, s in experience_sections:
            content = tailored.get(idx, s["text"])
            entries = _split_entries(content)
            for entry in entries:
                # Determine where the bullets begin so header lines (title /
                # company / date) before them get header styling.
                first_bullet_idx = next(
                    (i for i, l in enumerate(entry) if _is_bullet(l)), len(entry)
                )
                for ei, eline in enumerate(entry):
                    if _is_bullet(eline):
                        bullet_text = "• " + _strip_bullet(eline)
                        draw_wrapped(
                            bullet_text, x=_MARGIN_LEFT + _BULLET_INDENT,
                            hang_x=_MARGIN_LEFT + _HANGING_INDENT,
                            width=_TEXT_WIDTH - _BULLET_INDENT,
                            fontsize=_BODY_SIZE, fontname="helv", color=body_color,
                        )
                    elif ei == 0 and ei < first_bullet_idx:
                        # Job title
                        draw_wrapped(eline, x=_MARGIN_LEFT, hang_x=_MARGIN_LEFT,
                                     width=_TEXT_WIDTH, fontsize=9.5,
                                     fontname="helvetica-bold", color=body_color)
                    elif ei == 1 and ei < first_bullet_idx:
                        # Company
                        draw_wrapped(eline, x=_MARGIN_LEFT, hang_x=_MARGIN_LEFT,
                                     width=_TEXT_WIDTH, fontsize=_BODY_SIZE,
                                     fontname="helv", color=body_color)
                    else:
                        # Date / secondary line
                        draw_wrapped(eline, x=_MARGIN_LEFT, hang_x=_MARGIN_LEFT,
                                     width=_TEXT_WIDTH, fontsize=_BODY_SIZE,
                                     fontname="helv", color=light_color)
                state["y"] += _ENTRY_GAP

    # ─── Education Section (at the bottom) ───
    if education_text:
        draw_section_header("Education")
        for line in education_text.split("\n"):
            if line.strip():
                draw_wrapped(line.strip(), x=_MARGIN_LEFT, hang_x=_MARGIN_LEFT,
                             width=_TEXT_WIDTH, fontsize=_BODY_SIZE,
                             fontname="helv", color=body_color)

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
) -> dict:
    """Generate a tailored resume PDF for a specific job. Returns path and content."""
    settings = load_settings()
    resume_path = settings.get("resume_path", "")
    if not resume_path or not Path(resume_path).exists():
        raise FileNotFoundError("No resume PDF configured or file not found")

    doc = fitz.open(resume_path)
    sections = _extract_sections(doc)
    tailorable = _identify_tailorable_sections(sections, options)

    if not tailorable:
        doc.close()
        raise ValueError("No tailorable sections found in resume matching selected options")

    tailored_text = await _generate_tailored_text(tailorable, job_description, options)

    if not tailored_text:
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
    all_sections_for_pdf = [s for s in sections if s["section_type"] in ("skills", "experience", "overview")]
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
        content_parts.append(f"## {section_type}\n\n{tailored}")

    content = "\n\n".join(content_parts)
    output_md.write_text(content, encoding="utf-8")

    return {
        "path": str(output_pdf),
        "content": content,
        "sections_tailored": len(tailored_text),
        "sections_total": len(tailorable),
    }


async def refine_resume(job_url: str, job_description: str, instruction: str, options: dict) -> dict:
    """Refine an existing tailored resume with additional instructions."""
    return await tailor_resume(job_url, job_description, options)


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
