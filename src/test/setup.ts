/**
 * Global Vitest setup, loaded before every test file (see vite.config.ts).
 *
 * - Registers @testing-library/jest-dom matchers (toBeInTheDocument, etc.).
 * - Mocks the Tauri runtime (`@tauri-apps/api/*`), which is unavailable in
 *   jsdom — `invoke` is replaced with a vi.fn() that tests can override.
 * - Cleans up the React tree and resets mocks between tests.
 */
import "@testing-library/jest-dom/vitest";
import { afterEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

// ── Mock the Tauri core bridge ──────────────────────────────────────────────
// api.ts does `invoke<BackendInfo>("get_backend_info")`; default to a dummy
// port/token so the request helper doesn't throw. Individual tests can
// `vi.mocked(invoke)...`.
vi.mock("@tauri-apps/api/core", () => ({
  invoke: vi.fn(async (cmd: string) => {
    if (cmd === "get_backend_info")
      return { port: 8743, token: "test-token", managed: false, status: "running" };
    if (cmd === "get_api_token") return "test-token";
    return undefined;
  }),
}));

// backend-status events (src/lib/backendStatus.ts): no-op listener.
vi.mock("@tauri-apps/api/event", () => ({
  listen: vi.fn(async () => () => {}),
  emit: vi.fn(async () => {}),
}));

// Updater / process / opener plugins (UpdateChecker).
vi.mock("@tauri-apps/plugin-updater", () => ({
  check: vi.fn(async () => null),
}));
vi.mock("@tauri-apps/plugin-process", () => ({
  relaunch: vi.fn(async () => {}),
  exit: vi.fn(async () => {}),
}));
vi.mock("@tauri-apps/plugin-opener", () => ({
  openUrl: vi.fn(async () => {}),
  openPath: vi.fn(async () => {}),
}));

// Some components import the dialog/opener plugins; stub them defensively.
vi.mock("@tauri-apps/plugin-dialog", () => ({
  open: vi.fn(async () => null),
  save: vi.fn(async () => null),
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});
