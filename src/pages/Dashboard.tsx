import { useState, useEffect } from "react";
import {
  Briefcase,
  CheckCircle,
  XCircle,
  Clock,
  Brain,
  TrendingUp,
  BookOpen,
  User,
  Cpu,
  FileText,
  ArrowRight,
} from "lucide-react";
import { getDashboardData, checkHealth, getSetupStatus, getChromiumStatus, type SetupStatus } from "../lib/api";
import { Download, Loader2 as Spinner } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { PageHeader, LoadingSpinner, ProgressBar } from "../components/ui";

export default function Dashboard() {
  const [stats, setStats] = useState({
    totalJobs: 0, applied: 0, failed: 0, pending: 0, successRate: 0, totalMemories: 0,
  });
  const [backendOk, setBackendOk] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(true);
  const [setupStatus, setSetupStatus] = useState<SetupStatus | null>(null);
  const [chromiumState, setChromiumState] = useState<{ state: string; message: string } | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    let cancelled = false;

    async function init() {
      for (let i = 0; i < 10; i++) {
        try {
          await checkHealth();
          if (!cancelled) setBackendOk(true);
          break;
        } catch {
          if (i === 9) { if (!cancelled) setBackendOk(false); return; }
          await new Promise((r) => setTimeout(r, 1500));
        }
      }

      try {
        const [data, setup] = await Promise.all([
          getDashboardData(),
          getSetupStatus().catch(() => null),
        ]);

        const jobs = data.jobs || { total: 0, applied: 0, failed: 0, pending: 0, blocked: 0, in_progress: 0 };
        const mem = data.memory || { total_memories: 0, unique_domains: 0, by_category: {} };
        const total = jobs.total || 0;
        const applied = jobs.applied || 0;
        if (!cancelled) {
          setStats({
            totalJobs: total,
            applied,
            failed: jobs.failed || 0,
            pending: jobs.pending || 0,
            successRate: total > 0 ? Math.round((applied / total) * 100) : 0,
            totalMemories: mem.total_memories || 0,
          });
          if (setup) setSetupStatus(setup);
        }
      } catch {}
      if (!cancelled) setLoading(false);
    }

    init();

    const healthPoll = setInterval(() => {
      if (cancelled) return;
      checkHealth()
        .then(() => { if (!cancelled) setBackendOk(true); })
        .catch(() => { if (!cancelled) setBackendOk(false); });
    }, 30000);

    return () => { cancelled = true; clearInterval(healthPoll); };
  }, []);

  useEffect(() => {
    let active = true;
    const poll = () => {
      getChromiumStatus()
        .then((s) => {
          if (!active) return;
          setChromiumState(s);
          if (s.state === "installing" || s.state === "checking") {
            setTimeout(poll, 2000);
          }
        })
        .catch(() => {
          if (active) setTimeout(poll, 3000);
        });
    };
    poll();
    return () => { active = false; };
  }, []);

  const cards = [
    { label: "Total Jobs", value: stats.totalJobs, icon: Briefcase, color: "text-[#222222]", bg: "bg-[#F7F7F7]" },
    { label: "Applied", value: stats.applied, icon: CheckCircle, color: "text-success", bg: "bg-[#F0FFF0]" },
    { label: "Failed", value: stats.failed, icon: XCircle, color: "text-destructive", bg: "bg-[#FFF0F0]" },
    { label: "Pending", value: stats.pending, icon: Clock, color: "text-warning", bg: "bg-[#FFF8F0]" },
    { label: "Success Rate", value: `${stats.successRate}%`, icon: TrendingUp, color: "text-primary", bg: "bg-[#FFF0F3]" },
    { label: "Memories", value: stats.totalMemories, icon: Brain, color: "text-[#6B21A8]", bg: "bg-[#F5F0FF]" },
  ];

  const setupSteps = [
    { label: "Configure AI provider", done: setupStatus?.llm, path: "/llm", icon: Cpu, required: true },
    { label: "Set resume path", done: setupStatus?.resume, path: "/settings", icon: FileText, required: true },
    { label: "Set up your profile", done: setupStatus?.profile, path: "/profile", icon: User, required: true },
  ];

  const allRequiredDone = setupStatus?.all_required_done;
  const completedCount = setupSteps.filter((s) => s.done).length;

  if (loading) {
    return (
      <div className="max-w-5xl">
        <PageHeader title="Dashboard" subtitle="Overview of your job application progress" />
        {/* Show Chromium progress even while loading */}
        {chromiumState && chromiumState.state === "installing" && (
          <div className="card mb-6 flex items-center gap-4">
            <div className="bg-[#F7F7F7] p-3 rounded-2xl">
              <Download className="w-5 h-5 text-foreground" />
            </div>
            <div className="flex-1">
              <p className="text-sm font-semibold text-foreground">Installing Chromium Browser</p>
              <p className="text-[13px] text-muted-foreground mt-0.5">{chromiumState.message}</p>
            </div>
            <Spinner className="w-5 h-5 animate-spin text-muted-foreground" />
          </div>
        )}
        {chromiumState && chromiumState.state === "failed" && (
          <div className="error-banner mb-6">{chromiumState.message}</div>
        )}
        <LoadingSpinner />
      </div>
    );
  }

  return (
    <div className="max-w-5xl">
      <PageHeader title="Dashboard" subtitle="Overview of your job application progress" />

      {backendOk === false && (
        <div className="error-banner mb-6 flex items-center gap-2">
          <XCircle className="w-4 h-4 text-destructive flex-shrink-0" />
          <span>
            Backend not connected. Start it with: <code className="bg-[#FFE0E0] px-1.5 py-0.5 rounded-lg text-xs font-mono">uv run python backend/main.py</code>
          </span>
        </div>
      )}

      {/* Chromium Install Progress */}
      {chromiumState && chromiumState.state === "installing" && (
        <div className="card mb-6 flex items-center gap-4">
          <div className="bg-[#F7F7F7] p-3 rounded-2xl">
            <Download className="w-5 h-5 text-foreground" />
          </div>
          <div className="flex-1">
            <p className="text-sm font-semibold text-foreground">Installing Chromium Browser</p>
            <p className="text-[13px] text-muted-foreground mt-0.5">{chromiumState.message}</p>
          </div>
          <Spinner className="w-5 h-5 animate-spin text-muted-foreground" />
        </div>
      )}

      {chromiumState && chromiumState.state === "failed" && (
        <div className="error-banner mb-6 flex items-center gap-2">
          <XCircle className="w-4 h-4 text-destructive flex-shrink-0" />
          <span>Chromium install failed: {chromiumState.message}. Run <code className="bg-[#FFE0E0] px-1.5 py-0.5 rounded-lg text-xs font-mono">python3 -m playwright install chromium</code> manually.</span>
        </div>
      )}

      {/* Stats Grid */}
      <div className="grid grid-cols-3 gap-5 mb-8">
        {cards.map(({ label, value, icon: Icon, color, bg }) => (
          <div key={label} className="card flex items-center gap-4">
            <div className={`${bg} p-3.5 rounded-2xl`}>
              <Icon className={`w-5 h-5 ${color}`} />
            </div>
            <div>
              <p className="text-[13px] text-muted-foreground font-medium">{label}</p>
              <p className="text-2xl font-extrabold text-foreground">{value}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Quick Actions */}
      <div className="card mb-6">
        <h3 className="section-title mb-5">Quick Actions</h3>
        <div className="flex gap-3">
          <button onClick={() => navigate("/jobs")} className="btn-primary">
            Collect Jobs
            <ArrowRight className="w-4 h-4" />
          </button>
          <button onClick={() => navigate("/apply")} className="btn-secondary">
            Start Applying
            <ArrowRight className="w-4 h-4" />
          </button>
          <button onClick={() => navigate("/memory")} className="btn-ghost">
            View Memories
          </button>
        </div>
      </div>

      {/* Live Setup Checklist */}
      <div className="card">
        <div className="flex items-center justify-between mb-5">
          <h3 className="section-title">
            {allRequiredDone ? "Setup Complete" : "Getting Started"}
          </h3>
          <button
            onClick={() => navigate("/guide")}
            className="flex items-center gap-1.5 text-[13px] text-primary font-semibold hover:underline"
          >
            <BookOpen className="w-3.5 h-3.5" />
            View full guide
          </button>
        </div>

        {allRequiredDone ? (
          <div className="bg-[#F0FFF0] rounded-2xl p-5 flex items-start gap-3">
            <CheckCircle className="w-5 h-5 text-success mt-0.5 flex-shrink-0" />
            <div>
              <p className="text-sm font-semibold text-foreground">
                All required setup is done! You're ready to collect and apply to jobs.
              </p>
              <p className="text-[13px] text-muted-foreground mt-1">
                Need help? Visit the{" "}
                <button onClick={() => navigate("/guide")} className="underline font-semibold text-primary">Guide</button>
                {" "}for step-by-step instructions.
              </p>
            </div>
          </div>
        ) : (
          <>
            <div className="mb-5">
              <ProgressBar
                percent={(completedCount / setupSteps.length) * 100}
                label={`${completedCount} of ${setupSteps.length} steps complete`}
              />
            </div>

            <div className="space-y-1">
              {setupSteps.map((step) => {
                const Icon = step.icon;
                return (
                  <div key={step.label} className="flex items-center justify-between py-2.5 px-3 rounded-xl hover:bg-secondary transition-colors">
                    <div className="flex items-center gap-3">
                      {step.done ? (
                        <CheckCircle className="w-5 h-5 text-success" />
                      ) : (
                        <div className="w-5 h-5 rounded-full border-2 border-border" />
                      )}
                      <Icon className="w-4 h-4 text-muted-foreground" />
                      <span className={`text-sm font-medium ${step.done ? "text-muted-foreground line-through" : "text-foreground"}`}>
                        {step.label}
                      </span>
                    </div>
                    {!step.done && step.path !== "/" && (
                      <button onClick={() => navigate(step.path)} className="text-[13px] text-primary font-semibold hover:underline">
                        Set up
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
