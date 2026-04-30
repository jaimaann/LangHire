<p align="center">
 <img src="https://img.shields.io/badge/Platform-macOS%20%7C%20Windows%20%7C%20Linux-blue" alt="Platform" />
 <img src="https://img.shields.io/badge/UI-Tauri%20v2%20%2B%20React-purple" alt="UI" />
 <img src="https://img.shields.io/badge/Backend-Python%20%2B%20FastAPI-green" alt="Backend" />
 <img src="https://img.shields.io/badge/AI-OpenAI%20%7C%20Claude%20%7C%20Bedrock-orange" alt="AI" />
 <img src="https://img.shields.io/badge/License-MIT-lightgrey" alt="License" />
</p>

# ‍ LangHire

**AI-powered automated job application system with a native desktop UI.**

LangHire uses AI browser agents to automatically search LinkedIn for jobs, fill out applications, and submit them — all from a beautiful cross-platform desktop app. It features a self-learning memory system that gets better at each website over time.

> ** Non-technical users**: Download the pre-built binary for your OS from [Releases](../../releases). No coding required!
>
> ** Developers**: See [Contributing](#-contributing) for setup instructions.

---

## Features

### Native Desktop App
- Runs on **macOS**, **Windows**, and **Linux** as a native app (not a browser tab)
- Built with Tauri v2 — lightweight ~10MB shell using OS WebView
- No server setup required — everything runs locally on your machine

### AI-Powered Automation
- **Job Collection** — Searches LinkedIn for jobs matching your profile
- **Automated Applications** — AI agent fills forms, uploads resume, answers questions
- **Tailored Resumes** — Auto-customizes your resume per job description
- **Smart Q&A** — Learns answers from previous applications and reuses them

### Self-Learning Memory System
- Stores per-website procedural knowledge (navigation patterns, form strategies, UI quirks)
- Memories from one Workday site help on ALL Workday sites (ATS domain normalization)
- Confidence-based retrieval — high-confidence memories are prioritized
- Memory decay + cleanup for maintenance

### Multi-LLM Support
| Provider | Models | Auth |
|----------|--------|------|
| **OpenAI** | GPT-4o, GPT-4o-mini, GPT-4-turbo | API Key |
| **Anthropic** | Claude Sonnet, Haiku, Opus | API Key |
| **AWS Bedrock** | Claude via Bedrock | Access Key + Secret |

### Dashboard & Analytics
- Real-time job stats (collected, applied, failed, pending)
- Success rate tracking
- Per-domain performance breakdown
- Memory system impact analysis (A/B comparison)

---

## Screenshots

| Dashboard | Profile Editor | LLM Settings |
|-----------|---------------|--------------|
| Live stats, quick actions, getting started guide | Full candidate profile with tag inputs | Multi-provider config with connection test |

| Jobs Browser | Memory Browser | Settings |
|-------------|----------------|----------|
| Search, filter by status, status badges | Domain list, memory viewer, category stats | Resume, credentials, blocked domains |

---

## Quick Start (Users)

### Download Pre-Built Binary

Go to [**Releases**](../../releases) and download the installer for your OS:

| OS | File | Notes |
|----|------|-------|
| **macOS** | langhire_x.x.x_aarch64.dmg | Apple Silicon (M1/M2/M3) |
| **macOS** | langhire_x.x.x_x64.dmg | Intel Mac |
| **Windows** | langhire_x.x.x_x64-setup.exe | 64-bit Windows 10+ |
| **Linux** | langhire_x.x.x_amd64.AppImage | Universal Linux |
| **Linux** | langhire_x.x.x_amd64.deb | Debian/Ubuntu |

### First-Time Setup

1. **Open the app** — double-click the installed application
2. **Set up your profile** — Go to Profile → fill in your name, email, skills, target job titles
3. **Configure LLM** — Go to LLM Settings → select a provider → enter your API key → Test Connection
4. **Set resume path** — Go to Settings → point to your resume PDF
5. **Collect jobs** — Go to Jobs → Start collecting from LinkedIn
6. **Apply** — Go to Apply → Start applying to collected jobs

### Prerequisites

- **Python 3.13+** must be installed on your system ([python.org/downloads](https://www.python.org/downloads/))
- **Chromium browser** installed via Playwright:
 bash
 pip install playwright
 python -m playwright install chromium
 
- **An LLM API key** from OpenAI, Anthropic, or AWS

---

## Development Setup

### Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Node.js | 18+ | [nodejs.org](https://nodejs.org) |
| Rust | 1.77+ | curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \| sh |
| Python | 3.13+ | [python.org](https://python.org) or brew install python |
| uv | latest | curl -LsSf https://astral.sh/uv/install.sh \| sh |

### Clone & Install

bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/langhire.git
cd langhire

# Install Node dependencies
npm install

# Install Python dependencies
uv sync

# Install Playwright browser
uv run python -m playwright install chromium


### Running in Development

You need **two terminals**:

bash
# Terminal 1: Start the Python backend
uv run python backend/main.py

# Terminal 2: Start the frontend dev server
npm run dev


Then open http://localhost:1420 in your browser, or run the native Tauri app:

bash
# Terminal 2 (alternative): Start as native desktop app
cargo tauri dev


> **Note**: The first cargo tauri dev run will compile the Rust shell (~2 min). Subsequent runs are instant.

### Building for Production

bash
# Build the desktop app
cargo tauri build


This produces platform-specific installers in src-tauri/target/release/bundle/:
- macOS: .dmg and .app
- Windows: .exe and .msi
- Linux: .deb and .AppImage

---

## Project Structure


langhire/
 src/ # React frontend (TypeScript)
 App.tsx # Router + layout
 main.tsx # Entry point
 index.css # Tailwind CSS
 components/layout/ # Sidebar navigation
 pages/ # 7 page components
 Dashboard.tsx # Stats overview
 Profile.tsx # Candidate profile editor
 LLMSettings.tsx # LLM provider config
 Jobs.tsx # Job browser with filters
 Apply.tsx # Application controls
 Memory.tsx # Memory browser
 Settings.tsx # App settings
 lib/
 api.ts # Backend API client
 types.ts # TypeScript interfaces

 backend/ # Python backend (FastAPI)
 main.py # FastAPI server (20+ endpoints)
 requirements.txt # Python dependencies
 core/
 config.py # OS-aware config management
 llm_factory.py # Multi-provider LLM factory

 src-tauri/ # Tauri native shell (Rust)
 tauri.conf.json # App config (window, permissions)
 Cargo.toml # Rust dependencies
 src/lib.rs # Tauri plugins setup

 memory/ # Agent memory system (Python)
 store.py # SQLite memory store
 extractors.py # Post-run learning extraction
 metrics.py # Run metrics tracking

 collect_jobs.py # Job collection script
 apply_jobs.py # Job application script
 apply_jobs_tailored.py # Tailored resume application
 dashboard.py # CLI performance dashboard
 memory_cli.py # CLI memory management

 package.json # Node dependencies
 pyproject.toml # Python project config
 vite.config.ts # Vite bundler config
 index.html # HTML entry point


### Architecture



 Tauri Desktop Shell 
 
 React Frontend Python Backend 
 (TypeScript) (FastAPI sidecar) 
 
 • Profile Editor • browser-use agents 
 • LLM Settings • Playwright/Chromium 
 • Job Dashboard • Memory system 
 • Run Controls • Multi-LLM factory 
 • Memory Viewer • All automation 
 
 HTTP (localhost:8742) 
 
 
 Data: SQLite + JSON in OS app data directory 



---

## Configuration

All user data is stored locally in your OS app data directory:

| OS | Path |
|----|------|
| macOS | ~/Library/Application Support/langhire/ |
| Windows | %APPDATA%/langhire/ |
| Linux | ~/.config/langhire/ |

Files stored:
- candidate_profile.json — Your profile data
- llm_settings.json — LLM provider credentials
- settings.json — App preferences
- jobs.json — Collected job listings
- memory_store.db — Agent memory database

**All data stays on your machine. Nothing is sent to any server except the LLM API calls.**

---

## How the Memory System Works

1. **Before each run** — Memories for the target website are injected into the agent's prompt
2. **During the run** — The agent reports observations about the website's UI
3. **After each run** — Claude analyzes the run and extracts 3-8 procedural learnings

Memories are categorized: navigation, form_strategy, element_interaction, failure_recovery, site_structure, qa_pattern

ATS domains are normalized — a lesson learned on goodyear.wd1.myworkdayjobs.com helps on ALL Workday sites.

---

## CLI Usage (Advanced)

The original CLI scripts still work alongside the desktop app:

bash
# Collect jobs from LinkedIn
uv run python collect_jobs.py

# Apply to Easy Apply jobs
uv run python apply_jobs.py --workers 3

# Apply with tailored resumes
uv run python apply_jobs_tailored.py --workers 2

# Memory management
uv run python memory_cli.py stats
uv run python memory_cli.py domains
uv run python memory_cli.py show linkedin.com

# Performance dashboard (terminal)
uv run python dashboard.py


---

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

### Quick Start for Contributors

bash
git clone https://github.com/YOUR_USERNAME/langhire.git
cd langhire
npm install
uv sync
# Start developing (two terminals)
uv run python backend/main.py # Terminal 1
npm run dev # Terminal 2


### Areas We Need Help

- **More ATS integrations** — Workday, Greenhouse, Lever, etc.
- **UI/UX improvements** — Better dark mode, animations, responsive layout
- **More LLM providers** — Google Gemini, Ollama (local), Azure OpenAI
- **Dashboard enhancements** — Charts, trend visualization
- **Testing** — Unit tests, integration tests, E2E tests
- **Documentation** — Tutorials, video walkthroughs
- **Internationalization** — Multi-language support

---

## License

[MIT License](LICENSE) — Free for personal and commercial use.

---

## ️ Disclaimer

This tool automates job applications on LinkedIn and other platforms. Use responsibly:

- Respect each platform's Terms of Service and rate limits
- Don't spam employers with low-quality applications
- Review your profile and settings before running automated applications
- The AI agent makes decisions based on your profile — ensure your information is accurate
- You are responsible for all applications submitted through this tool

---

<p align="center">
 Built with ️ using <a href="https://tauri.app">Tauri</a>, <a href="https://react.dev">React</a>, <a href="https://python.org">Python</a>, and <a href="https://github.com/browser-use/browser-use">browser-use</a>
</p>
