"""Custom agent actions that give the engine structured results.

Before this, the agent reported outcomes by writing ``@@JOB_APPLIED: {...}``
into its free-text memory and the engine regex-parsed it; a model that forgot
the marker made a submitted application look failed. Now the agent calls real
tools whose arguments are validated by pydantic:

* ``report_application_result`` — submitted / failed / needs_input / skipped
* ``record_form_answer``        — every answer it typed, with source + confidence
* ``record_site_learning``      — procedural knowledge about the site / ATS
* ``record_job_listing``        — one job found during collection
* ``prefill_standard_fields``   — deterministic fill of known ATS fields (fast path)

Marker parsing stays as a fallback for older prompts and community plugins.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal, Optional

from pydantic import BaseModel, Field

from . import events


class ApplicationResult(BaseModel):
    outcome: Literal["submitted", "failed", "needs_input", "skipped", "ready_to_submit"] = Field(
        description="submitted = the application was sent and a confirmation was seen; "
                    "needs_input = a required question could not be answered from the profile or Q&A bank; "
                    "skipped = not a real application (video funnel, expired posting, blocked site); "
                    "ready_to_submit = TEST MODE only: the form passed validation and the request was intercepted; "
                    "failed = anything else")
    reason: str = Field(default="", description="One sentence explaining the outcome")
    confirmation_text: str = Field(default="", description="Text of the confirmation message, if any")
    missing_info: list[str] = Field(default_factory=list,
                                    description="Exact questions that need the candidate's answer (for needs_input)")


class FormAnswer(BaseModel):
    question: str = Field(description="The form question or field label, verbatim")
    answer: str = Field(description="What was entered or selected")
    field_type: Literal["text", "dropdown", "radio", "checkbox", "file", "date", "other"] = "text"
    source: Literal["profile", "qa_bank", "resume", "job_description", "inferred"] = Field(
        description="Where the answer came from. 'inferred' means you had to guess.")
    confidence: float = Field(default=1.0, ge=0, le=1)


class SiteLearning(BaseModel):
    category: Literal["navigation", "form_strategy", "element_interaction",
                      "failure_recovery", "site_structure", "qa_pattern"]
    insight: str = Field(description="A specific, reusable observation about this site's UI or flow")


class JobListing(BaseModel):
    title: str
    company: str
    location: str = ""
    url: str = Field(description="Full canonical URL of the job posting")
    easy_apply: Optional[bool] = Field(default=None, description="True if the board's own quick-apply flow is offered")


@dataclass
class AgentReport:
    """Everything the agent reported through tools during one agent run."""
    result: ApplicationResult | None = None
    answers: list[dict] = field(default_factory=list)
    learnings: list[dict] = field(default_factory=list)
    jobs: list[dict] = field(default_factory=list)
    prefilled: list[str] = field(default_factory=list)
    missing_from_text: list[str] = field(default_factory=list)  # parsed when the tool was not called
    submit_clicks: int = 0   # test mode: clicks on a final-submit control
    intercepted: int = 0     # test mode: application requests blocked by the guard


def build_apply_tools(report: AgentReport, profile: dict, resume_path: str = ""):
    """Tools for an application agent; results land in `report`."""
    from browser_use import Tools
    from browser_use.agent.views import ActionResult

    tools: Tools = Tools()

    @tools.action(
        "Call this ONCE when the application is finished or cannot continue, before calling done. "
        "Use outcome=submitted only after you saw a confirmation that the application was sent.",
        param_model=ApplicationResult,
    )
    async def report_application_result(params: ApplicationResult):
        report.result = params
        events.emit("job_result", f"Agent reported: {params.outcome} — {params.reason}"[:300],
                    outcome=params.outcome)
        return ActionResult(extracted_content=f"Recorded outcome: {params.outcome}. Now call done.",
                            long_term_memory=f"Reported outcome {params.outcome}")

    @tools.action(
        "Record a form answer right after you fill a question (not for name/email/phone).",
        param_model=FormAnswer,
    )
    async def record_form_answer(params: FormAnswer):
        report.answers.append(params.model_dump())
        level = "warning" if params.source == "inferred" or params.confidence < 0.6 else "info"
        events.emit("field_filled", f"✍️ {params.question[:80]} → {params.answer[:60]}", level,
                    source=params.source, confidence=params.confidence)
        return ActionResult(extracted_content="Answer recorded")

    @tools.action(
        "Record a reusable observation about how this website or applicant tracking system works.",
        param_model=SiteLearning,
    )
    async def record_site_learning(params: SiteLearning):
        report.learnings.append(params.model_dump())
        return ActionResult(extracted_content="Learning recorded")

    @tools.action(
        "Fill the standard contact fields (name, email, phone, links) of a known applicant tracking system "
        "form in one step. Call this as soon as the application form is visible; then fill the rest yourself.",
    )
    async def prefill_standard_fields(browser_session):
        from .ats_fastpath import prefill_page
        filled = await prefill_page(browser_session, profile)
        report.prefilled.extend(filled)
        if not filled:
            return ActionResult(extracted_content="No known ATS fields found on this page; fill the form normally.")
        events.emit("field_filled", f"⚡ Prefilled {len(filled)} standard field(s): {', '.join(filled)}",
                    fast_path=True)
        return ActionResult(extracted_content=f"Prefilled: {', '.join(filled)}. Check them, then continue "
                                              f"with upload_resume and the remaining questions.")

    @tools.action(
        "Attach the candidate's resume to the form's Resume/CV field. Works for hidden inputs, styled "
        "'Attach' buttons and forms inside embedded frames. Use this instead of upload_file, and never type "
        "a file path into a field.",
    )
    async def upload_resume(browser_session):
        from .upload import upload_resume_any_frame
        try:
            msg = await upload_resume_any_frame(browser_session, resume_path)
        except Exception as e:
            msg = f"Resume upload failed: {e}. Try upload_file on the resume field instead."
        events.emit("field_filled", f"📎 {msg}"[:200])
        return ActionResult(extracted_content=msg, long_term_memory=msg[:200])

    _guard_file_inputs(tools)
    return tools


def _guard_file_inputs(tools) -> None:
    """Typing a path into <input type=file> breaks React upload widgets; send the agent to upload_resume."""
    from browser_use.agent.views import ActionResult

    action = tools.registry.registry.actions.get("input")
    if action is None:
        return
    original = action.function

    async def guarded_input(*args, **kwargs):
        params = kwargs.get("params") or (args[0] if args else None)
        session = kwargs.get("browser_session")
        index = getattr(params, "index", None)
        try:
            node = await session.get_element_by_index(index) if session and index is not None else None
        except Exception:
            node = None
        attrs = (getattr(node, "attributes", None) or {}) if node is not None else {}
        is_file = (node is not None and str(getattr(node, "tag_name", "")).lower() == "input"
                   and str(attrs.get("type", "")).lower() == "file")
        if is_file:
            msg = "That is a file field: do not type into it. Call upload_resume to attach the resume."
            return ActionResult(error=msg, long_term_memory=msg)
        text = getattr(params, "text", None)
        clean = strip_leaked_json(text) if isinstance(text, str) else text
        if clean != text:
            try:
                params.text = clean
            except Exception:
                pass
            result = await original(*args, **kwargs)
            note = "Removed stray action JSON from the typed text; send one action's arguments per field."
            if isinstance(result, ActionResult):
                result.extracted_content = ((result.extracted_content or "") + " " + note).strip()
            return result
        return await original(*args, **kwargs)

    action.function = guarded_input


# Some models leak the next tool call into a text argument: "1}}, {" or '... "}, {"click": ...'.
_LEAKED_JSON = re.compile(r'\s*(?:\}\}|\}\s*,\s*\{|"\s*\}\s*[,\]]|\{\s*"[a-z_]+"\s*:\s*[\[{"\d]).*\Z', re.DOTALL)


def strip_leaked_json(text: str) -> str:
    """Cut a text value at the first tool-call fragment. Form answers never contain these."""
    m = _LEAKED_JSON.search(text)
    if not m or m.start() == 0:
        return text
    return text[: m.start()].rstrip()


def build_collect_tools(report: AgentReport):
    from browser_use import Tools
    from browser_use.agent.views import ActionResult

    tools: Tools = Tools()

    @tools.action("Record ONE job listing you found. Call it once per job.", param_model=JobListing)
    async def record_job_listing(params: JobListing):
        report.jobs.append(params.model_dump())
        return ActionResult(extracted_content=f"Recorded job {len(report.jobs)}: {params.title} at {params.company}")

    return tools
