"""Resume tailoring and cover letters."""
from __future__ import annotations

import re

from fastapi import APIRouter

from core.config import load_llm_settings, load_profile
from models import CoverLetterRequest, JobUrlRequest, RefineRequest, TailorRequest

from .common import api_error, llm_text

router = APIRouter()

_HASH = re.compile(r"^[0-9a-f]{8,64}$")


# ── Resume Tailoring ──────────────────────────────────────────────────────

@router.post("/resume/tailor")
async def tailor_resumes(body: TailorRequest):
    """Generate tailored resumes for one or more jobs."""
    from resume.tailor import tailor_resume
    from core.shared_config import read_jobs, update_job

    job_urls = body.job_urls
    options = body.options.model_dump()

    jobs = read_jobs()
    results = []

    for url in job_urls:
        job = jobs.get(url)
        if not job:
            results.append({"url": url, "status": "error", "message": "Job not found"})
            continue
        description = job.get("description", "")
        if not description:
            # Fallback: use title + company + location as context for tailoring
            title = job.get("title", "")
            company = job.get("company", "")
            location = job.get("location", "")
            if not title:
                results.append({"url": url, "status": "error", "message": "No job description or title available"})
                continue
            description = f"Job Title: {title}\nCompany: {company}\nLocation: {location}\n\nTailor the resume for this role based on the job title and company."
        try:
            result = await tailor_resume(url, description, options)
            update_job(url, tailored_resume_path=result["path"])
            results.append({"url": url, "status": "done", "path": result["path"], "content": result["content"]})
        except Exception as e:
            results.append({"url": url, "status": "error", "message": str(e)})

    return {"success": True, "results": results}


@router.post("/resume/tailor/refine")
async def refine_tailored_resume(body: RefineRequest):
    """Refine an existing tailored resume with additional instructions."""
    from resume.tailor import tailor_resume
    from core.shared_config import read_jobs, update_job

    job_url = body.job_url
    instruction = body.instruction

    jobs = read_jobs()
    job = jobs.get(job_url)
    if not job:
        return api_error("not_found", "Job not found", 404)

    description = job.get("description", "")
    options = body.options.model_dump()

    try:
        result = await tailor_resume(job_url, description + f"\n\nADDITIONAL INSTRUCTION: {instruction}", options)
        update_job(job_url, tailored_resume_path=result["path"])
        return {"success": True, "content": result["content"], "path": result["path"]}
    except Exception as e:
        return api_error("tailor_error", str(e), 500)


@router.post("/resume/tailor/get-by-url")
async def get_tailored_by_url(body: JobUrlRequest):
    """Get tailored resume content by job URL."""
    from resume.tailor import get_tailored_content
    result = get_tailored_content(body.job_url)
    if not result:
        return api_error("not_found", "No tailored resume for this job", 404)
    return {"success": True, "content": result["content"], "path": result["path"]}


@router.get("/resume/tailor/{url_hash}")
async def get_tailored_resume(url_hash: str):
    """Get tailored resume content by URL hash."""
    if not _HASH.match(url_hash):
        return api_error("invalid_hash", "Invalid id", 400)
    from resume.tailor import _get_tailored_dir
    md_path = _get_tailored_dir() / f"{url_hash}.md"
    pdf_path = _get_tailored_dir() / f"{url_hash}.pdf"
    if not md_path.exists():
        return api_error("not_found", "No tailored resume found", 404)
    return {
        "success": True,
        "content": md_path.read_text(encoding="utf-8"),
        "path": str(pdf_path) if pdf_path.exists() else None,
    }


@router.delete("/resume/tailor/{url_hash}")
async def delete_tailored(url_hash: str):
    """Delete a tailored resume."""
    if not _HASH.match(url_hash):
        return api_error("invalid_hash", "Invalid id", 400)
    from resume.tailor import _get_tailored_dir
    md_path = _get_tailored_dir() / f"{url_hash}.md"
    pdf_path = _get_tailored_dir() / f"{url_hash}.pdf"
    if md_path.exists():
        md_path.unlink()
    if pdf_path.exists():
        pdf_path.unlink()
    return {"success": True}


# ── Cover Letter Generation ───────────────────────────────────────────────

@router.post("/cover-letter/generate")
async def generate_cover_letter(body: CoverLetterRequest):
    """Generate a tailored cover letter using LLM based on job description + profile."""
    job_description = body.job_description.strip()
    job_title = body.job_title
    company = body.company

    llm_settings = load_llm_settings()
    if not llm_settings.get("provider"):
        return api_error("no_llm", "No LLM configured. Set up an LLM provider in Settings first.")

    profile = load_profile()

    prompt = (
        "Write a professional cover letter for the following job application.\n\n"
        f"JOB TITLE: {job_title}\n"
        f"COMPANY: {company}\n"
        f"JOB DESCRIPTION:\n{job_description}\n\n"
        f"CANDIDATE PROFILE:\n"
        f"Name: {profile.get('name', '')}\n"
        f"Current Role: {profile.get('current_role', '')}\n"
        f"Years of Experience: {profile.get('years_of_experience', 0)}\n"
        f"Skills: {', '.join(profile.get('skills', []))}\n"
        f"Education: {profile.get('education', {}).get('degree', '')} from {profile.get('education', {}).get('school', '')}\n"
        f"Languages: {', '.join(profile.get('languages', []))}\n\n"
        "INSTRUCTIONS:\n"
        "- Write 3-4 paragraphs\n"
        "- Highlight relevant skills and experience that match the job requirements\n"
        "- Be professional but not overly formal\n"
        "- Do NOT make up experience or skills the candidate doesn't have\n"
        "- Output ONLY the cover letter text — no subject line, headers, or metadata\n"
    )

    try:
        from core.llm_factory import create_llm
        from browser_use.llm.messages import UserMessage
        llm = create_llm(llm_settings)
        response = await llm.ainvoke([UserMessage(content=prompt)])
        text = llm_text(response)
        return {"success": True, "cover_letter": text.strip()}
    except Exception as e:
        return api_error("llm_error", f"Cover letter generation failed: {str(e)}", 500)
