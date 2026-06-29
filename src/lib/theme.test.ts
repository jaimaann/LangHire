import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { getStoredTheme, resolveTheme, applyTheme, setTheme, initTheme } from "./theme";

describe("theme", () => {
  beforeEach(() => {
    // jsdom in this project exposes a method-less `localStorage`; install a
    // minimal Map-backed shim so get/set/clear behave.
    const store = new Map<string, string>();
    vi.stubGlobal("localStorage", {
      getItem: (k: string) => (store.has(k) ? store.get(k)! : null),
      setItem: (k: string, v: string) => void store.set(k, String(v)),
      removeItem: (k: string) => void store.delete(k),
      clear: () => store.clear(),
    });
    document.documentElement.classList.remove("dark");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  function stubMatchMedia(matchesDark: boolean) {
    const listeners: Array<(e: MediaQueryListEvent) => void> = [];
    const mql = {
      matches: matchesDark,
      addEventListener: (_: string, cb: (e: MediaQueryListEvent) => void) => listeners.push(cb),
      removeEventListener: (_: string, cb: (e: MediaQueryListEvent) => void) => {
        const i = listeners.indexOf(cb);
        if (i >= 0) listeners.splice(i, 1);
      },
    };
    vi.stubGlobal("matchMedia", vi.fn(() => mql));
    return { mql, fire: () => listeners.forEach((cb) => cb({} as MediaQueryListEvent)) };
  }

  it("defaults to 'system' when nothing is stored", () => {
    expect(getStoredTheme()).toBe("system");
  });

  it("returns the stored value when valid, else falls back to system", () => {
    localStorage.setItem("langhire_theme", "dark");
    expect(getStoredTheme()).toBe("dark");
    localStorage.setItem("langhire_theme", "bogus");
    expect(getStoredTheme()).toBe("system");
  });

  it("resolveTheme passes through explicit modes", () => {
    expect(resolveTheme("light")).toBe("light");
    expect(resolveTheme("dark")).toBe("dark");
  });

  it("resolveTheme('system') follows prefers-color-scheme", () => {
    stubMatchMedia(true);
    expect(resolveTheme("system")).toBe("dark");
    stubMatchMedia(false);
    expect(resolveTheme("system")).toBe("light");
  });

  it("applyTheme toggles the dark class on <html>", () => {
    applyTheme("dark");
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    applyTheme("light");
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });

  it("setTheme persists to localStorage and applies", () => {
    stubMatchMedia(false);
    setTheme("dark");
    expect(localStorage.getItem("langhire_theme")).toBe("dark");
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });

  it("initTheme applies stored theme and reacts to OS changes while in system mode", () => {
    const { fire } = stubMatchMedia(true);
    localStorage.setItem("langhire_theme", "system");
    const cleanup = initTheme();
    // system + OS dark → dark applied
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    // OS flips; still in system mode → re-applies
    fire();
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    cleanup();
  });

  it("initTheme does not override an explicit choice on OS change", () => {
    const { fire } = stubMatchMedia(true);
    localStorage.setItem("langhire_theme", "light");
    const cleanup = initTheme();
    expect(document.documentElement.classList.contains("dark")).toBe(false);
    fire(); // OS goes dark, but user chose light
    expect(document.documentElement.classList.contains("dark")).toBe(false);
    cleanup();
  });
});
