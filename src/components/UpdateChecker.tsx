import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Download, Loader2, X } from "lucide-react";
import { check, type Update } from "@tauri-apps/plugin-updater";
import { relaunch } from "@tauri-apps/plugin-process";

function inTauri(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

/**
 * Checks for an app update once on startup. All errors (offline, no release
 * manifest yet, placeholder signing key, not running in Tauri) are ignored
 * silently. When an update exists, shows a small toast with a button that
 * downloads + installs it and relaunches the app.
 */
export default function UpdateChecker() {
  const { t } = useTranslation();
  const [update, setUpdate] = useState<Update | null>(null);
  const [installing, setInstalling] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if (!inTauri() || import.meta.env.DEV) return;
    let cancelled = false;
    check()
      .then((u) => {
        if (!cancelled && u) setUpdate(u);
      })
      .catch(() => {
        /* silently ignore update check failures */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!update || dismissed) return null;

  const install = async () => {
    setInstalling(true);
    try {
      await update.downloadAndInstall();
      await relaunch();
    } catch (e) {
      // e.g. signature verification failed (unconfigured pubkey) or network.
      console.warn("Update install failed:", e);
      setInstalling(false);
      setDismissed(true);
    }
  };

  return (
    <div
      role="status"
      className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 flex items-center gap-3 px-4 py-3 bg-card border border-border rounded-xl shadow-lg text-sm"
    >
      <span className="text-foreground">
        {t("update.available", { version: update.version })}
      </span>
      <button
        onClick={install}
        disabled={installing}
        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary text-primary-foreground text-xs font-semibold hover:bg-primary/90 disabled:opacity-60 transition-colors"
      >
        {installing ? (
          <Loader2 className="w-3.5 h-3.5 animate-spin" />
        ) : (
          <Download className="w-3.5 h-3.5" />
        )}
        {installing ? t("update.installing") : t("update.restartToInstall")}
      </button>
      {!installing && (
        <button
          onClick={() => setDismissed(true)}
          aria-label={t("update.dismiss")}
          className="p-1 rounded text-muted-foreground hover:text-foreground"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      )}
    </div>
  );
}
