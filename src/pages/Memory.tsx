import { useState, useEffect } from "react";
import { Brain, Search, Trash2, Download, ChevronRight, RefreshCw, Globe, Loader2 } from "lucide-react";
import { getMemoryStats, getMemoryDomains, getMemoriesForDomain, searchMemories, cleanupMemories, decayMemories, exportMemories } from "../lib/api";
import { trackEvent } from "../lib/analytics";
import { markStart, measureAndTrack } from "../lib/perf";
import type { DomainInfo, Memory as MemoryType } from "../lib/types";
import { PageHeader, LoadingSpinner } from "../components/ui";
import { useTranslation } from "react-i18next";

const CATEGORY_COLORS: Record<string, string> = {
  navigation: "bg-[#F0F4FF] text-[#3B5998]",
  form_strategy: "bg-purple-50 text-purple-700",
  element_interaction: "bg-amber-50 text-amber-700",
  failure_recovery: "bg-red-50 text-red-700",
  site_structure: "bg-green-50 text-green-700",
  qa_pattern: "bg-indigo-50 text-indigo-700",
};

export default function Memory() {
  const { t } = useTranslation("memory");
  const [stats, setStats] = useState({ total_memories: 0, unique_domains: 0, by_category: {} as Record<string, number> });
  const [domains, setDomains] = useState<DomainInfo[]>([]);
  const [selectedDomain, setSelectedDomain] = useState<string | null>(null);
  const [memories, setMemories] = useState<MemoryType[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<MemoryType[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMemories, setLoadingMemories] = useState(false);

  useEffect(() => {
    markStart("memory_page_load");
    Promise.all([
      getMemoryStats(),
      getMemoryDomains(),
    ])
      .then(([s, d]) => {
        setStats(s);
        setDomains(Array.isArray(d) ? (d as DomainInfo[]) : []);
      })
      .catch(() => {})
      .finally(() => { setLoading(false); measureAndTrack("memory_page_load"); });
  }, []);

  const selectDomain = (domain: string) => {
    setSelectedDomain(domain);
    setSearchResults(null);
    setLoadingMemories(true);
    getMemoriesForDomain(domain)
      .then((data) => setMemories((data as MemoryType[]) || []))
      .catch(() => setMemories([]))
      .finally(() => setLoadingMemories(false));
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) { setSearchResults(null); return; }
    setSelectedDomain(null);
    setLoadingMemories(true);
    searchMemories(searchQuery)
      .then((data) => setSearchResults((data as MemoryType[]) || []))
      .catch(() => setSearchResults([]))
      .finally(() => setLoadingMemories(false));
  };

  const handleDecay = async () => {
    if (!confirm(t("confirm.decay"))) return;
    const result = await decayMemories(30);
    trackEvent("memory_decay", { affected: result.affected });
    alert(t("toast.decayed", { count: result.affected }));
  };

  const handleCleanup = async () => {
    if (!confirm(t("confirm.cleanup"))) return;
    const result = await cleanupMemories();
    trackEvent("memory_cleanup", { deleted: result.deleted });
    alert(t("toast.deleted", { count: result.deleted }));
  };

  const handleExport = async () => {
    const data = await exportMemories();
    trackEvent("memory_export", { count: data.length });
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "memory_export.json";
    a.click();
    URL.revokeObjectURL(url);
  };

  const displayMemories = searchResults !== null ? searchResults : memories;

  if (loading) return <LoadingSpinner />;

  return (
    <div>
      <PageHeader
        title={t("title")}
        subtitle={t("subtitle", { total: stats.total_memories, domains: stats.unique_domains })}
        actions={
          <>
            <button onClick={handleExport} className="btn-secondary"><Download className="w-4 h-4" /> {t("actions.export")}</button>
            <button onClick={handleDecay} className="btn-secondary"><RefreshCw className="w-4 h-4" /> {t("actions.decay")}</button>
            <button onClick={handleCleanup} className="btn-destructive"><Trash2 className="w-4 h-4" /> {t("actions.cleanup")}</button>
          </>
        }
      />

      {/* Category stats */}
      {Object.keys(stats.by_category).length > 0 && (
        <div className="flex flex-wrap gap-2 mb-4">
          {Object.entries(stats.by_category).map(([cat, count]) => (
            <span key={cat} className={`px-2.5 py-1 rounded-full text-xs font-medium ${CATEGORY_COLORS[cat] || "bg-secondary text-foreground"}`}>
              {cat.replace("_", " ")}: {count}
            </span>
          ))}
        </div>
      )}

      {/* Search */}
      <form onSubmit={handleSearch} className="card mb-5">
        <div className="flex items-center gap-3">
          <div className="flex-1 relative">
            <Search className="w-4 h-4 absolute left-3 top-2.5 text-muted-foreground" />
            <input value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)}
              placeholder={t("search.placeholder")} className="w-full pl-9 pr-3 py-2 border border-border rounded-lg text-sm" />
          </div>
          <button type="submit" className="px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium">{t("search.button")}</button>
        </div>
      </form>

      <div className="grid grid-cols-3 gap-4">
        {/* Domain List */}
        <div className="col-span-1 bg-card rounded-2xl border border-border overflow-hidden shadow-sm">
          <div className="p-3 border-b border-border">
            <h3 className="text-sm font-bold text-foreground">{t("domains.title")}</h3>
          </div>
          {domains.length === 0 ? (
            <div className="p-4 text-center">
              <Globe className="w-8 h-8 text-muted-foreground mx-auto mb-2" />
              <p className="text-xs text-muted-foreground">{t("domains.empty")}</p>
            </div>
          ) : (
            <div className="divide-y divide-border max-h-[500px] overflow-y-auto">
              {domains.map((d) => (
                <button
                  key={d.website_domain}
                  onClick={() => selectDomain(d.website_domain)}
                  className={`w-full text-left p-3 hover:bg-secondary transition-colors flex items-center justify-between ${
                    selectedDomain === d.website_domain ? "bg-primary/5 border-l-2 border-l-primary" : ""
                  }`}
                >
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-foreground truncate">{d.website_domain}</p>
                    <p className="text-[10px] text-muted-foreground">
                      {d.ats_platform || "—"} · {d.count} memories · {Math.round(d.avg_confidence * 100)}% conf
                    </p>
                  </div>
                  <ChevronRight className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Memory List */}
        <div className="col-span-2 bg-card rounded-2xl border border-border overflow-hidden shadow-sm">
          <div className="p-3 border-b border-border">
            <h3 className="text-sm font-bold text-foreground">
              {searchResults !== null ? t("memories.searchResults", { count: searchResults.length }) :
               selectedDomain ? t("memories.domainTitle", { domain: selectedDomain, count: memories.length }) : t("memories.selectDomain")}
            </h3>
          </div>
          {loadingMemories ? (
            <div className="flex items-center justify-center h-48">
              <Loader2 className="w-6 h-6 animate-spin text-primary" />
            </div>
          ) : displayMemories.length === 0 ? (
            <div className="p-8 text-center">
              <Brain className="w-10 h-10 text-muted-foreground mx-auto mb-2" />
              <p className="text-sm text-muted-foreground">
                {selectedDomain || searchResults !== null ? t("memories.noMemoriesFound") : t("memories.selectDomainPrompt")}
              </p>
            </div>
          ) : (
            <div className="divide-y divide-border max-h-[500px] overflow-y-auto">
              {displayMemories.map((m) => (
                <div key={m.id} className="p-3">
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-sm text-foreground flex-1">{m.content}</p>
                    <div className="flex items-center gap-1 flex-shrink-0">
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${CATEGORY_COLORS[m.category] || "bg-secondary text-foreground"}`}>
                        {m.category.replace("_", " ")}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 mt-1.5">
                    <span className="text-[10px] text-muted-foreground">{m.website_domain}</span>
                    <span className={`text-[10px] ${m.success ? "text-green-600" : "text-red-500"}`}>
                      {m.success ? t("memories.success") : t("memories.failure")}
                    </span>
                    <span className="text-[10px] text-muted-foreground">
                      {t("memories.confidence", { percent: Math.round(m.confidence * 100) })}
                    </span>
                    <span className="text-[10px] text-muted-foreground">
                      {t("memories.accesses", { count: m.access_count })}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
