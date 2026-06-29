#!/bin/bash
# Build the LangHire desktop app + installer for the CURRENT host OS.
#
#   macOS  → .app + .dmg   (src-tauri/target/release/bundle/{macos,dmg})
#   Linux  → .deb + .AppImage (src-tauri/target/release/bundle/{deb,appimage})
#
# Why host-only: Tauri cannot cross-compile installers — the macOS bundler
# needs macOS, the Windows bundler (.msi/.exe) needs Windows, the Linux
# bundler (.deb/.AppImage) needs Linux. To produce all three at once, use
# scripts/build-all-platforms.sh (runs the GitHub Actions matrix), or run
# this script on each OS (Windows users: see scripts/build-windows.ps1).
#
# Usage:
#   bash scripts/build-app.sh                  # build for the host OS
#   bash scripts/build-app.sh --debug          # faster, unoptimized debug build
#   bash scripts/build-app.sh --clean-data     # wipe local app data, then build (fresh test)
#   bash scripts/build-app.sh --clean-data -y  # ...without the confirmation prompt
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

DEBUG_FLAG=""
CLEAN_DATA=0
ASSUME_YES=0
for arg in "$@"; do
  case "$arg" in
    --debug) DEBUG_FLAG="--debug" ;;
    --clean-data) CLEAN_DATA=1 ;;
    -y|--yes) ASSUME_YES=1 ;;
    -h|--help)
      sed -n '2,17p' "$0" | sed 's/^#$//; s/^# //'
      exit 0 ;;
    *) echo "❌ Unknown argument: $arg (try --help)"; exit 1 ;;
  esac
done

OS=$(uname -s)
ARCH=$(uname -m)

echo "════════════════════════════════════════════════════════"
echo " LangHire build — host: $OS/$ARCH ${DEBUG_FLAG:+(debug)}"
echo "════════════════════════════════════════════════════════"

if [ "$OS" != "Darwin" ] && [ "$OS" != "Linux" ]; then
  echo "❌ This script supports macOS and Linux."
  echo "   On Windows, run:  powershell -ExecutionPolicy Bypass -File scripts\\build-windows.ps1"
  exit 1
fi

# ── 0. Optional: clear local app data for a fresh-install test ───────────────
# Mirrors core.config.get_data_dir(): macOS → ~/Library/Application Support/langhire,
# Linux → ~/.config/langhire. Removes profile, jobs, memory DB, settings,
# saved logins/cookies, and the onboarding flag.
if [ "$CLEAN_DATA" = "1" ]; then
  if [ "$OS" = "Darwin" ]; then
    DATA_DIR="$HOME/Library/Application Support/langhire"
  else
    DATA_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/langhire"
  fi

  if [ -d "$DATA_DIR" ]; then
    echo "🧹 App data directory: $DATA_DIR"
    if [ "$ASSUME_YES" != "1" ]; then
      echo "   This permanently deletes your profile, jobs, memory, settings, and saved logins."
      printf "   Delete it and start fresh? [y/N] "
      read -r reply
      case "$reply" in
        y|Y|yes|YES) ;;
        *) echo "   Skipped — keeping existing data."; CLEAN_DATA=0 ;;
      esac
    fi
    if [ "$CLEAN_DATA" = "1" ]; then
      rm -rf "$DATA_DIR"
      echo "   ✅ Cleared. The app will onboard from scratch on next launch."
    fi
  else
    echo "🧹 No existing app data at $DATA_DIR — already fresh."
  fi
fi

# ── 1. Tooling checks ───────────────────────────────────────────────────────
command -v uv  >/dev/null || { echo "❌ 'uv' not found — install from https://docs.astral.sh/uv/"; exit 1; }
command -v npm >/dev/null || { echo "❌ 'npm' not found — install Node.js 20+"; exit 1; }
command -v cargo >/dev/null || { echo "❌ 'cargo' not found — install Rust from https://rustup.rs"; exit 1; }

# Resolve the Tauri CLI: prefer the local npm binary, fall back to cargo-tauri.
if [ -x "node_modules/.bin/tauri" ]; then
  TAURI="node_modules/.bin/tauri"
elif cargo tauri --version >/dev/null 2>&1; then
  TAURI="cargo tauri"
else
  TAURI=""
fi

# ── 2. Install dependencies ─────────────────────────────────────────────────
echo "📦 Installing JS dependencies..."
npm install
echo "📦 Syncing Python dependencies..."
uv sync

if [ -z "$TAURI" ]; then
  echo "❌ Tauri CLI not found. Install with one of:"
  echo "     npm install            # provides node_modules/.bin/tauri"
  echo "     cargo install tauri-cli --version '^2'"
  exit 1
fi

# ── 3. Build the Python backend sidecar ─────────────────────────────────────
echo "🔨 Building Python backend sidecar..."
bash "$SCRIPT_DIR/build-backend.sh"

# ── 4. Build the Tauri app + installer (also runs `npm run build`) ───────────
echo "🏗  Building Tauri app + installer..."
$TAURI build $DEBUG_FLAG

# ── 5. Report artifacts ─────────────────────────────────────────────────────
BUNDLE="src-tauri/target/release/bundle"
[ -n "$DEBUG_FLAG" ] && BUNDLE="src-tauri/target/debug/bundle"

echo ""
echo "✅ Build complete. Installers:"
if [ "$OS" = "Darwin" ]; then
  ls -1 "$BUNDLE"/dmg/*.dmg 2>/dev/null || echo "   (no .dmg — see $BUNDLE/macos/ for the .app)"
  ls -1 "$BUNDLE"/macos/*.app 2>/dev/null || true
  echo ""
  echo "ℹ️  Unsigned local builds are blocked by Gatekeeper on first launch."
  echo "   Right-click the app → Open, or run: xattr -cr /Applications/LangHire.app"
else
  ls -1 "$BUNDLE"/deb/*.deb 2>/dev/null || true
  ls -1 "$BUNDLE"/appimage/*.AppImage 2>/dev/null || true
  ls -1 "$BUNDLE"/rpm/*.rpm 2>/dev/null || true
fi
