<p align="center">
  <img src="../src-tauri/icons/icon.png" alt="LangHire" width="120" />
</p>

<h1 align="center">LangHire</h1>

<p align="center">
  <strong>Automatisation des candidatures par IA avec une interface de bureau native</strong>
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
  <a href="README.fr.md"><strong>Français</strong></a> &middot;
  <a href="README.es.md">Español</a> &middot;
  <a href="README.ar.md">العربية</a> &middot;
  <a href="README.nl.md">Nederlands</a> &middot;
  <a href="README.ja.md">日本語</a> &middot;
  <a href="README.ko.md">한국어</a> &middot;
  <a href="README.pt.md">Português</a> &middot;
  <a href="README.ms.md">Bahasa Melayu</a>
</p>

---

Postuler à des emplois est fastidieux. Vous trouvez une annonce, cliquez vers la candidature, remplissez les mêmes champs que la veille, répondez aux mêmes questions de présélection, téléversez votre CV à nouveau — et ce cinquante fois. LangHire automatise l'ensemble du processus.

Il utilise des agents navigateur IA pour rechercher sur LinkedIn, collecter les offres correspondantes, remplir les candidatures, téléverser votre CV et soumettre — tandis qu'un **système de mémoire auto-apprenant** retient le fonctionnement de chaque système de suivi des candidatures (ATS) pour devenir plus rapide et plus précis au fil du temps. Tout fonctionne localement sur votre machine. Aucune donnée ne quitte votre ordinateur sauf les appels API LLM.

---

## Téléchargement

<div align="center">

