<p align="center">
  <img src="../src-tauri/icons/icon.png" alt="LangHire" width="120" />
</p>

<h1 align="center">LangHire</h1>

<p align="center">
  <strong>Automatização de candidaturas a emprego com IA e interface de desktop nativa</strong>
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
  <a href="README.pt.md"><strong>Português</strong></a> &middot;
  <a href="README.ms.md">Bahasa Melayu</a>
</p>

---

Candidatar-se a empregos é tedioso. Você encontra uma vaga, clica para a candidatura, preenche os mesmos campos de ontem, responde às mesmas perguntas de triagem, envia o currículo novamente — repita cinquenta vezes. O LangHire automatiza todo o ciclo.

Ele usa agentes de navegador com IA para pesquisar no LinkedIn, coletar vagas compatíveis, preencher candidaturas, enviar seu currículo e submeter — enquanto um **sistema de memória auto-aprendiz** lembra como cada sistema de rastreamento de candidatos (ATS) funciona, ficando mais rápido e preciso com o tempo. Tudo roda localmente na sua máquina. Nenhum dado sai do seu computador exceto chamadas à API do LLM.

---

## Download

<div align="center">

| <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/apple/apple-original.svg" width="16" /> macOS | <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/windows11/windows11-original.svg" width="16" /> Windows | <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/linux/linux-original.svg" width="16" /> Linux |
|:---:|:---:|:---:|
| [**Apple Silicon (.dmg)**](https://github.com/jaimaann/LangHire/releases/latest/download/LangHire_1.0.0_aarch64.dmg) | [**64-bit Installer (.exe)**](https://github.com/jaimaann/LangHire/releases/latest/download/LangHire_1.0.0_x64-setup.exe) | [**AppImage (Universal)**](https://github.com/jaimaann/LangHire/releases/latest/download/LangHire_1.0.0_amd64.AppImage) |
| [Intel (.dmg)](https://github.com/jaimaann/LangHire/releases/latest/download/LangHire_1.0.0_x64.dmg) | | [Debian / Ubuntu x64 (.deb)](https://github.com/jaimaann/LangHire/releases/latest/download/LangHire_1.0.0_amd64.deb) |
| | | [Debian / Ubuntu ARM64 (.deb)](https://github.com/jaimaann/LangHire/releases/latest/download/LangHire_1.0.0_arm64.deb) |

</div>

<p align="center"><sub>Requer uma chave API de LLM (OpenAI, Anthropic ou AWS). O Chromium é instalado automaticamente na primeira execução. Veja <a href="#início-rápido">Início rápido</a>.</sub></p>

> **Desenvolvedores** -- Veja [Configuração de desenvolvimento](#configuração-de-desenvolvimento) para executar a partir do código-fonte.

### Notas de instalação

<details>
<summary><strong>macOS</strong></summary>

A versão macOS é **assinada e autenticada** pela Apple. Basta abrir o `.dmg`, arrastar o LangHire para Aplicativos e clicar duas vezes para iniciar. Nenhuma etapa extra necessária.
</details>

<details>
<summary><strong>Windows</strong> -- "O Windows protegeu seu PC" (SmartScreen)</summary>

O instalador do Windows não é assinado digitalmente. Você pode ver um aviso do SmartScreen:

1. Execute o instalador `.exe`
2. Se você vir **"O Windows protegeu seu PC"**:
   - Clique em **Mais informações**
   - Clique em **Executar mesmo assim**
3. Complete a instalação e inicie o LangHire
</details>

<details>
<summary><strong>Linux</strong> -- AppImage ou .deb</summary>

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
> **Se o Chromium não iniciar:** Algumas distribuições Linux (como Ubuntu 24.04+) têm restrições de sandbox. Execute isto para instalar manualmente os navegadores e dependências:
> ```bash
> uvx playwright install --with-deps chromium
> ```
</details>

---

## Funcionalidades

- **Aplicativo de desktop nativo** -- macOS, Windows e Linux
- **Coleta de vagas** -- Pesquisa no LinkedIn vagas que correspondam aos seus títulos e localizações alvo
- **Candidaturas automatizadas** -- Agente AI preenche formulários, envia seu currículo, responde perguntas de triagem
- **Currículos personalizados** (beta) -- Personaliza automaticamente seu currículo para cada descrição de vaga
- **Memória auto-aprendiz** -- Armazena conhecimento procedimental por ATS (padrões de navegação, estratégias de formulários, peculiaridades da interface). Lições de um site Workday se aplicam a todos os sites Workday.
- **Reutilização inteligente de Q&A** -- Aprende respostas de candidaturas anteriores e as reutiliza
- **Suporte multi-LLM** -- OpenAI, Anthropic, AWS Bedrock ou Ollama para modelos locais
- **Painel de controle** -- Estatísticas em tempo real, taxas de sucesso, desempenho por domínio, análise de impacto da memória
- **Ferramentas CLI** -- Scripts para usuários avançados para coleta, candidatura, gerenciamento de memória e análises
- **100% local** -- Todos os dados armazenados na sua máquina no diretório de dados do aplicativo do SO

---

## Capturas de tela

<table>
<tr>
<td align="center" width="33%">
<details>
<summary><img src="../screenshots/dashboard.png" alt="Dashboard" width="280" /><br/><strong>Painel de controle</strong></summary>
<img src="../screenshots/dashboard.png" alt="Dashboard" width="800" />
</details>
</td>
<td align="center" width="33%">
<details>
<summary><img src="../screenshots/jobs.png" alt="Jobs" width="280" /><br/><strong>Vagas</strong></summary>
<img src="../screenshots/jobs.png" alt="Jobs" width="800" />
</details>
</td>
<td align="center" width="33%">
<details>
<summary><img src="../screenshots/memory.png" alt="Memory" width="280" /><br/><strong>Memória</strong></summary>
<img src="../screenshots/memory.png" alt="Memory" width="800" />
</details>
</td>
</tr>
</table>

<p align="center"><sub>Clique em qualquer captura de tela para ampliar</sub></p>

---

## Início rápido

1. **Baixe e instale** a partir da seção [Download](#download) acima
2. **Abra o aplicativo** -- O Chromium é baixado automaticamente na primeira execução (~400 MB, uma vez)
3. **Assistente de configuração** guia você: **Provedor LLM** → **Upload do currículo** (analisa automaticamente seu perfil) → **Revisar perfil** → Pronto
4. **Colete vagas** -- vá para **Jobs** → digite um título de cargo → **Start Collecting**
5. **Candidate-se** -- vá para **Apply** → **Start Applying** e acompanhe o painel enquanto as candidaturas são enviadas

---

## Como funciona

O LangHire executa um ciclo de três etapas: **Coletar → Candidatar → Aprender**.

**Coletar** -- Um agente de navegador com IA faz login no LinkedIn, pesquisa vagas que correspondam aos seus títulos e localizações alvo, e salva cada listagem com URL, empresa, título e descrição.

**Candidatar** -- Para cada vaga pendente, o agente abre a candidatura (Easy Apply ou ATS externo), preenche todos os campos usando seu perfil, envia seu currículo, responde perguntas de triagem do seu banco de Q&A e submete. Múltiplos workers podem executar em paralelo.

**Aprender** -- Após cada candidatura, o sistema extrai aprendizados procedimentais: quais botões clicar, como os formulários são estruturados, o que falha e o que funciona. Essas memórias são armazenadas por domínio ATS com pontuações de confiança, para que na próxima vez que encontrar o mesmo ATS, já saiba como navegar.

### Arquitetura

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

Todos os dados são armazenados localmente:

| SO | Caminho |
|----|------|
| macOS | `~/Library/Application Support/langhire/` |
| Windows | `%APPDATA%/langhire/` |
| Linux | `~/.config/langhire/` |

---

## Configuração de desenvolvimento

### Pré-requisitos

| Ferramenta | Versão | Instalação |
|------|---------|---------|
| Node.js | 18+ | [nodejs.org](https://nodejs.org) |
| Rust | 1.77+ | `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \| sh` |
| Python | 3.13+ | [python.org](https://python.org) |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |

### Clonar e instalar

```bash
git clone https://github.com/jaimaann/LangHire.git
cd LangHire

npm install                                    # Node dependencies
uv sync                                        # Python dependencies
uv run python -m playwright install chromium   # Browser engine
```

### Executar em desenvolvimento

Dois terminais:

```bash
# Terminal 1 -- Python backend
uv run python backend/main.py

# Terminal 2 -- Frontend dev server
npm run dev
```

Abra http://localhost:1420, ou execute como aplicativo de desktop nativo:

```bash
# Terminal 2 (alternative) -- Native Tauri app
cargo tauri dev
```

> O primeiro `cargo tauri dev` compila o shell Rust (~2 min). Execuções subsequentes são rápidas.

### Compilar para produção

```bash
cargo tauri build
```

Produz instaladores específicos da plataforma em `src-tauri/target/release/bundle/`.

---

## Estrutura do projeto

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

## Uso do CLI

Os scripts CLI funcionam de forma independente junto ao aplicativo de desktop:

```bash
# Coletar vagas do LinkedIn
uv run python cli/collect_jobs.py

# Candidatar-se a vagas (3 workers paralelos)
uv run python cli/apply_jobs.py --workers 3

# Candidatar-se com currículos personalizados por vaga
uv run python cli/apply_jobs_tailored.py --workers 2

# Gerenciamento de memória
uv run python cli/memory_cli.py stats
uv run python cli/memory_cli.py domains
uv run python cli/memory_cli.py show linkedin.com

# Painel de desempenho no terminal
uv run python cli/dashboard.py
```

---

## Contribuindo

Contribuições são bem-vindas. Veja [CONTRIBUTING.md](../CONTRIBUTING.md) para diretrizes completas.

```bash
git clone https://github.com/jaimaann/LangHire.git
cd LangHire
npm install && uv sync
uv run python backend/main.py   # Terminal 1
npm run dev                     # Terminal 2
```

**Áreas onde ajuda é necessária:**

- **Mais plataformas de emprego** -- Indeed, Glassdoor e outros sites de vagas além do LinkedIn
- **Suporte a LLM local** -- Ollama, llama.cpp e outras opções de inferência local
- **Suporte multi-país** -- Sites de emprego localizados, formatos de endereço e fluxos de autorização de trabalho
- **Documentação** -- Tutoriais, vídeos explicativos e guias
- **Testes** -- Cobertura de testes unitários, de integração e E2E

---

## Licença

[MIT](../LICENSE)

---

## Aviso legal

Esta ferramenta automatiza candidaturas a emprego no LinkedIn e outras plataformas. Use de forma responsável:

- Respeite os Termos de Serviço e limites de taxa de cada plataforma
- Não envie spam para empregadores com candidaturas de baixa qualidade
- Revise seu perfil e configurações antes de executar candidaturas automatizadas
- Você é responsável por todas as candidaturas enviadas através desta ferramenta

---

<p align="center">
  Construído com <a href="https://tauri.app">Tauri</a>, <a href="https://react.dev">React</a>, <a href="https://python.org">Python</a> e <a href="https://github.com/browser-use/browser-use">browser-use</a>
</p>
