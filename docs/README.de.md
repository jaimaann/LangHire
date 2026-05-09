<p align="center">
  <img src="../src-tauri/icons/icon.png" alt="LangHire" width="120" />
</p>

<h1 align="center">LangHire</h1>

<p align="center">
  <strong>KI-gesteuerte Automatisierung von Bewerbungen mit nativer Desktop-Oberfläche</strong>
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
  <a href="README.de.md"><strong>Deutsch</strong></a> &middot;
  <a href="README.fr.md">Français</a> &middot;
  <a href="README.es.md">Español</a> &middot;
  <a href="README.ar.md">العربية</a> &middot;
  <a href="README.nl.md">Nederlands</a> &middot;
  <a href="README.ja.md">日本語</a> &middot;
  <a href="README.ko.md">한국어</a> &middot;
  <a href="README.pt.md">Português</a> &middot;
  <a href="README.ms.md">Bahasa Melayu</a>
</p>

---

Sich auf Jobs zu bewerben ist mühsam. Man findet eine Stellenanzeige, klickt sich zur Bewerbung durch, füllt dieselben Felder aus wie gestern, beantwortet dieselben Screening-Fragen, lädt den Lebenslauf erneut hoch — und das fünfzig Mal. LangHire automatisiert den gesamten Ablauf.

Es nutzt KI-Browser-Agenten, um LinkedIn zu durchsuchen, passende Jobs zu sammeln, Bewerbungen auszufüllen, Ihren Lebenslauf hochzuladen und abzuschicken — während ein **selbstlernendes Gedächtnissystem** sich merkt, wie jedes Applicant Tracking System (ATS) funktioniert, sodass es mit der Zeit schneller und genauer wird. Alles läuft lokal auf Ihrem Rechner. Keine Daten verlassen Ihren Computer außer LLM API-Aufrufe.

---

## Download

<div align="center">

