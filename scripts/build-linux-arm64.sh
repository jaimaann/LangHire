#!/bin/bash
# Build LangHire .deb for ARM64 Linux (run this ON an ARM64 Linux machine)
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

echo "=== Installing system dependencies ==="
sudo apt-get update
sudo apt-get install -y \
  libwebkit2gtk-4.1-dev libappindicator3-dev librsvg2-dev patchelf \
  curl build-essential pkg-config libssl-dev libgtk-3-dev libsoup-3.0-dev \
  libjavascriptcoregtk-4.1-dev

echo "=== Installing Rust ==="
if ! command -v rustc &> /dev/null; then
  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
  source "$HOME/.cargo/env"
fi
rustup target add aarch64-unknown-linux-gnu

echo "=== Installing Node.js ==="
if ! command -v node &> /dev/null; then
  curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
  sudo apt-get install -y nodejs
fi

echo "=== Installing Python ==="
if ! command -v python3.13 &> /dev/null; then
  sudo apt-get install -y software-properties-common
  sudo add-apt-repository -y ppa:deadsnakes/ppa
  sudo apt-get update
  sudo apt-get install -y python3.13 python3.13-venv python3.13-dev
fi

echo "=== Installing uv ==="
if ! command -v uv &> /dev/null; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  source "$HOME/.local/bin/env" 2>/dev/null || export PATH="$HOME/.local/bin:$PATH"
fi

echo "=== Installing Node dependencies ==="
npm install

echo "=== Installing Python dependencies ==="
uv sync

echo "=== Building Python backend ==="
bash scripts/build-backend.sh aarch64-unknown-linux-gnu

echo "=== Building Tauri app ==="
npx tauri build --target aarch64-unknown-linux-gnu

echo ""
echo "=== Done! ==="
echo "Look for .deb in: src-tauri/target/aarch64-unknown-linux-gnu/release/bundle/deb/"
ls -lh src-tauri/target/aarch64-unknown-linux-gnu/release/bundle/deb/*.deb 2>/dev/null || echo "(check target/release/bundle/deb/ if the above path doesn't exist)"
