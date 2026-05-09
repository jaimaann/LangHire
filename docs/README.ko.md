<p align="center">
  <img src="../src-tauri/icons/icon.png" alt="LangHire" width="120" />
</p>

<h1 align="center">LangHire</h1>

<p align="center">
  <strong>네이티브 데스크톱 UI를 갖춘 AI 기반 구직 지원 자동화</strong>
</p>

<p align="center">
  <a href="https://langhire.org"><img src="https://img.shields.io/badge/Website-langhire.org-FF385C?style=flat&logo=globe&logoColor=white" alt="Website" /></a>
  <img src="https://img.shields.io/badge/Platform-macOS%20%7C%20Windows%20%7C%20Linux-blue" alt="Platform" />
  <img src="https://img.shields.io/badge/Languages-11%20supported-teal" alt="Languages" />
  <img src="https://img.shields.io/badge/Tauri%20v2-React%20%2B%20TypeScript-purple" alt="UI" />
  <img src="https://img.shields.io/badge/Backend-Python%20%2B%20FastAPI-green" alt="Backend" />
  <img src="https://img.shields.io/badge/AI-OpenAI%20%7C%20Claude%20%7C%20Bedrock-orange" alt="AI" />
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-lightgrey" alt="License" /></a>
</p>

<p align="center">
  <a href="../README.md">English</a> &middot;
  <a href="README.hi.md">हिन्दी</a> &middot;
  <a href="README.de.md">Deutsch</a> &middot;
  <a href="README.fr.md">Français</a> &middot;
  <a href="README.es.md">Español</a> &middot;
  <a href="README.ar.md">العربية</a> &middot;
  <a href="README.nl.md">Nederlands</a> &middot;
  <a href="README.ja.md">日本語</a> &middot;
  <a href="README.ko.md"><strong>한국어</strong></a> &middot;
  <a href="README.pt.md">Português</a> &middot;
  <a href="README.ms.md">Bahasa Melayu</a>
</p>

---

구직 지원은 지루합니다. 채용 공고를 찾고, 지원 페이지로 클릭하고, 어제 채운 것과 같은 필드를 채우고, 같은 사전 심사 질문에 답하고, 이력서를 다시 업로드합니다 — 이것을 50번 반복합니다. LangHire는 이 전체 과정을 자동화합니다.

AI 브라우저 에이전트를 사용하여 LinkedIn을 검색하고, 매칭되는 채용 공고를 수집하고, 지원서를 작성하고, 이력서를 업로드하고, 제출합니다 — **자기 학습 메모리 시스템**이 각 지원자 추적 시스템(ATS)의 작동 방식을 기억하여 시간이 지남에 따라 더 빠르고 정확해집니다. 모든 것이 당신의 머신에서 로컬로 실행됩니다. LLM API 호출을 제외하고는 데이터가 컴퓨터를 떠나지 않습니다.

---

## 다운로드

<div align="center">

