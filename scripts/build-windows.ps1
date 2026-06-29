# Build the LangHire desktop app + installer on Windows.
#
#   Windows -> .exe (NSIS) + .msi  (src-tauri\target\release\bundle\{nsis,msi})
#
# Tauri cannot cross-compile installers, so run this ON Windows. For macOS and
# Linux installers, run scripts/build-app.sh on those OSes, or trigger the
# GitHub Actions matrix via scripts/build-all-platforms.sh.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\build-windows.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\build-windows.ps1 -DebugBuild
param([switch]$DebugBuild)

$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $PSScriptRoot
if (-not $ProjectDir) { $ProjectDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path) }
Set-Location $ProjectDir

Write-Host "================================================================"
Write-Host " LangHire build - host: Windows" $(if ($DebugBuild) { "(debug)" })
Write-Host "================================================================"

# 1. Tooling checks
foreach ($tool in @("uv", "npm", "cargo")) {
  if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
    Write-Error "'$tool' not found on PATH. Install uv, Node.js 20+, and Rust (rustup)."
    exit 1
  }
}

# Resolve the Tauri CLI: prefer the local npm binary, fall back to cargo-tauri.
$Tauri = $null
if (Test-Path "node_modules\.bin\tauri.cmd") {
  $Tauri = "node_modules\.bin\tauri.cmd"
} elseif (cargo tauri --version 2>$null) {
  $Tauri = "cargo-tauri"
}

# 2. Install dependencies
Write-Host "Installing JS dependencies..."
npm install
Write-Host "Syncing Python dependencies..."
uv sync

if (-not $Tauri) {
  Write-Error "Tauri CLI not found. Run 'npm install' or 'cargo install tauri-cli --version ^2'."
  exit 1
}

# 3. Build the Python backend sidecar
Write-Host "Building Python backend sidecar..."
powershell -ExecutionPolicy Bypass -File "$PSScriptRoot\build-backend.ps1"

# 4. Build the Tauri app + installer (also runs `npm run build`)
Write-Host "Building Tauri app + installer..."
if ($Tauri -eq "cargo-tauri") {
  if ($DebugBuild) { cargo tauri build --debug } else { cargo tauri build }
} else {
  if ($DebugBuild) { & $Tauri build --debug } else { & $Tauri build }
}

# 5. Report artifacts
$Bundle = if ($DebugBuild) { "src-tauri\target\debug\bundle" } else { "src-tauri\target\release\bundle" }
Write-Host ""
Write-Host "Build complete. Installers:"
Get-ChildItem -Path "$Bundle\nsis\*.exe","$Bundle\msi\*.msi" -ErrorAction SilentlyContinue | ForEach-Object { Write-Host "  $($_.FullName)" }
