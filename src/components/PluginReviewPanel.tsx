import { AlertTriangle, ShieldCheck, X, Loader2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { PluginPreview } from "../lib/types";

interface Props {
  plugin: PluginPreview;
  installing: boolean;
  error?: string | null;
  onInstall: () => void;
  onCancel: () => void;
}

/**
 * Review step before installing a community plugin: who made it, what it
 * tells the agent to do (both prompts, verbatim) and any warnings the
 * backend found. Installing approves exactly this file (its SHA-256).
 */
export default function PluginReviewPanel({ plugin, installing, error, onInstall, onCancel }: Props) {
  const { t } = useTranslation("settings");
  const warnings = plugin.warnings || [];
  return (
    <div
      role="region"
      aria-label={t("plugins.review.title")}
      className="mt-4 rounded-xl border border-border bg-secondary/30 p-4"
    >
      <div className="flex items-start justify-between gap-3 mb-3">
        <div>
          <h4 className="text-sm font-semibold text-foreground">{t("plugins.review.title")}</h4>
          <p className="text-[13px] text-muted-foreground mt-0.5">{t("plugins.review.description")}</p>
        </div>
        <button
          onClick={onCancel}
          aria-label={t("plugins.review.cancel")}
          className="p-1 text-muted-foreground hover:text-foreground"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      <dl className="grid grid-cols-[auto,1fr] gap-x-4 gap-y-1 text-[13px] mb-3">
        <dt className="text-muted-foreground">{t("plugins.review.name")}</dt>
        <dd className="text-foreground font-medium">
          {plugin.display_name} <span className="text-muted-foreground">({plugin.name}, v{plugin.version})</span>
        </dd>
        <dt className="text-muted-foreground">{t("plugins.review.author")}</dt>
        <dd className="text-foreground">{plugin.author || "—"}</dd>
        <dt className="text-muted-foreground">{t("plugins.review.website")}</dt>
        <dd className="text-foreground break-all">{plugin.website || "—"}</dd>
        <dt className="text-muted-foreground">{t("plugins.review.requiresLogin")}</dt>
        <dd className="text-foreground">{plugin.requires_login ? t("plugins.review.yes") : t("plugins.review.no")}</dd>
        <dt className="text-muted-foreground">SHA-256</dt>
        <dd className="text-foreground font-mono text-[11px] break-all">{plugin.sha256}</dd>
      </dl>

      {warnings.length > 0 ? (
        <div
          role="alert"
          data-testid="plugin-warnings"
          className="mb-3 rounded-lg border border-amber-300 bg-amber-50 p-3 text-[13px] text-amber-900"
        >
          <p className="font-semibold flex items-center gap-1.5 mb-1">
            <AlertTriangle className="w-4 h-4" /> {t("plugins.review.warnings", { n: warnings.length })}
          </p>
          <ul className="list-disc ml-5 space-y-0.5">
            {warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="mb-3 text-[13px] text-green-700 flex items-center gap-1.5">
          <ShieldCheck className="w-4 h-4" /> {t("plugins.review.noWarnings")}
        </p>
      )}

      <div className="space-y-3">
        <div>
          <p className="text-[12px] font-semibold text-muted-foreground uppercase mb-1">
            {t("plugins.review.collectionPrompt")}
          </p>
          <pre
            data-testid="plugin-collection-prompt"
            className="max-h-48 overflow-auto rounded-lg border border-border bg-card p-3 font-mono text-[12px] text-foreground whitespace-pre-wrap"
          >
            {plugin.collection_prompt || "—"}
          </pre>
        </div>
        <div>
          <p className="text-[12px] font-semibold text-muted-foreground uppercase mb-1">
            {t("plugins.review.applyPrompt")}
          </p>
          <pre
            data-testid="plugin-apply-prompt"
            className="max-h-48 overflow-auto rounded-lg border border-border bg-card p-3 font-mono text-[12px] text-foreground whitespace-pre-wrap"
          >
            {plugin.apply_prompt || "—"}
          </pre>
        </div>
      </div>

      {error && (
        <p className="mt-3 text-[13px] text-destructive" role="alert">
          {error}
        </p>
      )}

      <div className="flex justify-end gap-2 mt-4">
        <button onClick={onCancel} disabled={installing} className="btn-secondary">
          {t("plugins.review.cancel")}
        </button>
        <button onClick={onInstall} disabled={installing} className="btn-primary">
          {installing && <Loader2 className="w-4 h-4 animate-spin" />}
          {t("plugins.review.install")}
        </button>
      </div>
    </div>
  );
}
