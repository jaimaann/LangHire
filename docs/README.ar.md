<p align="center">
  <img src="../src-tauri/icons/icon.png" alt="LangHire" width="120" />
</p>

<h1 align="center">LangHire</h1>

<p align="center">
  <strong>أتمتة التقديم على الوظائف بالذكاء الاصطناعي مع واجهة سطح مكتب أصلية</strong>
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
  <a href="README.ar.md"><strong>العربية</strong></a> &middot;
  <a href="README.nl.md">Nederlands</a> &middot;
  <a href="README.ja.md">日本語</a> &middot;
  <a href="README.ko.md">한국어</a> &middot;
  <a href="README.pt.md">Português</a> &middot;
  <a href="README.ms.md">Bahasa Melayu</a>
</p>

---

التقديم على الوظائف أمر ممل. تجد إعلان وظيفة، تنقر للوصول إلى الطلب، تملأ نفس الحقول التي ملأتها بالأمس، تجيب على نفس أسئلة الفحص، ترفع سيرتك الذاتية مرة أخرى — كرر ذلك خمسين مرة. LangHire يؤتمت الدورة بأكملها.

يستخدم وكلاء متصفح بالذكاء الاصطناعي للبحث في LinkedIn، وجمع الوظائف المطابقة، وملء الطلبات، ورفع سيرتك الذاتية، والإرسال — بينما يتذكر **نظام ذاكرة ذاتي التعلم** كيف يعمل كل نظام تتبع المتقدمين (ATS) ليصبح أسرع وأكثر دقة مع مرور الوقت. كل شيء يعمل محلياً على جهازك. لا تغادر أي بيانات حاسوبك باستثناء استدعاءات API الخاصة بـ LLM.

---

## التحميل

<div align="center">

