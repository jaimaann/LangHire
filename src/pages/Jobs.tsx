import { useState, useEffect, useRef } from "react";
import { Briefcase, Search, ExternalLink, Loader2, CheckCircle, XCircle, Clock, Ban, Play, Square, Terminal } from "lucide-react";
import { getJobs, getJobStats, startJobCollection, stopJobCollection, getCollectionStatus, startApplying, getApplyStatus } from "../lib/api";
import type { Job, JobStatus, JobStats } from "../lib/types";
import LogLine from "../components/LogLine";
import { PageHeader, ProgressBar } from "../components/ui";

const STATUS_CONFIG: Record<JobStatus, { label: string; color: string; bg: string; icon: typeof CheckCircle }> = {
  pending: { label: "Pending", color: "text-amber-700", bg: "bg-amber-50", icon: Clock },
  applied: { label: "Applied", color: "text-success", bg: "bg-[#F0FFF0]", icon: CheckCircle },
  failed: { label: "Failed", color: "text-destructive", bg: "bg-[#FFF0F0]", icon: XCircle },
  blocked: { label: "Blocked", color: "text-muted-foreground", bg: "bg-[#F7F7F7]", icon: Ban },
  in_progress: { label: "In Progress", color: "text-primary", bg: "bg-[#FFF0F3]", icon: Loader2 },
};

