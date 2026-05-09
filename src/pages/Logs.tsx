import { useState, useEffect } from "react";
import { ScrollText, ChevronRight, Loader2, RefreshCw, CheckCircle, XCircle } from "lucide-react";
import { getRunsWithLogs, getRunLogs } from "../lib/api";
import type { RunWithLogs, RunLog } from "../lib/types";
import LogLine from "../components/LogLine";
import { PageHeader, LoadingSpinner } from "../components/ui";
import { useTranslation } from "react-i18next";

export default function Logs() {
  const { t } = useTranslation("logs");
  const [runs, setRuns] = useState<RunWithLogs[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [runLogs, setRunLogs] = useState<RunLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingLogs, setLoadingLogs] = useState(false);

  useEffect(() => {
    getRunsWithLogs(50)
      .then((data) => setRuns(data || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const selectRun = async (runId: string) => {
    setSelectedRunId(runId);
    setLoadingLogs(true);
    try {
      const logs = await getRunLogs(runId);
      setRunLogs(logs || []);
    } catch {
      setRunLogs([]);
    } finally {
      setLoadingLogs(false);
    }
  };

  const refresh = () => {
    setLoading(true);
    getRunsWithLogs(50)
      .then((data) => setRuns(data || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  if (loading) return <LoadingSpinner />;

  return (
    <div className="max-w-6xl">
      <PageHeader
        title={t("title")}
        subtitle={t("subtitle")}
        actions={
          <button onClick={refresh} className="btn-secondary">
            <RefreshCw className="w-4 h-4" /> {t("refresh")}
          </button>
        }
      />

      <div className="grid grid-cols-3 gap-4" style={{ minHeight: 500 }}>
        {/* Left: Run list */}
        <div className="col-span-1 border border-border rounded-2xl overflow-hidden bg-white shadow-sm">
          <div className="px-4 py-3 bg-gray-50 border-b border-border text-sm font-medium text-foreground">
            {t("runs.title", { count: runs.length })}
          </div>
          <div className="overflow-y-auto" style={{ maxHeight: 600 }}>
            {runs.length === 0 ? (
              <div className="p-4 text-sm text-muted-foreground text-center">
                {t("runs.empty")}
              </div>
            ) : (
              runs.map((run) => (
                <button
                  key={run.id}
                  onClick={() => run.run_id && selectRun(run.run_id)}
                  disabled={!run.run_id}
                  className={`w-full text-left px-4 py-3 border-b border-border hover:bg-gray-50 transition-colors ${
                    selectedRunId === run.run_id ? "bg-primary/5 border-l-2 border-l-primary" : ""
                  } ${!run.run_id ? "opacity-50" : ""}`}
                >
                  <div className="flex items-center gap-2 mb-1">
                    {run.success ? (
                      <CheckCircle className="w-3.5 h-3.5 text-green-600 shrink-0" />
                    ) : (
                      <XCircle className="w-3.5 h-3.5 text-red-500 shrink-0" />
                    )}
                    <span className="text-sm font-medium text-foreground truncate">
                      {run.job_title || t("runs.unknown")}
                    </span>
                  </div>
                  <div className="text-xs text-muted-foreground truncate">
                    {run.company || ""} {run.website_domain ? `(${run.website_domain})` : ""}
                  </div>
                  <div className="flex items-center justify-between mt-1">
                    <span className="text-xs text-muted-foreground">
                      {run.created_at ? new Date(run.created_at).toLocaleDateString() : ""}
                    </span>
                    <div className="flex items-center gap-1 text-xs text-muted-foreground">
                      <ScrollText className="w-3 h-3" />
                      {t("runs.lines", { count: run.log_count })}
                      <ChevronRight className="w-3 h-3" />
                    </div>
                  </div>
                </button>
              ))
            )}
          </div>
        </div>

        {/* Right: Log detail */}
        <div className="col-span-2 border border-border rounded-2xl overflow-hidden bg-white shadow-sm">
          <div className="px-4 py-3 bg-gray-50 border-b border-border text-sm font-medium text-foreground flex items-center gap-2">
            <ScrollText className="w-4 h-4" />
            {selectedRunId ? t("detail.runTitle", { id: selectedRunId }) : t("detail.selectPrompt")}
          </div>
          <div className="log-viewer !max-h-none" style={{ maxHeight: 600 }}>
            {!selectedRunId ? (
              <div className="text-gray-500 text-center mt-16">
                {t("detail.selectFromPanel")}
              </div>
            ) : loadingLogs ? (
              <div className="flex items-center justify-center h-32">
                <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
              </div>
            ) : runLogs.length === 0 ? (
              <div className="text-gray-500 text-center mt-16">
                {t("detail.noLogs")}
              </div>
            ) : (
              runLogs.map((log) => (
                <LogLine key={log.id} line={log.message} />
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
