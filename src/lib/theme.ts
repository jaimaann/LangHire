/**
 * Theme management — Light / Dark / System.
 *
 * The chosen mode is persisted in localStorage (so it applies instantly on the
 * next launch, before the backend settings round-trip) and mirrored into the
 * backend `theme` setting for cross-device/profile persistence.
 *
 * "system" follows the OS `prefers-color-scheme` and updates live.
 */
export type ThemeMode = "light" | "dark" | "system";

const STORAGE_KEY = "langhire_theme";

export function getStoredTheme(): ThemeMode {
  const v = typeof localStorage !== "undefined" ? localStorage.getItem(STORAGE_KEY) : null;
  return v === "light" || v === "dark" || v === "system" ? v : "system";
}

function prefersDark(): boolean {
  return typeof window !== "undefined" && typeof window.matchMedia === "function"
    ? window.matchMedia("(prefers-color-scheme: dark)").matches
    : false;
}

/** Resolve a mode to the concrete light/dark that should be displayed. */
export function resolveTheme(mode: ThemeMode): "light" | "dark" {
  if (mode === "system") return prefersDark() ? "dark" : "light";
  return mode;
}

/** Toggle the `dark` class on <html> to match the resolved mode. */
export function applyTheme(mode: ThemeMode): void {
  if (typeof document === "undefined") return;
  const resolved = resolveTheme(mode);
  document.documentElement.classList.toggle("dark", resolved === "dark");
}

/** Persist the mode locally and apply it immediately. */
export function setTheme(mode: ThemeMode): void {
  if (typeof localStorage !== "undefined") localStorage.setItem(STORAGE_KEY, mode);
  applyTheme(mode);
}

let mediaListener: ((e: MediaQueryListEvent) => void) | null = null;

/**
 * Apply the stored theme on startup and, while in "system" mode, keep it in
 * sync with live OS changes. Returns a cleanup function.
 */
export function initTheme(): () => void {
  const mode = getStoredTheme();
  applyTheme(mode);

  if (typeof window !== "undefined" && typeof window.matchMedia === "function") {
    const mql = window.matchMedia("(prefers-color-scheme: dark)");
    mediaListener = () => {
      if (getStoredTheme() === "system") applyTheme("system");
    };
    mql.addEventListener("change", mediaListener);
    return () => {
      if (mediaListener) mql.removeEventListener("change", mediaListener);
      mediaListener = null;
    };
  }
  return () => {};
}
