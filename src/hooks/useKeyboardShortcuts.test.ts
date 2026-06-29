import { describe, it, expect, beforeEach, vi } from "vitest";
import { renderHook } from "@testing-library/react";
import { useKeyboardShortcuts, SHORTCUT_ROUTES } from "./useKeyboardShortcuts";

const mockNavigate = vi.fn();
vi.mock("react-router-dom", () => ({
  useNavigate: () => mockNavigate,
}));

function press(key: string, opts: Partial<KeyboardEventInit> & { target?: EventTarget } = {}) {
  const ev = new KeyboardEvent("keydown", { key, metaKey: true, bubbles: true, cancelable: true, ...opts });
  if (opts.target) Object.defineProperty(ev, "target", { value: opts.target });
  window.dispatchEvent(ev);
  return ev;
}

describe("useKeyboardShortcuts", () => {
  beforeEach(() => {
    mockNavigate.mockClear();
  });

  it("navigates to each page on Cmd/Ctrl+1..8", () => {
    renderHook(() => useKeyboardShortcuts());
    for (let i = 1; i <= SHORTCUT_ROUTES.length; i++) {
      press(String(i));
      expect(mockNavigate).toHaveBeenLastCalledWith(SHORTCUT_ROUTES[i - 1]);
    }
  });

  it("opens settings on Cmd/Ctrl+,", () => {
    renderHook(() => useKeyboardShortcuts());
    press(",");
    expect(mockNavigate).toHaveBeenCalledWith("/settings");
  });

  it("dispatches a langhire:export event on Cmd/Ctrl+E", () => {
    renderHook(() => useKeyboardShortcuts());
    const spy = vi.fn();
    window.addEventListener("langhire:export", spy);
    press("e");
    expect(spy).toHaveBeenCalled();
    window.removeEventListener("langhire:export", spy);
  });

  it("ignores shortcuts without the modifier key", () => {
    renderHook(() => useKeyboardShortcuts());
    press("1", { metaKey: false, ctrlKey: false });
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it("ignores shortcuts while typing in an input", () => {
    renderHook(() => useKeyboardShortcuts());
    const input = document.createElement("input");
    document.body.appendChild(input);
    press("1", { target: input });
    expect(mockNavigate).not.toHaveBeenCalled();
    input.remove();
  });

  it("ignores out-of-range number keys (9, 0)", () => {
    renderHook(() => useKeyboardShortcuts());
    press("9");
    press("0");
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it("removes its listener on unmount", () => {
    const { unmount } = renderHook(() => useKeyboardShortcuts());
    unmount();
    press("1");
    expect(mockNavigate).not.toHaveBeenCalled();
  });
});
