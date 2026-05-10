import { useState, useEffect, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { getJobStats } from "../lib/api";
import { PageHeader } from "../components/ui";
import type { JobStats } from "../lib/types";
import { Search, Play, CheckCircle } from "lucide-react";
import CollectTab from "./jobs/CollectTab";
import PendingTab from "./jobs/PendingTab";
import HistoryTab from "./jobs/HistoryTab";

type TabId = "collect" | "pending" | "history";

export default function Jobs() {
  const { t } = useTranslation("jobs");
  const [activeTab, setActiveTab] = useState<TabId>("collect");
  const [stats, setStats] = useState<JobStats>({
    total: 0,
    pending: 0,
    applied: 0,
    failed: 0,
    blocked: 0,
    in_progress: 0,
  });

  const fetchStats = useCallback(() => {
    getJobStats()
      .then((s) => setStats(s || { total: 0, pending: 0, applied: 0, failed: 0, blocked: 0, in_progress: 0 }))
      .catch(() => {});
  }, []);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  const handleJobsChanged = useCallback(() => {
    fetchStats();
  }, [fetchStats]);

  const tabs: { id: TabId; label: string; icon: typeof Search; count?: number }[] = [
    { id: "collect", label: "Collect", icon: Search, count: stats.total },
    { id: "pending", label: "Review & Apply", icon: Play, count: stats.pending + stats.failed },
    { id: "history", label: "History", icon: CheckCircle, count: stats.applied },
  ];

  return (
    <div className="max-w-5xl">
      <PageHeader
        title={t("title")}
        subtitle={t("subtitle", {
          total: stats.total || 0,
          applied: stats.applied || 0,
          pending: stats.pending || 0,
        })}
      />

      {/* Workflow Steps */}
      <div className="flex items-center gap-0 mb-6">
        {tabs.map(({ id, label, icon: Icon, count }, index) => (
          <div key={id} className="flex items-center">
            <button
              onClick={() => setActiveTab(id)}
              className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold transition-all ${
                activeTab === id
                  ? "bg-foreground text-white shadow-sm"
                  : "bg-secondary/60 text-muted-foreground hover:bg-secondary hover:text-foreground"
              }`}
            >
              <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold ${
                activeTab === id ? "bg-white/20 text-white" : "bg-border text-muted-foreground"
              }`}>
                {index + 1}
              </span>
              <Icon className="w-3.5 h-3.5" />
              {label}
              {count !== undefined && count > 0 && (
                <span className={`text-[11px] px-1.5 py-0.5 rounded-full ${
                  activeTab === id ? "bg-white/20" : "bg-border"
                }`}>
                  {count}
                </span>
              )}
            </button>
            {index < tabs.length - 1 && (
              <div className="w-6 h-[2px] bg-border mx-1" />
            )}
          </div>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === "collect" && <CollectTab onJobsChanged={handleJobsChanged} />}
      {activeTab === "pending" && <PendingTab onJobsChanged={handleJobsChanged} stats={stats} />}
      {activeTab === "history" && <HistoryTab onJobsChanged={handleJobsChanged} />}
    </div>
  );
}
