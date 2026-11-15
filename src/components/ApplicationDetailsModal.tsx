import { useEffect, useState } from "react";
import { X, Loader2, Image as ImageIcon, FileText, AlertTriangle } from "lucide-react";
import { useTranslation } from "react-i18next";
import { getApplications, openLocalFile } from "../lib/api";
import type { ApplicationAnswer, ApplicationRecord, Job } from "../lib/types";

/** Answers below this confidence are flagged for the user to double-check. */
const LOW_CONFIDENCE = 0.6;

function isUncertainAnswer(a: ApplicationAnswer): boolean {
  return (
    a.source === "inferred" ||
    (typeof a.confidence === "number" && a.confidence < LOW_CONFIDENCE)
  );
}

const OUTCOME_STYLES: Record<string, string> = {
  submitted: "bg-green-50 text-green-700",
  failed: "bg-red-50 text-red-700",
  needs_input: "bg-violet-50 text-violet-700",
  skipped: "bg-secondary text-muted-foreground",
  ready_to_submit: "bg-sky-50 text-sky-700",
};

interface Props {
  job: Job;
  onClose: () => void;
}

/** Latest application record of a job: outcome, answers, resume, cost, screenshot. */
export default function ApplicationDetailsModal({ job, onClose }: Props) {
  const { t } = useTranslation("apply");
  const [record, setRecord] = useState<ApplicationRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [openError, setOpenError] = useState(false);

  useEffect(() => {
    let active = true;
    getApplications({ jobUrl: job.url, limit: 1 })
      .then((rows) => {
        if (active) setRecord(rows && rows.length > 0 ? rows[0] : null);
      })
      .catch(() => {
        if (active) setError(true);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [job.url]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const open = (path: string) => {
    setOpenError(false);
    openLocalFile(path).catch(() => setOpenError(true));
  };

  const outcomeLabel = (outcome: string) => {
    switch (outcome) {
      case "submitted":
        return t("details.outcomes.submitted");
      case "failed":
        return t("details.outcomes.failed");
      case "needs_input":
        return t("details.outcomes.needsInput");
      case "skipped":
        return t("details.outcomes.skipped");
      case "ready_to_submit":
        return t("details.outcomes.readyToSubmit");
      default:
        return outcome;
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={t("details.title")}
        className="bg-card rounded-2xl shadow-xl max-w-3xl w-full max-h-[85vh] overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between p-5 border-b border-border">
          <div className="min-w-0">
            <h3 className="text-base font-semibold text-foreground">{t("details.title")}</h3>
            <p className="text-[13px] text-muted-foreground mt-0.5 truncate">
              {job.title || job.url}
              {job.company ? ` · ${job.company}` : ""}
            </p>
          </div>
          <button
            onClick={onClose}
            aria-label={t("details.close")}
            className="p-1.5 text-muted-foreground hover:text-foreground"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-6 h-6 animate-spin text-primary" />
            </div>
          ) : error ? (
            <div className="error-banner">{t("details.loadFailed")}</div>
          ) : !record ? (
            <p className="text-sm text-muted-foreground text-center py-8">{t("details.none")}</p>
          ) : (
            <div className="space-y-5">
              {/* Summary */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-[11px] text-muted-foreground uppercase font-medium">
                    {t("details.outcome")}
                  </p>
                  <span
                    data-testid="application-outcome"
                    className={`inline-block mt-1 px-2.5 py-0.5 rounded-full text-[12px] font-semibold ${
                      OUTCOME_STYLES[record.outcome] || "bg-secondary text-foreground"
                    }`}
                  >
                    {outcomeLabel(record.outcome)}
                  </span>
                  {record.outcome === "ready_to_submit" && (
                    <p data-testid="intercepted-count" className="text-[13px] text-muted-foreground mt-1">
                      {t("details.intercepted", { n: Number(record.intercepted ?? 0) })}
                    </p>
                  )}
                  {record.reason && (
                    <p className="text-[13px] text-muted-foreground mt-1">{record.reason}</p>
                  )}
                  {record.confirmation && (
                    <p className="text-[13px] text-foreground mt-1">
                      {t("details.confirmation", { text: record.confirmation })}
                    </p>
                  )}
                </div>
                <div className="space-y-1">
                  <p className="text-[11px] text-muted-foreground uppercase font-medium">
                    {t("details.cost")}
                  </p>
                  <p className="text-sm text-foreground">
                    {record.cost_usd != null ? `$${record.cost_usd.toFixed(4)}` : "—"}
                    {record.steps != null && (
                      <span className="text-muted-foreground ml-2">
                        {t("details.steps", { n: record.steps })}
                      </span>
                    )}
                  </p>
                  {!!record.prompt_tokens && (
                    <p className="text-[13px] text-muted-foreground">
                      {t("details.tokens", {
                        prompt: record.prompt_tokens.toLocaleString(),
                        cached: (record.cached_tokens || 0).toLocaleString(),
                        completion: (record.completion_tokens || 0).toLocaleString(),
                      })}
                      {record.llm_model ? ` · ${record.llm_model}` : ""}
                    </p>
                  )}
                  {record.ats && (
                    <p className="text-[13px] text-muted-foreground">
                      {t("details.ats", { ats: record.ats })}
                    </p>
                  )}
                  <p className="text-[12px] text-muted-foreground">
                    {new Date(record.created_at).toLocaleString()}
                  </p>
                </div>
              </div>

              {/* Missing info */}
              {record.missing_info && record.missing_info.length > 0 && (
                <div className="rounded-lg border border-amber-200 bg-amber-50 p-3">
                  <p className="text-[13px] font-semibold text-amber-800 mb-1">
                    {t("details.missingInfo")}
                  </p>
                  <ul className="list-disc ml-5 text-[13px] text-amber-800">
                    {record.missing_info.map((m) => (
                      <li key={m}>{m}</li>
                    ))}
                  </ul>
                  <a href="#/qa" className="text-[13px] text-primary font-semibold hover:underline">
                    {t("needsInput.answerAndRetry")}
                  </a>
                </div>
              )}

              {/* Resume + screenshot */}
              <div className="flex flex-wrap items-center gap-3">
                <div className="flex items-center gap-2 min-w-0 flex-1">
                  <FileText className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                  <span className="text-[13px] text-muted-foreground">{t("details.resume")}</span>
                  <span className="text-[13px] text-foreground truncate" title={record.resume_path || ""}>
                    {record.resume_path || "—"}
                  </span>
                </div>
                {record.resume_path && (
                  <button onClick={() => open(record.resume_path!)} className="btn-secondary text-xs px-3 py-1.5">
                    <FileText className="w-3 h-3" /> {t("details.openResume")}
                  </button>
                )}
                {record.screenshot_path && (
                  <button onClick={() => open(record.screenshot_path!)} className="btn-secondary text-xs px-3 py-1.5">
                    <ImageIcon className="w-3 h-3" /> {t("details.openScreenshot")}
                  </button>
                )}
              </div>
              {openError && (
                <p className="text-[13px] text-destructive" role="alert">{t("details.openFailed")}</p>
              )}

              {/* Answers */}
              <div>
                <h4 className="text-sm font-semibold text-foreground mb-2">
                  {t("details.answers", { n: record.answers?.length || 0 })}
                </h4>
                {!record.answers || record.answers.length === 0 ? (
                  <p className="text-[13px] text-muted-foreground">{t("details.noAnswers")}</p>
                ) : (
                  <div className="rounded-lg border border-border overflow-hidden">
                    <table className="w-full text-[13px]">
                      <thead className="bg-secondary text-muted-foreground">
                        <tr>
                          <th className="text-left font-medium px-3 py-2">{t("details.question")}</th>
                          <th className="text-left font-medium px-3 py-2">{t("details.answer")}</th>
                          <th className="text-left font-medium px-3 py-2">{t("details.source")}</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border">
                        {record.answers.map((a, i) => {
                          const uncertain = isUncertainAnswer(a);
                          return (
                            <tr
                              key={`${a.question}-${i}`}
                              data-testid={uncertain ? "answer-flagged" : "answer-row"}
                              className={uncertain ? "bg-amber-50/60" : ""}
                            >
                              <td className="px-3 py-2 align-top text-foreground">{a.question}</td>
                              <td className="px-3 py-2 align-top text-foreground break-words">
                                {a.answer}
                                {uncertain && (
                                  <span
                                    className="ml-2 inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-amber-100 text-amber-800 text-[11px] font-semibold"
                                    title={t("details.checkAnswerTitle")}
                                  >
                                    <AlertTriangle className="w-3 h-3" /> {t("details.checkAnswer")}
                                  </span>
                                )}
                              </td>
                              <td className="px-3 py-2 align-top text-muted-foreground whitespace-nowrap">
                                {a.source || "—"}
                                {typeof a.confidence === "number" && (
                                  <span className="ml-1">({Math.round(a.confidence * 100)}%)</span>
                                )}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
