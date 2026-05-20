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


def _generate_fresh_pdf(
    sections: list[dict],
    tailored: dict[int, str],
    profile_name: str,
    contact_info: str,
    education_text: str,
    output_path: Path,
):
    """Generate a professional PDF matching the user's resume style."""
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)  # US Letter

    # Layout constants (matching typical professional resume)
    margin_left = 36
    margin_right = 576
    col_split = 200
    col_right = 214
    page_width = margin_right - margin_left

    # Colors
    header_color = (0.09, 0.09, 0.40)  # dark blue for section headers
    body_color = (0.19, 0.19, 0.19)    # dark gray for body
    light_color = (0.40, 0.40, 0.40)   # lighter gray for dates/secondary

    y = 50

    # ─── Name ───
    page.insert_text(fitz.Point(margin_left, y + 30), profile_name.upper() if profile_name else "", fontsize=28, fontname="helvetica-bold", color=(0, 0, 0))
    y += 42
    # Accent line under name
    page.draw_line(fitz.Point(margin_left, y), fitz.Point(margin_right, y), color=(0.85, 0.20, 0.35), width=2)
    y += 20

    # ─── Contact info (below name) ───
    for line in contact_info.split("\n"):
        if line.strip():
            page.insert_text(fitz.Point(margin_left, y + 10), line.strip(), fontsize=9, fontname="helv", color=body_color)
            y += 14
    y += 10

    # ─── Skills Section ───
    skills_section = None
    for i, s in enumerate(sections):
        if s["section_type"] == "skills":
            skills_section = (i, s)
            break

    if skills_section:
        idx, s = skills_section
        page.insert_text(fitz.Point(margin_left, y + 12), "Skills", fontsize=12, fontname="helvetica-bold", color=header_color)
        y += 18
        page.draw_line(fitz.Point(margin_left, y), fitz.Point(margin_right, y), color=(0.8, 0.8, 0.8), width=0.5)
        y += 10
        content = tailored.get(idx, s["text"])
        for line in content.split("\n"):
            if line.strip():
                page.insert_text(fitz.Point(margin_left, y + 9), line.strip(), fontsize=9, fontname="helv", color=body_color)
                y += 13
        y += 10

    # ─── Experience Section ───
    experience_sections = [(i, s) for i, s in enumerate(sections) if s["section_type"] == "experience"]

    if experience_sections:
        page.insert_text(fitz.Point(margin_left, y + 12), "Experience", fontsize=12, fontname="helvetica-bold", color=header_color)
        y += 18
        page.draw_line(fitz.Point(margin_left, y), fitz.Point(margin_right, y), color=(0.8, 0.8, 0.8), width=0.5)
        y += 12

        for idx, s in experience_sections:
            content = tailored.get(idx, s["text"])

            # Pre-process: split into entries, then pre-wrap all lines
            entries = []
            current_entry: list[str] = []
            for line in content.split("\n"):
                stripped = line.strip()
                if not stripped:
                    if current_entry:
                        entries.append(current_entry)
                        current_entry = []
                else:
                    if (current_entry and
                        not stripped.startswith("·") and not stripped.startswith("-") and
                        any(l.startswith("·") or l.startswith("-") for l in current_entry)):
                        entries.append(current_entry)
                        current_entry = []
                    current_entry.append(stripped)
            if current_entry:
                entries.append(current_entry)

            for entry in entries:
                if y > 720:
                    page = doc.new_page(width=612, height=792)
                    y = 50

                for ei, eline in enumerate(entry):
                    is_bullet = eline.startswith("·") or eline.startswith("-")

                    if is_bullet:
                        # Pre-wrap bullet text, render each wrapped line at same indent
                        wrapped = _wrap_text(eline, page_width - 30, 9)
                        for wl in wrapped:
                            if y > 760:
                                page = doc.new_page(width=612, height=792)
                                y = 50
                            page.insert_text(fitz.Point(margin_left + 15, y + 10), wl, fontsize=9, fontname="helv", color=body_color)
                            y += 12
                    else:
                        # Header line — find first bullet to determine position
                        first_bullet_idx = len(entry)
                        for fi, fl in enumerate(entry):
                            if fl.startswith("·") or fl.startswith("-"):
                                first_bullet_idx = fi
                                break

                        header_pos = ei if ei < first_bullet_idx else 0

                        if y > 760:
                            page = doc.new_page(width=612, height=792)
                            y = 50

                        if header_pos == 0:
                            # Job title
                            page.insert_text(fitz.Point(margin_left, y + 10), eline, fontsize=9.5, fontname="helvetica-bold", color=body_color)
                            y += 14
                        elif header_pos == 1:
                            # Company
                            page.insert_text(fitz.Point(margin_left, y + 10), eline, fontsize=9, fontname="helv", color=body_color)
                            y += 12
                        else:
                            # Date
                            page.insert_text(fitz.Point(margin_left, y + 10), eline, fontsize=9, fontname="helv", color=light_color)
                            y += 12

                y += 10

    # ─── Education Section (at the bottom) ───
    if education_text:
        if y > 700:
            page = doc.new_page(width=612, height=792)
            y = 50
        y += 5
        page.insert_text(fitz.Point(margin_left, y + 12), "Education", fontsize=12, fontname="helvetica-bold", color=header_color)
        y += 18
        page.draw_line(fitz.Point(margin_left, y), fitz.Point(margin_right, y), color=(0.8, 0.8, 0.8), width=0.5)
        y += 12
        for line in education_text.split("\n"):
            if line.strip():
                page.insert_text(fitz.Point(margin_left, y + 9), line.strip(), fontsize=9, fontname="helv", color=body_color)
                y += 13

    doc.save(str(output_path))
    doc.close()


def _wrap_text(text: str, max_width: float, fontsize: float) -> list[str]:
    """Simple word-wrap based on approximate character width."""
    char_width = fontsize * 0.52
    max_chars = int(max_width / char_width)
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = current + " " + word if current else word
        if len(test) > max_chars:
            if current:
                lines.append(current)
            current = word
        else:
            current = test
    if current:
        lines.append(current)
    return lines


def _draw_wrapped(page, x: float, y: float, text: str, max_width: float, fontsize: float, fontname: str, color: tuple):
    """Draw text with word wrap."""
    lines = _wrap_text(text, max_width, fontsize)
    for line in lines:
        page.insert_text(fitz.Point(x, y + 8), line, fontsize=fontsize, fontname=fontname, color=color)
        y += 11


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
