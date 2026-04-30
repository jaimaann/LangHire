"""
Post-run memory extraction.

After each agent run (success or failure), extracts procedural learnings
about the website and stores them in the memory system.

Two extraction modes:
  1. Marker-based  — parses @@LEARNING markers the agent proactively emits
  2. LLM-based     — uses Claude to summarise the agent's action history into learnings
"""

import json
import re

from .store import MemoryStore, CATEGORIES


# ── Marker-based extraction ──────────────────────────────────────────────────

def extract_learnings_from_markers(result) -> list[dict]:
    """Extract @@LEARNING markers from agent conversation history.

    The agent is prompted to emit these during its run:
        @@LEARNING: {"domain": "...", "category": "...", "insight": "..."}
    """
    learnings: list[dict] = []
    seen: set[str] = set()

    for item in result.history:
        if not item.model_output:
            continue
        memory = getattr(item.model_output, "memory", "") or ""

        for m in re.finditer(r"@@LEARNING:\s*(\{[^}]{1,2000}\})", memory):
            try:
                learning = json.loads(m.group(1))
                insight = learning.get("insight", "").strip()
                if insight and insight not in seen:
                    seen.add(insight)
                    learnings.append({
                        "domain": learning.get("domain", ""),
                        "category": learning.get("category", "form_strategy"),
                        "content": insight,
                    })
            except json.JSONDecodeError:
                pass

    return learnings


# ── LLM-based extraction ────────────────────────────────────────────────────

def _build_action_summary(result) -> str:
    """Build a condensed summary of the agent's actions from its history."""
    steps: list[str] = []

    for i, item in enumerate(result.history):
        if not item.model_output:
            continue

        parts: list[str] = []

        # Try to get the agent's evaluation of the previous goal
        state = getattr(item.model_output, "current_state", None)
        if state:
            eval_prev = getattr(state, "evaluation_previous_goal", "")
            next_goal = getattr(state, "next_goal", "")
            if eval_prev:
                parts.append(f"eval: {eval_prev[:150]}")
            if next_goal:
                parts.append(f"goal: {next_goal[:150]}")

        # The memory field is always useful
        memory = getattr(item.model_output, "memory", "") or ""
        if memory:
            # Strip our own markers to keep it clean
            clean = re.sub(r"@@\w+:\s*\{[^}]+\}", "", memory).strip()
            if clean:
                parts.append(f"memo: {clean[:200]}")

        # Try to get action descriptions
        actions = getattr(item.model_output, "action", []) or []
        if actions:
            action_descs: list[str] = []
            for act in actions[:3]:  # limit to 3 actions per step
                # browser-use actions have various shapes; grab what we can
                act_str = str(act)[:100]
                action_descs.append(act_str)
            if action_descs:
                parts.append(f"actions: {'; '.join(action_descs)}")

        if parts:
            steps.append(f"Step {i}: {' | '.join(parts)}")

    # Keep last 30 steps to stay within prompt limits
    return "\n".join(steps[-30:])


def extract_learnings_via_llm(
    result,
    job_url: str,
    job_title: str,
    success: bool,
    llm_call=None,
) -> list[dict]:
    """Use an LLM to summarise the agent's run into procedural learnings.

    llm_call: a callable that takes a prompt string and returns a response string.
    Returns a list of dicts with keys: domain, category, content.
    """
    if llm_call is None:
        return []

    actions_text = _build_action_summary(result)
    if not actions_text:
        return []

    domain = MemoryStore.extract_domain(job_url)
    ats = MemoryStore.detect_ats_platform(domain)
    ats_hint = f" (ATS platform: {ats})" if ats else ""
    status_word = "SUCCESSFUL" if success else "FAILED"
    categories_desc = "\n".join(f"- {k}: {v}" for k, v in CATEGORIES.items())

    prompt = f"""Analyze this {status_word} job application attempt on {domain}{ats_hint} for the role "{job_title}".

AGENT ACTIONS LOG:
{actions_text}

MEMORY CATEGORIES:
{categories_desc}

Extract 3-8 SPECIFIC, ACTIONABLE learnings that would help a future agent apply to another job on the SAME website ({domain}).

Focus on:
- Navigation patterns specific to this website (button locations, page flow)
- UI element interactions (checkboxes, dropdowns, modals, scrollable areas)
- Form flow and step sequence (how many steps, what each step contains)
- Common pitfalls or tricks unique to this website
- {"What worked well and the successful path through the application" if success else "What went wrong, what to try differently, and any blockers encountered"}

Rules:
- Each learning must be 1-2 sentences, specific and actionable
- Only include learnings relevant to the WEBSITE ITSELF, not the job content
- Do NOT include generic advice (like "fill in all fields") — only site-specific observations

Return a JSON array of objects, each with:
- "category": one of [{', '.join(CATEGORIES.keys())}]
- "content": the learning (1-2 sentences)

Example:
[
  {{"category": "navigation", "content": "On LinkedIn Easy Apply, the form opens as a modal overlay — don't navigate away from the page."}},
  {{"category": "element_interaction", "content": "The 'Submit application' button requires scrolling down within the modal to become visible."}},
  {{"category": "site_structure", "content": "LinkedIn Easy Apply has 3-5 steps: Contact Info → Resume → Additional Questions → Review → Submit."}}
]

Return ONLY the JSON array."""

    try:
        text = llm_call(prompt)

        # Parse JSON array from response
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            learnings = json.loads(match.group())
            return [
                {
                    "domain": domain,
                    "category": l.get("category", "form_strategy"),
                    "content": l.get("content", ""),
                }
                for l in learnings
                if isinstance(l, dict) and l.get("content", "").strip()
            ]
    except Exception as e:
        print(f"    ⚠️  Memory extraction LLM call failed: {e}")

    return []


# ── Storage helper ───────────────────────────────────────────────────────────

def store_learnings(
    store: MemoryStore,
    learnings: list[dict],
    job_url: str,
    success: bool,
) -> tuple[int, int]:
    """Store extracted learnings in the memory store.

    Returns (new_count, reinforced_count).
    """
    domain = store.extract_domain(job_url)
    new_count = 0
    reinforced_count = 0

    for learning in learnings:
        is_new = store.add(
            content=learning["content"],
            website_domain=learning.get("domain", domain),
            category=learning.get("category", "form_strategy"),
            success=success,
            confidence=0.85 if success else 0.5,
            job_url=job_url,
        )
        if is_new:
            new_count += 1
        else:
            reinforced_count += 1

    if new_count > 0:
        print(f"    🧠 Stored {new_count} new memories for {domain}")
    if reinforced_count > 0:
        print(f"    🧠 Reinforced {reinforced_count} existing memories for {domain}")

    return new_count, reinforced_count