export default function Jobs() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [stats, setStats] = useState<JobStats>({total: 0, pending: 0, applied: 0, failed: 0, blocked: 0, in_progress: 0});
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("");
  // Collection state
  const [collecting, setCollecting] = useState(false);
  const [collectTitle, setCollectTitle] = useState("");
  const [collectMaxJobs, setCollectMaxJobs] = useState<number | "">(20);
  const [collectLog, setCollectLog] = useState<string[]>([]);
  const [collected, setCollected] = useState(0);
  const [showCollector, setShowCollector] = useState(true);
  const [applyingUrl, setApplyingUrl] = useState<string | null>(null);
  const logRef = useRef<HTMLDivElement>(null);

  const fetchJobs = (isBackgroundRefresh = false) => {
    if (!isBackgroundRefresh) setLoading(true);
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
      .finally(() => setLoading(false));
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
    const poll = setInterval(() => {
      getCollectionStatus().then((s) => {
        if (!active) return;
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

  const handleStartCollect = async () => {
    try {
      const res = await startJobCollection(collectTitle || undefined, collectMaxJobs ? Number(collectMaxJobs) : undefined);
      if (res.success) {
        setCollecting(true);
        setCollectLog(["Starting collection..."]);
        setShowCollector(true);
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

  const handleApplySingle = async (jobUrl: string) => {
    try {
      const res = await startApplying({ job_url: jobUrl, workers: 1, mode: "all" });
      if (!res.success) { alert(res.message); return; }
      setApplyingUrl(jobUrl);
    } catch (e) {
      alert(e instanceof Error ? e.message : "Failed to start");
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

  const handleSearch = (e: React.FormEvent) => { e.preventDefault(); fetchJobs(); };

  return (
    <div className="max-w-5xl">
      <PageHeader
        title="Jobs"
        subtitle={`${stats.total || 0} jobs collected · ${stats.applied || 0} applied · ${stats.pending || 0} pending`}
        actions={
          <button onClick={() => setShowCollector(!showCollector)} className="btn-primary">
            <Search className="w-4 h-4" /> {showCollector ? "Hide Collector" : "Collect Jobs"}
          </button>
        }
      />

      {/* Job Collector Panel */}
      {showCollector && (
        <div className="card mb-5">
          <h3 className="section-title mb-3">Job Collector</h3>
          <p className="text-[13px] text-muted-foreground mb-4">
            Search LinkedIn for job listings matching your profile. Leave title blank to search all titles from your profile.
            Collection typically takes 3-10 minutes per job title as the agent scrolls through results.
          </p>
          <div className="info-box mb-4">
            <strong>Login:</strong> A browser will open and check LinkedIn & Gmail. If you're not logged in, the agent will wait for you to log in manually — then proceed automatically.
          </div>
          <div className="flex gap-3 mb-4">
            <input value={collectTitle} onChange={(e) => setCollectTitle(e.target.value)}
              placeholder="Job title (e.g. 'Data Analyst') or leave blank for all"
              className="input-base flex-1"
              disabled={collecting} />
            <input type="number" value={collectMaxJobs} onChange={(e) => setCollectMaxJobs(e.target.value ? Number(e.target.value) : "")}
              placeholder="Max jobs" min={1} max={200}
              className="input-base !w-32 !flex-initial"
              disabled={collecting} title="Max jobs to collect (per title)" />
            {collecting ? (
              <button onClick={handleStopCollect} className="btn-destructive">
                <Square className="w-4 h-4" /> Stop
              </button>
            ) : (
              <button onClick={handleStartCollect}
                className="btn-dark">
                <Play className="w-4 h-4" /> Start
              </button>
            )}
          </div>
          {/* Progress bar */}
          {collecting && collectMaxJobs && (
            <div className="mb-4">
              <ProgressBar
                percent={collectMaxJobs > 0 ? (collected / Number(collectMaxJobs)) * 100 : 0}
                label={`Collected ${collected} of ${collectMaxJobs} jobs`}
              />
            </div>
          )}
          {/* Log output */}
          {collectLog.length > 0 && (
            <div ref={logRef}
              className="log-viewer">
              <div className="flex items-center gap-2 mb-2 text-gray-400">
                <Terminal className="w-3.5 h-3.5" /> Collection Log
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
          { value: "", label: "All", count: stats.total },
          { value: "pending", label: "Pending", count: stats.pending },
          { value: "applied", label: "Applied", count: stats.applied },
          { value: "failed", label: "Failed", count: stats.failed },
          { value: "blocked", label: "Blocked", count: stats.blocked },
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
              placeholder="Search by job title or company..."
              className="input-base !pl-10" />
          </div>
          <button type="submit" className="btn-primary">
            Search
          </button>
        </div>
      </form>

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
              {searchQuery || statusFilter ? "No matching jobs" : "No jobs collected yet"}
            </h3>
            <p className="text-[13px] text-muted-foreground mb-5">
              {searchQuery || statusFilter ? "Try changing your search or filter."
                : "Click 'Collect Jobs' above to search LinkedIn for matching listings."}
            </p>
            {!searchQuery && !statusFilter && (
              <button onClick={() => setShowCollector(true)} className="btn-primary">
                Start Collecting
              </button>
            )}
          </div>
        </div>
      ) : (
        <div className="bg-white rounded-2xl border border-border shadow-sm divide-y divide-border">
          {jobs.map((job) => {
            const cfg = STATUS_CONFIG[job.status] || STATUS_CONFIG.pending;
            const StatusIcon = cfg.icon;
            return (
              <div key={job.url} className="p-5 hover:bg-secondary/50 transition-colors">
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <h4 className="text-sm font-semibold text-foreground truncate">{job.title || "Untitled"}</h4>
                      {job.easy_apply && (
                        <span className="px-2 py-0.5 bg-[#FFF0F3] text-primary rounded-full text-[10px] font-semibold flex-shrink-0">Easy Apply</span>
                      )}
                    </div>
                    <p className="text-[13px] text-muted-foreground">{job.company || "Unknown"} · {job.location || "—"}</p>
                    {job.error && <p className="text-[13px] text-destructive mt-1 truncate" title={job.error}>Error: {job.error}</p>}
                    {job.collected_at && (
                      <p className="text-[11px] text-muted-foreground mt-1">
                        Collected {new Date(job.collected_at).toLocaleDateString()}
                        {job.applied_at && ` · Applied ${new Date(job.applied_at).toLocaleDateString()}`}
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-2 ml-4 flex-shrink-0">
                    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold ${cfg.bg} ${cfg.color}`}>
                      <StatusIcon className="w-3 h-3" /> {cfg.label}
                    </span>
                    {(job.status === "pending" || job.status === "failed") && (
                      <button
                        onClick={() => handleApplySingle(job.url)}
                        disabled={applyingUrl !== null}
                        title={applyingUrl ? "An application is already running" : job.status === "failed" ? "Retry this job" : "Apply to this job"}
                        className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-semibold bg-foreground text-white hover:bg-foreground/90 disabled:opacity-40 transition-all"
                      >
                        {applyingUrl === job.url ? (
                          <Loader2 className="w-3 h-3 animate-spin" />
                        ) : (
                          <Play className="w-3 h-3" />
                        )}
                        {applyingUrl === job.url ? "Applying..." : job.status === "failed" ? "Retry" : "Apply"}
                      </button>
                    )}
                    <a href={job.url} target="_blank" rel="noopener noreferrer"
                      className="p-1.5 text-muted-foreground hover:text-primary transition-colors" title="Open on LinkedIn">
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
          Showing {jobs.length} job{jobs.length !== 1 ? "s" : ""}
        </p>
      )}
    </div>
  );
}
