import { useState, useEffect } from "react";
import { Brain, Search, Trash2, Download, ChevronRight, RefreshCw, Globe, Loader2 } from "lucide-react";
import { getMemoryStats, getMemoryDomains, getMemoriesForDomain, searchMemories, cleanupMemories, decayMemories, exportMemories } from "../lib/api";
import { trackEvent } from "../lib/analytics";
import { markStart, measureAndTrack } from "../lib/perf";
import type { DomainInfo, Memory } from "../lib/types";
import { PageHeader, LoadingSpinner } from "../components/ui";

const CATEGORY_COLORS: Record<string, string> = {
  navigation: "bg-[#F0F4FF] text-[#3B5998]",
  form_strategy: "bg-purple-50 text-purple-700",
  element_interaction: "bg-amber-50 text-amber-700",
  failure_recovery: "bg-red-50 text-red-700",
  site_structure: "bg-green-50 text-green-700",
  qa_pattern: "bg-indigo-50 text-indigo-700",
};

export default function Memory() {
  const [stats, setStats] = useState({ total_memories: 0, unique_domains: 0, by_category: {} as Record<string, number> });
  const [domains, setDomains] = useState<DomainInfo[]>([]);
  const [selectedDomain, setSelectedDomain] = useState<string | null>(null);
  const [memories, setMemories] = useState<Memory[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<Memory[] | null>(null);
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
      .then((data) => setMemories((data as Memory[]) || []))
      .catch(() => setMemories([]))
      .finally(() => setLoadingMemories(false));
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) { setSearchResults(null); return; }
    setSelectedDomain(null);
    setLoadingMemories(true);
    searchMemories(searchQuery)
      .then((data) => setSearchResults((data as Memory[]) || []))
      .catch(() => setSearchResults([]))
      .finally(() => setLoadingMemories(false));
  };

  const handleDecay = async () => {
    if (!confirm("Reduce confidence of memories not updated in 30+ days?")) return;
    const result = await decayMemories(30);
    trackEvent("memory_decay", { affected: result.affected });
    alert(`Decayed ${result.affected} memories`);
  };

  const handleCleanup = async () => {
    if (!confirm("Delete all memories with confidence below 0.3?")) return;
    const result = await cleanupMemories();
    trackEvent("memory_cleanup", { deleted: result.deleted });
    alert(`Deleted ${result.deleted} memories`);
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
        title="Memory"
        subtitle={`${stats.total_memories} memories across ${stats.unique_domains} domains`}
        actions={
          <>
            <button onClick={handleExport} className="btn-secondary"><Download className="w-4 h-4" /> Export</button>
            <button onClick={handleDecay} className="btn-secondary"><RefreshCw className="w-4 h-4" /> Decay</button>
            <button onClick={handleCleanup} className="btn-destructive"><Trash2 className="w-4 h-4" /> Cleanup</button>
          </>
        }
      />

      {/* Category stats */}
      {Object.keys(stats.by_category).length > 0 && (
        <div className="flex flex-wrap gap-2 mb-4">
          {Object.entries(stats.by_category).map(([cat, count]) => (
            <span key={cat} className={`px-2.5 py-1 rounded-full text-xs font-medium ${CATEGORY_COLORS[cat] || "bg-gray-50 text-gray-700"}`}>
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
              placeholder="Search memories..." className="w-full pl-9 pr-3 py-2 border border-border rounded-lg text-sm" />
          </div>
          <button type="submit" className="px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium">Search</button>
        </div>
      </form>

      <div className="grid grid-cols-3 gap-4">
        {/* Domain List */}
        <div className="col-span-1 bg-white rounded-2xl border border-border overflow-hidden shadow-sm">
          <div className="p-3 border-b border-border">
            <h3 className="text-sm font-bold text-foreground">Domains</h3>
          </div>
          {domains.length === 0 ? (
            <div className="p-4 text-center">
              <Globe className="w-8 h-8 text-muted-foreground mx-auto mb-2" />
              <p className="text-xs text-muted-foreground">No domains yet</p>
            </div>
          ) : (
            <div className="divide-y divide-border max-h-[500px] overflow-y-auto">
              {domains.map((d) => (
                <button
                  key={d.website_domain}
                  onClick={() => selectDomain(d.website_domain)}
                  className={`w-full text-left p-3 hover:bg-gray-50 transition-colors flex items-center justify-between ${
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
        <div className="col-span-2 bg-white rounded-2xl border border-border overflow-hidden shadow-sm">
          <div className="p-3 border-b border-border">
            <h3 className="text-sm font-bold text-foreground">
              {searchResults !== null ? `Search Results (${searchResults.length})` :
               selectedDomain ? `${selectedDomain} (${memories.length})` : "Select a domain"}
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
                {selectedDomain || searchResults !== null ? "No memories found" : "Select a domain to view its memories"}
              </p>
            </div>
          ) : (
            <div className="divide-y divide-border max-h-[500px] overflow-y-auto">
              {displayMemories.map((m) => (
                <div key={m.id} className="p-3">
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-sm text-foreground flex-1">{m.content}</p>
                    <div className="flex items-center gap-1 flex-shrink-0">
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${CATEGORY_COLORS[m.category] || "bg-gray-50 text-gray-700"}`}>
                        {m.category.replace("_", " ")}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 mt-1.5">
                    <span className="text-[10px] text-muted-foreground">{m.website_domain}</span>
                    <span className={`text-[10px] ${m.success ? "text-green-600" : "text-red-500"}`}>
                      {m.success ? "✓ success" : "✗ failure"}
                    </span>
                    <span className="text-[10px] text-muted-foreground">
                      {Math.round(m.confidence * 100)}% confidence
                    </span>
                    <span className="text-[10px] text-muted-foreground">
                      {m.access_count} accesses
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
