"""The desktop app's UI end to end: the production bundle (dist/) against the real backend.

Playwright drives the same pages a user clicks through, with the Tauri host
replaced by a stub that hands over the backend's port and token. The agent's
"model" is the scripted LLM, and the employer is the mock ATS.
"""
from __future__ import annotations

import re

from playwright.sync_api import Page, expect

ROUTES = ["#/", "#/analytics", "#/guide", "#/profile", "#/llm", "#/jobs", "#/memory", "#/qa",
          "#/logs", "#/settings", "#/feedback"]


def _go(page: Page, route: str) -> None:
    page.goto(page.url.split("#")[0] + route)


def _enable_test_mode(backend) -> None:
    s = backend.call("GET", "/settings")
    s["test_mode"] = True
    backend.call("PUT", "/settings", s)


def _add_job_in_ui(page: Page, url: str) -> None:
    _go(page, "#/jobs")
    page.get_by_role("button", name="Add Job").first.click()
    page.get_by_placeholder("Job URL (required)").fill(url)
    page.locator("form").get_by_role("button", name="Add Job").click()
    expect(page.get_by_placeholder("Job URL (required)")).to_have_count(0, timeout=30_000)


def _apply_in_ui(page: Page, title: str) -> None:
    page.get_by_role("button", name=re.compile("Review & Apply")).click()
    apply = page.get_by_role("button", name="Apply", exact=True)
    card = page.locator("div").filter(has=page.locator("h4", has_text=title)).filter(has=apply).last
    expect(card).to_be_visible(timeout=30_000)
    card.get_by_role("button", name="Apply", exact=True).click()
    # the app explains what automation will do before it starts
    page.get_by_role("dialog").get_by_role("button", name="Got it, start").click()


def test_every_page_renders_without_errors(page: Page):
    expect(page.locator("aside nav a").first).to_be_visible(timeout=30_000)
    for route in ROUTES:
        _go(page, route)
        page.wait_for_timeout(1200)
        body = page.inner_text("body")
        assert "Something went wrong" not in body, route
        assert page.inner_text("main").strip(), f"{route} rendered an empty page"
    assert page.errors == [], page.errors


def test_add_apply_in_test_mode_watch_progress_and_open_the_record(page: Page, backend, ats):
    _enable_test_mode(backend)
    _add_job_in_ui(page, f"{ats['base']}/jobs/gh-1")
    _apply_in_ui(page, "Data Analyst")

    # live progress: the per-job timeline shows the agent's current goal
    expect(page.get_by_test_id("apply-progress")).to_be_visible(timeout=30_000)
    expect(page.get_by_test_id("apply-timeline")).to_contain_text("Data Analyst", timeout=60_000)
    expect(page.get_by_test_id("apply-progress")).to_have_count(0, timeout=300_000)

    page.get_by_role("button", name=re.compile("History")).click()
    row = page.locator("div", has=page.get_by_text("Data Analyst", exact=False)).filter(
        has=page.get_by_test_id("status-badge-test_passed")).last
    expect(row).to_be_visible(timeout=30_000)
    row.get_by_role("button", name=re.compile("Details")).first.click()
    dialog = page.get_by_role("dialog")
    expect(dialog).to_contain_text("Tokens:", timeout=15_000)
    expect(dialog).to_contain_text("scripted-agent")
    assert not list(ats["submissions"].glob("gh-1-*.json")), "test mode sent the application"


def test_needs_input_badge_answer_in_qa_requeues_the_job(page: Page, backend, ats):
    _enable_test_mode(backend)
    _add_job_in_ui(page, f"{ats['base']}/jobs/ni-1")
    _apply_in_ui(page, "Junior Data Analyst")
    expect(page.get_by_test_id("apply-progress")).to_be_visible(timeout=30_000)
    expect(page.get_by_test_id("apply-progress")).to_have_count(0, timeout=300_000)

    badge = page.get_by_test_id("nav-badge-qa")
    expect(badge).to_have_text("2", timeout=60_000)  # the sidebar refreshes on its 15 s health poll
    expect(page.get_by_test_id("nav-badge-jobs")).to_have_text("1")

    _go(page, "#/qa")
    felony = page.locator("div.card", has_text="convicted of a felony")
    salary = page.locator("div.card", has_text="current base salary")
    felony.locator("textarea").fill("No")
    page.wait_for_timeout(1500)  # answers autosave after a short pause
    salary.locator("textarea").fill("USD 70,000")
    expect(page.get_by_text(re.compile("went back to the queue"))).to_be_visible(timeout=15_000)

    jobs = backend.call("GET", "/jobs")
    assert any(j["url"].endswith("/jobs/ni-1") and j["status"] == "pending" for j in jobs)
