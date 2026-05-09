<p align="center">
  <img src="../src-tauri/icons/icon.png" alt="LangHire" width="120" />
</p>

<h1 align="center">LangHire</h1>

<p align="center">
  <strong>Automasi permohonan kerja dikuasakan AI dengan antara muka desktop natif</strong>
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
  <a href="README.ko.md">한국어</a> &middot;
  <a href="README.pt.md">Português</a> &middot;
  <a href="README.ms.md"><strong>Bahasa Melayu</strong></a>
</p>

---

Memohon kerja adalah membosankan. Anda mencari iklan jawatan, klik ke permohonan, mengisi medan yang sama seperti semalam, menjawab soalan saringan yang sama, memuat naik resume sekali lagi — ulang lima puluh kali. LangHire mengautomasi keseluruhan kitaran ini.

Ia menggunakan ejen pelayar AI untuk mencari di LinkedIn, mengumpul pekerjaan yang sepadan, mengisi permohonan, memuat naik resume anda, dan menghantar — sementara **sistem memori pembelajaran kendiri** mengingati cara setiap sistem penjejakan pemohon (ATS) berfungsi supaya ia menjadi lebih pantas dan tepat dari semasa ke semasa. Semuanya berjalan secara setempat pada mesin anda. Tiada data meninggalkan komputer anda kecuali panggilan API LLM.

---

## Muat Turun

<div align="center">

