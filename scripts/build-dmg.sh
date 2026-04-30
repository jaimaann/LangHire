#!/bin/bash
# Build the DMG installer for distribution.
# Run after: cargo tauri build --bundles app
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BUNDLE_DIR="$PROJECT_DIR/src-tauri/target/release/bundle"
DMG_DIR="$BUNDLE_DIR/dmg"
APP_DIR="$BUNDLE_DIR/macos/Job Applicant.app"

if [ ! -d "$APP_DIR" ]; then
  echo "❌ App not found. Run 'cargo tauri build --bundles app' first."
  exit 1
fi

rm -f "$DMG_DIR/Job Applicant_1.0.0_aarch64.dmg"

bash "$DMG_DIR/bundle_dmg.sh" \
  --volname "Job Applicant" \
  --volicon "$DMG_DIR/icon.icns" \
  --app-drop-link 480 170 \
  --hide-extension "Job Applicant.app" \
  --skip-jenkins \
  "$DMG_DIR/Job Applicant_1.0.0_aarch64.dmg" \
  "$APP_DIR"

echo "✅ DMG: $DMG_DIR/Job Applicant_1.0.0_aarch64.dmg"
