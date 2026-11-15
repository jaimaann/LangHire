"""Deterministic job collection for boards whose result cards are in the DOM.

The agent used to click every job card and read the job id from the URL bar:
one model call (30-60 s) per job, so 20 jobs took about an hour, and it often
stalled on sign-in modals. LinkedIn's result list (guest and signed-in) already
contains each card's link, title, company and location, so one script reads
them all; the page is scrolled and "See more jobs" clicked until enough are
found. The LLM agent remains the fallback for anything this can't read.
"""
from __future__ import annotations

import asyncio
import json
import logging

_log = logging.getLogger("engine")

LINKEDIN_CARDS_JS = r"""() => {
  const cards = document.querySelectorAll(
    'ul.jobs-search__results-list li, div.base-card, li.jobs-search-results__list-item, div.job-card-container, li[data-occludable-job-id]');
  const out = [], seen = new Set();
  const txt = el => el ? el.innerText.replace(/\s+/g, ' ').trim() : '';
  for (const c of cards) {
    const a = c.querySelector('a.base-card__full-link, a.job-card-list__title, a.job-card-container__link, a[href*="/jobs/view/"]');
    if (!a || !a.href || seen.has(a.href)) continue;
    seen.add(a.href);
    out.push({
      url: a.href,
      title: txt(c.querySelector('.base-search-card__title, .job-card-list__title, .artdeco-entity-lockup__title, strong')) || txt(a),
      company: txt(c.querySelector('.base-search-card__subtitle, .job-card-container__primary-description, .artdeco-entity-lockup__subtitle')),
      location: txt(c.querySelector('.job-search-card__location, .job-card-container__metadata-item, .artdeco-entity-lockup__caption')),
      easy_apply: /easy apply/i.test(c.innerText || ''),
    });
  }
  return JSON.stringify(out);
}"""

LINKEDIN_MORE_JS = r"""() => {
  for (const sel of ['button.modal__dismiss', 'button[aria-label="Dismiss"]', 'button.contextual-sign-in-modal__modal-dismiss']) {
    const b = document.querySelector(sel); if (b && b.offsetParent !== null) b.click();
  }
  const list = document.querySelector('.jobs-search-results-list, .scaffold-layout__list > div');
  if (list) list.scrollTop = list.scrollHeight;
  window.scrollTo(0, document.body.scrollHeight);
  const more = document.querySelector('button.infinite-scroller__show-more-button, button[aria-label="See more jobs"]');
  if (more && !more.disabled && more.offsetParent !== null) { more.click(); return 'more'; }
  return 'scrolled';
}"""

SUPPORTED = {"linkedin"}


async def collect_cards(browser_session, search_url: str, want: int, max_rounds: int = 12) -> list[dict]:
    """Open the search URL and read job cards until `want` are found (0 = one page)."""
    await browser_session.start()
    page = await browser_session.get_current_page()
    if page is None:
        page = await browser_session.new_page(search_url)
    else:
        await page.goto(search_url)
    await asyncio.sleep(4)
    jobs: dict[str, dict] = {}
    stale = 0
    for _ in range(max_rounds):
        try:
            raw = await page.evaluate(LINKEDIN_CARDS_JS)
            for j in json.loads(raw or "[]"):
                jobs.setdefault(j["url"], j)
        except Exception as e:
            _log.info(f"fast collect: card read failed: {e}")
        if want and len(jobs) >= want:
            break
        before = len(jobs)
        try:
            await page.evaluate(LINKEDIN_MORE_JS)
        except Exception:
            pass
        await asyncio.sleep(3)
        stale = stale + 1 if len(jobs) == before else 0
        if not want or stale >= 3:
            if not want:
                raw = await page.evaluate(LINKEDIN_CARDS_JS)
                for j in json.loads(raw or "[]"):
                    jobs.setdefault(j["url"], j)
            break
    return list(jobs.values())
