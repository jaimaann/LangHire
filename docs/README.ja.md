<p align="center">
  <img src="../src-tauri/icons/icon.png" alt="LangHire" width="120" />
</p>

<h1 align="center">LangHire</h1>

<p align="center">
  <strong>ネイティブデスクトップUIを備えたAI駆動の求人応募自動化</strong>
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
  <a href="README.ja.md"><strong>日本語</strong></a> &middot;
  <a href="README.ko.md">한국어</a> &middot;
  <a href="README.pt.md">Português</a> &middot;
  <a href="README.ms.md">Bahasa Melayu</a>
</p>

---

求人への応募は面倒です。求人を見つけ、応募ページに移動し、昨日と同じフィールドを埋め、同じスクリーニング質問に答え、履歴書を再度アップロードする — これを50回繰り返します。LangHireはこのサイクル全体を自動化します。

AIブラウザエージェントを使用してLinkedInを検索し、マッチする求人を収集し、応募フォームを記入し、履歴書をアップロードして送信します — **自己学習メモリシステム**が各応募者追跡システム（ATS）の動作を記憶し、時間とともにより速く正確になります。すべてがあなたのマシン上でローカルに実行されます。LLM API呼び出し以外、データがコンピュータから出ることはありません。

---

## ダウンロード

<div align="center">

