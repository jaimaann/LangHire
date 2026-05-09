<p align="center">
  <img src="../src-tauri/icons/icon.png" alt="LangHire" width="120" />
</p>

<h1 align="center">LangHire</h1>

<p align="center">
  <strong>नेटिव डेस्कटॉप UI के साथ AI-संचालित नौकरी आवेदन स्वचालन</strong>
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
  <a href="README.hi.md"><strong>हिन्दी</strong></a> &middot;
  <a href="README.de.md">Deutsch</a> &middot;
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

नौकरी के लिए आवेदन करना थकाऊ काम है। आप एक लिस्टिंग ढूंढते हैं, आवेदन पर क्लिक करते हैं, वही फ़ील्ड भरते हैं जो कल भरी थीं, वही स्क्रीनिंग प्रश्नों का उत्तर देते हैं, अपना रिज़्यूमे फिर से अपलोड करते हैं — यह पचास बार दोहराएं। LangHire पूरे इस चक्र को स्वचालित करता है।

यह LinkedIn पर खोज करने, मिलते-जुलते जॉब्स एकत्र करने, आवेदन भरने, आपका रिज़्यूमे अपलोड करने और सबमिट करने के लिए AI ब्राउज़र एजेंट का उपयोग करता है — जबकि एक **स्व-शिक्षण मेमोरी सिस्टम** याद रखता है कि प्रत्येक applicant tracking system (ATS) कैसे काम करता है ताकि यह समय के साथ तेज़ और अधिक सटीक होता जाए। सब कुछ आपकी मशीन पर स्थानीय रूप से चलता है। LLM API कॉल के अलावा कोई डेटा आपके कंप्यूटर से बाहर नहीं जाता।

---

## डाउनलोड

<div align="center">

