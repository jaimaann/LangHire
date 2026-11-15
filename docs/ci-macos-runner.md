# Running the end-to-end tests on your Mac (self-hosted GitHub runner)

GitHub-hosted runners cover Linux and Windows on every push. macOS runs on your
own Mac, registered as a self-hosted runner. The `e2e-macos` job in
`.github/workflows/e2e.yml` stays off until you finish step 4.

## 1. Prerequisites on the Mac

- macOS 13 or newer, Apple silicon or Intel
- Xcode command line tools: `xcode-select --install`
- Nothing else: the workflow installs Node 22, Python 3.13 (via uv) and Chromium
  itself, into the runner's work folder.

Use a separate macOS user account for the runner if you can (System Settings →
Users & Groups). The tests start browsers and a local server; a separate account
keeps them away from your own Chrome profile, keychain and files.

## 2. Register the runner

In the GitHub repository: **Settings → Actions → Runners → New self-hosted
runner → macOS**, pick your architecture, and run the commands it shows in
Terminal (they download the runner into `~/actions-runner` and call
`./config.sh`). When `config.sh` asks:

- **Runner group**: Default
- **Name**: anything, e.g. `nitin-mac`
- **Additional labels**: `langhire-e2e` (the job targets `self-hosted, macOS, langhire-e2e`)
- **Work folder**: default `_work`

## 3. Keep it running

```bash
cd ~/actions-runner
./svc.sh install     # start at login as a launchd service
./svc.sh start
./svc.sh status
```

The Mac must be awake and logged in to that account while jobs run (System
Settings → Lock Screen / Energy: prevent automatic sleep when on power).
To stop: `./svc.sh stop`; to remove: `./svc.sh uninstall` then
`./config.sh remove --token <token from the Runners page>`.

## 4. Turn the macOS job on

**Settings → Secrets and variables → Actions → Variables → New repository
variable**: `MACOS_RUNNER` = `true`. From the next push, every commit also runs
the end-to-end suite on the Mac. Set it to `false` (or delete it) whenever the
Mac will be offline for a while, so commits don't wait in the queue for it.

## Security: the repository is public

A self-hosted runner executes whatever the workflow says, on your machine. The
workflow already refuses pull requests from forks on the Mac (`e2e-macos` only
runs for pushes and for pull requests from branches of this repository). Also set
**Settings → Actions → General → Fork pull request workflows → Require approval
for all outside collaborators**, and never add `pull_request_target` workflows
that check out PR code on the self-hosted runner.

The tests themselves are offline: the backend, the mock job site and the scripted
model all listen on 127.0.0.1, no API keys are needed, and no real application is
ever sent.

## Running the suite by hand on the Mac

```bash
npm ci && uv sync && npm run build
uv run python -m playwright install chromium
LANGHIRE_E2E=1 uv run pytest tests/e2e -v
```