| <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/apple/apple-original.svg" width="16" /> macOS | <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/windows11/windows11-original.svg" width="16" /> Windows | <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/linux/linux-original.svg" width="16" /> Linux |
|:---:|:---:|:---:|
| [**Apple Silicon (.dmg)**](https://github.com/jaimaann/LangHire/releases/latest/download/LangHire_1.0.0_aarch64.dmg) | [**64-bit Installer (.exe)**](https://github.com/jaimaann/LangHire/releases/latest/download/LangHire_1.0.0_x64-setup.exe) | [**AppImage (Universal)**](https://github.com/jaimaann/LangHire/releases/latest/download/LangHire_1.0.0_amd64.AppImage) |
| [Intel (.dmg)](https://github.com/jaimaann/LangHire/releases/latest/download/LangHire_1.0.0_x64.dmg) | | [Debian / Ubuntu x64 (.deb)](https://github.com/jaimaann/LangHire/releases/latest/download/LangHire_1.0.0_amd64.deb) |
| | | [Debian / Ubuntu ARM64 (.deb)](https://github.com/jaimaann/LangHire/releases/latest/download/LangHire_1.0.0_arm64.deb) |

</div>

<p align="center"><sub>LLM APIキー（OpenAI、Anthropic、またはAWS）が必要です。初回起動時にChromiumが自動インストールされます。<a href="#クイックスタート">クイックスタート</a>をご覧ください。</sub></p>

> **開発者の方へ** -- ソースから実行するには[開発環境セットアップ](#開発環境セットアップ)をご覧ください。

### インストールに関する注意事項

<details>
<summary><strong>macOS</strong></summary>

macOSリリースはAppleによって**署名・公証済み**です。`.dmg`を開き、LangHireをアプリケーションにドラッグし、ダブルクリックで起動するだけです。追加の手順は不要です。
</details>

<details>
<summary><strong>Windows</strong> -- 「WindowsによってPCが保護されました」(SmartScreen)</summary>

Windowsインストーラーはコード署名されていません。SmartScreen警告が表示される場合があります：

1. `.exe`インストーラーを実行
2. **「WindowsによってPCが保護されました」**が表示された場合：
   - **詳細情報**をクリック
   - **実行**をクリック
3. インストーラーを完了してLangHireを起動
</details>

<details>
<summary><strong>Linux</strong> -- AppImageまたは.deb</summary>

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
> **Chromiumが起動しない場合：** 一部のLinuxディストリビューション（Ubuntu 24.04+など）にはサンドボックス制限があります。ブラウザと依存関係を手動でインストールするには以下を実行してください：
> ```bash
> uvx playwright install --with-deps chromium
> ```
</details>

---

## 機能

- **ネイティブデスクトップアプリ** -- macOS、Windows、Linux対応
- **求人収集** -- ターゲットの職種と場所に一致する求人をLinkedInで検索
- **自動応募** -- AIエージェントがフォームを記入、履歴書をアップロード、スクリーニング質問に回答
- **カスタマイズ履歴書**（ベータ） -- 各求人内容に合わせて履歴書を自動カスタマイズ
- **自己学習メモリ** -- ATS毎の手続き的知識を保存（ナビゲーションパターン、フォーム戦略、UIの癖）。あるWorkdayサイトで学んだ教訓は全てのWorkdayサイトに適用されます。
- **スマートQ&A再利用** -- 過去の応募から回答を学習し再利用
- **マルチLLMサポート** -- OpenAI、Anthropic、AWS Bedrock、またはローカルモデル用のOllama
- **ダッシュボード** -- リアルタイム統計、成功率、ドメイン別パフォーマンス、メモリ影響分析
- **CLIツール** -- 収集、応募、メモリ管理、分析のためのパワーユーザースクリプト
- **100%ローカル** -- すべてのデータはOSのアプリデータディレクトリ内のマシンに保存

---

## スクリーンショット

<table>
<tr>
<td align="center" width="33%">
<details>
<summary><img src="../screenshots/dashboard.png" alt="Dashboard" width="280" /><br/><strong>ダッシュボード</strong></summary>
<img src="../screenshots/dashboard.png" alt="Dashboard" width="800" />
</details>
</td>
<td align="center" width="33%">
<details>
<summary><img src="../screenshots/jobs.png" alt="Jobs" width="280" /><br/><strong>求人</strong></summary>
<img src="../screenshots/jobs.png" alt="Jobs" width="800" />
</details>
</td>
<td align="center" width="33%">
<details>
<summary><img src="../screenshots/memory.png" alt="Memory" width="280" /><br/><strong>メモリ</strong></summary>
<img src="../screenshots/memory.png" alt="Memory" width="800" />
</details>
</td>
</tr>
</table>

<p align="center"><sub>スクリーンショットをクリックして拡大</sub></p>

---

## クイックスタート

1. 上記の[ダウンロード](#ダウンロード)セクションから**ダウンロードしてインストール**
2. **アプリを開く** -- 初回起動時にChromiumが自動ダウンロードされます（約400 MB、一度だけ）
3. **セットアップウィザード**がガイドします：**LLMプロバイダー** → **履歴書アップロード**（プロフィールを自動解析） → **プロフィール確認** → 準備完了
4. **求人を収集** -- **Jobs**に移動 → 職種を入力 → **Start Collecting**
5. **応募** -- **Apply**に移動 → **Start Applying** して応募が進むのをダッシュボードで確認

---

## 仕組み

LangHireは3段階のループを実行します：**収集 → 応募 → 学習**。

**収集** -- AIブラウザエージェントがLinkedInにログインし、ターゲットの職種と場所に一致する求人を検索し、各リストのURL、会社名、タイトル、説明を保存します。

**応募** -- 保留中の各求人に対して、エージェントが応募を開き（Easy Applyまたは外部ATS）、プロフィールを使用して全フィールドを記入し、履歴書をアップロードし、Q&Aバンクからスクリーニング質問に回答し、送信します。複数のワーカーを並列実行できます。

**学習** -- 各応募後、システムは手続き的な学びを抽出します：どのボタンをクリックするか、フォームがどう構成されているか、何が失敗し何が機能するか。これらのメモリは信頼スコア付きでATS・ドメインごとに保存されるため、次に同じATSに遭遇した際には既にナビゲーション方法を知っています。

### アーキテクチャ

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

すべてのデータはローカルに保存されます：

| OS | パス |
|----|------|
| macOS | `~/Library/Application Support/langhire/` |
| Windows | `%APPDATA%/langhire/` |
| Linux | `~/.config/langhire/` |

---

## 開発環境セットアップ

### 前提条件

| ツール | バージョン | インストール |
|------|---------|---------|
| Node.js | 18+ | [nodejs.org](https://nodejs.org) |
| Rust | 1.77+ | `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \| sh` |
| Python | 3.13+ | [python.org](https://python.org) |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |

### クローンとインストール

```bash
git clone https://github.com/jaimaann/LangHire.git
cd LangHire

npm install                                    # Node dependencies
uv sync                                        # Python dependencies
uv run python -m playwright install chromium   # Browser engine
```

### 開発モードで実行

2つのターミナル：

```bash
# Terminal 1 -- Python backend
uv run python backend/main.py

# Terminal 2 -- Frontend dev server
npm run dev
```

http://localhost:1420 を開くか、代わりにネイティブデスクトップアプリとして実行：

```bash
# Terminal 2 (alternative) -- Native Tauri app
cargo tauri dev
```

> 最初の`cargo tauri dev`はRustシェルをコンパイルします（約2分）。以降の実行は高速です。

### 本番用ビルド

```bash
cargo tauri build
```

`src-tauri/target/release/bundle/`にプラットフォーム固有のインストーラーを生成します。

---

## プロジェクト構成

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

## CLI使用方法

CLIスクリプトはデスクトップアプリと並行してスタンドアロンで動作します：

```bash
# LinkedInから求人を収集
uv run python cli/collect_jobs.py

# 求人に応募（3つの並列ワーカー）
uv run python cli/apply_jobs.py --workers 3

# 求人ごとにカスタマイズした履歴書で応募
uv run python cli/apply_jobs_tailored.py --workers 2

# メモリ管理
uv run python cli/memory_cli.py stats
uv run python cli/memory_cli.py domains
uv run python cli/memory_cli.py show linkedin.com

# ターミナルパフォーマンスダッシュボード
uv run python cli/dashboard.py
```

---

## コントリビューション

コントリビューションを歓迎します。完全なガイドラインは[CONTRIBUTING.md](../CONTRIBUTING.md)をご覧ください。

```bash
git clone https://github.com/jaimaann/LangHire.git
cd LangHire
npm install && uv sync
uv run python backend/main.py   # Terminal 1
npm run dev                     # Terminal 2
```

**助けが必要な分野：**

- **より多くの求人プラットフォーム** -- Indeed、Glassdoor、その他LinkedIn以外の求人サイト
- **ローカルLLMサポート** -- Ollama、llama.cpp、その他のローカル推論オプション
- **多国対応** -- ローカライズされた求人サイト、住所形式、就労許可フロー
- **ドキュメント** -- チュートリアル、動画ウォークスルー、ガイド
- **テスト** -- ユニット、統合、E2Eテストカバレッジ

---

## ライセンス

[MIT](../LICENSE)

---

## 免責事項

このツールはLinkedInやその他のプラットフォームでの求人応募を自動化します。責任を持って使用してください：

- 各プラットフォームの利用規約とレート制限を尊重してください
- 低品質な応募で雇用主にスパムを送らないでください
- 自動応募を実行する前にプロフィールと設定を確認してください
- このツールを通じて送信されたすべての応募に対してあなたが責任を負います

---

<p align="center">
  <a href="https://tauri.app">Tauri</a>、<a href="https://react.dev">React</a>、<a href="https://python.org">Python</a>、<a href="https://github.com/browser-use/browser-use">browser-use</a>で構築
</p>
