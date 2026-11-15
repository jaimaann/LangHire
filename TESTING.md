# Testing Guide

LangHire has two test suites — a **Python/pytest** suite for the FastAPI backend and a
**Vitest + React Testing Library** suite for the React frontend. Both produce coverage reports
and run in CI (`.github/workflows/test.yml`) on every push/PR across macOS, Linux, and Windows.

## Quick start

```bash
# Frontend (Vitest)
npm test                 # run once
npm run test:watch       # watch mode
npm run test:coverage    # with coverage report (./coverage)
npm run typecheck        # tsc project build (app + node + test projects)

# Backend (pytest) — run via uv
uv run pytest                                   # run all backend tests
uv run pytest --cov --cov-report=term-missing   # with coverage
uv run pytest tests/backend/core -v             # a subset
```

## Layout

```
tests/                          # backend pytest suite
  conftest.py                   # sys.path setup + `data_dir` fixture (isolated tmp HOME)
  backend/
    core/      test_config.py, test_country_config.py, test_llm_factory.py,
               test_shared_config.py, test_agent_logger.py
    memory/    test_store.py, test_extractors.py, test_metrics.py
    resume/    test_tailor.py
    sources/   test_registry.py
    test_models.py, test_main_api.py

src/**/*.test.{ts,tsx}          # frontend tests, co-located with the code they cover
src/test/setup.ts               # global Vitest setup (mocks Tauri, jest-dom matchers)
```

## Conventions

### Backend (pytest)
- Configuration lives in `pyproject.toml` (`[tool.pytest.ini_options]`, `[tool.coverage.*]`).
- `asyncio_mode = "auto"` — `async def test_*` functions run without extra decorators.
- The **`data_dir` fixture** (in `tests/conftest.py`) redirects the OS app-data directory into a
  per-test temp `HOME`, so tests never touch your real `~/.config/langhire`. Use it for anything
  that reads/writes settings, profile, jobs, or the memory DB.
- **No network, no AWS, no real browser.** External calls (LLMs, boto3, subprocess, Playwright)
  are mocked with `unittest.mock` / `monkeypatch`.

### Frontend (Vitest)
- Configuration lives in the `test` block of `vite.config.ts` (jsdom env, globals, v8 coverage).
- `src/test/setup.ts` mocks `@tauri-apps/api/core` (`invoke`) and `@tauri-apps/plugin-dialog`,
  registers `@testing-library/jest-dom` matchers, and cleans up the DOM + mocks after each test.
- Tests mock `../lib/api`, `react-i18next`, `../lib/analytics`, and `fetch` — **no real network
  or Tauri runtime** is used.
- Test files are type-checked under `tsconfig.test.json` (with `vitest/globals` + jest-dom types)
  and excluded from the production build (`tsconfig.app.json`).

## Coverage status

Backend business-logic modules (`core`, `memory`, `resume`, `sources`, `models`) sit at
**86–100%**. The FastAPI entrypoint `backend/main.py` is partially covered by `test_main_api.py`;
its browser/subprocess/worker endpoints are exercised by the end-to-end harness
`scripts/integration-test.py` instead. Frontend statement coverage is **~90%**.

Run the coverage commands above to see the current per-module breakdown.

## Real-browser and end-to-end tests

**Mock ATS.** `tests/fixtures/ats/server.py` serves job postings and application
forms shaped like Greenhouse, Lever, a two-step form and a form with a required
sensitive question. It records each submission as JSON and includes
prompt-injection bait in the job description. No application ever reaches a real
employer.

```bash
# ATS fast-path checks against the mock ATS in a real Chromium (no LLM)
LANGHIRE_BROWSER_TESTS=1 uv run pytest tests/integration -q

# Full flow with a real LLM: resume parsing, cover letter, tailoring, applications,
# needs-input handling, parallel workers, daily cap, export and delete
LANGHIRE_E2E_BASE_URL=https://api.example.com/v1 LANGHIRE_E2E_MODEL=<vision model> \
LANGHIRE_E2E_API_KEY=... uv run python scripts/e2e-flow.py \
  --resume path/to/resume.pdf --out e2e-report.json
```

`scripts/make-sample-resume.py` writes a fictional one-page resume. The nightly
`.github/workflows/canary.yml` runs the same flow (enable with `CANARY_ENABLED`).

**UI in a normal browser.** Start a backend by hand and point the dev server at it:

```bash
LANGHIRE_DATA_DIR=/tmp/lh LANGHIRE_PORT=18800 LANGHIRE_API_TOKEN=devtoken \
  uv run python backend/main.py
VITE_DEV_BACKEND_TOKEN=devtoken VITE_DEV_BACKEND_PORT=18800 npx vite --port 1420
```

The override is ignored in production builds. Use `LANGHIRE_DATA_DIR` for any
manual testing so your real data in the OS app-data folder is never touched.
