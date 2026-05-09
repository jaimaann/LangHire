<p align="center">
  <img src="../src-tauri/icons/icon.png" alt="LangHire" width="120" />
</p>

<h1 align="center">LangHire</h1>

<p align="center">
  <strong>Automatización de solicitudes de empleo impulsada por IA con interfaz de escritorio nativa</strong>
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
  <a href="README.es.md"><strong>Español</strong></a> &middot;
  <a href="README.ar.md">العربية</a> &middot;
  <a href="README.nl.md">Nederlands</a> &middot;
  <a href="README.ja.md">日本語</a> &middot;
  <a href="README.ko.md">한국어</a> &middot;
  <a href="README.pt.md">Português</a> &middot;
  <a href="README.ms.md">Bahasa Melayu</a>
</p>

---

Solicitar empleos es tedioso. Encuentras una oferta, haces clic en la solicitud, rellenas los mismos campos que ayer, respondes las mismas preguntas de selección, subes tu currículum de nuevo — repite cincuenta veces. LangHire automatiza todo el ciclo.

Utiliza agentes de navegador con IA para buscar en LinkedIn, recopilar ofertas relevantes, rellenar solicitudes, subir tu currículum y enviar — mientras un **sistema de memoria auto-aprendizaje** recuerda cómo funciona cada sistema de seguimiento de candidatos (ATS) para volverse más rápido y preciso con el tiempo. Todo se ejecuta localmente en tu máquina. Ningún dato sale de tu computadora excepto las llamadas a la API del LLM.

---

## Descarga

<div align="center">

