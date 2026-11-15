import { AlertTriangle, Clock, Globe, X } from "lucide-react";
import { useTranslation } from "react-i18next";

interface AutomationDialogProps {
  open: boolean;
  title: string;
  onConfirm: () => void;
  onCancel: () => void;
}

export default function AutomationDialog({ open, title, onConfirm, onCancel }: AutomationDialogProps) {
  const { t } = useTranslation("common");
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onCancel}>
      {/* max-h + scrolling body: on short windows the Start button stays reachable */}
      <div
        role="dialog"
        aria-modal="true"
        className="bg-card rounded-2xl shadow-xl w-full max-w-lg max-h-full flex flex-col overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-6 pt-6 pb-0 flex-shrink-0">
          <h2 className="text-lg font-bold text-foreground">{title}</h2>
          <button
            onClick={onCancel}
            aria-label={t("automation.cancel")}
            className="p-1.5 rounded-lg hover:bg-secondary transition-colors cursor-pointer"
          >
            <X className="w-5 h-5 text-muted-foreground" />
          </button>
        </div>

        <div className="px-6 py-5 space-y-4 overflow-y-auto min-h-0">
          <div className="flex gap-3 p-4 bg-amber-50 border border-amber-200 rounded-xl">
            <Clock className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
            <div className="text-sm text-amber-900">
              <strong className="block mb-1">{t("automation.slowTitle")}</strong>
              {t("automation.slowBody")}
            </div>
          </div>

          <div className="flex gap-3 p-4 bg-blue-50 border border-blue-200 rounded-xl">
            <Globe className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
            <div className="text-sm text-blue-900">
              <strong className="block mb-1">{t("automation.loginTitle")}</strong>
              {t("automation.loginBody")}
            </div>
          </div>

          <div className="flex gap-3 p-4 bg-secondary border border-border rounded-xl">
            <AlertTriangle className="w-5 h-5 text-muted-foreground flex-shrink-0 mt-0.5" />
            <div className="text-sm text-foreground">
              <strong className="block mb-1">{t("automation.windowTitle")}</strong>
              {t("automation.windowBody")}
            </div>
          </div>
        </div>

        <div className="flex justify-end gap-3 px-6 pb-6 pt-1 flex-shrink-0">
          <button onClick={onCancel} className="btn-secondary">{t("automation.cancel")}</button>
          <button onClick={onConfirm} className="btn-dark">{t("automation.start")}</button>
        </div>
      </div>
    </div>
  );
}
