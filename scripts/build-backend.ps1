# Build the Python backend into a standalone executable using PyInstaller.
# The output binary is placed in src-tauri/binaries/ for Tauri sidecar bundling.
# Windows equivalent of build-backend.sh

$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not $ProjectDir) { $ProjectDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path) }
Set-Location $ProjectDir

Write-Host "🔨 Building Python backend with PyInstaller..."

# Detect target triple for Tauri sidecar naming
$Target = "x86_64-pc-windows-msvc"
if ($env:PROCESSOR_ARCHITECTURE -eq "ARM64") {
    $Target = "aarch64-pc-windows-msvc"
}

# Build with PyInstaller
uv run pyinstaller `
  --onefile `
  --name "langhire-backend-$Target" `
  --distpath src-tauri/binaries `
  --workpath build/pyinstaller `
  --specpath build `
  --paths "$ProjectDir/backend" `
  --add-data "$ProjectDir/backend/core;core" `
  --add-data "$ProjectDir/backend/memory;memory" `
  --add-data "$ProjectDir/cli;cli" `
  --hidden-import uvicorn.logging `
  --hidden-import uvicorn.lifespan.on `
  --hidden-import uvicorn.protocols.http.auto `
  --hidden-import uvicorn.protocols.http.h11_impl `
  --hidden-import uvicorn.protocols.websockets.auto `
  --hidden-import fastapi `
  --hidden-import langchain_openai `
  --hidden-import langchain_anthropic `
  --hidden-import langchain_aws `
  --hidden-import browser_use `
  --hidden-import browser_use.agent `
  --hidden-import browser_use.browser `
  --hidden-import browser_use.llm `
  --hidden-import playwright `
  --hidden-import playwright.async_api `
  --hidden-import filelock `
  --hidden-import pydantic_settings `
  --hidden-import psutil `
  --collect-all browser_use `
  --collect-all playwright `
  --clean `
  backend/main.py

$BinaryPath = "src-tauri/binaries/langhire-backend-" + $Target + ".exe"
Write-Host "Backend binary built: $BinaryPath"
Get-Item $BinaryPath | Select-Object Name, Length

