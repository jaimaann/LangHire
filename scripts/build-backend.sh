#!/bin/bash
# Build the Python backend into a standalone executable using PyInstaller.
# The output binary is placed in src-tauri/binaries/ for Tauri sidecar bundling.
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "🔨 Building Python backend with PyInstaller..."

# Use target triple from argument, or auto-detect from host
if [ -n "$1" ]; then
  TARGET="$1"
else
  ARCH=$(uname -m)
  OS=$(uname -s)
  if [ "$OS" = "Darwin" ]; then
    if [ "$ARCH" = "arm64" ]; then
      TARGET="aarch64-apple-darwin"
    else
      TARGET="x86_64-apple-darwin"
    fi
  elif [ "$OS" = "Linux" ]; then
    TARGET="x86_64-unknown-linux-gnu"
  else
    TARGET="x86_64-pc-windows-msvc"
  fi
fi

# Build with PyInstaller
uv run python -m PyInstaller \
  --onefile \
  --name "langhire-backend-${TARGET}" \
  --distpath src-tauri/binaries \
  --workpath build/pyinstaller \
  --specpath build \
  --paths "${PROJECT_DIR}/backend" \
  --add-data "${PROJECT_DIR}/backend/core:core" \
  --add-data "${PROJECT_DIR}/backend/memory:memory" \
  --add-data "${PROJECT_DIR}/cli:cli" \
  --hidden-import uvicorn.logging \
  --hidden-import uvicorn.lifespan.on \
  --hidden-import uvicorn.protocols.http.auto \
  --hidden-import uvicorn.protocols.http.h11_impl \
  --hidden-import uvicorn.protocols.websockets.auto \
  --hidden-import fastapi \
  --hidden-import langchain_openai \
  --hidden-import langchain_anthropic \
  --hidden-import langchain_aws \
  --hidden-import browser_use \
  --hidden-import browser_use.agent \
  --hidden-import browser_use.browser \
  --hidden-import browser_use.llm \
  --hidden-import playwright \
  --hidden-import playwright.async_api \
  --hidden-import filelock \
  --hidden-import pydantic_settings \
  --hidden-import psutil \
  --collect-all browser_use \
  --collect-all playwright \
  --clean \
  backend/main.py

echo "✅ Backend binary built: src-tauri/binaries/langhire-backend-${TARGET}"
ls -lh "src-tauri/binaries/langhire-backend-${TARGET}"

