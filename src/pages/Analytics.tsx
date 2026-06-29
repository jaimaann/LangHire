import { useState, useEffect, useMemo } from "react";
import { Briefcase, CheckCircle, XCircle, TrendingUp, Building2, Globe } from "lucide-react";
import { getJobs, getMetricRuns } from "../lib/api";
import { PageHeader, LoadingSpinner, EmptyState } from "../components/ui";
import type { Job, RunMetric } from "../lib/types";
import { useTranslation } from "react-i18next";

/** Count occurrences of a field across jobs, returning the top N as sorted pairs. */
function topCounts(items: string[], n: number): Array<[string, number]> {
  const counts = new Map<string, number>();
  for (const raw of items) {
    const key = (raw || "").trim();
    if (!key) continue;
    counts.set(key, (counts.get(key) || 0) + 1);
  }
  return [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, n);
}

/** Group applied jobs by day (last `days` days) for a simple trend. */
function dailyTrend(jobs: Job[], days: number): Array<{ day: string; count: number }> {
  const buckets = new Map<string, number>();
  for (const j of jobs) {
    const ts = j.applied_at || j.collected_at;
    if (!ts) continue;
    const day = ts.slice(0, 10); // YYYY-MM-DD
    buckets.set(day, (buckets.get(day) || 0) + 1);
  }
  return [...buckets.entries()]
    .sort((a, b) => a[0].localeCompare(b[0]))
    .slice(-days)
    .map(([day, count]) => ({ day, count }));
}

interface StatCardProps {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string | number;
}

function StatCard({ icon: Icon, label, value }: StatCardProps) {
  return (
    <div className="card flex items-center gap-4">
      <div className="w-10 h-10 rounded-xl bg-secondary flex items-center justify-center">
        <Icon className="w-5 h-5 text-foreground" />
      </div>
      <div>
        <p className="text-2xl font-bold text-foreground leading-tight">{value}</p>
        <p className="text-[13px] text-muted-foreground">{label}</p>
      </div>
    </div>
  );
}

/** Horizontal labeled bar (no chart dependency). */
function Bar({ label, value, max }: { label: string; value: number; max: number }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <div className="flex items-center gap-3 text-[13px]">
      <span className="w-40 truncate text-foreground" title={label}>{label}</span>
      <div className="flex-1 h-2.5 rounded-full bg-secondary overflow-hidden">
        <div className="h-full bg-primary rounded-full" style={{ width: `${pct}%` }} />
      </div>
      <span className="w-8 text-right text-muted-foreground tabular-nums">{value}</span>
    </div>
  );
}

