import { useState, useEffect, useRef } from "react";
import {
  Square,
  Terminal,
  Loader2,
  Briefcase,
  CheckCircle,
  XCircle,
  Clock,
  ExternalLink,
  Brain,
  ChevronDown,
  ChevronRight,
  FileText,
  Zap,
} from "lucide-react";
import {
  stopApplying,
  getApplyStatus,
  getJobs,
  getMetricRuns,
  getSettings,
} from "../../lib/api";
import { trackEvent } from "../../lib/analytics";
import LogLine from "../../components/LogLine";
import { useTranslation } from "react-i18next";
import type { Job, RunMetric, AppSettings } from "../../lib/types";

interface AppliedJobRow {
  job: Job;
  metric?: RunMetric;
}

interface HistoryTabProps {
  onJobsChanged: () => void;
}

export default function HistoryTab({ onJobsChanged }: HistoryTabProps) {
  const { t } = useTranslation("apply");

  const [running, setRunning] = useState(false);
  const [log, setLog] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const logRef = useRef<HTMLDivElement>(null);

  // Applied jobs state
  const [appliedJobs, setAppliedJobs] = useState<AppliedJobRow[]>([]);
  const [expandedUrl, setExpandedUrl] = useState<string | null>(null);
  const [resumePath, setResumePath] = useState<string>("");

  useEffect(() => {
    Promise.all([
      getApplyStatus().then((s) => {
        setRunning(s.running);
        setLog(s.log || []);
      }),
      loadAppliedJobs(),
    ]).finally(() => setLoading(false));
  }, []);

  async function loadAppliedJobs() {
    try {
      const [applied, failed, metrics, settings] = await Promise.all([
        getJobs({ status: "applied" }),
        getJobs({ status: "failed" }),
        getMetricRuns(200),
        getSettings(),
      ]);

      setResumePath((settings as AppSettings).resume_path || "");

      const allJobs = [...applied, ...failed];
      // Build a map of metrics by job_url for quick lookup
      const metricsByUrl = new Map<string, RunMetric>();
      for (const m of metrics) {
        // Keep the most recent metric per job_url
        const existing = metricsByUrl.get(m.job_url);
        if (
          !existing ||
          new Date(m.started_at) > new Date(existing.started_at)
        ) {
          metricsByUrl.set(m.job_url, m);
        }
      }

      const rows: AppliedJobRow[] = allJobs.map((job) => ({
        job,
        metric: metricsByUrl.get(job.url),
      }));

      // Sort by applied_at desc (newest first)
      rows.sort((a, b) => {
        const dateA = a.job.applied_at || a.metric?.started_at || "";
        const dateB = b.job.applied_at || b.metric?.started_at || "";
        return dateB.localeCompare(dateA);
      });

      setAppliedJobs(rows);
    } catch {
      // Silently fail
    }
  }

  useEffect(() => {
    if (!running) return;
    let active = true;
    const poll = setInterval(() => {
      getApplyStatus()
        .then((s) => {
          if (active) {
            if (!s.running) {
              trackEvent("apply_completed", { error: s.error || null });
              loadAppliedJobs();
              onJobsChanged();
            }
            setRunning(s.running);
            setLog(s.log || []);
          }
        })
        .catch(() => {});
    }, 2000);
    return () => {
      active = false;
      clearInterval(poll);
    };
  }, [running, onJobsChanged]);

  useEffect(() => {
    const el = logRef.current;
    if (el) {
      const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
      if (nearBottom) el.scrollTop = el.scrollHeight;
    }
  }, [log]);

  const handleStop = async () => {
    await stopApplying();
    setRunning(false);
  };

  const toggleExpand = (url: string) => {
    setExpandedUrl(expandedUrl === url ? null : url);
  };

  const formatDuration = (seconds: number): string => {
    if (seconds < 60) return `${Math.round(seconds)}s`;
    const mins = Math.floor(seconds / 60);
    const secs = Math.round(seconds % 60);
    return `${mins}m ${secs}s`;
  };

  const formatDate = (dateStr: string | undefined): string => {
    if (!dateStr) return "—";
    const d = new Date(dateStr);
    return d.toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-48">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div>
      {/* Live Log (only shown when automation is running) */}
      {(log.length > 0 || running) && (
        <div className="card mb-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="section-title">
              {running ? t("log.liveOutput") : t("log.outputLog")}
            </h3>
            {running && (
              <button onClick={handleStop} className="btn-destructive text-xs px-3 py-1.5">
                <Square className="w-3 h-3" /> {t("controls.stop")}
              </button>
            )}
          </div>
          <div ref={logRef} className="log-viewer">
            <div className="flex items-center gap-2 mb-2 text-gray-400">
              <Terminal className="w-3.5 h-3.5" /> {t("log.applicationLog")}
              {running && (
                <Loader2 className="w-3.5 h-3.5 animate-spin text-green-400" />
              )}
            </div>
            {log.map((line, i) => (
              <LogLine key={i} line={line} />
            ))}
          </div>
        </div>
      )}

      {/* Applied Jobs Section */}
      {appliedJobs.length > 0 && (
        <div className="card">
          <h3 className="section-title mb-4">
            Applied Jobs
            <span className="ml-2 text-sm font-normal text-muted-foreground">
              ({appliedJobs.length})
            </span>
          </h3>

          <div className="divide-y divide-border rounded-xl border border-border overflow-hidden">
            {appliedJobs.map((row) => {
              const isExpanded = expandedUrl === row.job.url;
              const isSuccess = row.job.status === "applied";

              return (
                <div key={row.job.url}>
                  {/* Row */}
                  <button
                    onClick={() => toggleExpand(row.job.url)}
                    className="w-full text-left px-4 py-3 hover:bg-gray-50 transition-colors flex items-center gap-3"
                  >
                    {isExpanded ? (
                      <ChevronDown className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                    ) : (
                      <ChevronRight className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                    )}

                    {/* Status icon */}
                    {isSuccess ? (
                      <CheckCircle className="w-4 h-4 text-green-500 flex-shrink-0" />
                    ) : (
                      <XCircle className="w-4 h-4 text-red-500 flex-shrink-0" />
                    )}

                    {/* Title & Company */}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-foreground truncate">
                        {row.job.title || "Untitled"}
                      </p>
                      <p className="text-[12px] text-muted-foreground truncate">
                        {row.job.company || "Unknown company"}
                      </p>
                    </div>

                    {/* Status badge */}
                    <span
                      className={`px-2 py-0.5 rounded-full text-[11px] font-medium flex-shrink-0 ${
                        isSuccess
                          ? "bg-green-50 text-green-700"
                          : "bg-red-50 text-red-700"
                      }`}
                    >
                      {isSuccess ? "Applied" : "Failed"}
                    </span>

                    {/* Date */}
                    <span className="text-[12px] text-muted-foreground flex-shrink-0 w-36 text-right">
                      {formatDate(row.job.applied_at || row.metric?.started_at)}
                    </span>

                    {/* Duration */}
                    <span className="text-[12px] text-muted-foreground flex-shrink-0 w-16 text-right">
                      {row.metric
                        ? formatDuration(row.metric.duration_seconds)
                        : "—"}
                    </span>
                  </button>

                  {/* Expanded detail panel */}
                  {isExpanded && (
                    <div className="px-4 py-4 bg-gray-50 border-t border-border">
                      <div className="grid grid-cols-2 gap-4">
                        {/* Left column */}
                        <div className="space-y-3">
                          {/* Job URL */}
                          <div className="flex items-start gap-2">
                            <ExternalLink className="w-3.5 h-3.5 text-muted-foreground mt-0.5 flex-shrink-0" />
                            <div className="min-w-0">
                              <p className="text-[11px] text-muted-foreground uppercase font-medium">
                                Job URL
                              </p>
                              <a
                                href={row.job.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-sm text-primary hover:underline truncate block"
                              >
                                {row.job.url}
                              </a>
                            </div>
                          </div>

                          {/* Status + Error */}
                          <div className="flex items-start gap-2">
                            {isSuccess ? (
                              <CheckCircle className="w-3.5 h-3.5 text-green-500 mt-0.5 flex-shrink-0" />
                            ) : (
                              <XCircle className="w-3.5 h-3.5 text-red-500 mt-0.5 flex-shrink-0" />
                            )}
                            <div>
                              <p className="text-[11px] text-muted-foreground uppercase font-medium">
                                Status
                              </p>
                              <p className="text-sm text-foreground">
                                {isSuccess ? "Successfully applied" : "Failed"}
                              </p>
                              {(row.job.error ||
                                row.metric?.error_message) && (
                                <p className="text-xs text-red-600 mt-0.5">
                                  {row.job.error || row.metric?.error_message}
                                </p>
                              )}
                            </div>
                          </div>

                          {/* Date & Duration */}
                          <div className="flex items-start gap-2">
                            <Clock className="w-3.5 h-3.5 text-muted-foreground mt-0.5 flex-shrink-0" />
                            <div>
                              <p className="text-[11px] text-muted-foreground uppercase font-medium">
                                Date & Duration
                              </p>
                              <p className="text-sm text-foreground">
                                {formatDate(
                                  row.job.applied_at || row.metric?.started_at
                                )}
                                {row.metric && (
                                  <span className="text-muted-foreground ml-2">
                                    (
                                    {formatDuration(
                                      row.metric.duration_seconds
                                    )}
                                    )
                                  </span>
                                )}
                              </p>
                            </div>
                          </div>

                          {/* Resume path */}
                          {resumePath && (
                            <div className="flex items-start gap-2">
                              <FileText className="w-3.5 h-3.5 text-muted-foreground mt-0.5 flex-shrink-0" />
                              <div className="min-w-0">
                                <p className="text-[11px] text-muted-foreground uppercase font-medium">
                                  Resume
                                </p>
                                <p className="text-sm text-foreground truncate">
                                  {resumePath}
                                </p>
                              </div>
                            </div>
                          )}
                        </div>

                        {/* Right column — metrics */}
                        {row.metric && (
                          <div className="space-y-3">
                            <div className="flex items-start gap-2">
                              <Brain className="w-3.5 h-3.5 text-muted-foreground mt-0.5 flex-shrink-0" />
                              <div>
                                <p className="text-[11px] text-muted-foreground uppercase font-medium">
                                  Memories Injected
                                </p>
                                <p className="text-sm text-foreground">
                                  {row.metric.memories_injected}
                                </p>
                              </div>
                            </div>

                            <div className="flex items-start gap-2">
                              <Brain className="w-3.5 h-3.5 text-muted-foreground mt-0.5 flex-shrink-0" />
                              <div>
                                <p className="text-[11px] text-muted-foreground uppercase font-medium">
                                  Memories Extracted
                                </p>
                                <p className="text-sm text-foreground">
                                  {row.metric.memories_extracted}
                                </p>
                              </div>
                            </div>

                            <div className="flex items-start gap-2">
                              <Zap className="w-3.5 h-3.5 text-muted-foreground mt-0.5 flex-shrink-0" />
                              <div>
                                <p className="text-[11px] text-muted-foreground uppercase font-medium">
                                  Steps (LLM Calls)
                                </p>
                                <p className="text-sm text-foreground">
                                  {row.metric.step_count}
                                </p>
                              </div>
                            </div>

                            {row.metric.cost_usd != null &&
                              row.metric.cost_usd > 0 && (
                                <div className="flex items-start gap-2">
                                  <Zap className="w-3.5 h-3.5 text-muted-foreground mt-0.5 flex-shrink-0" />
                                  <div>
                                    <p className="text-[11px] text-muted-foreground uppercase font-medium">
                                      Cost
                                    </p>
                                    <p className="text-sm text-foreground">
                                      ${row.metric.cost_usd.toFixed(4)}
                                    </p>
                                  </div>
                                </div>
                              )}
                          </div>
                        )}

                        {/* No metrics available */}
                        {!row.metric && (
                          <div className="flex items-center justify-center text-sm text-muted-foreground">
                            No detailed metrics available for this run.
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Empty state for applied jobs */}
      {appliedJobs.length === 0 && (
        <div className="card">
          <h3 className="section-title mb-4">Applied Jobs</h3>
          <div className="py-8 text-center">
            <Briefcase className="w-10 h-10 text-muted-foreground mx-auto mb-2" />
            <p className="text-sm text-muted-foreground">
              No applications yet. Start applying to see results here.
            </p>
          </div>
        </div>
      )}

    </div>
  );
}
