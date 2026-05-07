# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).

## [1.4.0](https://github.com/jaimaann/LangHire/compare/v1.3.0...v1.4.0) - 2026-05-06

### Added
- Google Analytics 4 integration for website and desktop app (opt-out in Settings)
- Sentry crash reporting with full stack traces
- Performance metrics: startup latency, backend connection time, page load times
- Event tracking for job collection, apply, LLM provider, memory operations, Q&A
- Dashboard stats event with jobs/memories/questions counts

### Fixed
- Backend default port changed to 8743 to avoid conflicts
- macOS entitlements added to fix PyInstaller sidecar library validation

### Changed
- ARM64 .deb download link added to website and README

## [1.3.0](https://github.com/jaimaann/LangHire/compare/v1.2.0...v1.3.0) - 2026-05-02

### Added
- OpenRouter LLM provider with dynamic vision model fetching and pricing display
- Q&A repository with auto-squash and LLM-powered smart-squash deduplication
- Feedback screen in desktop app and website
- Marketing website built with Astro + Tailwind
- macOS code signing and notarization in CI
- Blog with comparison post (LangHire vs LazyApply vs Sonara vs AIHawk)
- Loop detection and smarter persistence prompt for agents
- Direct LinkedIn search URL navigation for faster collection
- Step-by-step job extraction method for collection prompt
- OTP/2FA instructions for both Easy Apply and external paths
- External site navigation instructions for non-Easy Apply jobs
- Linux ARM64 CI build support

### Fixed
- Chromium sandbox disabled on Linux for compatibility
- xdg-utils added to Linux CI dependencies for AppImage
- Agent step limit increased from 30 to 70
- Per-job easy_apply flag used instead of worker-level override
- Profile, Q&A, and memories now injected into agent system prompt
- Agent collects max_jobs NEW jobs, excluding already-known ones
- DOM truncation params removed (broke agent interaction)
- OpenRouter fallback model ordering corrected
- Dependency versions pinned to prevent Vite 8 conflict in website build

### Changed
- OpenRouter set as default provider with Qwen 3.6 Plus
- New rocket icon logo across app and website
- Copyright holder updated in LICENSE to LangHire

## [1.2.0](https://github.com/jaimaann/LangHire/compare/v1.1.0...v1.2.0) - 2026-04-28

### Added
- Verbose agent logging to `agent_verbose.log`
- Confirmation dialog before starting automation

### Fixed
- Profile email used for form filling, credentials email for ATS login
- Ollama connection optimized with increased timeouts and better error reporting

## [1.1.0](https://github.com/jaimaann/LangHire/compare/v1.0.0...v1.1.0) - 2026-04-26

### Added
- Ollama support for self-hosted local LLMs

## [1.0.0] - 2026-04-25

### Added
- Initial release
- Tauri desktop app with React frontend and FastAPI Python backend
- Job collection from LinkedIn with AI browser agents
- Automated job applications (Easy Apply + external ATS)
- Self-learning memory system with per-domain procedural knowledge
- Multi-LLM support: OpenAI, Anthropic, AWS Bedrock
- Dashboard with real-time stats
- Profile management with resume PDF parsing
- Setup wizard for onboarding
- Cross-platform builds: macOS, Windows, Linux
- CLI tools for collection, application, and memory management