export default function Analytics() {
  const { t } = useTranslation("dashboard");
  const [jobs, setJobs] = useState<Job[]>([]);
  const [runs, setRuns] = useState<RunMetric[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getJobs({ limit: 1000 }), getMetricRuns(500)])
      .then(([j, r]) => {
        setJobs(Array.isArray(j) ? j : []);
        setRuns(Array.isArray(r) ? r : []);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const metrics = useMemo(() => {
    const total = jobs.length;
    const applied = jobs.filter((j) => j.status === "applied").length;
    const failed = jobs.filter((j) => j.status === "failed").length;
    const attempts = applied + failed;
    const successRate = attempts > 0 ? Math.round((applied / attempts) * 100) : 0;

    const now = new Date();
    const weekAgo = new Date(now.getTime() - 7 * 24 * 3600 * 1000).toISOString();
    const monthAgo = new Date(now.getTime() - 30 * 24 * 3600 * 1000).toISOString();
    const appliedThisWeek = jobs.filter((j) => (j.applied_at || "") >= weekAgo).length;
    const appliedThisMonth = jobs.filter((j) => (j.applied_at || "") >= monthAgo).length;

    const bySource = topCounts(jobs.map((j) => j.source || "unknown"), 6);
    const byCompany = topCounts(jobs.map((j) => j.company), 6);
    const byStatus: Array<[string, number]> = [
      ["applied", applied],
      ["pending", jobs.filter((j) => j.status === "pending").length],
      ["failed", failed],
      ["blocked", jobs.filter((j) => j.status === "blocked").length],
    ];
    const trend = dailyTrend(jobs, 14);

    const avgSteps = runs.length
      ? Math.round(runs.reduce((s, r) => s + (r.step_count || 0), 0) / runs.length)
      : 0;

    return {
      total, applied, failed, successRate, appliedThisWeek, appliedThisMonth,
      bySource, byCompany, byStatus, trend, avgSteps,
    };
  }, [jobs, runs]);

  if (loading) return <LoadingSpinner />;

  return (
    <div className="max-w-4xl">
      <PageHeader title={t("analytics.title", "Analytics")} subtitle={t("analytics.subtitle", "Insights into your job applications")} />

      {metrics.total === 0 ? (
        <EmptyState
          icon={TrendingUp}
          title={t("analytics.emptyTitle", "No data yet")}
          description={t("analytics.emptyDescription", "Collect and apply to jobs to see analytics here.")}
        />
      ) : (
        <div className="space-y-5">
          {/* Headline stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard icon={Briefcase} label={t("analytics.totalJobs", "Total jobs")} value={metrics.total} />
            <StatCard icon={CheckCircle} label={t("analytics.applied", "Applied")} value={metrics.applied} />
            <StatCard icon={TrendingUp} label={t("analytics.successRate", "Success rate")} value={`${metrics.successRate}%`} />
            <StatCard icon={XCircle} label={t("analytics.failed", "Failed")} value={metrics.failed} />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <StatCard icon={Briefcase} label={t("analytics.appliedThisWeek", "Applied this week")} value={metrics.appliedThisWeek} />
            <StatCard icon={Briefcase} label={t("analytics.appliedThisMonth", "Applied this month")} value={metrics.appliedThisMonth} />
          </div>

          {/* Status breakdown */}
          <div className="card">
            <h3 className="section-title mb-4">{t("analytics.byStatus", "By status")}</h3>
            <div className="space-y-2.5">
              {metrics.byStatus.map(([label, value]) => (
                <Bar key={label} label={label} value={value} max={metrics.total} />
              ))}
            </div>
          </div>

          {/* By source */}
          <div className="card">
            <h3 className="section-title mb-4 flex items-center gap-2"><Globe className="w-4 h-4" /> {t("analytics.bySource", "By source")}</h3>
            <div className="space-y-2.5">
              {metrics.bySource.map(([label, value]) => (
                <Bar key={label} label={label} value={value} max={metrics.bySource[0]?.[1] || 1} />
              ))}
            </div>
          </div>

          {/* Top companies */}
          <div className="card">
            <h3 className="section-title mb-4 flex items-center gap-2"><Building2 className="w-4 h-4" /> {t("analytics.topCompanies", "Top companies")}</h3>
            <div className="space-y-2.5">
              {metrics.byCompany.map(([label, value]) => (
                <Bar key={label} label={label} value={value} max={metrics.byCompany[0]?.[1] || 1} />
              ))}
            </div>
          </div>

          {/* Daily trend */}
          <div className="card">
            <h3 className="section-title mb-4">{t("analytics.trend", "Recent activity")}</h3>
            <div className="flex items-end gap-1.5 h-32">
              {metrics.trend.map(({ day, count }) => {
                const maxCount = Math.max(...metrics.trend.map((d) => d.count), 1);
                const h = Math.round((count / maxCount) * 100);
                return (
                  <div key={day} className="flex-1 flex flex-col items-center justify-end gap-1" title={`${day}: ${count}`}>
                    <div className="w-full bg-primary/80 rounded-t" style={{ height: `${h}%` }} />
                    <span className="text-[9px] text-muted-foreground rotate-0">{day.slice(5)}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
