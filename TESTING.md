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
