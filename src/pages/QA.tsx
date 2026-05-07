import { useState, useEffect, useCallback, useRef } from "react";
import { Search, Trash2, Merge, Sparkles, Zap, HelpCircle, X } from "lucide-react";
import { getQAList, getQAStats, updateQA, deleteQA, mergeQA, autoSquashQA, smartSquashQA } from "../lib/api";
import { trackEvent } from "../lib/analytics";
import type { QAEntry, QAStats } from "../lib/types";

export default function QA() {
  const [questions, setQuestions] = useState<QAEntry[]>([]);
  const [stats, setStats] = useState<QAStats>({ total: 0, answered: 0, unanswered: 0 });
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<"all" | "unanswered">("all");
  const [loading, setLoading] = useState(true);
  const [squashing, setSquashing] = useState(false);
  const [smartSquashing, setSmartSquashing] = useState(false);
  const [mergeSource, setMergeSource] = useState<QAEntry | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const [qs, st] = await Promise.all([
        getQAList({ search, unanswered: filter === "unanswered" }),
        getQAStats(),
      ]);
      setQuestions(qs);
      setStats(st);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load Q&A");
    } finally {
      setLoading(false);
    }
  }, [search, filter]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  };

  const handleUpdate = async (id: number, answer: string) => {
    await updateQA(id, answer);
    setQuestions(prev => prev.map(q => q.id === id ? { ...q, answer } : q));
    trackEvent("qa_answer_updated");
  };

  const handleDelete = async (id: number) => {
    await deleteQA(id);
    fetchData();
    showToast("Question deleted");
  };

  const handleMerge = async (targetId: number) => {
    if (!mergeSource) return;
    await mergeQA(mergeSource.id, targetId);
    setMergeSource(null);
    fetchData();
    showToast("Questions merged");
  };

  const handleAutoSquash = async () => {
    setSquashing(true);
    try {
      const res = await autoSquashQA();
      fetchData();
      showToast(res.merged > 0 ? `Merged ${res.merged} duplicate(s)` : "No duplicates found");
    } catch { showToast("Auto-squash failed"); }
    finally { setSquashing(false); }
  };

  const handleSmartSquash = async () => {
    setSmartSquashing(true);
    try {
      const res = await smartSquashQA();
      fetchData();
      showToast(res.merged > 0 ? `Smart-merged ${res.merged} duplicate(s)` : "No semantic duplicates found");
      trackEvent("qa_smart_squash", { merged: res.merged });
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Smart squash failed");
    }
    finally { setSmartSquashing(false); }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="max-w-3xl">
      <div className="flex items-start justify-between mb-1">
        <div>
          <h1 className="text-2xl font-bold text-foreground tracking-tight">Q&A Repository</h1>
          <p className="text-[13px] text-muted-foreground mt-1">
            {stats.total} question{stats.total !== 1 ? "s" : ""} &middot; {stats.answered} answered &middot; {stats.unanswered} unanswered
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={handleAutoSquash} disabled={squashing} className="btn-secondary text-xs" title="Merge questions with similar text">
            <Zap className="w-3.5 h-3.5" />
            {squashing ? "Squashing..." : "Auto-Squash"}
          </button>
          <button onClick={handleSmartSquash} disabled={smartSquashing} className="btn-secondary text-xs" title="Use LLM to find semantically identical questions">
            <Sparkles className="w-3.5 h-3.5" />
            {smartSquashing ? "Analyzing..." : "Smart Squash"}
          </button>
        </div>
      </div>

      {error && <div className="error-banner mt-4 mb-4">{error}</div>}

      {/* Search + Filter */}
      <div className="flex items-center gap-3 mt-5 mb-4">
        <div className="flex-1 relative">
          <Search className="w-4 h-4 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search questions or answers..."
            className="input-base pl-9"
          />
        </div>
        <div className="flex gap-1">
          {(["all", "unanswered"] as const).map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-2 rounded-xl text-xs font-semibold transition-all ${
                filter === f
                  ? "bg-foreground text-white"
                  : "bg-secondary text-muted-foreground hover:bg-border"
              }`}
            >
              {f === "all" ? `All (${stats.total})` : `Unanswered (${stats.unanswered})`}
            </button>
          ))}
        </div>
      </div>

      {/* Merge mode banner */}
      {mergeSource && (
        <div className="bg-primary/10 border border-primary/20 rounded-xl px-4 py-3 mb-4 flex items-center justify-between">
          <p className="text-sm text-foreground">
            <strong>Merge mode:</strong> Click a question below to merge &ldquo;{mergeSource.question.substring(0, 60)}...&rdquo; into it.
          </p>
          <button onClick={() => setMergeSource(null)} className="text-muted-foreground hover:text-foreground">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Question list */}
      {questions.length === 0 ? (
        <div className="card text-center py-16">
          <HelpCircle className="w-10 h-10 text-border mx-auto mb-3" />
          <p className="text-muted-foreground text-sm">
            {search || filter === "unanswered"
              ? "No matching questions found."
              : "No questions yet. Questions will appear here as the agent applies to jobs."}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {questions.map(q => (
            <QACard
              key={q.id}
              entry={q}
              onUpdate={handleUpdate}
              onDelete={handleDelete}
              onMergeStart={() => setMergeSource(q)}
              onMergeTarget={() => handleMerge(q.id)}
              isMerging={!!mergeSource}
              isMergeSource={mergeSource?.id === q.id}
            />
          ))}
        </div>
      )}

      {/* Toast */}
      {toast && (
        <div className="fixed bottom-6 right-6 bg-foreground text-white px-4 py-2.5 rounded-xl text-sm font-semibold shadow-lg z-50 animate-in fade-in">
          {toast}
        </div>
      )}
    </div>
  );
}

function QACard({
  entry,
  onUpdate,
  onDelete,
  onMergeStart,
  onMergeTarget,
  isMerging,
  isMergeSource,
}: {
  entry: QAEntry;
  onUpdate: (id: number, answer: string) => void;
  onDelete: (id: number) => void;
  onMergeStart: () => void;
  onMergeTarget: () => void;
  isMerging: boolean;
  isMergeSource: boolean;
}) {
  const [answer, setAnswer] = useState(entry.answer);
  const [saving, setSaving] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  const handleChange = (val: string) => {
    setAnswer(val);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      setSaving(true);
      await onUpdate(entry.id, val);
      setSaving(false);
    }, 800);
  };

  return (
    <div
      className={`card transition-all ${isMerging && !isMergeSource ? "cursor-pointer hover:border-primary hover:shadow-md" : ""} ${isMergeSource ? "opacity-50" : ""}`}
      onClick={isMerging && !isMergeSource ? onMergeTarget : undefined}
    >
      <div className="flex items-start justify-between gap-3 mb-3">
        <p className="text-sm font-semibold text-foreground leading-snug flex-1">{entry.question}</p>
        <div className="flex items-center gap-1.5 shrink-0">
          {entry.times_seen > 1 && (
            <span className="px-2 py-0.5 bg-secondary rounded text-[10px] font-bold text-muted-foreground">
              {entry.times_seen}x
            </span>
          )}
          <span className="px-2 py-0.5 bg-secondary rounded text-[10px] font-semibold text-muted-foreground">
            {entry.question_type}
          </span>
        </div>
      </div>

      <textarea
        value={answer}
        onChange={(e) => handleChange(e.target.value)}
        placeholder="Type your answer here..."
        rows={2}
        className="input-base resize-y text-sm mb-2"
        onClick={(e) => e.stopPropagation()}
      />

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
          {entry.source_domain && <span>{entry.source_domain}</span>}
          {saving && <span className="text-primary">Saving...</span>}
          {!saving && answer !== entry.answer && <span className="text-primary">Unsaved</span>}
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={(e) => { e.stopPropagation(); onMergeStart(); }}
            className="p-1.5 rounded-lg text-muted-foreground hover:bg-secondary hover:text-foreground transition-colors"
            title="Merge into another question"
          >
            <Merge className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); onDelete(entry.id); }}
            className="p-1.5 rounded-lg text-muted-foreground hover:bg-destructive/10 hover:text-destructive transition-colors"
            title="Delete question"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
}