| <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/apple/apple-original.svg" width="16" /> macOS | <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/windows11/windows11-original.svg" width="16" /> Windows | <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/linux/linux-original.svg" width="16" /> Linux |
|:---:|:---:|:---:|
| [**Apple Silicon (.dmg)**](https://github.com/jaimaann/LangHire/releases/latest/download/LangHire_1.0.0_aarch64.dmg) | [**64-bit Installer (.exe)**](https://github.com/jaimaann/LangHire/releases/latest/download/LangHire_1.0.0_x64-setup.exe) | [**AppImage (Universal)**](https://github.com/jaimaann/LangHire/releases/latest/download/LangHire_1.0.0_amd64.AppImage) |
| [Intel (.dmg)](https://github.com/jaimaann/LangHire/releases/latest/download/LangHire_1.0.0_x64.dmg) | | [Debian / Ubuntu x64 (.deb)](https://github.com/jaimaann/LangHire/releases/latest/download/LangHire_1.0.0_amd64.deb) |
| | | [Debian / Ubuntu ARM64 (.deb)](https://github.com/jaimaann/LangHire/releases/latest/download/LangHire_1.0.0_arm64.deb) |

</div>

<p align="center"><sub>एक LLM API कुंजी (OpenAI, Anthropic, या AWS) आवश्यक है। पहली बार लॉन्च करने पर Chromium स्वचालित रूप से इंस्टॉल हो जाता है। <a href="#त्वरित-शुरुआत">त्वरित शुरुआत</a> देखें।</sub></p>

> **डेवलपर्स** -- सोर्स से चलाने के लिए [डेवलपमेंट सेटअप](#डेवलपमेंट-सेटअप) देखें।

### इंस्टॉलेशन नोट्स

<details>
<summary><strong>macOS</strong></summary>

macOS रिलीज़ Apple द्वारा **साइन और नोटराइज़्ड** है। बस `.dmg` खोलें, LangHire को Applications में ड्रैग करें, और लॉन्च करने के लिए डबल-क्लिक करें। कोई अतिरिक्त कदम की आवश्यकता नहीं है।
</details>

<details>
<summary><strong>Windows</strong> -- "Windows protected your PC" (SmartScreen)</summary>

Windows इंस्टॉलर कोड-साइन नहीं है। आपको SmartScreen चेतावनी दिखाई दे सकती है:

1. `.exe` इंस्टॉलर चलाएं
2. यदि आपको **"Windows protected your PC"** दिखाई दे:
   - **More info** पर क्लिक करें
   - **Run anyway** पर क्लिक करें
3. इंस्टॉलर पूरा करें और LangHire लॉन्च करें
</details>

<details>
<summary><strong>Linux</strong> -- AppImage या .deb</summary>

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
> **अगर Chromium लॉन्च नहीं होता:** कुछ Linux वितरण (जैसे Ubuntu 24.04+) में sandbox प्रतिबंध हैं। ब्राउज़र और डिपेंडेंसी मैन्युअली इंस्टॉल करने के लिए यह चलाएं:
> ```bash
> uvx playwright install --with-deps chromium
> ```
</details>

---

## विशेषताएं

- **नेटिव डेस्कटॉप ऐप** -- macOS, Windows, और Linux
- **जॉब कलेक्शन** -- आपके लक्षित शीर्षकों और स्थानों के अनुसार LinkedIn पर जॉब खोजता है
- **स्वचालित आवेदन** -- AI एजेंट फ़ॉर्म भरता है, आपका रिज़्यूमे अपलोड करता है, स्क्रीनिंग प्रश्नों का उत्तर देता है
- **अनुकूलित रिज़्यूमे** (बीटा) -- प्रत्येक जॉब विवरण के लिए आपके रिज़्यूमे को स्वतः अनुकूलित करता है
- **स्व-शिक्षण मेमोरी** -- प्रति-ATS प्रक्रियात्मक ज्ञान संग्रहीत करता है (नेविगेशन पैटर्न, फ़ॉर्म रणनीतियां, UI विशेषताएं)। एक Workday साइट से सीखे गए पाठ सभी Workday साइटों पर लागू होते हैं।
- **स्मार्ट Q&A पुनः उपयोग** -- पिछले आवेदनों से उत्तर सीखता है और उनका पुनः उपयोग करता है
- **मल्टी-LLM सपोर्ट** -- OpenAI, Anthropic, AWS Bedrock, या स्थानीय मॉडल के लिए Ollama
- **डैशबोर्ड** -- रीयल-टाइम आंकड़े, सफलता दर, प्रति-डोमेन प्रदर्शन, मेमोरी प्रभाव विश्लेषण
- **CLI टूल्स** -- कलेक्शन, एप्लिकेशन, मेमोरी प्रबंधन और एनालिटिक्स के लिए पावर-यूज़र स्क्रिप्ट
- **100% स्थानीय** -- सारा डेटा आपकी मशीन पर आपके OS ऐप डेटा डायरेक्टरी में संग्रहीत

---

## स्क्रीनशॉट

<table>
<tr>
<td align="center" width="33%">
<details>
<summary><img src="../screenshots/dashboard.png" alt="Dashboard" width="280" /><br/><strong>डैशबोर्ड</strong></summary>
<img src="../screenshots/dashboard.png" alt="Dashboard" width="800" />
</details>
</td>
<td align="center" width="33%">
<details>
<summary><img src="../screenshots/jobs.png" alt="Jobs" width="280" /><br/><strong>जॉब्स</strong></summary>
<img src="../screenshots/jobs.png" alt="Jobs" width="800" />
</details>
</td>
<td align="center" width="33%">
<details>
<summary><img src="../screenshots/memory.png" alt="Memory" width="280" /><br/><strong>मेमोरी</strong></summary>
<img src="../screenshots/memory.png" alt="Memory" width="800" />
</details>
</td>
</tr>
</table>

<p align="center"><sub>विस्तार करने के लिए किसी भी स्क्रीनशॉट पर क्लिक करें</sub></p>

---

## त्वरित शुरुआत

1. **डाउनलोड और इंस्टॉल करें** ऊपर [डाउनलोड](#डाउनलोड) सेक्शन से
2. **ऐप खोलें** -- पहली बार लॉन्च पर Chromium स्वचालित रूप से डाउनलोड होता है (~400 MB, एक बार)
3. **सेटअप विज़ार्ड** आपको गाइड करता है: **LLM प्रदाता** → **रिज़्यूमे अपलोड** (स्वतः आपकी प्रोफ़ाइल पार्स करता है) → **प्रोफ़ाइल समीक्षा** → तैयार
4. **जॉब्स एकत्र करें** -- **Jobs** पर जाएं → जॉब टाइटल दर्ज करें → **Start Collecting**
5. **आवेदन करें** -- **Apply** पर जाएं → **Start Applying** और डैशबोर्ड देखें जैसे-जैसे आवेदन जमा होते हैं

---

## यह कैसे काम करता है

LangHire एक तीन-चरणीय लूप चलाता है: **एकत्र करें → आवेदन करें → सीखें**।

**एकत्र करें** -- एक AI ब्राउज़र एजेंट LinkedIn में लॉग इन करता है, आपके लक्षित शीर्षकों और स्थानों से मिलते जॉब खोजता है, और प्रत्येक लिस्टिंग को उसके URL, कंपनी, शीर्षक और विवरण के साथ सहेजता है।

**आवेदन करें** -- प्रत्येक पेंडिंग जॉब के लिए, एजेंट आवेदन खोलता है (Easy Apply या बाहरी ATS), आपकी प्रोफ़ाइल का उपयोग करके हर फ़ील्ड भरता है, आपका रिज़्यूमे अपलोड करता है, अपने Q&A बैंक से स्क्रीनिंग प्रश्नों का उत्तर देता है, और सबमिट करता है। कई वर्कर समानांतर में चल सकते हैं।

**सीखें** -- प्रत्येक आवेदन के बाद, सिस्टम प्रक्रियात्मक शिक्षा निकालता है: कौन से बटन क्लिक करने हैं, फ़ॉर्म कैसे संरचित हैं, क्या विफल होता है और क्या काम करता है। ये मेमोरी विश्वास स्कोर के साथ प्रति-ATS डोमेन संग्रहीत की जाती हैं, इसलिए अगली बार जब वह उसी ATS का सामना करता है, तो उसे पहले से पता होता है कि कैसे नेविगेट करना है।

### आर्किटेक्चर

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

सारा डेटा स्थानीय रूप से संग्रहीत है:

| OS | पथ |
|----|------|
| macOS | `~/Library/Application Support/langhire/` |
| Windows | `%APPDATA%/langhire/` |
| Linux | `~/.config/langhire/` |

---

## डेवलपमेंट सेटअप

### आवश्यक शर्तें

| टूल | संस्करण | इंस्टॉल |
|------|---------|---------|
| Node.js | 18+ | [nodejs.org](https://nodejs.org) |
| Rust | 1.77+ | `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \| sh` |
| Python | 3.13+ | [python.org](https://python.org) |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |

### क्लोन और इंस्टॉल

```bash
git clone https://github.com/jaimaann/LangHire.git
cd LangHire

npm install                                    # Node dependencies
uv sync                                        # Python dependencies
uv run python -m playwright install chromium   # Browser engine
```

### डेवलपमेंट में चलाएं

दो टर्मिनल:

```bash
# Terminal 1 -- Python backend
uv run python backend/main.py

# Terminal 2 -- Frontend dev server
npm run dev
```

http://localhost:1420 खोलें, या इसके बजाय नेटिव डेस्कटॉप ऐप के रूप में चलाएं:

```bash
# Terminal 2 (alternative) -- Native Tauri app
cargo tauri dev
```

> पहला `cargo tauri dev` Rust शेल कंपाइल करता है (~2 मिनट)। बाद के रन तेज़ होते हैं।

### प्रोडक्शन के लिए बिल्ड

```bash
cargo tauri build
```

`src-tauri/target/release/bundle/` में प्लेटफ़ॉर्म-विशिष्ट इंस्टॉलर बनाता है।

---

## प्रोजेक्ट संरचना

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

## CLI उपयोग

CLI स्क्रिप्ट डेस्कटॉप ऐप के साथ स्वतंत्र रूप से काम करती हैं:

```bash
# LinkedIn से जॉब्स एकत्र करें
uv run python cli/collect_jobs.py

# जॉब्स पर आवेदन करें (3 समानांतर वर्कर)
uv run python cli/apply_jobs.py --workers 3

# प्रति-जॉब अनुकूलित रिज़्यूमे के साथ आवेदन करें
uv run python cli/apply_jobs_tailored.py --workers 2

# मेमोरी प्रबंधन
uv run python cli/memory_cli.py stats
uv run python cli/memory_cli.py domains
uv run python cli/memory_cli.py show linkedin.com

# टर्मिनल प्रदर्शन डैशबोर्ड
uv run python cli/dashboard.py
```

---

## योगदान

योगदान का स्वागत है। पूर्ण दिशानिर्देशों के लिए [CONTRIBUTING.md](../CONTRIBUTING.md) देखें।

```bash
git clone https://github.com/jaimaann/LangHire.git
cd LangHire
npm install && uv sync
uv run python backend/main.py   # Terminal 1
npm run dev                     # Terminal 2
```

**जहां मदद की ज़रूरत है:**

- **अधिक जॉब प्लेटफ़ॉर्म** -- Indeed, Glassdoor, और LinkedIn के अलावा अन्य जॉब लिस्टिंग साइट्स
- **स्थानीय LLM सपोर्ट** -- Ollama, llama.cpp, और अन्य स्थानीय इन्फ़रेंस विकल्प
- **बहु-देश सपोर्ट** -- स्थानीयकृत जॉब साइट्स, पता प्रारूप, और कार्य प्राधिकरण फ़्लो
- **दस्तावेज़ीकरण** -- ट्यूटोरियल, वीडियो वॉकथ्रू, और गाइड
- **परीक्षण** -- यूनिट, इंटीग्रेशन, और E2E टेस्ट कवरेज

---

## लाइसेंस

[MIT](../LICENSE)

---

## अस्वीकरण

यह टूल LinkedIn और अन्य प्लेटफ़ॉर्म पर जॉब आवेदनों को स्वचालित करता है। इसे ज़िम्मेदारी से उपयोग करें:

- प्रत्येक प्लेटफ़ॉर्म की सेवा की शर्तों और दर सीमाओं का सम्मान करें
- नियोक्ताओं को निम्न-गुणवत्ता वाले आवेदनों से स्पैम न करें
- स्वचालित आवेदन चलाने से पहले अपनी प्रोफ़ाइल और सेटिंग्स की समीक्षा करें
- इस टूल के माध्यम से जमा किए गए सभी आवेदनों के लिए आप ज़िम्मेदार हैं

---

<p align="center">
  <a href="https://tauri.app">Tauri</a>, <a href="https://react.dev">React</a>, <a href="https://python.org">Python</a>, और <a href="https://github.com/browser-use/browser-use">browser-use</a> के साथ बनाया गया
</p>
