#!/bin/bash
# Build installers for ALL platforms (macOS ARM + Intel, Linux x64 + ARM64,
# Windows) in one command.
#
# Tauri cannot cross-compile installers locally, so this delegates to the
# repo's GitHub Actions matrix (.github/workflows/build.yml), which builds
# every target on its native runner and uploads them to a GitHub Release.
#
# Requires: the `gh` CLI, authenticated (`gh auth status`).
#
# Usage:
#   bash scripts/build-all-platforms.sh                 # run the matrix on the current branch
#   bash scripts/build-all-platforms.sh --watch         # ...and stream progress
#   bash scripts/build-all-platforms.sh --tag v1.9.0    # build + publish a versioned Release
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

command -v gh >/dev/null || { echo "❌ 'gh' (GitHub CLI) not found — https://cli.github.com"; exit 1; }
gh auth status >/dev/null 2>&1 || { echo "❌ Not authenticated. Run: gh auth login"; exit 1; }

WATCH=0
TAG=""
while [ $# -gt 0 ]; do
  case "$1" in
    --watch) WATCH=1; shift ;;
    --tag) TAG="$2"; shift 2 ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

if [ -n "$TAG" ]; then
  # Tag-driven release: pushing a v* tag triggers build.yml, which publishes a
  # GitHub Release with all five installers attached.
  echo "🏷  Creating and pushing tag $TAG (triggers the release build for all platforms)..."
  git tag -a "$TAG" -m "Release $TAG"
  git push origin "refs/tags/$TAG"
  echo "✅ Tag pushed. The 'Build & Release' workflow will attach installers to the $TAG Release."
else
  # On-demand run on the current branch via workflow_dispatch.
  BRANCH="$(git rev-parse --abbrev-ref HEAD)"
  echo "🚀 Dispatching 'Build & Release' workflow on branch '$BRANCH' (all platforms)..."
  gh workflow run build.yml --ref "$BRANCH"
  sleep 3
fi

echo ""
echo "Targets built by the matrix:"
echo "  • macOS  (aarch64-apple-darwin)      → .dmg"
echo "  • macOS  (x86_64-apple-darwin)       → .dmg"
echo "  • Linux  (x86_64-unknown-linux-gnu)  → .deb / .AppImage"
echo "  • Linux  (aarch64-unknown-linux-gnu) → .deb"
echo "  • Windows(x86_64-pc-windows-msvc)    → .exe / .msi"
echo ""

if [ "$WATCH" = "1" ]; then
  echo "⏳ Watching the latest run..."
  sleep 5
  RUN_ID="$(gh run list --workflow=build.yml --limit 1 --json databaseId --jq '.[0].databaseId')"
  gh run watch "$RUN_ID" --exit-status
else
  echo "👀 Track progress with:  gh run list --workflow=build.yml"
  echo "   or open the Actions tab on GitHub. Artifacts attach to the Release on completion."
fi