| <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/apple/apple-original.svg" width="16" /> macOS | <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/windows11/windows11-original.svg" width="16" /> Windows | <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/linux/linux-original.svg" width="16" /> Linux |
|:---:|:---:|:---:|
| [**Apple Silicon (.dmg)**](https://github.com/jaimaann/LangHire/releases/latest/download/LangHire_1.0.0_aarch64.dmg) | [**64-bit Installer (.exe)**](https://github.com/jaimaann/LangHire/releases/latest/download/LangHire_1.0.0_x64-setup.exe) | [**AppImage (Universal)**](https://github.com/jaimaann/LangHire/releases/latest/download/LangHire_1.0.0_amd64.AppImage) |
| [Intel (.dmg)](https://github.com/jaimaann/LangHire/releases/latest/download/LangHire_1.0.0_x64.dmg) | | [Debian / Ubuntu x64 (.deb)](https://github.com/jaimaann/LangHire/releases/latest/download/LangHire_1.0.0_amd64.deb) |
| | | [Debian / Ubuntu ARM64 (.deb)](https://github.com/jaimaann/LangHire/releases/latest/download/LangHire_1.0.0_arm64.deb) |

</div>

<p align="center"><sub>LLM API 키(OpenAI, Anthropic 또는 AWS)가 필요합니다. 첫 실행 시 Chromium이 자동 설치됩니다. <a href="#빠른-시작">빠른 시작</a>을 참조하세요.</sub></p>

> **개발자** -- 소스에서 실행하려면 [개발 환경 설정](#개발-환경-설정)을 참조하세요.

### 설치 참고사항

<details>
<summary><strong>macOS</strong></summary>

macOS 릴리스는 Apple에 의해 **서명 및 공증**되었습니다. `.dmg`를 열고 LangHire를 응용 프로그램으로 드래그한 후 더블클릭하여 실행하면 됩니다. 추가 단계가 필요 없습니다.
</details>

<details>
<summary><strong>Windows</strong> -- "Windows가 PC를 보호했습니다" (SmartScreen)</summary>

Windows 설치 프로그램은 코드 서명되지 않았습니다. SmartScreen 경고가 표시될 수 있습니다:

1. `.exe` 설치 프로그램을 실행
2. **"Windows가 PC를 보호했습니다"**가 표시되면:
   - **추가 정보**를 클릭
   - **실행**을 클릭
3. 설치를 완료하고 LangHire를 실행
</details>

<details>
<summary><strong>Linux</strong> -- AppImage 또는 .deb</summary>

**AppImage:**
```bash
chmod +x LangHire_1.0.0_amd64.AppImage
./LangHire_1.0.0_amd64.AppImage
```

**Debian / Ubuntu:**
```bash
# Install uv package manager (required for browser management)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install the app
sudo dpkg -i LangHire_1.0.0_arm64.deb
```

> [!TIP]
> **Chromium이 실행되지 않는 경우:** 일부 Linux 배포판(Ubuntu 24.04+ 등)에는 샌드박스 제한이 있습니다. 브라우저와 종속성을 수동으로 설치하려면 다음을 실행하세요:
> ```bash
> uvx playwright install --with-deps chromium
> ```
</details>

---

## 기능

- **네이티브 데스크톱 앱** -- macOS, Windows, Linux 지원
- **채용 공고 수집** -- 목표 직함과 위치에 맞는 LinkedIn 채용 공고 검색
- **자동 지원** -- AI 에이전트가 양식을 작성하고, 이력서를 업로드하고, 사전 심사 질문에 답변
- **맞춤형 이력서** (베타) -- 각 채용 설명에 맞게 이력서를 자동 맞춤화
- **자기 학습 메모리** -- ATS별 절차적 지식을 저장(탐색 패턴, 양식 전략, UI 특이사항). 한 Workday 사이트에서 배운 교훈이 모든 Workday 사이트에 적용됩니다.
- **스마트 Q&A 재사용** -- 이전 지원에서 답변을 학습하고 재사용
- **멀티 LLM 지원** -- OpenAI, Anthropic, AWS Bedrock 또는 로컬 모델용 Ollama
- **대시보드** -- 실시간 통계, 성공률, 도메인별 성능, 메모리 영향 분석
- **CLI 도구** -- 수집, 지원, 메모리 관리, 분석을 위한 고급 사용자 스크립트
- **100% 로컬** -- 모든 데이터가 OS 앱 데이터 디렉토리의 머신에 저장

---

## 스크린샷

<table>
<tr>
<td align="center" width="33%">
<details>
<summary><img src="../screenshots/dashboard.png" alt="Dashboard" width="280" /><br/><strong>대시보드</strong></summary>
<img src="../screenshots/dashboard.png" alt="Dashboard" width="800" />
</details>
</td>
<td align="center" width="33%">
<details>
<summary><img src="../screenshots/jobs.png" alt="Jobs" width="280" /><br/><strong>채용 공고</strong></summary>
<img src="../screenshots/jobs.png" alt="Jobs" width="800" />
</details>
</td>
<td align="center" width="33%">
<details>
<summary><img src="../screenshots/memory.png" alt="Memory" width="280" /><br/><strong>메모리</strong></summary>
<img src="../screenshots/memory.png" alt="Memory" width="800" />
</details>
</td>
</tr>
</table>

<p align="center"><sub>스크린샷을 클릭하여 확대</sub></p>

---

## 빠른 시작

1. 위의 [다운로드](#다운로드) 섹션에서 **다운로드 및 설치**
2. **앱 열기** -- 첫 실행 시 Chromium이 자동 다운로드됩니다 (~400 MB, 한 번만)
3. **설정 마법사**가 안내합니다: **LLM 제공자** → **이력서 업로드** (프로필 자동 파싱) → **프로필 검토** → 준비 완료
4. **채용 공고 수집** -- **Jobs**로 이동 → 직함 입력 → **Start Collecting**
5. **지원** -- **Apply**로 이동 → **Start Applying** 후 대시보드에서 지원 현황 확인

---

## 작동 방식

LangHire는 3단계 루프를 실행합니다: **수집 → 지원 → 학습**.

**수집** -- AI 브라우저 에이전트가 LinkedIn에 로그인하고, 목표 직함과 위치에 맞는 채용 공고를 검색하고, 각 공고의 URL, 회사, 직함, 설명을 저장합니다.

**지원** -- 대기 중인 각 채용 공고에 대해, 에이전트가 지원서를 열고(Easy Apply 또는 외부 ATS), 프로필을 사용하여 모든 필드를 채우고, 이력서를 업로드하고, Q&A 뱅크에서 사전 심사 질문에 답하고, 제출합니다. 여러 워커가 병렬로 실행될 수 있습니다.

**학습** -- 각 지원 후, 시스템이 절차적 학습을 추출합니다: 어떤 버튼을 클릭해야 하는지, 양식이 어떻게 구성되어 있는지, 무엇이 실패하고 무엇이 작동하는지. 이러한 메모리는 신뢰도 점수와 함께 ATS 도메인별로 저장되므로, 다음에 같은 ATS를 만나면 이미 탐색 방법을 알고 있습니다.

### 아키텍처

```
┌──────────────────────────────────────────────────┐
│              Tauri Desktop Shell (Rust)           │
│     Lightweight native wrapper, ~10 MB           │
└────────────────────┬─────────────────────────────┘
                     │ spawns sidecar
                     ▼
┌──────────────────────────────────────────────────┐
│  React Frontend          │  FastAPI Backend      │
│  (TypeScript)            │  (Python sidecar)     │
│                          │                       │
│  - Dashboard             │  - browser-use agents │
│  - Profile editor        │  - Playwright browser │
│  - LLM settings          │  - Memory system      │
│  - Job browser           │  - Multi-LLM factory  │
│  - Apply controls        │  - 20+ REST endpoints │
│  - Memory viewer         │                       │
│          ◄── HTTP localhost:8742 ──►             │
└──────────────────────────────────────────────────┘
                     │
                     ▼
        SQLite + JSON (OS app data directory)
```

모든 데이터는 로컬에 저장됩니다:

| OS | 경로 |
|----|------|
| macOS | `~/Library/Application Support/langhire/` |
| Windows | `%APPDATA%/langhire/` |
| Linux | `~/.config/langhire/` |

---

## 개발 환경 설정

### 전제 조건

| 도구 | 버전 | 설치 |
|------|---------|---------|
| Node.js | 18+ | [nodejs.org](https://nodejs.org) |
| Rust | 1.77+ | `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \| sh` |
| Python | 3.13+ | [python.org](https://python.org) |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |

### 클론 및 설치

```bash
git clone https://github.com/jaimaann/LangHire.git
cd LangHire

npm install                                    # Node dependencies
uv sync                                        # Python dependencies
uv run python -m playwright install chromium   # Browser engine
```

### 개발 모드에서 실행

두 개의 터미널:

```bash
# Terminal 1 -- Python backend
uv run python backend/main.py

# Terminal 2 -- Frontend dev server
npm run dev
```

http://localhost:1420 을 열거나, 네이티브 데스크톱 앱으로 실행:

```bash
# Terminal 2 (alternative) -- Native Tauri app
cargo tauri dev
```

> 첫 `cargo tauri dev`는 Rust 셸을 컴파일합니다 (~2분). 이후 실행은 빠릅니다.

### 프로덕션 빌드

```bash
cargo tauri build
```

`src-tauri/target/release/bundle/`에 플랫폼별 설치 프로그램을 생성합니다.

---

## 프로젝트 구조

```
LangHire/
├── src/                        # React frontend (TypeScript)
│   ├── pages/                  # Dashboard, Profile, Jobs, Apply, Memory, Settings, LLMSettings, Logs
│   ├── components/             # UI primitives, SetupWizard, Sidebar, LoginCards
│   └── lib/                    # API client, TypeScript types
│
├── backend/                    # Python backend (FastAPI)
│   ├── main.py                 # Server with 20+ endpoints
│   ├── core/                   # Config, LLM factory, shared utilities
│   └── memory/                 # SQLite store, post-run extractors, metrics
│
├── src-tauri/                  # Tauri native shell (Rust)
│   ├── src/lib.rs              # App setup, sidecar launch
│   └── tauri.conf.json         # Window config, permissions, bundling
│
├── cli/                        # CLI automation scripts
│   ├── collect_jobs.py         # Job collection
│   ├── apply_jobs.py           # Job application (multi-worker)
│   ├── apply_jobs_tailored.py  # Tailored resume variant
│   ├── dashboard.py            # Terminal analytics dashboard
│   └── memory_cli.py           # Memory management
│
└── scripts/                    # Build helpers (macOS DMG, backend bundling)
```

---

## CLI 사용법

CLI 스크립트는 데스크톱 앱과 함께 독립적으로 작동합니다:

```bash
# LinkedIn에서 채용 공고 수집
uv run python cli/collect_jobs.py

# 채용 공고에 지원 (3개의 병렬 워커)
uv run python cli/apply_jobs.py --workers 3

# 채용 공고별 맞춤 이력서로 지원
uv run python cli/apply_jobs_tailored.py --workers 2

# 메모리 관리
uv run python cli/memory_cli.py stats
uv run python cli/memory_cli.py domains
uv run python cli/memory_cli.py show linkedin.com

# 터미널 성능 대시보드
uv run python cli/dashboard.py
```

---

## 기여하기

기여를 환영합니다. 전체 가이드라인은 [CONTRIBUTING.md](../CONTRIBUTING.md)를 참조하세요.

```bash
git clone https://github.com/jaimaann/LangHire.git
cd LangHire
npm install && uv sync
uv run python backend/main.py   # Terminal 1
npm run dev                     # Terminal 2
```

**도움이 필요한 분야:**

- **더 많은 구직 플랫폼** -- Indeed, Glassdoor 및 LinkedIn 외의 기타 구인 사이트
- **로컬 LLM 지원** -- Ollama, llama.cpp 및 기타 로컬 추론 옵션
- **다국가 지원** -- 현지화된 구인 사이트, 주소 형식, 취업 허가 절차
- **문서** -- 튜토리얼, 비디오 안내, 가이드
- **테스트** -- 유닛, 통합, E2E 테스트 커버리지

---

## 라이선스

[MIT](../LICENSE)

---

## 면책 조항

이 도구는 LinkedIn 및 기타 플랫폼에서 구직 지원을 자동화합니다. 책임감 있게 사용하세요:

- 각 플랫폼의 서비스 약관 및 속도 제한을 준수하세요
- 저품질 지원으로 고용주에게 스팸을 보내지 마세요
- 자동 지원을 실행하기 전에 프로필과 설정을 확인하세요
- 이 도구를 통해 제출된 모든 지원에 대해 본인이 책임집니다

---

<p align="center">
  <a href="https://tauri.app">Tauri</a>, <a href="https://react.dev">React</a>, <a href="https://python.org">Python</a>, <a href="https://github.com/browser-use/browser-use">browser-use</a>로 제작
</p>
