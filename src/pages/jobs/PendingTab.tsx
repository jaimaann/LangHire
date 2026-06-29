import { useState, useEffect } from "react";
import {
  Briefcase,
  Search,
  ExternalLink,
  Loader2,
  CheckCircle,
  XCircle,
  Clock,
  Ban,
  Play,
  FileText,
  X,
  Copy,
  Save,
  MoreVertical,
  Trash2,
  CheckSquare,
  Wand2,
  ChevronDown,
  ChevronRight,
  Sparkles,
  Send,
} from "lucide-react";
import {
  getJobs,
  startApplying,
  getApplyStatus,
  generateCoverLetter,
  saveProfile,
  getProfile,
  updateJobStatus,
  deleteJobs,
  tailorResumes,
  refineTailoredResume,
  getTailoredResumeContent,
} from "../../lib/api";
import { markStart, measureAndTrack } from "../../lib/perf";
import type { Job, JobStatus, JobStats, TailorOptions } from "../../lib/types";
import AutomationDialog from "../../components/AutomationDialog";
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

interface PendingTabProps {
  onJobsChanged: () => void;
  stats: JobStats;
}

function loadTailorOptions(): TailorOptions {
  try {
    const stored = localStorage.getItem("langhire_tailor_options");
    if (stored) return JSON.parse(stored);
  } catch {
    /* ignore */
  }
  return { skills: true, title: false, overview: false, experience: false };
}

function saveTailorOptions(options: TailorOptions) {
  localStorage.setItem("langhire_tailor_options", JSON.stringify(options));
}

function loadAutoTailor(): boolean {
  try {
    return localStorage.getItem("langhire_auto_tailor") === "true";
  } catch {
    return false;
  }
}

function saveAutoTailor(value: boolean) {
  localStorage.setItem("langhire_auto_tailor", value ? "true" : "false");
}

