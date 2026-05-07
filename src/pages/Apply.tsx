import { useState, useEffect, useRef } from "react";
import { Play, Square, Terminal, Loader2, Briefcase } from "lucide-react";
import { startApplying, stopApplying, getApplyStatus, getJobStats } from "../lib/api";
import { trackEvent } from "../lib/analytics";
import { useNavigate } from "react-router-dom";
import LogLine from "../components/LogLine";
import AutomationDialog from "../components/AutomationDialog";
import { PageHeader, LoadingSpinner, EmptyState } from "../components/ui";

export default function Apply() {
  const [limit, setLimit] = useState<number | "">("");
  const [running, setRunning] = useState(false);
  const [log, setLog] = useState<string[]>([]);
  const [pendingCount, setPendingCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  useEffect(() => {
    Promise.all([
      getJobStats().then((s) => setPendingCount(s.pending || 0)),
      getApplyStatus().then((s) => { setRunning(s.running); setLog(s.log || []); }),
    ]).finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!running) return;
    let active = true;
    const poll = setInterval(() => {
      getApplyStatus().then((s) => {
        if (active) {
          if (!s.running) {
            trackEvent("apply_completed", { error: s.error || null });
          }
          setRunning(s.running);
          setLog(s.log || []);
        }
      }).catch(() => {});
    }, 2000);
    return () => { active = false; clearInterval(poll); };
  }, [running]);

  useEffect(() => {
    const el = logRef.current;
    if (el) {
      const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
      if (nearBottom) el.scrollTop = el.scrollHeight;
    }
  }, [log]);

  const handleStart = () => {
    setShowConfirmDialog(true);
  };

  const confirmStart = async () => {
    setShowConfirmDialog(false);
    try {
      const res = await startApplying({
        workers: 1,
        mode: "all",
        limit: limit ? Number(limit) : undefined,
      });
      if (res.success) {
        setRunning(true);
        setLog(["Starting..."]);
        trackEvent("apply_started", { limit: limit || "unlimited", pending: pendingCount });
      } else {
        alert(res.message);
      }
    } catch (e) {
      alert(e instanceof Error ? e.message : "Failed to start");
    }
  };

  const handleStop = async () => {
    await stopApplying();
    setRunning(false);
  };

  if (loading) {
    return <LoadingSpinner />;
  }

  return (
    <div className="max-w-5xl">
      <PageHeader title="Apply" subtitle={`Automated job applications · ${pendingCount} pending jobs`} />

      {/* No pending jobs — prompt to collect */}
      {pendingCount === 0 && !running && log.length === 0 && (
        <EmptyState
          icon={Briefcase}
          title="No jobs to apply to yet"
          description="Collect jobs from LinkedIn first, then come back here to apply automatically."
          action={
            <button onClick={() => navigate("/jobs")} className="btn-primary">
              Go to Jobs & Collect
            </button>
          }
        />
      )}

      {/* Controls */}
      {(pendingCount > 0 || running || log.length > 0) && (
        <div className="card mb-5">
          <h3 className="section-title mb-5">Application Controls</h3>

          <div className="info-box mb-5">
            <strong>Login:</strong> A browser will open and check LinkedIn & Gmail. If you're not logged in, the agent will wait for you to log in manually — then proceed automatically.
          </div>

          <div className="flex items-end gap-5 mb-5">
            <div className="flex-1 max-w-xs">
              <label className="block text-sm font-semibold text-foreground mb-1.5">Limit (optional)</label>
              <input type="number" value={limit} onChange={(e) => setLimit(e.target.value ? Number(e.target.value) : "")}
                disabled={running} placeholder="No limit — apply to all" min={1}
                className="input-base" />
              <p className="text-[13px] text-muted-foreground mt-1.5">Leave blank to apply to all {pendingCount} pending jobs</p>
            </div>
            <div>
              {running ? (
                <button onClick={handleStop} className="btn-destructive">
                  <Square className="w-4 h-4" /> Stop
                </button>
              ) : (
                <button onClick={handleStart}
                  className="btn-dark">
                  <Play className="w-4 h-4" /> Start Applying
                </button>
              )}
            </div>
          </div>

          {/* Tailored Resumes — Coming Soon */}
          <div className="border border-dashed border-border rounded-2xl p-4 bg-[#F7F7F7]">
            <div className="flex items-center gap-2">
              <span className="px-2.5 py-0.5 bg-amber-100 text-amber-700 rounded-full text-[10px] font-bold uppercase">Coming Soon</span>
              <span className="text-sm font-semibold text-foreground">Tailored Resumes</span>
            </div>
            <p className="text-[13px] text-muted-foreground mt-1">
              Auto-customize your resume for each job by extracting skills from the job description.
            </p>
          </div>
        </div>
      )}

      {/* Live Log */}
      {(log.length > 0 || running) && (
        <div className="card">
          <h3 className="section-title mb-4">
            {running ? "Live Output" : "Output Log"}
          </h3>
          <div ref={logRef}
            className="log-viewer">
            <div className="flex items-center gap-2 mb-2 text-gray-400">
              <Terminal className="w-3.5 h-3.5" /> Application Log
              {running && <Loader2 className="w-3.5 h-3.5 animate-spin text-green-400" />}
            </div>
            {log.map((line, i) => (
              <LogLine key={i} line={line} />
            ))}
          </div>
        </div>
      )}

      <AutomationDialog
        open={showConfirmDialog}
        title="Start Applying"
        onConfirm={confirmStart}
        onCancel={() => setShowConfirmDialog(false)}
      />
    </div>
  );
}
