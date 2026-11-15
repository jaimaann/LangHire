import { X, AlertCircle, CheckCircle } from "lucide-react";
import { useTranslation } from "react-i18next";

export interface Notice {
  kind: "error" | "info";
  text: string;
}

/**
 * A dismissible message inside the page. Replaces window.alert(), which blocks
 * the whole desktop window, can't be styled or translated, and in a webview
 * shows the app's internal origin as its title.
 */
export default function InlineNotice({ notice, onClose }: { notice: Notice | null; onClose: () => void }) {
  const { t } = useTranslation("common");
  if (!notice) return null;
  const error = notice.kind === "error";
  return (
    <div
      role={error ? "alert" : "status"}
      data-testid="inline-notice"
      className={`card mb-4 flex items-start gap-3 text-sm ${
        error ? "border-destructive/40 text-destructive" : "border-green-300 text-green-800 dark:text-green-300"
      }`}
    >
      {error ? <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" /> : <CheckCircle className="w-4 h-4 mt-0.5 shrink-0" />}
      <span className="flex-1 whitespace-pre-line">{notice.text}</span>
      <button onClick={onClose} aria-label={t("notice.dismiss")} className="shrink-0 opacity-70 hover:opacity-100">
        <X className="w-4 h-4" />
      </button>
    </div>
  );
}