| <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/apple/apple-original.svg" width="16" /> macOS | <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/windows11/windows11-original.svg" width="16" /> Windows | <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/linux/linux-original.svg" width="16" /> Linux |
|:---:|:---:|:---:|
| [**Apple Silicon (.dmg)**](https://github.com/jaimaann/LangHire/releases/latest/download/LangHire_1.0.0_aarch64.dmg) | [**64-bit Installer (.exe)**](https://github.com/jaimaann/LangHire/releases/latest/download/LangHire_1.0.0_x64-setup.exe) | [**AppImage (Universal)**](https://github.com/jaimaann/LangHire/releases/latest/download/LangHire_1.0.0_amd64.AppImage) |
| [Intel (.dmg)](https://github.com/jaimaann/LangHire/releases/latest/download/LangHire_1.0.0_x64.dmg) | | [Debian / Ubuntu x64 (.deb)](https://github.com/jaimaann/LangHire/releases/latest/download/LangHire_1.0.0_amd64.deb) |
| | | [Debian / Ubuntu ARM64 (.deb)](https://github.com/jaimaann/LangHire/releases/latest/download/LangHire_1.0.0_arm64.deb) |

</div>

<p align="center"><sub>Memerlukan kunci API LLM (OpenAI, Anthropic, atau AWS). Chromium dipasang secara automatik pada pelancaran pertama. Lihat <a href="#mula-pantas">Mula Pantas</a>.</sub></p>

> **Pembangun** -- Lihat [Persediaan Pembangunan](#persediaan-pembangunan) untuk menjalankan dari kod sumber.

### Nota Pemasangan

<details>
<summary><strong>macOS</strong></summary>

Keluaran macOS telah **ditandatangani dan dinotarisasi** oleh Apple. Cuma buka `.dmg`, seret LangHire ke Applications, dan dwi-klik untuk melancarkan. Tiada langkah tambahan diperlukan.
</details>

<details>
<summary><strong>Windows</strong> -- "Windows protected your PC" (SmartScreen)</summary>

Pemasang Windows tidak ditandatangani kod. Anda mungkin melihat amaran SmartScreen:

1. Jalankan pemasang `.exe`
2. Jika anda melihat **"Windows protected your PC"**:
   - Klik **More info**
   - Klik **Run anyway**
3. Lengkapkan pemasang dan lancarkan LangHire
</details>

<details>
<summary><strong>Linux</strong> -- AppImage atau .deb</summary>

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
> **Jika Chromium tidak dapat dilancarkan:** Sesetengah pengedaran Linux (seperti Ubuntu 24.04+) mempunyai sekatan sandbox. Jalankan ini untuk memasang pelayar dan kebergantungan secara manual:
> ```bash
> uvx playwright install --with-deps chromium
> ```
</details>

---

## Ciri-ciri

- **Aplikasi desktop natif** -- macOS, Windows, dan Linux
- **Pengumpulan pekerjaan** -- Mencari LinkedIn untuk pekerjaan yang sepadan dengan jawatan dan lokasi sasaran anda
- **Permohonan automatik** -- Ejen AI mengisi borang, memuat naik resume anda, menjawab soalan saringan
- **Resume tersuai** (beta) -- Menyesuaikan resume anda secara automatik untuk setiap deskripsi pekerjaan
- **Memori pembelajaran kendiri** -- Menyimpan pengetahuan prosedur per-ATS (corak navigasi, strategi borang, keanehan UI). Pelajaran dari satu laman Workday terpakai untuk semua laman Workday.
- **Penggunaan semula Q&A pintar** -- Mempelajari jawapan dari permohonan terdahulu dan menggunakannya semula
- **Sokongan multi-LLM** -- OpenAI, Anthropic, AWS Bedrock, atau Ollama untuk model setempat
- **Papan pemuka** -- Statistik masa nyata, kadar kejayaan, prestasi per-domain, analisis kesan memori
- **Alat CLI** -- Skrip pengguna berkuasa untuk pengumpulan, permohonan, pengurusan memori, dan analitik
- **100% setempat** -- Semua data disimpan pada mesin anda dalam direktori data aplikasi OS

---

## Tangkapan Skrin

<table>
<tr>
<td align="center" width="33%">
<details>
<summary><img src="../screenshots/dashboard.png" alt="Dashboard" width="280" /><br/><strong>Papan Pemuka</strong></summary>
<img src="../screenshots/dashboard.png" alt="Dashboard" width="800" />
</details>
</td>
<td align="center" width="33%">
<details>
<summary><img src="../screenshots/jobs.png" alt="Jobs" width="280" /><br/><strong>Pekerjaan</strong></summary>
<img src="../screenshots/jobs.png" alt="Jobs" width="800" />
</details>
</td>
<td align="center" width="33%">
<details>
<summary><img src="../screenshots/memory.png" alt="Memory" width="280" /><br/><strong>Memori</strong></summary>
<img src="../screenshots/memory.png" alt="Memory" width="800" />
</details>
</td>
</tr>
</table>

<p align="center"><sub>Klik mana-mana tangkapan skrin untuk besarkan</sub></p>

---

## Mula Pantas

1. **Muat turun dan pasang** dari bahagian [Muat Turun](#muat-turun) di atas
2. **Buka aplikasi** -- Chromium dimuat turun secara automatik pada pelancaran pertama (~400 MB, sekali sahaja)
3. **Wizard persediaan** membimbing anda melalui: **Pembekal LLM** → **Muat naik resume** (mengurai profil anda secara automatik) → **Semak profil** → Sedia
4. **Kumpul pekerjaan** -- pergi ke **Jobs** → masukkan jawatan → **Start Collecting**
5. **Mohon** -- pergi ke **Apply** → **Start Applying** dan pantau papan pemuka semasa permohonan dihantar

---

## Cara Ia Berfungsi

LangHire menjalankan gelung tiga peringkat: **Kumpul → Mohon → Belajar**.

**Kumpul** -- Ejen pelayar AI log masuk ke LinkedIn, mencari pekerjaan yang sepadan dengan jawatan dan lokasi sasaran anda, dan menyimpan setiap senarai dengan URL, syarikat, jawatan, dan deskripsinya.

**Mohon** -- Untuk setiap pekerjaan yang menunggu, ejen membuka permohonan (Easy Apply atau ATS luaran), mengisi setiap medan menggunakan profil anda, memuat naik resume anda, menjawab soalan saringan dari bank Q&A, dan menghantar. Berbilang worker boleh berjalan secara selari.

**Belajar** -- Selepas setiap permohonan, sistem mengekstrak pembelajaran prosedur: butang mana yang perlu diklik, bagaimana borang distruktur, apa yang gagal dan apa yang berjaya. Memori ini disimpan per-domain ATS dengan skor keyakinan, jadi kali seterusnya ia menemui ATS yang sama, ia sudah tahu cara menavigasi.

### Seni Bina

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

Semua data disimpan secara setempat:

| OS | Laluan |
|----|------|
| macOS | `~/Library/Application Support/langhire/` |
| Windows | `%APPDATA%/langhire/` |
| Linux | `~/.config/langhire/` |

---

## Persediaan Pembangunan

### Prasyarat

| Alat | Versi | Pemasangan |
|------|---------|---------|
| Node.js | 18+ | [nodejs.org](https://nodejs.org) |
| Rust | 1.77+ | `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \| sh` |
| Python | 3.13+ | [python.org](https://python.org) |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |

### Klon dan Pasang

```bash
git clone https://github.com/jaimaann/LangHire.git
cd LangHire

npm install                                    # Node dependencies
uv sync                                        # Python dependencies
uv run python -m playwright install chromium   # Browser engine
```

### Jalankan dalam Mod Pembangunan

Dua terminal:

```bash
# Terminal 1 -- Python backend
uv run python backend/main.py

# Terminal 2 -- Frontend dev server
npm run dev
```

Buka http://localhost:1420, atau jalankan sebagai aplikasi desktop natif:

```bash
# Terminal 2 (alternative) -- Native Tauri app
cargo tauri dev
```

> `cargo tauri dev` pertama mengkompil shell Rust (~2 min). Pelancaran seterusnya adalah pantas.

### Bina untuk Pengeluaran

```bash
cargo tauri build
```

Menghasilkan pemasang khusus platform dalam `src-tauri/target/release/bundle/`.

---

## Struktur Projek

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

## Penggunaan CLI

Skrip CLI berfungsi secara kendiri bersama aplikasi desktop:

```bash
# Kumpul pekerjaan dari LinkedIn
uv run python cli/collect_jobs.py

# Mohon pekerjaan (3 worker selari)
uv run python cli/apply_jobs.py --workers 3

# Mohon dengan resume tersuai per-pekerjaan
uv run python cli/apply_jobs_tailored.py --workers 2

# Pengurusan memori
uv run python cli/memory_cli.py stats
uv run python cli/memory_cli.py domains
uv run python cli/memory_cli.py show linkedin.com

# Papan pemuka prestasi terminal
uv run python cli/dashboard.py
```

---

## Menyumbang

Sumbangan dialu-alukan. Lihat [CONTRIBUTING.md](../CONTRIBUTING.md) untuk garis panduan penuh.

```bash
git clone https://github.com/jaimaann/LangHire.git
cd LangHire
npm install && uv sync
uv run python backend/main.py   # Terminal 1
npm run dev                     # Terminal 2
```

**Bidang yang memerlukan bantuan:**

- **Lebih banyak platform pekerjaan** -- Indeed, Glassdoor, dan laman senarai pekerjaan lain selain LinkedIn
- **Sokongan LLM setempat** -- Ollama, llama.cpp, dan pilihan inferens setempat yang lain
- **Sokongan pelbagai negara** -- Laman pekerjaan setempat, format alamat, dan aliran kebenaran kerja
- **Dokumentasi** -- Tutorial, panduan video, dan panduan
- **Ujian** -- Liputan ujian unit, integrasi, dan E2E

---

## Lesen

[MIT](../LICENSE)

---

## Penafian

Alat ini mengautomasi permohonan kerja di LinkedIn dan platform lain. Gunakannya secara bertanggungjawab:

- Hormati Terma Perkhidmatan dan had kadar setiap platform
- Jangan spam majikan dengan permohonan berkualiti rendah
- Semak profil dan tetapan anda sebelum menjalankan permohonan automatik
- Anda bertanggungjawab untuk semua permohonan yang dihantar melalui alat ini

---

<p align="center">
  Dibina dengan <a href="https://tauri.app">Tauri</a>, <a href="https://react.dev">React</a>, <a href="https://python.org">Python</a>, dan <a href="https://github.com/browser-use/browser-use">browser-use</a>
</p>
