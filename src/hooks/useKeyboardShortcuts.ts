/**
 * Global keyboard shortcuts for power users (issue #46).
 *
 * - Cmd/Ctrl + 1..8  → navigate to the Nth page (order matches the sidebar)
 * - Cmd/Ctrl + ,     → open Settings
 * - Cmd/Ctrl + E     → trigger an export (dispatches a `langhire:export` event)
 *
 * Shortcuts are ignored while the user is typing in an input/textarea/select
 * or a contentEditable element, so they never clobber normal text entry.
 */
import { useEffect } from "react";
import { useNavigate } from "react-router-dom";

/** Page order for Cmd/Ctrl+1..N — kept in sync with the sidebar nav. */
export const SHORTCUT_ROUTES: string[] = [
  "/", // 1 Dashboard
  "/guide", // 2 Guide
  "/profile", // 3 Profile
  "/llm", // 4 LLM Settings
  "/jobs", // 5 Jobs
  "/memory", // 6 Memory
  "/qa", // 7 Q&A
  "/logs", // 8 Logs
];

function isTypingTarget(el: EventTarget | null): boolean {
  if (!(el instanceof HTMLElement)) return false;
  const tag = el.tagName;
  return (
    tag === "INPUT" ||
    tag === "TEXTAREA" ||
    tag === "SELECT" ||
    el.isContentEditable
  );
}

export function useKeyboardShortcuts(): void {
  const navigate = useNavigate();

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      const mod = e.metaKey || e.ctrlKey;
      if (!mod) return;
      if (isTypingTarget(e.target)) return;

      // Cmd/Ctrl + , → Settings
      if (e.key === ",") {
        e.preventDefault();
        navigate("/settings");
        return;
      }

      // Cmd/Ctrl + E → export (page decides what to do)
      if (e.key.toLowerCase() === "e") {
        e.preventDefault();
        window.dispatchEvent(new CustomEvent("langhire:export"));
        return;
      }

      // Cmd/Ctrl + 1..8 → page navigation
      if (/^[1-8]$/.test(e.key)) {
        const idx = Number(e.key) - 1;
        const route = SHORTCUT_ROUTES[idx];
        if (route) {
          e.preventDefault();
          navigate(route);
        }
      }
    }

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [navigate]);
}
