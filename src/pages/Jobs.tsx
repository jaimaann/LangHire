import { useState, useEffect, useRef } from "react";
import { Briefcase, Search, ExternalLink, Loader2, CheckCircle, XCircle, Clock, Ban, Play, Square, Terminal, FileText, X, Copy, Save, MoreVertical, Plus, Trash2, CheckSquare } from "lucide-react";
import { getJobs, getJobStats, startJobCollection, stopJobCollection, getCollectionStatus, startApplying, getApplyStatus, getPlugins, getProfile, generateCoverLetter, saveProfile, updateJobStatus, addJob, deleteJobs } from "../lib/api";
import { trackEvent } from "../lib/analytics";
import { markStart, measureAndTrack } from "../lib/perf";
import type { Job, JobStatus, JobStats, PluginConfig } from "../lib/types";
import LogLine from "../components/LogLine";
import AutomationDialog from "../components/AutomationDialog";
import { PageHeader, ProgressBar } from "../components/ui";
import { useTranslation } from "react-i18next";

const STATUS_ICONS: Record<JobStatus, typeof CheckCircle> = {
  pending: Clock,
  applied: CheckCircle,
  failed: XCircle,
  blocked: Ban,
  in_progress: Loader2,
};

const STATUS_STYLES: Record<JobStatus, { color: string; bg: string }> = {
  pending: { color: "text-amber-700", bg: "bg-amber-50" },
  applied: { color: "text-success", bg: "bg-[#F0FFF0]" },
  failed: { color: "text-destructive", bg: "bg-[#FFF0F0]" },
  blocked: { color: "text-muted-foreground", bg: "bg-[#F7F7F7]" },
  in_progress: { color: "text-primary", bg: "bg-[#FFF0F3]" },
};

