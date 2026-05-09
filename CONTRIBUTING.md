# 🤝 Contributing to LangHire

Thank you for your interest in contributing! This guide will help you get set up and make your first contribution.

---

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Environment](#development-environment)
- [Project Architecture](#project-architecture)
- [Making Changes](#making-changes)
- [Pull Request Process](#pull-request-process)
- [Style Guide](#style-guide)
- [Common Tasks](#common-tasks)

---

## Code of Conduct

This project follows a standard code of conduct. Be respectful, inclusive, and constructive in all interactions.

---

## Getting Started

### Prerequisites

Make sure you have these installed:

| Tool | Version | Check | Install |
|------|---------|-------|---------|
| **Node.js** | 18+ | `node --version` | [nodejs.org](https://nodejs.org) |
| **npm** | 9+ | `npm --version` | Comes with Node.js |
| **Rust** | 1.77+ | `rustc --version` | [rustup.rs](https://rustup.rs) |
| **Python** | 3.13+ | `python3 --version` | [python.org](https://python.org) |
| **uv** | latest | `uv --version` | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| **Git** | 2+ | `git --version` | [git-scm.com](https://git-scm.com) |

### Fork & Clone

```bash
# 1. Fork the repo on GitHub (click "Fork" button)

# 2. Clone your fork
git clone https://github.com/YOUR_USERNAME/langhire.git
cd langhire

# 3. Add upstream remote
git remote add upstream https://github.com/ORIGINAL_OWNER/langhire.git
```

### Install Dependencies

```bash
# Install Node.js dependencies (frontend + Tauri)
npm install

# Install Python dependencies (backend + automation)
uv sync

# Install Playwright browser for automation
uv run python -m playwright install chromium
```

### Verify Setup

```bash
# Start the backend (Terminal 1)
uv run python backend/main.py
# Should print: "Starting backend on port 8742"

# Start the frontend (Terminal 2)
npm run dev
# Should print: "VITE ready" and open http://localhost:1420

# Verify backend health
curl http://127.0.0.1:8742/health
# Should return: {"status":"ok","version":"1.0.0"}
```

---

## Development Environment

### Two-Terminal Workflow

For day-to-day development, run both processes:

```bash
# Terminal 1: Python backend (auto-reloads on save)
uv run python backend/main.py

# Terminal 2: Vite dev server (HMR, instant reload)
npm run dev
```

### Native Desktop App

To test as a native desktop app:

```bash
# This compiles the Rust shell + starts Vite + opens native window
cargo tauri dev
```

> ⚠️ First run takes ~2 minutes to compile Rust. Subsequent runs are fast.

### Directory Overview

| Directory | Language | Purpose |
|-----------|----------|---------|
| `src/` | TypeScript/React | Frontend UI components |
| `backend/` | Python | FastAPI REST API server |
| `src-tauri/` | Rust | Tauri native shell |
| `memory/` | Python | Agent memory system |
| `*.py` (root) | Python | CLI automation scripts |

---

## Project Architecture

```
User → React UI → HTTP API → Python Backend → {
  • FastAPI endpoints (profile, settings, jobs, memory)
  • browser-use AI agents (Playwright + LLM)
  • SQLite memory store
  • JSON file storage
}
```

### Key Design Decisions

1. **Tauri v2** for the desktop shell — uses OS WebView, ~10MB vs Electron's ~200MB
2. **Python sidecar** — the automation engine (browser-use, Playwright) must stay in Python
3. **FastAPI** — lightweight HTTP server for frontend ↔ backend communication
4. **Direct LangChain providers** — `langchain-openai`, `langchain-anthropic`, `langchain-aws` (no LiteLLM)
5. **OS app data directory** — all user data stored in platform-appropriate location
6. **No hardcoded values** — all config loaded from user settings files

---

## Making Changes

### Create a Branch

```bash
# Sync with upstream
git fetch upstream
git checkout main
git merge upstream/main

# Create a feature branch
git checkout -b feature/your-feature-name
```

### Branch Naming Convention

| Prefix | Use |
|--------|-----|
| `feature/` | New features (e.g., `feature/google-gemini-support`) |
| `fix/` | Bug fixes (e.g., `fix/memory-search-crash`) |
| `docs/` | Documentation (e.g., `docs/setup-tutorial`) |
| `ui/` | UI/UX changes (e.g., `ui/dark-mode`) |
| `refactor/` | Code refactoring (e.g., `refactor/api-client`) |

### Where to Make Changes

| I want to... | Files to edit |
|--------------|---------------|
| Add a new UI page | `src/pages/NewPage.tsx` + `src/App.tsx` (route) + `src/components/layout/Sidebar.tsx` (nav) |
| Add a backend endpoint | `backend/main.py` + `src/lib/api.ts` (client function) |
| Add an LLM provider | `backend/core/llm_factory.py` + `src/pages/LLMSettings.tsx` |
| Add an ATS platform | `memory/store.py` (`ATS_DOMAINS` + `DOMAIN_NORMALIZATION`) |
| Add a memory category | `memory/store.py` (`CATEGORIES` dict) |
| Change app styling | `src/index.css` (Tailwind theme vars) |

---

## Pull Request Process

### Before Submitting

1. **Test your changes** — make sure the app loads and your feature works
2. **Run the frontend** — `npm run dev` → verify no console errors
3. **Run the backend** — `uv run python backend/main.py` → verify endpoints work
4. **Check TypeScript** — `npx tsc --noEmit` (no type errors)
5. **Update docs** if your change affects the README or user-facing behavior

### Submitting a PR

1. Push your branch to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```

2. Open a PR on GitHub against the `main` branch

3. Fill in the PR template:
   - **What** — What does this PR do?
   - **Why** — Why is this change needed?
   - **How** — How did you implement it?
   - **Testing** — How did you test it?
   - **Screenshots** — Include UI screenshots if applicable

### PR Review

- PRs need at least 1 approval before merging
- Address all review comments
- Keep PRs focused — one feature/fix per PR
- Rebase on `main` if there are conflicts

---

## Style Guide

### TypeScript / React

- **Functional components** with hooks (no class components)
- **Tailwind CSS** for all styling (no CSS modules or styled-components)
- **Named exports** for page components, **default exports** for main components
- File names: `PascalCase.tsx` for components, `camelCase.ts` for utilities

### Python

- **Type hints** on all function signatures
- **Docstrings** for public functions
- **f-strings** for string formatting
- Emoji prefixes for log messages: 🚀 🔑 ✅ ❌ ⚠️ 🧠 💾 📋
- Timestamps always UTC ISO format

### Git Commits

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add Google Gemini LLM support
fix: memory search crash on empty query
docs: add video walkthrough link to README
ui: improve dark mode color contrast
refactor: extract tag input into reusable component
```

---

## Common Tasks

### Adding a New LLM Provider

1. **Backend** — Add to `backend/core/llm_factory.py`:
   ```python
   elif provider == "your_provider":
       from langchain_yourprovider import ChatYourProvider
       cfg = settings.get("your_provider", {})
       return ChatYourProvider(model=cfg.get("model"), api_key=cfg.get("api_key"))
   ```

2. **Frontend types** — Update `src/lib/types.ts`:
   ```typescript
   export type LLMProvider = "openai" | "anthropic" | "bedrock" | "your_provider";
   ```

3. **Frontend UI** — Update `src/pages/LLMSettings.tsx`:
   - Add to `PROVIDERS` array
   - Add model list
   - Add provider-specific form fields

### Adding a New Page

1. Create `src/pages/YourPage.tsx`
2. Add route in `src/App.tsx`
3. Add nav item in `src/components/layout/Sidebar.tsx`
4. Add any needed API functions in `src/lib/api.ts`
5. Add backend endpoint in `backend/main.py` if needed

### Adding a New ATS Platform

1. Add domain pattern to `ATS_DOMAINS` in `backend/memory/store.py`
2. Add normalization rule to `DOMAIN_NORMALIZATION` in `backend/memory/store.py`
3. Test with `uv run python -c "from memory.store import MemoryStore; print(MemoryStore.extract_domain('https://example.yourplatform.com/job/123'))"`

### Creating a Job Source Plugin

LangHire uses a YAML-based plugin system for job sources. Each plugin tells the AI browser agent how to search for jobs and how to apply on a specific website. No code execution — plugins are pure data files, safe to share with anyone.

#### Plugin File Structure

Create a `.yaml` file with this format:

```yaml
# my-job-site.yaml
name: my-job-site                    # Unique slug (lowercase, hyphens)
display_name: My Job Site            # Display name in the UI
version: "1.0.0"                     # Semver
author: your-github-username         # Your name or handle
description: "Short description of what this job site is"
countries: [US, GB]                  # ISO country codes where this site is relevant (or [ALL] for global)
website: https://www.myjobsite.com   # Platform homepage
requires_login: true                 # Whether the user needs to log in first
login_url: https://www.myjobsite.com/login  # URL to open for manual login

# Cookies that prove the user is logged in
auth_cookies:
  - name: session_id
    domain: .myjobsite.com

# URL template for searching jobs (uses {title} and {location} placeholders)
search_url: "https://www.myjobsite.com/jobs?q={title}&location={location}"

# Prompt that tells the AI agent how to COLLECT jobs from this site
collection_prompt: |
  FIRST — LOGIN CHECK:
  1. Go to https://www.myjobsite.com/account to check if you're logged in.
     - If you see your account page → logged in
     - If you see a login page → WAIT for user to log in manually. Check every 15 seconds. Wait up to 5 minutes.

  THEN: Navigate to:
  {search_url}

  HOW TO COLLECT JOBS:
  1. You will see a list of job cards on the page.
  2. For each job card, extract: title, company, location, URL.
  3. Check if the job has a "Quick Apply" button (easy_apply: true) or redirects externally (easy_apply: false).
  4. Output a @@JOB_FOUND marker for each job in your MEMORY field.
  5. Navigate to the next page of results.
  6. Stop after collecting {max_jobs} jobs.

  IMPORTANT RULES:
  - Output ONE @@JOB_FOUND marker per job.
  - Do NOT apply to any jobs — only collect listings.
  - Stop after {max_jobs} jobs and call done.

  @@JOB_FOUND format:
  @@JOB_FOUND: {{"title": "<title>", "company": "<company>", "location": "<location>", "url": "<url>", "easy_apply": true/false}}

# Prompt that tells the AI agent how to APPLY to a job on this site
apply_prompt: |
  Go to {job_url}

  Click the Apply button and complete the application form.
  Fill all fields using the candidate profile data.
  Upload resume at {resume_path} when prompted.
  Answer screening questions using the Q&A bank.
  If a cover letter is requested: {cover_letter}
  Submit the application.

  If the form is broken after 3 attempts, report failure and stop.

# Optional: domain normalization patterns for the memory system
domain_patterns:
  - pattern: "*.myjobsite.com"
    normalize_to: "myjobsite.com"
```

#### Template Variables

Your prompts can use these placeholders that get filled at runtime:

**Collection prompt:**
| Variable | Description |
|----------|-------------|
| `{search_url}` | Built from your `search_url` template with title/location filled in |
| `{title}` | The job title being searched |
| `{titles}` | All target titles (comma-separated) |
| `{location}` | Target location |
| `{locations}` | All target locations (comma-separated) |
| `{max_jobs}` | Maximum jobs to collect |

**Apply prompt:**
| Variable | Description |
|----------|-------------|
| `{job_url}` | URL of the job to apply to |
| `{job_title}` | Job title |
| `{company}` | Company name |
| `{profile}` | Formatted candidate profile text |
| `{resume_path}` | Path to the user's resume PDF |
| `{qa_bank}` | Relevant Q&A pairs for screening questions |
| `{cover_letter}` | User's cover letter (if they have one) |
| `{memories}` | Previously learned memories for this domain |

#### Writing Good Prompts

The AI agent (powered by an LLM + Playwright browser) will follow your prompts to navigate the website. Tips:

1. **Be specific about UI elements** — "Click the blue 'Apply Now' button in the top-right" is better than "Apply"
2. **Describe the page layout** — "Job cards are listed on the left, details on the right"
3. **Handle edge cases** — "If a CAPTCHA appears, wait 10 seconds and retry"
4. **Include login checks** — Always verify the user is logged in before proceeding
5. **Use the @@JOB_FOUND format exactly** — The backend parses these markers to save jobs
6. **Test your prompts** — Try the collection flow manually and note each step

#### Installing Your Plugin

**For personal use:**
1. Open LangHire → Settings → Plugins section
2. Click "Import Plugin"
3. Select your `.yaml` file
4. The plugin appears in the job source dropdown for matching countries

**Or manually:** Copy your `.yaml` file to `~/.langhire/plugins/` (macOS: `~/Library/Application Support/langhire/plugins/`)

#### Sharing with the Community

1. Test your plugin works end-to-end (collect + apply)
2. Submit a PR adding your `.yaml` file to `backend/sources/plugins/`
3. Add the site's domain to `backend/memory/store.py` (`ATS_DOMAINS` and `DOMAIN_NORMALIZATION`)
4. Add the platform to the relevant country's `default_sources` in `backend/core/country_config.py`

#### Reference: Built-in Plugins

See these files for real-world examples:
- `backend/sources/plugins/linkedin.yaml` — Global, Easy Apply + external
- `backend/sources/plugins/indeed.yaml` — Global, Indeed Apply
- `backend/sources/plugins/seek.yaml` — Australia/NZ, Quick Apply
- `backend/sources/plugins/naukri.yaml` — India, handles CAPTCHAs
- `backend/sources/plugins/reed.yaml` — UK, direct application forms
- `backend/sources/plugins/stepstone.yaml` — Germany, German-language forms

---

## 🙋 Questions?

- Open a [Discussion](../../discussions) for questions
- Open an [Issue](../../issues) for bugs or feature requests
- Tag `@maintainers` in your PR if you need help

Thank you for contributing! 🎉
