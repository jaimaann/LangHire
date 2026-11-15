/// <reference types="vite/client" />

/** App version from package.json, injected by Vite `define`. */
declare const __APP_VERSION__: string;

interface ImportMetaEnv {
  readonly VITE_ANALYTICS_ENDPOINT?: string;
  readonly VITE_SENTRY_DSN: string;
  readonly VITE_GITHUB_TOKEN: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
