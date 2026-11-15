/**
 * PendingTab: needs_input / skipped statuses, match-score pills and sorting,
 * and live apply progress from the SSE event stream.
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor, within, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import PendingTab from "./PendingTab";
import { getJobs, startApplying, getApplyStatus, subscribeEvents } from "../../lib/api";
import { sortJobs } from "../../lib/jobSort";
import type { Job, JobStats, RunEvent } from "../../lib/types";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (k: string, o?: Record<string, unknown>) => (o ? `${k}:${JSON.stringify(o)}` : k),
    i18n: { changeLanguage: vi.fn() },
  }),
}));

vi.mock("../../lib/perf", () => ({ markStart: vi.fn(), measureAndTrack: vi.fn() }));

vi.mock("../../lib/api", () => ({
  subscribeEvents: vi.fn(() => () => {}),
  getJobs: vi.fn(),
  startApplying: vi.fn(),
  getApplyStatus: vi.fn(),
  generateCoverLetter: vi.fn(),
  saveProfile: vi.fn(),
  getProfile: vi.fn(),
  updateJobStatus: vi.fn(),
  deleteJobs: vi.fn(),
  tailorResumes: vi.fn(),
  refineTailoredResume: vi.fn(),
  getTailoredResumeContent: vi.fn(),
  openLocalFile: vi.fn(),
}));

function installLocalStorage() {
  const store = new Map<string, string>();
  vi.stubGlobal("localStorage", {
    getItem: (k: string) => (store.has(k) ? store.get(k)! : null),
    setItem: (k: string, v: string) => void store.set(k, String(v)),
    removeItem: (k: string) => void store.delete(k),
    clear: () => store.clear(),
    key: (i: number) => [...store.keys()][i] ?? null,
    get length() {
      return store.size;
    },
  });
}

const stats: JobStats = {
  total: 6, pending: 2, applied: 0, failed: 1, blocked: 0, in_progress: 0, skipped: 1, needs_input: 1,
};

const job = (over: Partial<Job>): Job => ({
  url: `https://jobs.example.com/${over.title}`,
  title: "Job",
  company: "Co",
  location: "Remote",
  easy_apply: false,
  status: "pending",
  ...over,
});

const jobs: Job[] = [
  job({ title: "Low", match_score: 20, collected_at: "2026-11-10T00:00:00Z" }),
  job({ title: "Unscored", match_score: null, collected_at: "2026-11-13T00:00:00Z" }),
  job({ title: "High", match_score: 91.6, collected_at: "2026-11-01T00:00:00Z" }),
  job({
    title: "Asks",
    status: "needs_input",
    match_score: 55,
    error: "Needs your answer: What is your notice period?",
    collected_at: "2026-11-05T00:00:00Z",
  }),
  job({ title: "Dup", status: "skipped", collected_at: "2026-11-02T00:00:00Z" }),
];

let emit: (e: RunEvent) => void = () => {};

function titlesInOrder(): string[] {
  return screen.getAllByRole("heading", { level: 4 }).map((h) => h.textContent || "");
}

describe("PendingTab statuses, match score and live progress", () => {
  beforeEach(() => {
    installLocalStorage();
    vi.stubGlobal("alert", vi.fn());
    vi.mocked(getJobs).mockResolvedValue(structuredClone(jobs) as never);
    vi.mocked(getApplyStatus).mockResolvedValue({ running: true, log: [], cost_usd: 0 } as never);
    vi.mocked(startApplying).mockResolvedValue({ success: true, message: "ok" } as never);
    vi.mocked(subscribeEvents).mockImplementation((cb) => {
      emit = cb;
      return () => {};
    });
  });

  it("sorts by match score (desc, unscored last) by default and shows score pills", async () => {
    render(<PendingTab onJobsChanged={vi.fn()} stats={stats} />);
    await screen.findByText("High");
    expect(titlesInOrder()).toEqual(["High", "Asks", "Low", "Unscored", "Dup"]);
    const pills = screen.getAllByTestId("match-score").map((p) => p.textContent);
    expect(pills[0]).toBe('jobItem.match:{"score":92}');
    // Unscored jobs get no pill.
    expect(pills).toHaveLength(3);
  });

  it("can sort by newest instead", async () => {
    const user = userEvent.setup();
    render(<PendingTab onJobsChanged={vi.fn()} stats={stats} />);
    await screen.findByText("High");
    await user.selectOptions(screen.getByLabelText("sort.label"), "newest");
    expect(titlesInOrder()).toEqual(["Unscored", "Low", "Asks", "Dup", "High"]);
  });

  it("shows a needs_input badge with an 'Answer and retry' link to the Q&A page, and lets it be retried", async () => {
    const user = userEvent.setup();
    render(<PendingTab onJobsChanged={vi.fn()} stats={stats} />);
    await screen.findByText("Asks");
    expect(screen.getByTestId("status-badge-needs_input")).toHaveTextContent("status.needsInput");
    expect(screen.getByText(/What is your notice period/)).toBeInTheDocument();
    const link = screen.getByRole("link", { name: "jobItem.answerAndRetry" });
    expect(link).toHaveAttribute("href", "#/qa");

    // Retry goes through the normal single-job apply call.
    const row = screen.getByText("Asks").closest("div.p-5") as HTMLElement;
    await user.click(within(row).getByRole("button", { name: /jobItem.retry/ }));
    await user.click(await screen.findByRole("button", { name: /I Understand|Start|Confirm|Continue/i }));
    await waitFor(() =>
      expect(startApplying).toHaveBeenCalledWith(
        expect.objectContaining({ job_url: "https://jobs.example.com/Asks" }),
      ),
    );
  });

  it("shows a skipped badge without an apply button", async () => {
    render(<PendingTab onJobsChanged={vi.fn()} stats={stats} />);
    await screen.findByText("Dup");
    expect(screen.getByTestId("status-badge-skipped")).toHaveTextContent("status.skipped");
    const row = screen.getByText("Dup").closest("div.p-5") as HTMLElement;
    expect(within(row).queryByRole("button", { name: /jobItem.apply/ })).not.toBeInTheDocument();
  });

  it("has filter tabs for needs_input and skipped with counts", async () => {
    const user = userEvent.setup();
    render(<PendingTab onJobsChanged={vi.fn()} stats={stats} />);
    await screen.findByText("High");
    await user.click(screen.getByRole("button", { name: "status.needsInput (1)" }));
    await waitFor(() => expect(getJobs).toHaveBeenLastCalledWith(expect.objectContaining({ status: "needs_input" })));
    expect(screen.getByRole("button", { name: "status.skipped (1)" })).toBeInTheDocument();
  });

  it("shows live LLM cost from cost events and refreshes when the run finishes", async () => {
    const user = userEvent.setup();
    const onJobsChanged = vi.fn();
    render(<PendingTab onJobsChanged={onJobsChanged} stats={stats} />);
    await screen.findByText("High");
    const row = screen.getByText("High").closest("div.p-5") as HTMLElement;
    await user.click(within(row).getByRole("button", { name: /jobItem.apply/ }));
    await user.click(await screen.findByRole("button", { name: /I Understand|Start|Confirm|Continue/i }));
    await screen.findByTestId("apply-progress");

    act(() => emit({ id: 1, run_id: "r", kind: "apply", type: "cost", level: "info", message: "", data: { cost_usd: 0.0425 } }));
    expect(screen.getByTestId("apply-progress")).toHaveTextContent('progress.cost:{"cost":"0.043"}');

    // Collect events are ignored by the apply view.
    act(() => emit({ id: 2, run_id: "c", kind: "collect", type: "run_finished", level: "info", message: "", data: {} }));
    expect(screen.getByTestId("apply-progress")).toBeInTheDocument();

    act(() => emit({ id: 3, run_id: "r", kind: "apply", type: "run_finished", level: "info", message: "done", data: {} }));
    await waitFor(() => expect(screen.queryByTestId("apply-progress")).not.toBeInTheDocument());
    expect(onJobsChanged).toHaveBeenCalled();
  });
});

describe("sortJobs", () => {
  it("does not mutate the input and breaks score ties by newest", () => {
    const input = [
      job({ title: "a", match_score: 50, collected_at: "2026-01-01" }),
      job({ title: "b", match_score: 50, collected_at: "2026-02-01" }),
    ];
    const out = sortJobs(input, "match");
    expect(out.map((j) => j.title)).toEqual(["b", "a"]);
    expect(input.map((j) => j.title)).toEqual(["a", "b"]);
  });
});