| <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/apple/apple-original.svg" width="16" /> macOS | <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/windows11/windows11-original.svg" width="16" /> Windows | <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/linux/linux-original.svg" width="16" /> Linux |
|:---:|:---:|:---:|
| [**Apple Silicon (.dmg)**](https://github.com/jaimaann/LangHire/releases/latest/download/LangHire_1.0.0_aarch64.dmg) | [**64-bit Installer (.exe)**](https://github.com/jaimaann/LangHire/releases/latest/download/LangHire_1.0.0_x64-setup.exe) | [**AppImage (Universal)**](https://github.com/jaimaann/LangHire/releases/latest/download/LangHire_1.0.0_amd64.AppImage) |
| [Intel (.dmg)](https://github.com/jaimaann/LangHire/releases/latest/download/LangHire_1.0.0_x64.dmg) | | [Debian / Ubuntu x64 (.deb)](https://github.com/jaimaann/LangHire/releases/latest/download/LangHire_1.0.0_amd64.deb) |
| | | [Debian / Ubuntu ARM64 (.deb)](https://github.com/jaimaann/LangHire/releases/latest/download/LangHire_1.0.0_arm64.deb) |

</div>

<p align="center"><sub>Nécessite une clé API LLM (OpenAI, Anthropic ou AWS). Chromium est installé automatiquement au premier lancement. Voir <a href="#démarrage-rapide">Démarrage rapide</a>.</sub></p>

> **Développeurs** -- Voir [Configuration de développement](#configuration-de-développement) pour exécuter depuis le code source.

### Notes d'installation

<details>
<summary><strong>macOS</strong></summary>

La version macOS est **signée et notariée** par Apple. Ouvrez simplement le `.dmg`, glissez LangHire dans Applications et double-cliquez pour lancer. Aucune étape supplémentaire nécessaire.
</details>

<details>
<summary><strong>Windows</strong> -- "Windows a protégé votre PC" (SmartScreen)</summary>

L'installateur Windows n'est pas signé numériquement. Vous pourriez voir un avertissement SmartScreen :

1. Exécutez l'installateur `.exe`
2. Si vous voyez **"Windows a protégé votre PC"** :
   - Cliquez sur **Informations complémentaires**
   - Cliquez sur **Exécuter quand même**
3. Terminez l'installation et lancez LangHire
</details>

<details>
<summary><strong>Linux</strong> -- AppImage ou .deb</summary>

**AppImage :**
```bash
chmod +x LangHire_1.0.0_amd64.AppImage
./LangHire_1.0.0_amd64.AppImage
```

**Debian / Ubuntu :**
```bash
# Install uv package manager (required for browser management)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install the app
sudo dpkg -i LangHire_1.0.0_arm64.deb
```

> [!TIP]
> **Si Chromium ne se lance pas :** Certaines distributions Linux (comme Ubuntu 24.04+) ont des restrictions de sandbox. Exécutez ceci pour installer manuellement les navigateurs et dépendances :
> ```bash
> uvx playwright install --with-deps chromium
> ```
</details>

---

## Fonctionnalités

- **Application de bureau native** -- macOS, Windows et Linux
- **Collecte d'offres** -- Recherche sur LinkedIn les offres correspondant à vos titres et localisations cibles
- **Candidatures automatisées** -- L'agent IA remplit les formulaires, téléverse votre CV, répond aux questions de présélection
- **CV personnalisés** (bêta) -- Adapte automatiquement votre CV à chaque description de poste
- **Mémoire auto-apprenante** -- Stocke les connaissances procédurales par ATS (schémas de navigation, stratégies de formulaires, particularités d'interface). Les leçons d'un site Workday s'appliquent à tous les sites Workday.
- **Réutilisation intelligente des Q&R** -- Apprend les réponses des candidatures précédentes et les réutilise
- **Support multi-LLM** -- OpenAI, Anthropic, AWS Bedrock ou Ollama pour les modèles locaux
- **Tableau de bord** -- Statistiques en temps réel, taux de réussite, performance par domaine, analyse de l'impact mémoire
- **Outils CLI** -- Scripts pour utilisateurs avancés pour la collecte, les candidatures, la gestion de la mémoire et l'analytique
- **100% local** -- Toutes les données sont stockées sur votre machine dans le répertoire de données d'application de votre OS

---

## Captures d'écran

<table>
<tr>
<td align="center" width="33%">
<details>
<summary><img src="../screenshots/dashboard.png" alt="Dashboard" width="280" /><br/><strong>Tableau de bord</strong></summary>
<img src="../screenshots/dashboard.png" alt="Dashboard" width="800" />
</details>
</td>
<td align="center" width="33%">
<details>
<summary><img src="../screenshots/jobs.png" alt="Jobs" width="280" /><br/><strong>Offres</strong></summary>
<img src="../screenshots/jobs.png" alt="Jobs" width="800" />
</details>
</td>
<td align="center" width="33%">
<details>
<summary><img src="../screenshots/memory.png" alt="Memory" width="280" /><br/><strong>Mémoire</strong></summary>
<img src="../screenshots/memory.png" alt="Memory" width="800" />
</details>
</td>
</tr>
</table>

<p align="center"><sub>Cliquez sur une capture d'écran pour agrandir</sub></p>

---

## Démarrage rapide

1. **Téléchargez et installez** depuis la section [Téléchargement](#téléchargement) ci-dessus
2. **Ouvrez l'application** -- Chromium se télécharge automatiquement au premier lancement (~400 Mo, une seule fois)
3. **L'assistant de configuration** vous guide : **Fournisseur LLM** → **Téléversement du CV** (analyse automatiquement votre profil) → **Vérification du profil** → Prêt
4. **Collectez des offres** -- allez dans **Jobs** → entrez un titre de poste → **Start Collecting**
5. **Postulez** -- allez dans **Apply** → **Start Applying** et observez le tableau de bord pendant que les candidatures sont envoyées

---

## Comment ça marche

LangHire exécute une boucle en trois étapes : **Collecter → Postuler → Apprendre**.

**Collecter** -- Un agent navigateur IA se connecte à LinkedIn, recherche des offres correspondant à vos titres et localisations cibles, et enregistre chaque annonce avec son URL, entreprise, titre et description.

**Postuler** -- Pour chaque offre en attente, l'agent ouvre la candidature (Easy Apply ou ATS externe), remplit chaque champ avec votre profil, téléverse votre CV, répond aux questions de présélection depuis sa banque de Q&R, et soumet. Plusieurs workers peuvent fonctionner en parallèle.

**Apprendre** -- Après chaque candidature, le système extrait des apprentissages procéduraux : quels boutons cliquer, comment les formulaires sont structurés, ce qui échoue et ce qui fonctionne. Ces mémoires sont stockées par domaine ATS avec des scores de confiance, de sorte que la prochaine fois qu'il rencontre le même ATS, il sait déjà comment naviguer.

### Architecture

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

Toutes les données sont stockées localement :

| OS | Chemin |
|----|------|
| macOS | `~/Library/Application Support/langhire/` |
| Windows | `%APPDATA%/langhire/` |
| Linux | `~/.config/langhire/` |

---

## Configuration de développement

### Prérequis

| Outil | Version | Installation |
|------|---------|---------|
| Node.js | 18+ | [nodejs.org](https://nodejs.org) |
| Rust | 1.77+ | `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \| sh` |
| Python | 3.13+ | [python.org](https://python.org) |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |

### Cloner et installer

```bash
git clone https://github.com/jaimaann/LangHire.git
cd LangHire

npm install                                    # Node dependencies
uv sync                                        # Python dependencies
uv run python -m playwright install chromium   # Browser engine
```

### Exécuter en développement

Deux terminaux :

```bash
# Terminal 1 -- Python backend
uv run python backend/main.py

# Terminal 2 -- Frontend dev server
npm run dev
```

Ouvrez http://localhost:1420, ou exécutez plutôt en tant qu'application de bureau native :

```bash
# Terminal 2 (alternative) -- Native Tauri app
cargo tauri dev
```

> Le premier `cargo tauri dev` compile le shell Rust (~2 min). Les exécutions suivantes sont rapides.

### Compiler pour la production

```bash
cargo tauri build
```

Produit des installateurs spécifiques à la plateforme dans `src-tauri/target/release/bundle/`.

---

## Structure du projet

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

## Utilisation du CLI

Les scripts CLI fonctionnent de manière autonome aux côtés de l'application de bureau :

```bash
# Collecter des offres depuis LinkedIn
uv run python cli/collect_jobs.py

# Postuler aux offres (3 workers parallèles)
uv run python cli/apply_jobs.py --workers 3

# Postuler avec des CV personnalisés par offre
uv run python cli/apply_jobs_tailored.py --workers 2

# Gestion de la mémoire
uv run python cli/memory_cli.py stats
uv run python cli/memory_cli.py domains
uv run python cli/memory_cli.py show linkedin.com

# Tableau de bord de performance terminal
uv run python cli/dashboard.py
```

---

## Contribuer

Les contributions sont les bienvenues. Voir [CONTRIBUTING.md](../CONTRIBUTING.md) pour les directives complètes.

```bash
git clone https://github.com/jaimaann/LangHire.git
cd LangHire
npm install && uv sync
uv run python backend/main.py   # Terminal 1
npm run dev                     # Terminal 2
```

**Domaines où de l'aide est nécessaire :**

- **Plus de plateformes d'emploi** -- Indeed, Glassdoor et d'autres sites d'offres au-delà de LinkedIn
- **Support LLM local** -- Ollama, llama.cpp et d'autres options d'inférence locale
- **Support multi-pays** -- Sites d'emploi localisés, formats d'adresse et flux d'autorisation de travail
- **Documentation** -- Tutoriels, guides vidéo et guides
- **Tests** -- Couverture de tests unitaires, d'intégration et E2E

---

## Licence

[MIT](../LICENSE)

---

## Avertissement

Cet outil automatise les candidatures sur LinkedIn et d'autres plateformes. Utilisez-le de manière responsable :

- Respectez les conditions d'utilisation et les limites de débit de chaque plateforme
- Ne spammez pas les employeurs avec des candidatures de faible qualité
- Vérifiez votre profil et vos paramètres avant de lancer des candidatures automatisées
- Vous êtes responsable de toutes les candidatures soumises via cet outil

---

<p align="center">
  Construit avec <a href="https://tauri.app">Tauri</a>, <a href="https://react.dev">React</a>, <a href="https://python.org">Python</a> et <a href="https://github.com/browser-use/browser-use">browser-use</a>
</p>
