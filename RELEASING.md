# Releasing LangHire

## Version

`package.json` is the single source of truth for the app version.
`src-tauri/tauri.conf.json` reads it (`"version": "../package.json"`) and Vite
injects it as `__APP_VERSION__` (used for the Sentry release). Bump
`package.json` (and `src-tauri/Cargo.toml` if you want the crate version to
match), commit, then push a `vX.Y.Z` tag. The **Build & Release** workflow
(`.github/workflows/build.yml`) builds every platform and creates a draft
GitHub release. Publish the draft to make it the "latest" release.

## Auto-update signing (one-time setup)

The app uses `tauri-plugin-updater`. On startup it fetches
`https://github.com/jaimaann/LangHire/releases/latest/download/latest.json`
and only installs updates whose signature matches the public key compiled
into the app. You need a signing key pair.

1. Generate a key pair locally (never commit the private key):

   ```bash
   npx tauri signer generate -w ~/.tauri/langhire.key
   ```

   This writes the private key to `~/.tauri/langhire.key`, the public key to
   `~/.tauri/langhire.key.pub`, and asks for an optional password.

2. Put the **public** key (the contents of `langhire.key.pub`, a single
   base64 string) into `src-tauri/tauri.conf.json`, replacing the placeholder:

   ```json
   "plugins": {
     "updater": {
       "endpoints": ["https://github.com/jaimaann/LangHire/releases/latest/download/latest.json"],
       "pubkey": "REPLACE_WITH_TAURI_SIGNING_PUBLIC_KEY"
     }
   }
   ```

   The public key is safe to commit.

3. Add these GitHub repository secrets
   (Settings → Secrets and variables → Actions):

   | Secret | Value |
   |---|---|
   | `TAURI_SIGNING_PRIVATE_KEY` | the full contents of `~/.tauri/langhire.key` |
   | `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` | the password you chose (empty if none) |

   Back up the private key somewhere safe (password manager). If it is lost,
   existing installs can no longer be updated automatically and users must
   reinstall manually.

With the secrets set, `tauri-action` signs the bundles and uploads
`latest.json` plus the `.sig` files to the release.

## Without a signing key

`bundle.createUpdaterArtifacts` is `true`, and `tauri build` fails when it is
`true` but no `TAURI_SIGNING_PRIVATE_KEY` is present. CI detects a missing
secret and builds with `--config src-tauri/tauri.no-updater.conf.json`
instead (a warning is shown; that release will not auto-update).

For local release builds without the key, do the same:

```bash
npx tauri build --config src-tauri/tauri.no-updater.conf.json
```

or export the key first:

```bash
export TAURI_SIGNING_PRIVATE_KEY="$(cat ~/.tauri/langhire.key)"
export TAURI_SIGNING_PRIVATE_KEY_PASSWORD="..."
npx tauri build
```

Until the real public key replaces the placeholder, the in-app update check
may still find a release, but installation fails signature verification; the
`UpdateChecker` component ignores that silently.

## Backend sidecar

The Tauri host spawns `langhire-backend` on a random free localhost port with
a per-launch API token and passes `LANGHIRE_PORT`, `LANGHIRE_API_TOKEN`,
`LANGHIRE_DATA_DIR` and `LANGHIRE_APP_VERSION` in its environment. The
sidecar binary must be present at
`src-tauri/binaries/langhire-backend-<target-triple>[.exe]` before
`tauri build` (built by `scripts/build-backend.sh` / `.ps1`).