| <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/apple/apple-original.svg" width="16" /> macOS | <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/windows11/windows11-original.svg" width="16" /> Windows | <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/linux/linux-original.svg" width="16" /> Linux |
|:---:|:---:|:---:|
| [**Apple Silicon (.dmg)**](https://github.com/jaimaann/LangHire/releases/latest/download/LangHire_1.0.0_aarch64.dmg) | [**64-bit Installer (.exe)**](https://github.com/jaimaann/LangHire/releases/latest/download/LangHire_1.0.0_x64-setup.exe) | [**AppImage (Universal)**](https://github.com/jaimaann/LangHire/releases/latest/download/LangHire_1.0.0_amd64.AppImage) |
| [Intel (.dmg)](https://github.com/jaimaann/LangHire/releases/latest/download/LangHire_1.0.0_x64.dmg) | | [Debian / Ubuntu x64 (.deb)](https://github.com/jaimaann/LangHire/releases/latest/download/LangHire_1.0.0_amd64.deb) |
| | | [Debian / Ubuntu ARM64 (.deb)](https://github.com/jaimaann/LangHire/releases/latest/download/LangHire_1.0.0_arm64.deb) |

</div>

<p align="center"><sub>Requiere una clave API de LLM (OpenAI, Anthropic o AWS). Chromium se instala automáticamente en el primer inicio. Ver <a href="#inicio-rápido">Inicio rápido</a>.</sub></p>

> **Desarrolladores** -- Ver [Configuración de desarrollo](#configuración-de-desarrollo) para ejecutar desde el código fuente.

### Notas de instalación

<details>
<summary><strong>macOS</strong></summary>

La versión de macOS está **firmada y notarizada** por Apple. Simplemente abre el `.dmg`, arrastra LangHire a Aplicaciones y haz doble clic para iniciar. No se necesitan pasos adicionales.
</details>

<details>
<summary><strong>Windows</strong> -- "Windows protegió tu PC" (SmartScreen)</summary>

El instalador de Windows no está firmado digitalmente. Podrías ver una advertencia de SmartScreen:

1. Ejecuta el instalador `.exe`
2. Si ves **"Windows protegió tu PC"**:
   - Haz clic en **Más información**
   - Haz clic en **Ejecutar de todas formas**
3. Completa el instalador e inicia LangHire
</details>

<details>
<summary><strong>Linux</strong> -- AppImage o .deb</summary>

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
> **Si Chromium no se inicia:** Algunas distribuciones de Linux (como Ubuntu 24.04+) tienen restricciones de sandbox. Ejecuta esto para instalar manualmente los navegadores y dependencias:
> ```bash
> uvx playwright install --with-deps chromium
> ```
</details>

---

## Características

- **Aplicación de escritorio nativa** -- macOS, Windows y Linux
- **Recopilación de empleos** -- Busca en LinkedIn ofertas que coincidan con tus títulos y ubicaciones objetivo
- **Solicitudes automatizadas** -- El agente IA rellena formularios, sube tu currículum, responde preguntas de selección
- **Currículums personalizados** (beta) -- Personaliza automáticamente tu currículum para cada descripción de puesto
- **Memoria auto-aprendizaje** -- Almacena conocimiento procedimental por ATS (patrones de navegación, estrategias de formularios, peculiaridades de la interfaz). Las lecciones de un sitio Workday se aplican a todos los sitios Workday.
- **Reutilización inteligente de Q&A** -- Aprende respuestas de solicitudes anteriores y las reutiliza
- **Soporte multi-LLM** -- OpenAI, Anthropic, AWS Bedrock u Ollama para modelos locales
- **Panel de control** -- Estadísticas en tiempo real, tasas de éxito, rendimiento por dominio, análisis del impacto de memoria
- **Herramientas CLI** -- Scripts para usuarios avanzados para recopilación, solicitudes, gestión de memoria y analítica
- **100% local** -- Todos los datos se almacenan en tu máquina en el directorio de datos de la aplicación del SO

---

## Capturas de pantalla

<table>
<tr>
<td align="center" width="33%">
<details>
<summary><img src="../screenshots/dashboard.png" alt="Dashboard" width="280" /><br/><strong>Panel de control</strong></summary>
<img src="../screenshots/dashboard.png" alt="Dashboard" width="800" />
</details>
</td>
<td align="center" width="33%">
<details>
<summary><img src="../screenshots/jobs.png" alt="Jobs" width="280" /><br/><strong>Empleos</strong></summary>
<img src="../screenshots/jobs.png" alt="Jobs" width="800" />
</details>
</td>
<td align="center" width="33%">
<details>
<summary><img src="../screenshots/memory.png" alt="Memory" width="280" /><br/><strong>Memoria</strong></summary>
<img src="../screenshots/memory.png" alt="Memory" width="800" />
</details>
</td>
</tr>
</table>

<p align="center"><sub>Haz clic en cualquier captura de pantalla para ampliar</sub></p>

---

## Inicio rápido

1. **Descarga e instala** desde la sección [Descarga](#descarga) anterior
2. **Abre la aplicación** -- Chromium se descarga automáticamente en el primer inicio (~400 MB, una sola vez)
3. **El asistente de configuración** te guía: **Proveedor LLM** → **Subir currículum** (analiza automáticamente tu perfil) → **Revisar perfil** → Listo
4. **Recopila empleos** -- ve a **Jobs** → ingresa un título de puesto → **Start Collecting**
5. **Postula** -- ve a **Apply** → **Start Applying** y observa el panel mientras las solicitudes se envían

---

## Cómo funciona

LangHire ejecuta un ciclo de tres etapas: **Recopilar → Postular → Aprender**.

**Recopilar** -- Un agente de navegador con IA inicia sesión en LinkedIn, busca ofertas que coincidan con tus títulos y ubicaciones objetivo, y guarda cada listado con su URL, empresa, título y descripción.

**Postular** -- Para cada empleo pendiente, el agente abre la solicitud (Easy Apply o ATS externo), rellena cada campo usando tu perfil, sube tu currículum, responde preguntas de selección desde su banco de Q&A y envía. Múltiples workers pueden ejecutarse en paralelo.

**Aprender** -- Después de cada solicitud, el sistema extrae aprendizajes procedimentales: qué botones hacer clic, cómo están estructurados los formularios, qué falla y qué funciona. Estas memorias se almacenan por dominio ATS con puntuaciones de confianza, de modo que la próxima vez que encuentre el mismo ATS, ya sabe cómo navegar.

### Arquitectura

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

Todos los datos se almacenan localmente:

| SO | Ruta |
|----|------|
| macOS | `~/Library/Application Support/langhire/` |
| Windows | `%APPDATA%/langhire/` |
| Linux | `~/.config/langhire/` |

---

## Configuración de desarrollo

### Requisitos previos

| Herramienta | Versión | Instalación |
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

### Ejecutar en desarrollo

Dos terminales:

```bash
# Terminal 1 -- Python backend
uv run python backend/main.py

# Terminal 2 -- Frontend dev server
npm run dev
```

Abre http://localhost:1420, o ejecútalo como aplicación de escritorio nativa:

```bash
# Terminal 2 (alternative) -- Native Tauri app
cargo tauri dev
```

> El primer `cargo tauri dev` compila el shell Rust (~2 min). Las ejecuciones posteriores son rápidas.

### Compilar para producción

```bash
cargo tauri build
```

Produce instaladores específicos de plataforma en `src-tauri/target/release/bundle/`.

---

## Estructura del proyecto

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

## Uso del CLI

Los scripts CLI funcionan de forma independiente junto a la aplicación de escritorio:

```bash
# Recopilar empleos de LinkedIn
uv run python cli/collect_jobs.py

# Postular a empleos (3 workers paralelos)
uv run python cli/apply_jobs.py --workers 3

# Postular con currículums personalizados por empleo
uv run python cli/apply_jobs_tailored.py --workers 2

# Gestión de memoria
uv run python cli/memory_cli.py stats
uv run python cli/memory_cli.py domains
uv run python cli/memory_cli.py show linkedin.com

# Panel de rendimiento en terminal
uv run python cli/dashboard.py
```

---

## Contribuir

Las contribuciones son bienvenidas. Ver [CONTRIBUTING.md](../CONTRIBUTING.md) para las directrices completas.

```bash
git clone https://github.com/jaimaann/LangHire.git
cd LangHire
npm install && uv sync
uv run python backend/main.py   # Terminal 1
npm run dev                     # Terminal 2
```

**Áreas donde se necesita ayuda:**

- **Más plataformas de empleo** -- Indeed, Glassdoor y otros sitios de ofertas más allá de LinkedIn
- **Soporte de LLM local** -- Ollama, llama.cpp y otras opciones de inferencia local
- **Soporte multi-país** -- Sitios de empleo localizados, formatos de dirección y flujos de autorización de trabajo
- **Documentación** -- Tutoriales, recorridos en video y guías
- **Pruebas** -- Cobertura de pruebas unitarias, de integración y E2E

---

## Licencia

[MIT](../LICENSE)

---

## Descargo de responsabilidad

Esta herramienta automatiza las solicitudes de empleo en LinkedIn y otras plataformas. Úsala de forma responsable:

- Respeta los Términos de Servicio y los límites de velocidad de cada plataforma
- No envíes spam a los empleadores con solicitudes de baja calidad
- Revisa tu perfil y configuración antes de ejecutar solicitudes automatizadas
- Eres responsable de todas las solicitudes enviadas a través de esta herramienta

---

<p align="center">
  Construido con <a href="https://tauri.app">Tauri</a>, <a href="https://react.dev">React</a>, <a href="https://python.org">Python</a> y <a href="https://github.com/browser-use/browser-use">browser-use</a>
</p>
