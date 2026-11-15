import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { AlertTriangle, Loader2 } from "lucide-react";
import { getBackendInfo } from "../lib/api";
import { applyBackendStatus, useBackendStatus, type BackendStatus } from "../lib/backendStatus";

const KNOWN: BackendStatus[] = ["starting", "running", "crashed", "failed"];

/**
 * Non-blocking banner shown while the supervised backend sidecar is being
 * restarted after a crash, or after the host gave up restarting it.
 * The initial "starting" phase is not shown here (the sidebar covers it).
 */
export default function BackendStatusBanner() {
  const { t } = useTranslation();
  const { status, restarts } = useBackendStatus();

  // Seed from the host in case a status event fired before we subscribed.
  useEffect(() => {
    getBackendInfo()
      .then((info) => {
        const s = info.status as BackendStatus | undefined;
        if (info.managed && s && KNOWN.includes(s) && s !== "starting") {
          applyBackendStatus({ status: s });
        }
      })
      .catch(() => {});
  }, []);

  const restarting = status === "crashed" || (status === "starting" && restarts > 0);
  if (!restarting && status !== "failed") return null;

  const failed = status === "failed";
  return (
    <div
      role="status"
      aria-live="polite"
      className={`fixed top-3 left-1/2 -translate-x-1/2 z-50 flex items-center gap-2 px-4 py-2 rounded-lg shadow-lg text-sm font-medium border ${
        failed
          ? "bg-destructive/10 text-destructive border-destructive/30"
          : "bg-card text-foreground border-border"
      }`}
    >
      {failed ? (
        <AlertTriangle className="w-4 h-4" />
      ) : (
        <Loader2 className="w-4 h-4 animate-spin text-primary" />
      )}
      {failed ? t("backend.failed") : t("backend.restarting")}
    </div>
  );
}