export default function PendingTab({ onJobsChanged, stats }: PendingTabProps) {
  const { t } = useTranslation("jobs");

  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("");

  // Apply state
  const [applyingUrl, setApplyingUrl] = useState<string | null>(null);
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);
  const [pendingApplyUrl, setPendingApplyUrl] = useState<string | null>(null);

  // Cover letter state
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

  // Batch apply state
  const [batchApplying, setBatchApplying] = useState(false);

  // Tailoring options panel state
  const [showTailorOptions, setShowTailorOptions] = useState(false);
  const [autoTailor, setAutoTailor] = useState(loadAutoTailor);
  const [tailorOptions, setTailorOptions] = useState<TailorOptions>(loadTailorOptions);

  // Expanded job detail (resume preview + refine)
  const [expandedJob, setExpandedJob] = useState<string | null>(null);
  const [tailoredContent, setTailoredContent] = useState<Record<string, string>>({});
  const [refineInput, setRefineInput] = useState<Record<string, string>>({});
  const [refining, setRefining] = useState<Record<string, boolean>>({});
  const [contentLoading, setContentLoading] = useState<Record<string, boolean>>({});

  const STATUS_LABELS: Record<JobStatus, string> = {
    pending: t("status.pending"),
    applied: t("status.applied"),
    failed: t("status.failed"),
    blocked: t("status.blocked"),
    in_progress: t("status.inProgress"),
  };

  const fetchJobs = (isBackgroundRefresh = false) => {
    if (!isBackgroundRefresh) {
      setLoading(true);
      markStart("jobs_page_load");
    }
    const params: Record<string, string | number> = {};
    // For the pending tab, exclude "applied" unless explicitly filtered
    if (statusFilter) {
      params.status = statusFilter;
    }
    if (searchQuery) params.search = searchQuery;
    getJobs(params as { status?: string; search?: string })
      .then((jobsData) => {
        // Filter out applied jobs from this tab (they show in History)
        const filtered = statusFilter
          ? jobsData || []
          : (jobsData || []).filter((j: Job) => j.status !== "applied");
        setJobs(filtered);
      })
      .catch(() => {})
      .finally(() => {
        setLoading(false);
        if (!isBackgroundRefresh) measureAndTrack("jobs_page_load");
      });
  };

  useEffect(() => {
    fetchJobs();
  }, [statusFilter]);

  // Poll apply status for single apply
  useEffect(() => {
    if (!applyingUrl) return;
    let active = true;
    const poll = setInterval(async () => {
      try {
        const s = await getApplyStatus();
        if (active && !s.running) {
          setApplyingUrl(null);
          fetchJobs(true);
          onJobsChanged();
        }
      } catch {
        /* ignore */
      }
    }, 2000);
    return () => {
      active = false;
      clearInterval(poll);
    };
  }, [applyingUrl, onJobsChanged]);

  // Poll apply status during batch apply
  useEffect(() => {
    if (!batchApplying) return;
    let active = true;
    const poll = setInterval(async () => {
      if (!active) return;
      try {
        const s = await getApplyStatus();
        fetchJobs(true);
        if (!s.running) {
          setBatchApplying(false);
          onJobsChanged();
        }
      } catch {
        /* ignore */
      }
    }, 2000);
    return () => {
      active = false;
      clearInterval(poll);
    };
  }, [batchApplying, onJobsChanged]);

  // Close status menu on outside click
  useEffect(() => {
    if (!statusMenuJob) return;
    const handleClick = () => setStatusMenuJob(null);
    document.addEventListener("click", handleClick);
    return () => document.removeEventListener("click", handleClick);
  }, [statusMenuJob]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    fetchJobs();
  };

  const handleApplySingle = (jobUrl: string) => {
    setPendingApplyUrl(jobUrl);
    setShowConfirmDialog(true);
  };

  const confirmApplySingle = async () => {
    setShowConfirmDialog(false);
    if (!pendingApplyUrl) return;
    try {
      const res = await startApplying({
        job_url: pendingApplyUrl,
        workers: 1,
        mode: "all",
      });
      if (!res.success) {
        alert(res.message);
        return;
      }
      setApplyingUrl(pendingApplyUrl);
    } catch (e) {
      alert(e instanceof Error ? e.message : "Failed to start");
    } finally {
      setPendingApplyUrl(null);
    }
  };

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
      const res = await generateCoverLetter(
        manualDescription,
        coverLetterJob.title,
        coverLetterJob.company
      );
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

  // Multi-select helpers
  const selectableJobs = jobs.filter(
    (j) => j.status === "pending" || j.status === "failed"
  );
  const allSelectableSelected =
    selectableJobs.length > 0 &&
    selectableJobs.every((j) => selectedJobs.has(j.url));

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
      const res = await startApplying({
        job_urls: [...selectedJobs],
        workers: 1,
        mode: "all",
      });
      if (!res.success) {
        alert(res.message);
        setBatchApplying(false);
      } else {
        setSelectedJobs(new Set());
      }
    } catch (e) {
      alert(e instanceof Error ? e.message : "Failed to start batch apply");
      setBatchApplying(false);
    }
  };

  // Batch delete selected jobs
  const handleBatchDelete = async () => {
    if (selectedJobs.size === 0) return;
    if (!confirm(`Delete ${selectedJobs.size} selected job(s)? This cannot be undone.`))
      return;
    try {
      await deleteJobs([...selectedJobs]);
      setSelectedJobs(new Set());
      fetchJobs();
      onJobsChanged();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Failed to delete jobs");
    }
  };

  // Batch tailor resumes
  const [tailoring, setTailoring] = useState(false);
  const handleBatchTailor = async () => {
    if (selectedJobs.size === 0) return;
    setTailoring(true);
    try {
      const res = await tailorResumes([...selectedJobs], tailorOptions);
      if (res.success) {
        const done = res.results.filter(r => r.status === "done").length;
        const failed = res.results.filter(r => r.status === "error").length;
        // Store content from successful tailoring results
        const newContent: Record<string, string> = { ...tailoredContent };
        for (const r of res.results) {
          if (r.status === "done" && r.content) {
            newContent[r.url] = r.content;
          }
        }
        setTailoredContent(newContent);
        alert(`Tailored ${done} resume(s)${failed ? `, ${failed} failed` : ""}`);
        setSelectedJobs(new Set());
        fetchJobs();
      }
    } catch (e) {
      alert(e instanceof Error ? e.message : "Failed to tailor resumes");
    } finally {
      setTailoring(false);
    }
  };

  // Status change handler
  const handleStatusChange = async (jobUrl: string, newStatus: string) => {
    setStatusMenuJob(null);
    try {
      await updateJobStatus(jobUrl, newStatus);
      fetchJobs(true);
      onJobsChanged();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Failed to update status");
    }
  };

  // Tailoring options handlers
  const handleAutoTailorToggle = () => {
    const newVal = !autoTailor;
    setAutoTailor(newVal);
    saveAutoTailor(newVal);
  };

  const handleTailorOptionChange = (key: keyof TailorOptions) => {
    const updated = { ...tailorOptions, [key]: !tailorOptions[key] };
    setTailorOptions(updated);
    saveTailorOptions(updated);
  };

  // Expand/collapse job detail for resume preview
  const handleToggleExpand = async (jobUrl: string) => {
    if (expandedJob === jobUrl) {
      setExpandedJob(null);
      return;
    }
    setExpandedJob(jobUrl);

    // If we already have content cached, no need to fetch
    if (tailoredContent[jobUrl]) return;

    // Fetch the tailored content
    setContentLoading((prev) => ({ ...prev, [jobUrl]: true }));
    try {
      const res = await getTailoredResumeContent(jobUrl);
      if (res.success) {
        setTailoredContent((prev) => ({ ...prev, [jobUrl]: res.content }));
      }
    } catch {
      // Content not available, that is fine
    } finally {
      setContentLoading((prev) => ({ ...prev, [jobUrl]: false }));
    }
  };

  // Refine handler
  const handleRefine = async (jobUrl: string) => {
    const instruction = refineInput[jobUrl]?.trim();
    if (!instruction) return;

    setRefining((prev) => ({ ...prev, [jobUrl]: true }));
    try {
      const res = await refineTailoredResume(jobUrl, instruction);
      if (res.success) {
        setTailoredContent((prev) => ({ ...prev, [jobUrl]: res.content }));
        setRefineInput((prev) => ({ ...prev, [jobUrl]: "" }));
      }
    } catch (e) {
      alert(e instanceof Error ? e.message : "Refinement failed");
    } finally {
      setRefining((prev) => ({ ...prev, [jobUrl]: false }));
    }
  };

  return (
    <div>
      {/* Tailoring Options Panel */}
      <div className="card mb-4">
        <button
          onClick={() => setShowTailorOptions(!showTailorOptions)}
          className="flex items-center gap-2 w-full text-left text-sm font-semibold text-foreground"
        >
          {showTailorOptions ? (
            <ChevronDown className="w-4 h-4" />
          ) : (
            <ChevronRight className="w-4 h-4" />
          )}
          <Wand2 className="w-4 h-4 text-primary" />
          Tailoring Options
        </button>
        {showTailorOptions && (
          <div className="mt-3 pt-3 border-t border-border">
            {/* Auto-tailor toggle */}
            <label className="flex items-center gap-2 mb-3 cursor-pointer">
              <input
                type="checkbox"
                checked={autoTailor}
                onChange={handleAutoTailorToggle}
                className="w-4 h-4 rounded border-border text-primary focus:ring-primary"
              />
              <span className="text-sm text-foreground">
                Auto-tailor before applying
              </span>
            </label>
            {/* Tailor options checkboxes */}
            <div className="flex flex-wrap gap-4">
              {(
                [
                  { key: "skills" as const, label: "Skills" },
                  { key: "title" as const, label: "Job Title" },
                  { key: "overview" as const, label: "Overview/Summary" },
                  { key: "experience" as const, label: "Job Experience" },
                ] as const
              ).map(({ key, label }) => (
                <label
                  key={key}
                  className="flex items-center gap-1.5 cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={tailorOptions[key]}
                    onChange={() => handleTailorOptionChange(key)}
                    className="w-3.5 h-3.5 rounded border-border text-primary focus:ring-primary"
                  />
                  <span className="text-[13px] text-muted-foreground">
                    {label}
                  </span>
                </label>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Status Filter Sub-tabs */}
      <div className="flex gap-2 mb-5">
        {[
          { value: "", label: t("filter.all"), count: stats.total - (stats.applied || 0) },
          { value: "pending", label: t("status.pending"), count: stats.pending },
          { value: "failed", label: t("status.failed"), count: stats.failed },
          { value: "blocked", label: t("status.blocked"), count: stats.blocked },
        ].map(({ value, label, count }) => (
          <button
            key={value}
            onClick={() => setStatusFilter(value)}
            className={`filter-tab ${
              statusFilter === value ? "filter-tab-active" : "filter-tab-inactive"
            }`}
          >
            {label} {count !== undefined ? `(${count})` : ""}
          </button>
        ))}
      </div>

      {/* Search */}
      <form onSubmit={handleSearch} className="card mb-5">
        <div className="flex items-center gap-3">
          <div className="flex-1 relative">
            <Search className="w-4 h-4 absolute left-4 top-3.5 text-muted-foreground" />
            <input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder={t("searchPlaceholder")}
              className="input-base !pl-10"
            />
          </div>
          <button type="submit" className="btn-primary">
            {t("search")}
          </button>
        </div>
      </form>

      {/* Select All Toggle */}
      {!loading && jobs.length > 0 && selectableJobs.length > 0 && (
        <div className="flex items-center gap-2 mb-3">
          <button
            onClick={toggleSelectAll}
            className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            <CheckSquare className="w-4 h-4" />
            {allSelectableSelected ? "Deselect All" : "Select All"} (
            {selectableJobs.length})
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
              {searchQuery || statusFilter
                ? t("emptyState.noMatching")
                : t("emptyState.noJobsYet")}
            </h3>
            <p className="text-[13px] text-muted-foreground mb-5">
              {searchQuery || statusFilter
                ? t("emptyState.tryChanging")
                : t("emptyState.clickCollect")}
            </p>
          </div>
        </div>
      ) : (
        <div className="bg-white rounded-2xl border border-border shadow-sm divide-y divide-border">
          {jobs.map((job) => {
            const icon = STATUS_ICONS[job.status] || STATUS_ICONS.pending;
            const styles = STATUS_STYLES[job.status] || STATUS_STYLES.pending;
            const StatusIcon = icon;
            const isSelectable = job.status === "pending" || job.status === "failed";
            const hasTailoredResume = !!job.tailored_resume_path;
            const isExpanded = expandedJob === job.url;
            return (
              <div key={job.url}>
                <div className="p-5 hover:bg-secondary/50 transition-colors">
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
                          <h4 className="text-sm font-semibold text-foreground truncate">
                            {job.title || t("jobItem.untitled")}
                          </h4>
                          {job.easy_apply && (
                            <span className="px-2 py-0.5 bg-[#FFF0F3] text-primary rounded-full text-[10px] font-semibold flex-shrink-0">
                              {t("jobItem.easyApply")}
                            </span>
                          )}
                          {hasTailoredResume && (
                            <span className="px-2 py-0.5 bg-primary/10 text-primary rounded-full text-[10px] font-semibold flex-shrink-0 inline-flex items-center gap-0.5">
                              <Sparkles className="w-2.5 h-2.5" />
                              Tailored
                            </span>
                          )}
                        </div>
                        <p className="text-[13px] text-muted-foreground">
                          {job.company || t("jobItem.unknown")} ·{" "}
                          {job.location || "—"}
                        </p>
                        {job.error && (
                          <p
                            className="text-[13px] text-destructive mt-1 truncate"
                            title={job.error}
                          >
                            {t("jobItem.error", { error: job.error })}
                          </p>
                        )}
                        {job.collected_at && (
                          <p className="text-[11px] text-muted-foreground mt-1">
                            {t("jobItem.collected", {
                              date: new Date(job.collected_at).toLocaleDateString(),
                            })}
                            {job.applied_at &&
                              t("jobItem.applied", {
                                date: new Date(job.applied_at).toLocaleDateString(),
                              })}
                          </p>
                        )}
                        {/* Clickable expand button for tailored jobs */}
                        {hasTailoredResume && (
                          <button
                            onClick={() => handleToggleExpand(job.url)}
                            className="mt-1.5 text-[11px] text-primary hover:text-primary/80 font-medium inline-flex items-center gap-1 transition-colors"
                          >
                            {isExpanded ? (
                              <ChevronDown className="w-3 h-3" />
                            ) : (
                              <ChevronRight className="w-3 h-3" />
                            )}
                            {isExpanded ? "Hide" : "View"} tailored resume
                          </button>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-2 ml-4 flex-shrink-0">
                      <span
                        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold ${styles.bg} ${styles.color}`}
                      >
                        <StatusIcon className="w-3 h-3" />{" "}
                        {STATUS_LABELS[job.status] || STATUS_LABELS.pending}
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
                            title={
                              applyingUrl
                                ? t("jobItem.applyRunningTitle")
                                : job.status === "failed"
                                ? t("jobItem.retryTitle")
                                : t("jobItem.applyTitle")
                            }
                            className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-semibold bg-foreground text-background hover:bg-foreground/90 disabled:opacity-40 transition-all"
                          >
                            {applyingUrl === job.url ? (
                              <Loader2 className="w-3 h-3 animate-spin" />
                            ) : (
                              <Play className="w-3 h-3" />
                            )}
                            {applyingUrl === job.url
                              ? t("jobItem.applying")
                              : job.status === "failed"
                              ? t("jobItem.retry")
                              : t("jobItem.apply")}
                          </button>
                        </>
                      )}
                      {/* Three-dot status menu */}
                      <div className="relative">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setStatusMenuJob(
                              statusMenuJob === job.url ? null : job.url
                            );
                          }}
                          className="p-1.5 text-muted-foreground hover:text-foreground transition-colors"
                          title="Change status"
                        >
                          <MoreVertical className="w-4 h-4" />
                        </button>
                        {statusMenuJob === job.url && (
                          <div
                            className="absolute right-0 top-8 z-50 bg-white border border-border rounded-lg shadow-lg py-1 min-w-[160px]"
                            onClick={(e) => e.stopPropagation()}
                          >
                            {(
                              ["pending", "applied", "failed", "blocked"] as const
                            ).map((s) => (
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
                      <a
                        href={job.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="p-1.5 text-muted-foreground hover:text-primary transition-colors"
                        title={t("jobItem.openOnLinkedIn")}
                      >
                        <ExternalLink className="w-4 h-4" />
                      </a>
                    </div>
                  </div>
                </div>
                {/* Expanded Detail: Resume Preview + Refine */}
                {isExpanded && hasTailoredResume && (
                  <div className="px-5 pb-5 border-t border-border/50 bg-secondary/20">
                    <div className="pt-4">
                      {contentLoading[job.url] ? (
                        <div className="flex items-center gap-2 py-4">
                          <Loader2 className="w-4 h-4 animate-spin text-primary" />
                          <span className="text-sm text-muted-foreground">
                            Loading tailored resume...
                          </span>
                        </div>
                      ) : tailoredContent[job.url] ? (
                        <div className="mb-4">
                          <div className="flex items-center justify-between mb-2">
                            <h5 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                              Tailored Resume Content
                            </h5>
                            {job.tailored_resume_path && (
                              <button
                                onClick={() => {
                                  import("@tauri-apps/api/core").then(({ invoke }) => {
                                    invoke("open_file", { path: job.tailored_resume_path! });
                                  });
                                }}
                                className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-semibold border border-border hover:bg-secondary transition-colors"
                              >
                                <FileText className="w-3 h-3" />
                                Open PDF
                              </button>
                            )}
                          </div>
                          <div className="bg-white rounded-lg border border-border p-4 text-sm text-foreground whitespace-pre-wrap max-h-64 overflow-y-auto leading-relaxed">
                            {tailoredContent[job.url]}
                          </div>
                        </div>
                      ) : (
                        <div className="flex items-center gap-3 py-2 mb-3">
                          <p className="text-sm text-muted-foreground">
                            Tailored resume generated.
                          </p>
                          {job.tailored_resume_path && (
                            <button
                              onClick={() => {
                                import("@tauri-apps/plugin-shell").then(({ open }) => {
                                  open(job.tailored_resume_path!);
                                }).catch(() => {
                                  window.open(`file://${job.tailored_resume_path}`, "_blank");
                                });
                              }}
                              className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-semibold border border-primary text-primary hover:bg-primary/10 transition-colors"
                            >
                              <FileText className="w-3 h-3" />
                              Open PDF
                            </button>
                          )}
                        </div>
                      )}
                      {/* Refine input */}
                      <div className="flex items-center gap-2">
                        <input
                          type="text"
                          value={refineInput[job.url] || ""}
                          onChange={(e) =>
                            setRefineInput((prev) => ({
                              ...prev,
                              [job.url]: e.target.value,
                            }))
                          }
                          onKeyDown={(e) => {
                            if (e.key === "Enter" && !refining[job.url]) {
                              handleRefine(job.url);
                            }
                          }}
                          placeholder="Refine: e.g. 'emphasize my AWS experience'"
                          className="input-base flex-1 text-sm"
                          disabled={refining[job.url]}
                        />
                        <button
                          onClick={() => handleRefine(job.url)}
                          disabled={
                            refining[job.url] || !refineInput[job.url]?.trim()
                          }
                          className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-semibold bg-primary text-white hover:bg-primary/90 disabled:opacity-40 transition-all"
                        >
                          {refining[job.url] ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          ) : (
                            <Send className="w-3.5 h-3.5" />
                          )}
                          Refine
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {jobs.length > 0 && (
        <p className="text-[13px] text-muted-foreground mt-4 text-center">
          {jobs.length === 1
            ? t("showingJobs", { count: jobs.length })
            : t("showingJobs_plural", { count: jobs.length })}
        </p>
      )}

      {/* Floating Action Bar for Multi-Select */}
      {selectedJobs.size > 0 && (
        <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-40 bg-white/90 backdrop-blur border border-border rounded-xl shadow-lg px-5 py-3 flex items-center gap-4">
          <span className="text-sm font-medium text-foreground">
            {selectedJobs.size} selected
          </span>
          <button
            onClick={handleBatchApply}
            disabled={batchApplying}
            className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-sm font-semibold bg-foreground text-background hover:bg-foreground/90 disabled:opacity-40 transition-all"
          >
            {batchApplying ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Play className="w-4 h-4" />
            )}
            Apply to {selectedJobs.size} job{selectedJobs.size > 1 ? "s" : ""}
          </button>
          <button
            onClick={handleBatchTailor}
            disabled={tailoring}
            className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-sm font-semibold bg-primary text-white hover:bg-primary/90 disabled:opacity-40 transition-all"
          >
            {tailoring ? <Loader2 className="w-4 h-4 animate-spin" /> : <Wand2 className="w-4 h-4" />}
            Tailor Resume{selectedJobs.size > 1 ? "s" : ""}
          </button>
          <button
            onClick={handleBatchDelete}
            className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-sm font-semibold bg-destructive text-white hover:bg-destructive/90 transition-all"
          >
            <Trash2 className="w-4 h-4" />
            Delete {selectedJobs.size}
          </button>
          <button
            onClick={() => setSelectedJobs(new Set())}
            className="text-sm text-muted-foreground hover:text-foreground underline transition-colors"
          >
            Deselect All
          </button>
        </div>
      )}

      <AutomationDialog
        open={showConfirmDialog}
        title={t("dialog.startApplying")}
        onConfirm={confirmApplySingle}
        onCancel={() => {
          setShowConfirmDialog(false);
          setPendingApplyUrl(null);
        }}
      />

      {/* Cover Letter Modal */}
      {coverLetterJob && (
        <div
          className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
          onClick={() => setCoverLetterJob(null)}
        >
          <div
            className="bg-white rounded-2xl shadow-xl max-w-2xl w-full max-h-[85vh] overflow-hidden flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between p-5 border-b border-border">
              <div>
                <h3 className="text-base font-semibold text-foreground">
                  {t("coverLetterModal.title")}
                </h3>
                <p className="text-[13px] text-muted-foreground mt-0.5">
                  {t("coverLetterModal.jobAt", {
                    title: coverLetterJob.title,
                    company: coverLetterJob.company,
                  })}
                </p>
              </div>
              <button
                onClick={() => setCoverLetterJob(null)}
                className="p-1.5 text-muted-foreground hover:text-foreground"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-5">
              {!coverLetterJob.description &&
                !generatedLetter &&
                !generating && (
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
                      <FileText className="w-4 h-4" />
                      {t("coverLetterModal.generate")}
                    </button>
                  </div>
                )}

              {generating && (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="w-6 h-6 animate-spin text-primary mr-3" />
                  <span className="text-sm text-muted-foreground">
                    {t("coverLetterModal.generating")}
                  </span>
                </div>
              )}

              {generateError && !generating && (
                <div className="error-banner mb-4">
                  {generateError}
                  <button
                    onClick={() => setGenerateError(null)}
                    className="ml-2 underline text-sm"
                  >
                    Dismiss
                  </button>
                </div>
              )}

              {generatedLetter && (
                <div>
                  <label className="block text-sm font-semibold text-foreground mb-1.5">
                    {t("coverLetterModal.generatedLabel")}
                  </label>
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
                  onClick={() => {
                    navigator.clipboard.writeText(generatedLetter);
                  }}
                  className="btn-secondary"
                >
                  <Copy className="w-4 h-4" /> {t("coverLetterModal.copy")}
                </button>
                <button onClick={handleSaveCoverLetter} className="btn-primary">
                  <Save className="w-4 h-4" />{" "}
                  {letterSaved
                    ? t("coverLetterModal.saved")
                    : t("coverLetterModal.saveToProfile")}
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