| <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/apple/apple-original.svg" width="16" /> macOS | <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/windows11/windows11-original.svg" width="16" /> Windows | <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/linux/linux-original.svg" width="16" /> Linux |
|:---:|:---:|:---:|
| [**Apple Silicon (.dmg)**](https://github.com/jaimaann/LangHire/releases/latest/download/LangHire_1.0.0_aarch64.dmg) | [**64-bit Installer (.exe)**](https://github.com/jaimaann/LangHire/releases/latest/download/LangHire_1.0.0_x64-setup.exe) | [**AppImage (Universal)**](https://github.com/jaimaann/LangHire/releases/latest/download/LangHire_1.0.0_amd64.AppImage) |
| [Intel (.dmg)](https://github.com/jaimaann/LangHire/releases/latest/download/LangHire_1.0.0_x64.dmg) | | [Debian / Ubuntu x64 (.deb)](https://github.com/jaimaann/LangHire/releases/latest/download/LangHire_1.0.0_amd64.deb) |
| | | [Debian / Ubuntu ARM64 (.deb)](https://github.com/jaimaann/LangHire/releases/latest/download/LangHire_1.0.0_arm64.deb) |

</div>

<p align="center"><sub>Erfordert einen LLM API-Schlüssel (OpenAI, Anthropic oder AWS). Chromium wird beim ersten Start automatisch installiert. Siehe <a href="#schnellstart">Schnellstart</a>.</sub></p>

> **Entwickler** -- Siehe [Entwicklungssetup](#entwicklungssetup) zum Ausführen aus dem Quellcode.

### Installationshinweise

<details>
<summary><strong>macOS</strong></summary>

Die macOS-Version ist von Apple **signiert und notarisiert**. Öffnen Sie einfach die `.dmg`, ziehen Sie LangHire in den Programme-Ordner und doppelklicken Sie zum Starten. Keine weiteren Schritte nötig.
</details>

<details>
<summary><strong>Windows</strong> -- "Windows hat Ihren PC geschützt" (SmartScreen)</summary>

Der Windows-Installer ist nicht code-signiert. Möglicherweise sehen Sie eine SmartScreen-Warnung:

1. Führen Sie den `.exe`-Installer aus
2. Wenn Sie **"Windows hat Ihren PC geschützt"** sehen:
   - Klicken Sie auf **Weitere Informationen**
   - Klicken Sie auf **Trotzdem ausführen**
3. Schließen Sie den Installer ab und starten Sie LangHire
</details>

<details>
<summary><strong>Linux</strong> -- AppImage oder .deb</summary>

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
> **Wenn Chromium nicht startet:** Einige Linux-Distributionen (wie Ubuntu 24.04+) haben Sandbox-Einschränkungen. Führen Sie dies aus, um Browser und Abhängigkeiten manuell zu installieren:
> ```bash
> uvx playwright install --with-deps chromium
> ```
</details>

---

## Funktionen

- **Native Desktop-App** -- macOS, Windows und Linux
- **Job-Sammlung** -- Durchsucht LinkedIn nach Jobs, die Ihren Zielbezeichnungen und Standorten entsprechen
- **Automatisierte Bewerbungen** -- KI-Agent füllt Formulare aus, lädt Ihren Lebenslauf hoch, beantwortet Screening-Fragen
- **Maßgeschneiderte Lebensläufe** (Beta) -- Passt Ihren Lebenslauf automatisch an jede Stellenbeschreibung an
- **Selbstlernendes Gedächtnis** -- Speichert prozedurales Wissen pro ATS (Navigationsmuster, Formularstrategien, UI-Eigenheiten). Erkenntnisse von einer Workday-Seite gelten für alle Workday-Seiten.
- **Intelligente Q&A-Wiederverwendung** -- Lernt Antworten aus früheren Bewerbungen und verwendet sie wieder
- **Multi-LLM-Unterstützung** -- OpenAI, Anthropic, AWS Bedrock oder Ollama für lokale Modelle
- **Dashboard** -- Echtzeit-Statistiken, Erfolgsraten, Leistung pro Domain, Analyse der Gedächtnisauswirkungen
- **CLI-Tools** -- Power-User-Skripte für Sammlung, Bewerbung, Gedächtnisverwaltung und Analytik
- **100% lokal** -- Alle Daten werden auf Ihrem Rechner im OS-App-Datenverzeichnis gespeichert

---

## Screenshots

<table>
<tr>
<td align="center" width="33%">
<details>
<summary><img src="../screenshots/dashboard.png" alt="Dashboard" width="280" /><br/><strong>Dashboard</strong></summary>
<img src="../screenshots/dashboard.png" alt="Dashboard" width="800" />
</details>
</td>
<td align="center" width="33%">
<details>
<summary><img src="../screenshots/jobs.png" alt="Jobs" width="280" /><br/><strong>Jobs</strong></summary>
<img src="../screenshots/jobs.png" alt="Jobs" width="800" />
</details>
</td>
<td align="center" width="33%">
<details>
<summary><img src="../screenshots/memory.png" alt="Memory" width="280" /><br/><strong>Gedächtnis</strong></summary>
<img src="../screenshots/memory.png" alt="Memory" width="800" />
</details>
</td>
</tr>
</table>

<p align="center"><sub>Klicken Sie auf einen Screenshot zum Vergrößern</sub></p>

---

## Schnellstart

1. **Herunterladen und installieren** aus dem [Download](#download)-Abschnitt oben
2. **App öffnen** -- Chromium wird beim ersten Start automatisch heruntergeladen (~400 MB, einmalig)
3. **Einrichtungsassistent** führt Sie durch: **LLM-Anbieter** → **Lebenslauf hochladen** (parst automatisch Ihr Profil) → **Profil überprüfen** → Bereit
4. **Jobs sammeln** -- gehen Sie zu **Jobs** → geben Sie eine Berufsbezeichnung ein → **Start Collecting**
5. **Bewerben** -- gehen Sie zu **Apply** → **Start Applying** und beobachten Sie das Dashboard, während Bewerbungen eingehen

---

## So funktioniert es

LangHire führt eine dreistufige Schleife aus: **Sammeln → Bewerben → Lernen**.

**Sammeln** -- Ein KI-Browser-Agent meldet sich bei LinkedIn an, sucht nach Jobs, die Ihren Zielbezeichnungen und Standorten entsprechen, und speichert jede Anzeige mit URL, Unternehmen, Titel und Beschreibung.

**Bewerben** -- Für jeden ausstehenden Job öffnet der Agent die Bewerbung (Easy Apply oder externes ATS), füllt jedes Feld mit Ihrem Profil aus, lädt Ihren Lebenslauf hoch, beantwortet Screening-Fragen aus seiner Q&A-Datenbank und sendet ab. Mehrere Worker können parallel laufen.

**Lernen** -- Nach jeder Bewerbung extrahiert das System prozedurales Wissen: welche Buttons zu klicken sind, wie Formulare aufgebaut sind, was fehlschlägt und was funktioniert. Diese Erinnerungen werden pro ATS-Domain mit Vertrauenswerten gespeichert, sodass es beim nächsten Mal, wenn es auf dasselbe ATS trifft, bereits weiß, wie es navigieren muss.

### Architektur

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

Alle Daten werden lokal gespeichert:

| OS | Pfad |
|----|------|
| macOS | `~/Library/Application Support/langhire/` |
| Windows | `%APPDATA%/langhire/` |
| Linux | `~/.config/langhire/` |

---

## Entwicklungssetup

### Voraussetzungen

| Tool | Version | Installation |
|------|---------|---------|
| Node.js | 18+ | [nodejs.org](https://nodejs.org) |
| Rust | 1.77+ | `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \| sh` |
| Python | 3.13+ | [python.org](https://python.org) |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |

### Klonen und Installieren

```bash
git clone https://github.com/jaimaann/LangHire.git
cd LangHire

npm install                                    # Node dependencies
uv sync                                        # Python dependencies
uv run python -m playwright install chromium   # Browser engine
```

### Im Entwicklungsmodus ausführen

Zwei Terminals:

```bash
# Terminal 1 -- Python backend
uv run python backend/main.py

# Terminal 2 -- Frontend dev server
npm run dev
```

Öffnen Sie http://localhost:1420, oder führen Sie stattdessen als native Desktop-App aus:

```bash
# Terminal 2 (alternative) -- Native Tauri app
cargo tauri dev
```

> Der erste `cargo tauri dev`-Aufruf kompiliert die Rust-Shell (~2 Min). Nachfolgende Starts sind schnell.

### Für Produktion bauen

```bash
cargo tauri build
```

Erzeugt plattformspezifische Installer in `src-tauri/target/release/bundle/`.

---

## Projektstruktur

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

## CLI-Nutzung

Die CLI-Skripte funktionieren eigenständig neben der Desktop-App:

```bash
# Jobs von LinkedIn sammeln
uv run python cli/collect_jobs.py

# Auf Jobs bewerben (3 parallele Worker)
uv run python cli/apply_jobs.py --workers 3

# Mit job-spezifisch angepassten Lebensläufen bewerben
uv run python cli/apply_jobs_tailored.py --workers 2

# Gedächtnisverwaltung
uv run python cli/memory_cli.py stats
uv run python cli/memory_cli.py domains
uv run python cli/memory_cli.py show linkedin.com

# Terminal-Performance-Dashboard
uv run python cli/dashboard.py
```

---

## Mitwirken

Beiträge sind willkommen. Siehe [CONTRIBUTING.md](../CONTRIBUTING.md) für vollständige Richtlinien.

```bash
git clone https://github.com/jaimaann/LangHire.git
cd LangHire
npm install && uv sync
uv run python backend/main.py   # Terminal 1
npm run dev                     # Terminal 2
```

**Bereiche, in denen Hilfe benötigt wird:**

- **Mehr Job-Plattformen** -- Indeed, Glassdoor und andere Stellenbörsen über LinkedIn hinaus
- **Lokale LLM-Unterstützung** -- Ollama, llama.cpp und andere lokale Inferenz-Optionen
- **Mehrländer-Unterstützung** -- Lokalisierte Jobseiten, Adressformate und Arbeitserlaubnis-Abläufe
- **Dokumentation** -- Tutorials, Video-Anleitungen und Guides
- **Tests** -- Unit-, Integrations- und E2E-Testabdeckung

---

## Lizenz

[MIT](../LICENSE)

---

## Haftungsausschluss

Dieses Tool automatisiert Bewerbungen auf LinkedIn und anderen Plattformen. Nutzen Sie es verantwortungsvoll:

- Respektieren Sie die Nutzungsbedingungen und Ratenlimits jeder Plattform
- Spammen Sie Arbeitgeber nicht mit minderwertigen Bewerbungen
- Überprüfen Sie Ihr Profil und Ihre Einstellungen, bevor Sie automatisierte Bewerbungen ausführen
- Sie sind für alle über dieses Tool eingereichten Bewerbungen verantwortlich

---

<p align="center">
  Gebaut mit <a href="https://tauri.app">Tauri</a>, <a href="https://react.dev">React</a>, <a href="https://python.org">Python</a> und <a href="https://github.com/browser-use/browser-use">browser-use</a>
</p>