export default function Jobs() {
  const { t } = useTranslation("jobs");
  const [jobs, setJobs] = useState<Job[]>([]);
  const [stats, setStats] = useState<JobStats>({total: 0, pending: 0, applied: 0, failed: 0, blocked: 0, in_progress: 0});
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("");
  // Collection state
  const [collecting, setCollecting] = useState(false);
  const [collectTitle, setCollectTitle] = useState("");
  const [collectMaxJobs, setCollectMaxJobs] = useState<number | "">(20);
  const [collectSource, setCollectSource] = useState("linkedin");
  const [availableSources, setAvailableSources] = useState<PluginConfig[]>([]);
  const [collectLog, setCollectLog] = useState<string[]>([]);
  const [collected, setCollected] = useState(0);
  const [showCollector, setShowCollector] = useState(true);
  const [applyingUrl, setApplyingUrl] = useState<string | null>(null);
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);
  const [pendingApplyUrl, setPendingApplyUrl] = useState<string | null>(null);
  const [coverLetterJob, setCoverLetterJob] = useState<Job | null>(null);
  const [generatedLetter, setGeneratedLetter] = useState("");
  const [generating, setGenerating] = useState(false);
  const [generateError, setGenerateError] = useState<string | null>(null);
  const [manualDescription, setManualDescription] = useState("");
  const [letterSaved, setLetterSaved] = useState(false);
  // Multi-select state
  const [selectedJobs, setSelectedJobs] = useState<Set<string>>(new Set());
  // Status dropdown state
  const [statusMenuJob, setStatusMenuJob] = useState<string | null>(null);
  // Add job form state
  const [showAddJobForm, setShowAddJobForm] = useState(false);
  const [addJobUrl, setAddJobUrl] = useState("");
  const [addJobTitle, setAddJobTitle] = useState("");
  const [addJobCompany, setAddJobCompany] = useState("");
  const [addingJob, setAddingJob] = useState(false);
  // Batch apply state
  const [batchApplying, setBatchApplying] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);

  const STATUS_LABELS: Record<JobStatus, string> = {
    pending: t("status.pending"),
    applied: t("status.applied"),
    failed: t("status.failed"),
    blocked: t("status.blocked"),
    in_progress: t("status.inProgress"),
  };

  useEffect(() => {
    getProfile().then((p) => {
      const country = p.country || "US";
      getPlugins(country).then((res) => {
        if (res.plugins) setAvailableSources(res.plugins);
      }).catch(() => {});
    }).catch(() => {
      getPlugins().then((res) => {
        if (res.plugins) setAvailableSources(res.plugins);
      }).catch(() => {});
    });
  }, []);

  const fetchJobs = (isBackgroundRefresh = false) => {
    if (!isBackgroundRefresh) {
      setLoading(true);
      markStart("jobs_page_load");
    }
    const params: Record<string, string | number> = {};
    if (statusFilter) params.status = statusFilter;
    if (searchQuery) params.search = searchQuery;
    Promise.all([
      getJobs(params as { status?: string; search?: string }),
      getJobStats(),
    ])
      .then(([jobsData, statsData]) => {
        setJobs(jobsData || []);
        setStats(statsData || {total: 0, pending: 0, applied: 0, failed: 0, blocked: 0, in_progress: 0});
      })
      .catch(() => {})
      .finally(() => {
        setLoading(false);
        if (!isBackgroundRefresh) measureAndTrack("jobs_page_load");
      });
  };

  useEffect(() => { fetchJobs(); }, [statusFilter]);

  // Check if collection is already running on mount
  useEffect(() => {
    getCollectionStatus().then((s) => {
      if (s.running) {
        setCollecting(true);
        setCollectLog(s.log || []);
        setCollected(s.collected || 0);
        setShowCollector(true);
      }
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (!showCollector) return;
    let active = true;
    let wasRunning = collecting;
    const poll = setInterval(() => {
      getCollectionStatus().then((s) => {
        if (!active) return;
        if (wasRunning && !s.running) {
          trackEvent("collection_completed", { jobs_collected: s.collected || 0 });
        }
        wasRunning = s.running;
        setCollecting(s.running);
        setCollectLog(s.log || []);
        setCollected(s.collected || 0);
        fetchJobs(true);
      }).catch(() => {});
    }, 2000);
    return () => { active = false; clearInterval(poll); };
  }, [showCollector]);

  // Auto-scroll log
  useEffect(() => {
    const el = logRef.current;
    if (el) {
      const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
      if (nearBottom) el.scrollTop = el.scrollHeight;
    }
  }, [collectLog]);

  const handleStartCollect = () => {
    setPendingApplyUrl(null);
    setShowConfirmDialog(true);
  };

  const confirmStartCollect = async () => {
    setShowConfirmDialog(false);
    try {
      const res = await startJobCollection(collectTitle || undefined, collectMaxJobs ? Number(collectMaxJobs) : undefined, collectSource);
      if (res.success) {
        setCollecting(true);
        setCollectLog([t("collector.startingCollection")]);
        setShowCollector(true);
        trackEvent("collection_started", { title: collectTitle || "all", max_jobs: collectMaxJobs || "unlimited", source: collectSource });
      } else {
        alert(res.message);
      }
    } catch (e) {
      alert(e instanceof Error ? e.message : "Failed to start collection");
    }
  };

  const handleStopCollect = async () => {
    await stopJobCollection();
    setCollecting(false);
  };

  const handleApplySingle = (jobUrl: string) => {
    setPendingApplyUrl(jobUrl);
    setShowConfirmDialog(true);
  };

  const confirmApplySingle = async () => {
    setShowConfirmDialog(false);
    if (!pendingApplyUrl) return;
    try {
      const res = await startApplying({ job_url: pendingApplyUrl, workers: 1, mode: "all" });
      if (!res.success) { alert(res.message); return; }
      setApplyingUrl(pendingApplyUrl);
    } catch (e) {
      alert(e instanceof Error ? e.message : "Failed to start");
    } finally {
      setPendingApplyUrl(null);
    }
  };

  useEffect(() => {
    if (!applyingUrl) return;
    let active = true;
    const poll = setInterval(async () => {
      try {
        const s = await getApplyStatus();
        if (active && !s.running) {
          setApplyingUrl(null);
          fetchJobs(true);
        }
      } catch { /* ignore */ }
    }, 2000);
    return () => { active = false; clearInterval(poll); };
  }, [applyingUrl]);

  const handleGenerateCoverLetter = async (job: Job) => {
    setCoverLetterJob(job);
    setGeneratedLetter("");
    setGenerateError(null);
    setLetterSaved(false);
    setManualDescription("");

    const description = job.description;
    if (!description) return;

    setGenerating(true);
    try {
      const res = await generateCoverLetter(description, job.title, job.company);
      if (res.success) {
        setGeneratedLetter(res.cover_letter);
      } else {
        setGenerateError(t("coverLetterModal.failedGenerate"));
      }
    } catch (e) {
      setGenerateError(e instanceof Error ? e.message : "Generation failed");
    } finally {
      setGenerating(false);
    }
  };

  const handleGenerateFromManual = async () => {
    if (!manualDescription.trim() || !coverLetterJob) return;
    setGenerating(true);
    setGenerateError(null);
    try {
      const res = await generateCoverLetter(manualDescription, coverLetterJob.title, coverLetterJob.company);
      if (res.success) {
        setGeneratedLetter(res.cover_letter);
      } else {
        setGenerateError(t("coverLetterModal.failedGenerate"));
      }
    } catch (e) {
      setGenerateError(e instanceof Error ? e.message : "Generation failed");
    } finally {
      setGenerating(false);
    }
  };

  const handleSaveCoverLetter = async () => {
    try {
      const profile = await getProfile();
      await saveProfile({ ...profile, cover_letter: generatedLetter });
      setLetterSaved(true);
      setTimeout(() => setLetterSaved(false), 3000);
    } catch {
      setGenerateError(t("coverLetterModal.failedSave"));
    }
  };

  // Close status menu on outside click
  useEffect(() => {
    if (!statusMenuJob) return;
    const handleClick = () => setStatusMenuJob(null);
    document.addEventListener("click", handleClick);
    return () => document.removeEventListener("click", handleClick);
  }, [statusMenuJob]);

  const handleSearch = (e: React.FormEvent) => { e.preventDefault(); fetchJobs(); };

  // Multi-select helpers
  const selectableJobs = jobs.filter((j) => j.status === "pending" || j.status === "failed");
  const allSelectableSelected = selectableJobs.length > 0 && selectableJobs.every((j) => selectedJobs.has(j.url));

  const toggleSelectJob = (url: string) => {
    setSelectedJobs((prev) => {
      const next = new Set(prev);
      if (next.has(url)) next.delete(url);
      else next.add(url);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (allSelectableSelected) {
      setSelectedJobs(new Set());
    } else {
      setSelectedJobs(new Set(selectableJobs.map((j) => j.url)));
    }
  };

  // Batch apply selected jobs
  const handleBatchApply = async () => {
    if (selectedJobs.size === 0) return;
    setBatchApplying(true);
    try {
      const res = await startApplying({ job_urls: [...selectedJobs], workers: 1, mode: "all" });
      if (!res.success) {
        alert(res.message);
      } else {
        setSelectedJobs(new Set());
      }
    } catch (e) {
      alert(e instanceof Error ? e.message : "Failed to start batch apply");
    } finally {
      setBatchApplying(false);
    }
  };

  // Batch delete selected jobs
  const handleBatchDelete = async () => {
    if (selectedJobs.size === 0) return;
    if (!confirm(`Delete ${selectedJobs.size} selected job(s)? This cannot be undone.`)) return;
    try {
      await deleteJobs([...selectedJobs]);
      setSelectedJobs(new Set());
      fetchJobs();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Failed to delete jobs");
    }
  };

  // Status change handler
  const handleStatusChange = async (jobUrl: string, newStatus: string) => {
    setStatusMenuJob(null);
    try {
      await updateJobStatus(jobUrl, newStatus);
      fetchJobs(true);
    } catch (e) {
      alert(e instanceof Error ? e.message : "Failed to update status");
    }
  };

  // Add job manually
  const handleAddJob = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!addJobUrl.trim()) return;
    setAddingJob(true);
    try {
      const res = await addJob(addJobUrl.trim(), addJobTitle.trim() || undefined, addJobCompany.trim() || undefined);
      if (res.success) {
        setAddJobUrl("");
        setAddJobTitle("");
        setAddJobCompany("");
        setShowAddJobForm(false);
        fetchJobs();
      }
    } catch (e2) {
      alert(e2 instanceof Error ? e2.message : "Failed to add job");
    } finally {
      setAddingJob(false);
    }
  };

  return (
    <div className="max-w-5xl">
      <PageHeader
        title={t("title")}
        subtitle={t("subtitle", { total: stats.total || 0, applied: stats.applied || 0, pending: stats.pending || 0 })}
        actions={
          <div className="flex items-center gap-2">
            <button onClick={() => setShowAddJobForm(!showAddJobForm)} className="btn-secondary">
              <Plus className="w-4 h-4" /> Add Job
            </button>
            <button onClick={() => setShowCollector(!showCollector)} className="btn-primary">
              <Search className="w-4 h-4" /> {showCollector ? t("hideCollector") : t("collectJobs")}
            </button>
          </div>
        }
      />

      {/* Add Job Form */}
      {showAddJobForm && (
        <div className="card mb-5">
          <h3 className="section-title mb-3">Add Job Manually</h3>
          <form onSubmit={handleAddJob} className="flex flex-col gap-3">
            <input
              value={addJobUrl}
              onChange={(e) => setAddJobUrl(e.target.value)}
              placeholder="Job URL (required)"
              className="input-base"
              required
            />
            <div className="flex gap-3">
              <input
                value={addJobTitle}
                onChange={(e) => setAddJobTitle(e.target.value)}
                placeholder="Job title (optional)"
                className="input-base flex-1"
              />
              <input
                value={addJobCompany}
                onChange={(e) => setAddJobCompany(e.target.value)}
                placeholder="Company (optional)"
                className="input-base flex-1"
              />
            </div>
            <div className="flex gap-2">
              <button type="submit" disabled={addingJob || !addJobUrl.trim()} className="btn-primary">
                {addingJob ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
                Add Job
              </button>
              <button type="button" onClick={() => setShowAddJobForm(false)} className="btn-secondary">
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Job Collector Panel */}
      {showCollector && (
        <div className="card mb-5">
          <h3 className="section-title mb-3">{t("collector.title")}</h3>
          <p className="text-[13px] text-muted-foreground mb-4">
            {t("collector.description")}
          </p>
          <div className="info-box mb-4" dangerouslySetInnerHTML={{ __html: t("collector.loginInfo") }} />
          {/* Source selector */}
          {availableSources.length > 1 && (
            <div className="mb-4">
              <label className="block text-sm font-semibold text-foreground mb-1.5">{t("collector.sourcePlatform")}</label>
              <div className="flex gap-2 flex-wrap">
                {availableSources.map((source) => (
                  <button
                    key={source.name}
                    onClick={() => setCollectSource(source.name)}
                    disabled={collecting}
                    className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors ${
                      collectSource === source.name
                        ? "border-primary bg-primary/10 text-primary"
                        : "border-border bg-white text-foreground hover:border-primary/50"
                    }`}
                  >
                    {source.display_name}
                  </button>
                ))}
              </div>
            </div>
          )}
          <div className="flex gap-3 mb-4">
            <input value={collectTitle} onChange={(e) => setCollectTitle(e.target.value)}
              placeholder={t("collector.jobTitlePlaceholder")}
              className="input-base flex-1"
              disabled={collecting} />
            <input type="number" value={collectMaxJobs} onChange={(e) => setCollectMaxJobs(e.target.value ? Number(e.target.value) : "")}
              placeholder={t("collector.maxJobsPlaceholder")} min={1} max={200}
              className="input-base !w-32 !flex-initial"
              disabled={collecting} title={t("collector.maxJobsTitle")} />
            {collecting ? (
              <button onClick={handleStopCollect} className="btn-destructive">
                <Square className="w-4 h-4" /> {t("collector.stop")}
              </button>
            ) : (
              <button onClick={handleStartCollect}
                className="btn-dark">
                <Play className="w-4 h-4" /> {t("collector.start")}
              </button>
            )}
          </div>
          {/* Progress bar */}
          {collecting && collectMaxJobs && (
            <div className="mb-4">
              <ProgressBar
                percent={collectMaxJobs > 0 ? (collected / Number(collectMaxJobs)) * 100 : 0}
                label={t("collector.collectedProgress", { collected, max: collectMaxJobs })}
              />
            </div>
          )}
          {/* Log output */}
          {collectLog.length > 0 && (
            <div ref={logRef}
              className="log-viewer">
              <div className="flex items-center gap-2 mb-2 text-gray-400">
                <Terminal className="w-3.5 h-3.5" /> {t("collector.collectionLog")}
                {collecting && <Loader2 className="w-3.5 h-3.5 animate-spin text-green-400" />}
              </div>
              {collectLog.map((line, i) => (
                <LogLine key={i} line={line} />
              ))}
            </div>
          )}
        </div>
      )}

      {/* Status Filter Tabs */}
      <div className="flex gap-2 mb-5">
        {[
          { value: "", label: t("filter.all"), count: stats.total },
          { value: "pending", label: t("status.pending"), count: stats.pending },
          { value: "applied", label: t("status.applied"), count: stats.applied },
          { value: "failed", label: t("status.failed"), count: stats.failed },
          { value: "blocked", label: t("status.blocked"), count: stats.blocked },
        ].map(({ value, label, count }) => (
          <button key={value} onClick={() => setStatusFilter(value)}
            className={`filter-tab ${statusFilter === value ? "filter-tab-active" : "filter-tab-inactive"}`}>
            {label} {count !== undefined ? `(${count})` : ""}
          </button>
        ))}
      </div>

      {/* Search */}
      <form onSubmit={handleSearch} className="card mb-5">
        <div className="flex items-center gap-3">
          <div className="flex-1 relative">
            <Search className="w-4 h-4 absolute left-4 top-3.5 text-muted-foreground" />
            <input value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)}
              placeholder={t("searchPlaceholder")}
              className="input-base !pl-10" />
          </div>
          <button type="submit" className="btn-primary">
            {t("search")}
          </button>
        </div>
      </form>

      {/* Select All Toggle */}
      {!loading && jobs.length > 0 && selectableJobs.length > 0 && (
        <div className="flex items-center gap-2 mb-3">
          <button onClick={toggleSelectAll} className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors">
            <CheckSquare className="w-4 h-4" />
            {allSelectableSelected ? "Deselect All" : "Select All"} ({selectableJobs.length})
          </button>
        </div>
      )}

      {/* Jobs List */}
      {loading ? (
        <div className="flex items-center justify-center h-48">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
        </div>
      ) : jobs.length === 0 ? (
        <div className="card">
          <div className="text-center py-12">
            <Briefcase className="w-12 h-12 text-muted-foreground mx-auto mb-3" />
            <h3 className="section-title mb-1">
              {searchQuery || statusFilter ? t("emptyState.noMatching") : t("emptyState.noJobsYet")}
            </h3>
            <p className="text-[13px] text-muted-foreground mb-5">
              {searchQuery || statusFilter ? t("emptyState.tryChanging")
                : t("emptyState.clickCollect")}
            </p>
            {!searchQuery && !statusFilter && (
              <button onClick={() => setShowCollector(true)} className="btn-primary">
                {t("emptyState.startCollecting")}
              </button>
            )}
          </div>
        </div>
      ) : (
        <div className="bg-white rounded-2xl border border-border shadow-sm divide-y divide-border">
          {jobs.map((job) => {
            const icon = STATUS_ICONS[job.status] || STATUS_ICONS.pending;
            const styles = STATUS_STYLES[job.status] || STATUS_STYLES.pending;
            const StatusIcon = icon;
            const isSelectable = job.status === "pending" || job.status === "failed";
            return (
              <div key={job.url} className="p-5 hover:bg-secondary/50 transition-colors">
                <div className="flex items-start justify-between">
                  <div className="flex items-start gap-3 flex-1 min-w-0">
                    {/* Checkbox for selectable jobs */}
                    {isSelectable && (
                      <input
                        type="checkbox"
                        checked={selectedJobs.has(job.url)}
                        onChange={() => toggleSelectJob(job.url)}
                        className="mt-1 w-4 h-4 rounded border-border text-primary focus:ring-primary cursor-pointer flex-shrink-0"
                      />
                    )}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <h4 className="text-sm font-semibold text-foreground truncate">{job.title || t("jobItem.untitled")}</h4>
                        {job.easy_apply && (
                          <span className="px-2 py-0.5 bg-[#FFF0F3] text-primary rounded-full text-[10px] font-semibold flex-shrink-0">{t("jobItem.easyApply")}</span>
                        )}
                      </div>
                      <p className="text-[13px] text-muted-foreground">{job.company || t("jobItem.unknown")} · {job.location || "—"}</p>
                      {job.error && <p className="text-[13px] text-destructive mt-1 truncate" title={job.error}>{t("jobItem.error", { error: job.error })}</p>}
                      {job.collected_at && (
                        <p className="text-[11px] text-muted-foreground mt-1">
                          {t("jobItem.collected", { date: new Date(job.collected_at).toLocaleDateString() })}
                          {job.applied_at && t("jobItem.applied", { date: new Date(job.applied_at).toLocaleDateString() })}
                        </p>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 ml-4 flex-shrink-0">
                    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold ${styles.bg} ${styles.color}`}>
                      <StatusIcon className="w-3 h-3" /> {STATUS_LABELS[job.status] || STATUS_LABELS.pending}
                    </span>
                    {(job.status === "pending" || job.status === "failed") && (
                      <>
                        <button
                          onClick={() => handleGenerateCoverLetter(job)}
                          title={t("jobItem.coverLetterTitle")}
                          className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-semibold border border-border text-foreground hover:bg-secondary transition-all"
                        >
                          <FileText className="w-3 h-3" /> {t("jobItem.coverLetter")}
                        </button>
                        <button
                          onClick={() => handleApplySingle(job.url)}
                          disabled={applyingUrl !== null}
                          title={applyingUrl ? t("jobItem.applyRunningTitle") : job.status === "failed" ? t("jobItem.retryTitle") : t("jobItem.applyTitle")}
                          className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-semibold bg-foreground text-white hover:bg-foreground/90 disabled:opacity-40 transition-all"
                        >
                          {applyingUrl === job.url ? (
                            <Loader2 className="w-3 h-3 animate-spin" />
                          ) : (
                            <Play className="w-3 h-3" />
                          )}
                          {applyingUrl === job.url ? t("jobItem.applying") : job.status === "failed" ? t("jobItem.retry") : t("jobItem.apply")}
                        </button>
                      </>
                    )}
                    {/* Three-dot status menu */}
                    <div className="relative">
                      <button
                        onClick={(e) => { e.stopPropagation(); setStatusMenuJob(statusMenuJob === job.url ? null : job.url); }}
                        className="p-1.5 text-muted-foreground hover:text-foreground transition-colors"
                        title="Change status"
                      >
                        <MoreVertical className="w-4 h-4" />
                      </button>
                      {statusMenuJob === job.url && (
                        <div className="absolute right-0 top-8 z-50 bg-white border border-border rounded-lg shadow-lg py-1 min-w-[160px]" onClick={(e) => e.stopPropagation()}>
                          {(["pending", "applied", "failed", "blocked"] as const).map((s) => (
                            <button
                              key={s}
                              onClick={() => handleStatusChange(job.url, s)}
                              disabled={job.status === s}
                              className="w-full text-left px-3 py-1.5 text-sm hover:bg-secondary disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                            >
                              Mark as {s.charAt(0).toUpperCase() + s.slice(1)}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                    <a href={job.url} target="_blank" rel="noopener noreferrer"
                      className="p-1.5 text-muted-foreground hover:text-primary transition-colors" title={t("jobItem.openOnLinkedIn")}>
                      <ExternalLink className="w-4 h-4" />
                    </a>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {jobs.length > 0 && (
        <p className="text-[13px] text-muted-foreground mt-4 text-center">
          {jobs.length === 1 ? t("showingJobs", { count: jobs.length }) : t("showingJobs_plural", { count: jobs.length })}
        </p>
      )}

      <AutomationDialog
        open={showConfirmDialog}
        title={pendingApplyUrl ? t("dialog.startApplying") : t("dialog.startCollecting")}
        onConfirm={pendingApplyUrl ? confirmApplySingle : confirmStartCollect}
        onCancel={() => { setShowConfirmDialog(false); setPendingApplyUrl(null); }}
      />

      {/* Floating Action Bar for Multi-Select */}
      {selectedJobs.size > 0 && (
        <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-40 bg-white/90 backdrop-blur border border-border rounded-xl shadow-lg px-5 py-3 flex items-center gap-4">
          <span className="text-sm font-medium text-foreground">{selectedJobs.size} selected</span>
          <button
            onClick={handleBatchApply}
            disabled={batchApplying}
            className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-sm font-semibold bg-foreground text-white hover:bg-foreground/90 disabled:opacity-40 transition-all"
          >
            {batchApplying ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
            Apply to {selectedJobs.size} job{selectedJobs.size > 1 ? "s" : ""}
          </button>
          <button
            onClick={handleBatchDelete}
            className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-sm font-semibold bg-destructive text-white hover:bg-destructive/90 transition-all"
          >
            <Trash2 className="w-4 h-4" />
            Delete {selectedJobs.size} job{selectedJobs.size > 1 ? "s" : ""}
          </button>
          <button
            onClick={() => setSelectedJobs(new Set())}
            className="text-sm text-muted-foreground hover:text-foreground underline transition-colors"
          >
            Deselect All
          </button>
        </div>
      )}

      {/* Cover Letter Modal */}
      {coverLetterJob && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={() => setCoverLetterJob(null)}>
          <div className="bg-white rounded-2xl shadow-xl max-w-2xl w-full max-h-[85vh] overflow-hidden flex flex-col" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between p-5 border-b border-border">
              <div>
                <h3 className="text-base font-semibold text-foreground">{t("coverLetterModal.title")}</h3>
                <p className="text-[13px] text-muted-foreground mt-0.5">{t("coverLetterModal.jobAt", { title: coverLetterJob.title, company: coverLetterJob.company })}</p>
              </div>
              <button onClick={() => setCoverLetterJob(null)} className="p-1.5 text-muted-foreground hover:text-foreground">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-5">
              {!coverLetterJob.description && !generatedLetter && (
                <div className="mb-4">
                  <p className="text-sm text-muted-foreground mb-2">
                    {t("coverLetterModal.noDescription")}
                  </p>
                  <textarea
                    value={manualDescription}
                    onChange={(e) => setManualDescription(e.target.value)}
                    rows={6}
                    className="input-base mb-3"
                    placeholder={t("coverLetterModal.pastePlaceholder")}
                  />
                  <button
                    onClick={handleGenerateFromManual}
                    disabled={!manualDescription.trim() || generating}
                    className="btn-primary"
                  >
                    {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileText className="w-4 h-4" />}
                    {t("coverLetterModal.generate")}
                  </button>
                </div>
              )}

              {generating && (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="w-6 h-6 animate-spin text-primary mr-3" />
                  <span className="text-sm text-muted-foreground">{t("coverLetterModal.generating")}</span>
                </div>
              )}

              {generateError && (
                <div className="error-banner mb-4">{generateError}</div>
              )}

              {generatedLetter && (
                <div>
                  <label className="block text-sm font-semibold text-foreground mb-1.5">{t("coverLetterModal.generatedLabel")}</label>
                  <textarea
                    value={generatedLetter}
                    onChange={(e) => setGeneratedLetter(e.target.value)}
                    rows={12}
                    className="input-base font-[inherit] text-sm leading-relaxed"
                  />
                </div>
              )}
            </div>

            {generatedLetter && (
              <div className="flex items-center justify-between p-5 border-t border-border bg-secondary/30">
                <button
                  onClick={() => { navigator.clipboard.writeText(generatedLetter); }}
                  className="btn-secondary"
                >
                  <Copy className="w-4 h-4" /> {t("coverLetterModal.copy")}
                </button>
                <button
                  onClick={handleSaveCoverLetter}
                  className="btn-primary"
                >
                  <Save className="w-4 h-4" /> {letterSaved ? t("coverLetterModal.saved") : t("coverLetterModal.saveToProfile")}
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
