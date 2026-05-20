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


def _replace_text_in_pdf(doc: fitz.Document, sections: list[dict], tailored: dict[int, str]) -> fitz.Document:
    """Replace text blocks in the PDF with tailored versions."""
    for i, s in enumerate(sections):
        if i not in tailored:
            continue
        page = doc[s["page"]]

        # Redact each content block individually
        for block in s.get("content_blocks", []):
            rect = fitz.Rect(block["bbox"])
            page.add_redact_annot(rect)
        page.apply_redactions()

        # Detect font size from the first content block
        fontsize = 9.5
        if s.get("content_blocks"):
            first_block_rect = fitz.Rect(s["content_blocks"][0]["bbox"])
            page_dict = page.get_text("dict")
            for block in page_dict.get("blocks", []):
                if block.get("type") == 0 and block.get("bbox"):
                    if fitz.Rect(block["bbox"]).intersects(first_block_rect):
                        for line in block.get("lines", []):
                            for span in line.get("spans", []):
                                fontsize = span.get("size", 9.5)
                                break
                            break
                        break

        # Insert tailored text into the combined bounding box
        rect = fitz.Rect(s["bbox"])
        page.insert_textbox(
            rect,
            tailored[i],
            fontsize=fontsize,
            align=fitz.TEXT_ALIGN_LEFT,
        )

    return doc


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

    doc_copy = fitz.open(resume_path)
    _replace_text_in_pdf(doc_copy, tailorable, tailored_text)

    url_hash = _url_hash(job_url)
    output_pdf = _get_tailored_dir() / f"{url_hash}.pdf"
    output_md = _get_tailored_dir() / f"{url_hash}.md"

    doc_copy.save(str(output_pdf))
    doc_copy.close()
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