| <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/apple/apple-original.svg" width="16" /> macOS | <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/windows11/windows11-original.svg" width="16" /> Windows | <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/linux/linux-original.svg" width="16" /> Linux |
|:---:|:---:|:---:|
| [**Apple Silicon (.dmg)**](https://github.com/jaimaann/LangHire/releases/latest/download/LangHire_1.0.0_aarch64.dmg) | [**64-bit Installer (.exe)**](https://github.com/jaimaann/LangHire/releases/latest/download/LangHire_1.0.0_x64-setup.exe) | [**AppImage (Universal)**](https://github.com/jaimaann/LangHire/releases/latest/download/LangHire_1.0.0_amd64.AppImage) |
| [Intel (.dmg)](https://github.com/jaimaann/LangHire/releases/latest/download/LangHire_1.0.0_x64.dmg) | | [Debian / Ubuntu x64 (.deb)](https://github.com/jaimaann/LangHire/releases/latest/download/LangHire_1.0.0_amd64.deb) |
| | | [Debian / Ubuntu ARM64 (.deb)](https://github.com/jaimaann/LangHire/releases/latest/download/LangHire_1.0.0_arm64.deb) |

</div>

<p align="center"><sub>يتطلب مفتاح API لـ LLM (OpenAI أو Anthropic أو AWS). يُثبَّت Chromium تلقائياً عند أول تشغيل. انظر <a href="#البدء-السريع">البدء السريع</a>.</sub></p>

> **المطورون** -- انظر [إعداد التطوير](#إعداد-التطوير) للتشغيل من الكود المصدري.

### ملاحظات التثبيت

<details>
<summary><strong>macOS</strong></summary>

إصدار macOS **موقَّع ومعتمد** من Apple. فقط افتح ملف `.dmg`، اسحب LangHire إلى التطبيقات، وانقر نقراً مزدوجاً للتشغيل. لا حاجة لخطوات إضافية.
</details>

<details>
<summary><strong>Windows</strong> -- "Windows حمى جهاز الكمبيوتر الخاص بك" (SmartScreen)</summary>

مُثبِّت Windows غير موقَّع رقمياً. قد ترى تحذير SmartScreen:

1. شغِّل مُثبِّت `.exe`
2. إذا رأيت **"Windows حمى جهاز الكمبيوتر الخاص بك"**:
   - انقر على **مزيد من المعلومات**
   - انقر على **تشغيل على أي حال**
3. أكمل المُثبِّت وشغِّل LangHire
</details>

<details>
<summary><strong>Linux</strong> -- AppImage أو .deb</summary>

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
> **إذا لم يعمل Chromium:** بعض توزيعات Linux (مثل Ubuntu 24.04+) لديها قيود sandbox. شغِّل هذا لتثبيت المتصفحات والتبعيات يدوياً:
> ```bash
> uvx playwright install --with-deps chromium
> ```
</details>

---

## الميزات

- **تطبيق سطح مكتب أصلي** -- macOS وWindows وLinux
- **جمع الوظائف** -- يبحث في LinkedIn عن وظائف تطابق مسمياتك ومواقعك المستهدفة
- **طلبات تلقائية** -- وكيل AI يملأ النماذج، يرفع سيرتك الذاتية، يجيب على أسئلة الفحص
- **سير ذاتية مخصصة** (تجريبي) -- يخصص سيرتك الذاتية تلقائياً لكل وصف وظيفي
- **ذاكرة ذاتية التعلم** -- يخزن المعرفة الإجرائية لكل ATS (أنماط التنقل، استراتيجيات النماذج، خصائص الواجهة). الدروس المستفادة من موقع Workday واحد تنطبق على جميع مواقع Workday.
- **إعادة استخدام ذكية للأسئلة والأجوبة** -- يتعلم الإجابات من الطلبات السابقة ويعيد استخدامها
- **دعم متعدد LLM** -- OpenAI وAnthropic وAWS Bedrock أو Ollama للنماذج المحلية
- **لوحة تحكم** -- إحصائيات فورية، معدلات النجاح، الأداء حسب النطاق، تحليل تأثير الذاكرة
- **أدوات CLI** -- سكربتات للمستخدمين المتقدمين للجمع والتقديم وإدارة الذاكرة والتحليلات
- **محلي 100%** -- جميع البيانات مخزنة على جهازك في مجلد بيانات التطبيق الخاص بنظام التشغيل

---

## لقطات الشاشة

<table>
<tr>
<td align="center" width="33%">
<details>
<summary><img src="../screenshots/dashboard.png" alt="Dashboard" width="280" /><br/><strong>لوحة التحكم</strong></summary>
<img src="../screenshots/dashboard.png" alt="Dashboard" width="800" />
</details>
</td>
<td align="center" width="33%">
<details>
<summary><img src="../screenshots/jobs.png" alt="Jobs" width="280" /><br/><strong>الوظائف</strong></summary>
<img src="../screenshots/jobs.png" alt="Jobs" width="800" />
</details>
</td>
<td align="center" width="33%">
<details>
<summary><img src="../screenshots/memory.png" alt="Memory" width="280" /><br/><strong>الذاكرة</strong></summary>
<img src="../screenshots/memory.png" alt="Memory" width="800" />
</details>
</td>
</tr>
</table>

<p align="center"><sub>انقر على أي لقطة شاشة للتكبير</sub></p>

---

## البدء السريع

1. **حمِّل وثبِّت** من قسم [التحميل](#التحميل) أعلاه
2. **افتح التطبيق** -- يُحمَّل Chromium تلقائياً عند أول تشغيل (~400 ميجابايت، مرة واحدة)
3. **معالج الإعداد** يرشدك خلال: **مزود LLM** → **رفع السيرة الذاتية** (يحلل ملفك الشخصي تلقائياً) → **مراجعة الملف الشخصي** → جاهز
4. **اجمع الوظائف** -- اذهب إلى **Jobs** → أدخل مسمى وظيفي → **Start Collecting**
5. **قدِّم** -- اذهب إلى **Apply** → **Start Applying** وراقب لوحة التحكم بينما تُرسَل الطلبات

---

## كيف يعمل

يشغِّل LangHire حلقة من ثلاث مراحل: **جمع → تقديم → تعلم**.

**جمع** -- وكيل متصفح بالذكاء الاصطناعي يسجل الدخول إلى LinkedIn، يبحث عن وظائف تطابق مسمياتك ومواقعك المستهدفة، ويحفظ كل إعلان مع رابطه وشركته ومسماه ووصفه.

**تقديم** -- لكل وظيفة معلقة، يفتح الوكيل الطلب (Easy Apply أو ATS خارجي)، يملأ كل حقل باستخدام ملفك الشخصي، يرفع سيرتك الذاتية، يجيب على أسئلة الفحص من بنك الأسئلة والأجوبة، ويرسل. يمكن تشغيل عدة workers بالتوازي.

**تعلم** -- بعد كل طلب، يستخلص النظام دروساً إجرائية: أي أزرار يجب النقر عليها، كيف تُنظَّم النماذج، ما يفشل وما ينجح. تُخزَّن هذه الذكريات لكل نطاق ATS مع درجات ثقة، بحيث في المرة التالية التي يواجه فيها نفس ATS، يعرف مسبقاً كيف يتنقل.

### البنية المعمارية

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

جميع البيانات مخزنة محلياً:

| نظام التشغيل | المسار |
|----|------|
| macOS | `~/Library/Application Support/langhire/` |
| Windows | `%APPDATA%/langhire/` |
| Linux | `~/.config/langhire/` |

---

## إعداد التطوير

### المتطلبات الأساسية

| الأداة | الإصدار | التثبيت |
|------|---------|---------|
| Node.js | 18+ | [nodejs.org](https://nodejs.org) |
| Rust | 1.77+ | `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \| sh` |
| Python | 3.13+ | [python.org](https://python.org) |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |

### الاستنساخ والتثبيت

```bash
git clone https://github.com/jaimaann/LangHire.git
cd LangHire

npm install                                    # Node dependencies
uv sync                                        # Python dependencies
uv run python -m playwright install chromium   # Browser engine
```

### التشغيل في وضع التطوير

نافذتا طرفية:

```bash
# Terminal 1 -- Python backend
uv run python backend/main.py

# Terminal 2 -- Frontend dev server
npm run dev
```

افتح http://localhost:1420، أو شغِّله كتطبيق سطح مكتب أصلي بدلاً من ذلك:

```bash
# Terminal 2 (alternative) -- Native Tauri app
cargo tauri dev
```

> أول `cargo tauri dev` يُجمِّع غلاف Rust (~دقيقتان). التشغيلات اللاحقة سريعة.

### البناء للإنتاج

```bash
cargo tauri build
```

ينتج مُثبِّتات خاصة بالمنصة في `src-tauri/target/release/bundle/`.

---

## هيكل المشروع

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

## استخدام CLI

سكربتات CLI تعمل بشكل مستقل إلى جانب تطبيق سطح المكتب:

```bash
# جمع الوظائف من LinkedIn
uv run python cli/collect_jobs.py

# التقديم على الوظائف (3 workers متوازية)
uv run python cli/apply_jobs.py --workers 3

# التقديم بسير ذاتية مخصصة لكل وظيفة
uv run python cli/apply_jobs_tailored.py --workers 2

# إدارة الذاكرة
uv run python cli/memory_cli.py stats
uv run python cli/memory_cli.py domains
uv run python cli/memory_cli.py show linkedin.com

# لوحة أداء الطرفية
uv run python cli/dashboard.py
```

---

## المساهمة

المساهمات مرحب بها. انظر [CONTRIBUTING.md](../CONTRIBUTING.md) للإرشادات الكاملة.

```bash
git clone https://github.com/jaimaann/LangHire.git
cd LangHire
npm install && uv sync
uv run python backend/main.py   # Terminal 1
npm run dev                     # Terminal 2
```

**المجالات التي تحتاج مساعدة:**

- **المزيد من منصات التوظيف** -- Indeed وGlassdoor ومواقع إعلانات الوظائف الأخرى بخلاف LinkedIn
- **دعم LLM المحلي** -- Ollama وllama.cpp وخيارات الاستدلال المحلي الأخرى
- **دعم متعدد البلدان** -- مواقع توظيف محلية، تنسيقات عناوين، وتدفقات تصريح العمل
- **التوثيق** -- دروس تعليمية، عروض فيديو، وأدلة
- **الاختبار** -- تغطية اختبارات الوحدات والتكامل وE2E

---

## الترخيص

[MIT](../LICENSE)

---

## إخلاء المسؤولية

هذه الأداة تؤتمت طلبات التوظيف على LinkedIn ومنصات أخرى. استخدمها بمسؤولية:

- احترم شروط الخدمة وحدود المعدل لكل منصة
- لا ترسل رسائل مزعجة لأصحاب العمل بطلبات منخفضة الجودة
- راجع ملفك الشخصي وإعداداتك قبل تشغيل الطلبات التلقائية
- أنت مسؤول عن جميع الطلبات المقدمة من خلال هذه الأداة

---

<p align="center">
  مبني بـ <a href="https://tauri.app">Tauri</a> و<a href="https://react.dev">React</a> و<a href="https://python.org">Python</a> و<a href="https://github.com/browser-use/browser-use">browser-use</a>
</p>
