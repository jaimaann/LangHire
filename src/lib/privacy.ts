/** Client-side helpers for the "Delete all my data" flow. */

/** Remove every LangHire-owned key (prefixed `langhire`) from web storage. */
export function clearLocalAppData(): void {
  for (const storage of [safeStorage("localStorage"), safeStorage("sessionStorage")]) {
    if (!storage) continue;
    try {
      const keys: string[] = [];
      for (let i = 0; i < storage.length; i++) {
        const k = storage.key(i);
        if (k && k.toLowerCase().startsWith("langhire")) keys.push(k);
      }
      keys.forEach((k) => storage.removeItem(k));
    } catch {
      /* storage unavailable */
    }
  }
}

function safeStorage(name: "localStorage" | "sessionStorage"): Storage | null {
  try {
    return window[name] ?? null;
  } catch {
    return null;
  }
}

/** Return to the app root and reload so first-run setup shows again. */
export function restartApp(): void {
  window.location.hash = "#/";
  window.location.reload();
}

/** `langhire-export-YYYY-MM-DD.json` for the given (local) date. */
export function exportFileName(date: Date = new Date()): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `langhire-export-${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}.json`;
}

/** Trigger a browser download of `data` as pretty-printed JSON. */
export function downloadJson(data: unknown, fileName: string): void {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = fileName;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
