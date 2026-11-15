import { useState, useEffect, useRef, useCallback } from "react";
import { useRunEvents, appendLogLine, FALLBACK_POLL_MS } from "../../hooks/useRunEvents";
import { Play, Square, Terminal, Loader2, Plus } from "lucide-react";
import {
  startJobCollection,
  stopJobCollection,
  getCollectionStatus,
  getPlugins,
  getProfile,
  addJob,
} from "../../lib/api";
import { trackEvent, usageParams } from "../../lib/analytics";
import type { PluginConfig } from "../../lib/types";
import LogLine from "../../components/LogLine";
import AutomationDialog from "../../components/AutomationDialog";
import { ProgressBar } from "../../components/ui";
import { useTranslation } from "react-i18next";
import InlineNotice, { type Notice } from "../../components/InlineNotice";

interface CollectTabProps {
  onJobsChanged: () => void;
}

export default function CollectTab({ onJobsChanged }: CollectTabProps) {
  const { t } = useTranslation("jobs");

  // Collection state
  const [collecting, setCollecting] = useState(false);
  const [collectTitle, setCollectTitle] = useState("");
  const [collectMaxJobs, setCollectMaxJobs] = useState<number | "">(20);
  const [collectSource, setCollectSource] = useState("linkedin");
  const [availableSources, setAvailableSources] = useState<PluginConfig[]>([]);
  const [collectLog, setCollectLog] = useState<string[]>([]);
  const [collected, setCollected] = useState(0);
  const [collectFilters, setCollectFilters] = useState<Record<string, string>>({});
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);

  // Add job form state
  const [showAddJobForm, setShowAddJobForm] = useState(false);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [profileCountry, setProfileCountry] = useState("");
  const [addJobUrl, setAddJobUrl] = useState("");
  const [addJobTitle, setAddJobTitle] = useState("");
  const [addJobCompany, setAddJobCompany] = useState("");
  const [addingJob, setAddingJob] = useState(false);

  const logRef = useRef<HTMLDivElement>(null);

  const selectedPlugin = availableSources.find((s) => s.name === collectSource);

  // Load available plugins/sources
  useEffect(() => {
    getProfile()
      .then((p) => {
        const country = p.country || "US";
        setProfileCountry(country);
        getPlugins(country)
          .then((res) => {
            if (res.plugins) setAvailableSources(res.plugins);
          })
          .catch(() => {});
      })
      .catch(() => {
        getPlugins()
          .then((res) => {
            if (res.plugins) setAvailableSources(res.plugins);
          })
          .catch(() => {});
      });
  }, []);

  // Check if collection is already running on mount
  useEffect(() => {
    getCollectionStatus()
      .then((s) => {
        if (s.running) {
          setCollecting(true);
          setCollectLog(s.log || []);
          setCollected(s.collected || 0);
        }
      })
      .catch(() => {});
  }, []);

  // Sync from the status endpoint (authoritative log + collected count).
  const wasRunningRef = useRef(false);
  useEffect(() => {
    wasRunningRef.current = collecting;
  }, [collecting]);
  const syncStatus = useCallback(() => {
    getCollectionStatus()
      .then((s) => {
        if (wasRunningRef.current && !s.running) {
          trackEvent("collection_completed", { jobs_collected: s.collected || 0, ...usageParams(s.usage) });
          onJobsChanged();
        }
        wasRunningRef.current = s.running;
        setCollecting(s.running);
        setCollectLog(s.log || []);
        setCollected(s.collected || 0);
      })
      .catch(() => {});
  }, [onJobsChanged]);

  // Live updates over SSE; job_found / run boundaries re-sync the counters.
  const syncTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useRunEvents("collect", (event) => {
    if (event.type === "run_started") setCollecting(true);
    setCollectLog((prev) => appendLogLine(prev, event.message));
    if (["run_started", "run_finished", "job_found"].includes(event.type)) {
      if (syncTimer.current) clearTimeout(syncTimer.current);
      syncTimer.current = setTimeout(syncStatus, 300);
    }
  });
  useEffect(() => () => {
    if (syncTimer.current) clearTimeout(syncTimer.current);
  }, []);

  // Slow fallback poll while collecting, in case the event stream drops.
  useEffect(() => {
    if (!collecting) return;
    const poll = setInterval(syncStatus, FALLBACK_POLL_MS);
    return () => clearInterval(poll);
  }, [collecting, syncStatus]);

  // Auto-scroll log
  useEffect(() => {
    const el = logRef.current;
    if (el) {
      const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
      if (nearBottom) el.scrollTop = el.scrollHeight;
    }
  }, [collectLog]);

  const handleStartCollect = () => {
    setShowConfirmDialog(true);
  };

  const confirmStartCollect = async () => {
    setShowConfirmDialog(false);
    try {
      const res = await startJobCollection(
        collectTitle || undefined,
        collectMaxJobs ? Number(collectMaxJobs) : undefined,
        collectSource,
        collectFilters
      );
      if (res.success) {
        setCollecting(true);
        setCollectLog([t("collector.startingCollection")]);
        trackEvent("collection_started", {
          title: collectTitle || "all",
          max_jobs: collectMaxJobs || "unlimited",
          source: collectSource,
        });
      } else {
        setNotice({ kind: "error", text: res.message || t("errors.startCollection") });
      }
    } catch (e) {
      setNotice({ kind: "error", text: e instanceof Error ? e.message : t("errors.startCollection") });
    }
  };

  const handleStopCollect = async () => {
    await stopJobCollection();
    setCollecting(false);
  };

  // Add job manually
  const handleAddJob = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!addJobUrl.trim()) return;
    setAddingJob(true);
    try {
      const res = await addJob(
        addJobUrl.trim(),
        addJobTitle.trim() || undefined,
        addJobCompany.trim() || undefined
      );
      if (res.success) {
        setAddJobUrl("");
        setAddJobTitle("");
        setAddJobCompany("");
        setShowAddJobForm(false);
        onJobsChanged();
      }
    } catch (e2) {
      setNotice({ kind: "error", text: e2 instanceof Error ? e2.message : t("errors.addJob") });
    } finally {
      setAddingJob(false);
    }
  };

  return (
    <div>
      {/* Action buttons */}
      <div className="flex items-center gap-2 mb-5">
        <button
          onClick={() => setShowAddJobForm(!showAddJobForm)}
          className="btn-secondary"
        >
          <Plus className="w-4 h-4" /> {t("addJob.button")}
        </button>
      </div>
      <InlineNotice notice={notice} onClose={() => setNotice(null)} />

      {/* Add Job Form */}
      {showAddJobForm && (
        <div className="card mb-5">
          <h3 className="section-title mb-1">{t("addJob.title")}</h3>
          <p className="text-xs text-muted-foreground mb-3">{t("addJob.hint")}</p>
          <form onSubmit={handleAddJob} className="flex flex-col gap-3">
            <input
              value={addJobUrl}
              onChange={(e) => setAddJobUrl(e.target.value)}
              placeholder={t("addJob.url")}
              className="input-base"
              required
            />
            <div className="flex gap-3">
              <input
                value={addJobTitle}
                onChange={(e) => setAddJobTitle(e.target.value)}
                placeholder={t("addJob.jobTitle")}
                className="input-base flex-1"
              />
              <input
                value={addJobCompany}
                onChange={(e) => setAddJobCompany(e.target.value)}
                placeholder={t("addJob.company")}
                className="input-base flex-1"
              />
            </div>
            <div className="flex gap-2">
              <button
                type="submit"
                disabled={addingJob || !addJobUrl.trim()}
                className="btn-primary"
              >
                {addingJob ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Plus className="w-4 h-4" />
                )}
                {t("addJob.button")}
              </button>
              <button
                type="button"
                onClick={() => setShowAddJobForm(false)}
                className="btn-secondary"
              >
                {t("addJob.cancel")}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Job Collector Panel */}
      <div className="card mb-5">
        <h3 className="section-title mb-3">{t("collector.title")}</h3>
        <p className="text-[13px] text-muted-foreground mb-4">
          {t("collector.description")}
        </p>
        <div
          className="info-box mb-4"
          dangerouslySetInnerHTML={{ __html: t("collector.loginInfo") }}
        />
        {/* Source selector */}
        {availableSources.length > 1 && (
          <div className="mb-4">
            <label className="block text-sm font-semibold text-foreground mb-1.5">
              {t("collector.sourcePlatform")}
            </label>
            {profileCountry && (
              <p className="text-[12px] text-muted-foreground mb-2" data-testid="sources-country-hint">
                {t("collector.sourcesForCountry", { country: profileCountry })}
              </p>
            )}
            <div className="flex gap-2 flex-wrap">
              {availableSources.map((source) => (
                <button
                  key={source.name}
                  onClick={() => setCollectSource(source.name)}
                  disabled={collecting}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors ${
                    collectSource === source.name
                      ? "border-primary bg-primary/10 text-primary"
                      : "border-border bg-card text-foreground hover:border-primary/50"
                  }`}
                >
                  {source.display_name}
                </button>
              ))}
            </div>
          </div>
        )}
        {/* Dynamic filters from selected plugin */}
        {selectedPlugin?.filters && selectedPlugin.filters.length > 0 && (
          <div className="grid grid-cols-2 gap-3 mb-4">
            {selectedPlugin.filters.map((filter) => (
              <div key={filter.key}>
                <label className="block text-xs font-medium text-muted-foreground mb-1">
                  {filter.label}
                </label>
                {filter.type === "select" ? (
                  <select
                    value={collectFilters[filter.key] || filter.default || ""}
                    onChange={(e) =>
                      setCollectFilters((prev) => ({
                        ...prev,
                        [filter.key]: e.target.value,
                      }))
                    }
                    disabled={collecting}
                    className="w-full px-2.5 py-1.5 border border-border rounded-lg text-sm bg-card"
                  >
                    <option value="">Any</option>
                    {filter.options.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    type="text"
                    value={collectFilters[filter.key] || ""}
                    onChange={(e) =>
                      setCollectFilters((prev) => ({
                        ...prev,
                        [filter.key]: e.target.value,
                      }))
                    }
                    disabled={collecting}
                    className="input-base !py-1.5 text-sm"
                    placeholder={filter.label}
                  />
                )}
              </div>
            ))}
          </div>
        )}
        <div className="flex gap-3 mb-4">
          <input
            value={collectTitle}
            onChange={(e) => setCollectTitle(e.target.value)}
            placeholder={t("collector.jobTitlePlaceholder")}
            className="input-base flex-1"
            disabled={collecting}
          />
          <input
            type="number"
            value={collectMaxJobs}
            onChange={(e) =>
              setCollectMaxJobs(e.target.value ? Number(e.target.value) : "")
            }
            placeholder={t("collector.maxJobsPlaceholder")}
            min={1}
            max={200}
            className="input-base !w-32 !flex-initial"
            disabled={collecting}
            title={t("collector.maxJobsTitle")}
          />
          {collecting ? (
            <button onClick={handleStopCollect} className="btn-destructive">
              <Square className="w-4 h-4" /> {t("collector.stop")}
            </button>
          ) : (
            <button onClick={handleStartCollect} className="btn-dark">
              <Play className="w-4 h-4" /> {t("collector.start")}
            </button>
          )}
        </div>
        {/* Progress bar */}
        {collecting && collectMaxJobs && (
          <div className="mb-4">
            <ProgressBar
              percent={
                collectMaxJobs > 0
                  ? (collected / Number(collectMaxJobs)) * 100
                  : 0
              }
              label={t("collector.collectedProgress", {
                collected,
                max: collectMaxJobs,
              })}
            />
          </div>
        )}
        {/* Log output */}
        {collectLog.length > 0 && (
          <div ref={logRef} className="log-viewer">
            <div className="flex items-center gap-2 mb-2 text-muted-foreground">
              <Terminal className="w-3.5 h-3.5" /> {t("collector.collectionLog")}
              {collecting && (
                <Loader2 className="w-3.5 h-3.5 animate-spin text-green-400" />
              )}
            </div>
            {collectLog.map((line, i) => (
              <LogLine key={i} line={line} />
            ))}
          </div>
        )}
      </div>

      <AutomationDialog
        open={showConfirmDialog}
        title={t("dialog.startCollecting")}
        onConfirm={confirmStartCollect}
        onCancel={() => setShowConfirmDialog(false)}
      />
    </div>
  );
}
