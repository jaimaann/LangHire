import { useState, useEffect, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { getJobStats } from "../lib/api";
import { PageHeader } from "../components/ui";
import type { JobStats } from "../lib/types";
import CollectTab from "./jobs/CollectTab";
import PendingTab from "./jobs/PendingTab";
import HistoryTab from "./jobs/HistoryTab";

type TabId = "collect" | "pending" | "history";

export default function Jobs() {
  const { t } = useTranslation("jobs");
  const [activeTab, setActiveTab] = useState<TabId>("pending");
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

  const tabs: { id: TabId; label: string }[] = [
    { id: "collect", label: t("tabs.collect", "Collect") },
    { id: "pending", label: t("tabs.pending", "Pipeline") },
    { id: "history", label: t("tabs.history", "History") },
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

      {/* Tab Navigation */}
      <div className="flex gap-2 mb-6">
        {tabs.map(({ id, label }) => (
          <button
            key={id}
            onClick={() => setActiveTab(id)}
            className={`filter-tab ${
              activeTab === id ? "filter-tab-active" : "filter-tab-inactive"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === "collect" && <CollectTab onJobsChanged={handleJobsChanged} />}
      {activeTab === "pending" && <PendingTab onJobsChanged={handleJobsChanged} stats={stats} />}
      {activeTab === "history" && <HistoryTab onJobsChanged={handleJobsChanged} />}
    </div>
  );
}
