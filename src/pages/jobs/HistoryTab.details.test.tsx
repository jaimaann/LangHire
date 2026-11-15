/**
 * HistoryTab: needs_input / skipped rows, the per-job "Details" panel and
 * the live log + LLM cost driven by SSE events.
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor, within, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import HistoryTab from "./HistoryTab";
import { getApplyStatus, getJobs, getMetricRuns, getSettings, getApplications, subscribeEvents } from "../../lib/api";
import type { Job, RunEvent } from "../../lib/types";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (k: string, o?: Record<string, unknown>) => (o && typeof o === "object" && !("defaultValue" in o) ? `${k}:${JSON.stringify(o)}` : k),
    i18n: { changeLanguage: vi.fn() },
  }),
}));

vi.mock("../../lib/analytics", () => ({ trackEvent: vi.fn() }));

vi.mock("../../lib/api", () => ({
  subscribeEvents: vi.fn(() => () => {}),
  getApplications: vi.fn(),
  openLocalFile: vi.fn(),
  stopApplying: vi.fn(),
  getApplyStatus: vi.fn(),
  getJobs: vi.fn(),
  getMetricRuns: vi.fn(),
  getSettings: vi.fn(),
  exportJobsCsv: vi.fn(),
}));

const base = { company: "Co", location: "Remote", easy_apply: false };
const applied: Job = { ...base, url: "https://j/applied", title: "Applied Job", status: "applied", applied_at: "2026-11-10T00:00:00Z" };
const needsInput: Job = {
  ...base,
  url: "https://j/needs",
  title: "Question Job",
  status: "needs_input",
  error: "Needs your answer: Do you have a driving licence?",
  applied_at: "2026-11-12T00:00:00Z",
};
const skipped: Job = { ...base, url: "https://j/skipped", title: "Skipped Job", status: "skipped", applied_at: "2026-11-11T00:00:00Z" };

let emit: (e: RunEvent) => void = () => {};
const ev = (over: Partial<RunEvent>): RunEvent => ({
  id: 1, run_id: "r", kind: "apply", type: "log", level: "info", message: "", data: {}, ...over,
});

describe("HistoryTab details and new statuses", () => {
  beforeEach(() => {
    vi.mocked(getApplyStatus).mockResolvedValue({ running: false, log: [], error: null, finished_at: null } as never);
    vi.mocked(getJobs).mockImplementation(async (params?: { status?: string }) => {
      const byStatus: Record<string, Job[]> = { applied: [applied], needs_input: [needsInput], skipped: [skipped] };
      return structuredClone(byStatus[params?.status || ""] || []) as never;
    });
    vi.mocked(getMetricRuns).mockResolvedValue([] as never);
    vi.mocked(getSettings).mockResolvedValue({ resume_path: "" } as never);
    vi.mocked(getApplications).mockResolvedValue([
      {
        outcome: "submitted", reason: null, confirmation: null, answers: [], missing_info: [],
        resume_path: "/r.pdf", screenshot_path: "/s.png", cost_usd: 0.02, steps: 3, ats: "lever",
        prompt_tokens: 12000, cached_tokens: 9000, completion_tokens: 600, llm_model: "glm-5.3-flash",
        created_at: "2026-11-10T00:00:00Z",
      },
    ] as never);
    vi.mocked(subscribeEvents).mockImplementation((cb) => {
      emit = cb;
      return () => {};
    });
  });

  it("lists needs_input and skipped jobs with their badges and an answer link", async () => {
    render(<HistoryTab onJobsChanged={vi.fn()} />);
    await screen.findByText("Question Job");
    expect(getJobs).toHaveBeenCalledWith({ status: "needs_input" });
    expect(getJobs).toHaveBeenCalledWith({ status: "skipped" });
    expect(screen.getByTestId("status-badge-needs_input")).toHaveTextContent("status.needsInput");
    expect(screen.getByTestId("status-badge-skipped")).toHaveTextContent("status.skipped");
    expect(screen.getByText(/driving licence/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "needsInput.answerAndRetry" })).toHaveAttribute("href", "#/qa");
  });

  it("opens the application details panel for a job", async () => {
    const user = userEvent.setup();
    render(<HistoryTab onJobsChanged={vi.fn()} />);
    const title = await screen.findByText("Applied Job");
    const row = title.closest("div.flex.items-center") as HTMLElement;
    await user.click(within(row.parentElement as HTMLElement).getByRole("button", { name: /details.button/ }));
    const dialog = await screen.findByRole("dialog");
    await waitFor(() => expect(getApplications).toHaveBeenCalledWith({ jobUrl: "https://j/applied", limit: 1 }));
    expect(await within(dialog).findByText("$0.0200")).toBeInTheDocument();
    expect(within(dialog).getByText(/details\.tokens.*"cached":"9,000".*glm-5\.3-flash/)).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "details.close" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("appends live log lines and shows the running cost from SSE events", async () => {
    render(<HistoryTab onJobsChanged={vi.fn()} />);
    await screen.findByText("Applied Job");

    act(() => emit(ev({ type: "run_started", message: "Starting all apply" })));
    act(() => emit(ev({ type: "job_started", message: "🚀 Starting: Applied Job" })));
    act(() => emit(ev({ type: "cost", message: "💰 cost", data: { cost_usd: 0.1234 } })));
    act(() => emit(ev({ kind: "collect", type: "log", message: "collector noise" })));

    expect(await screen.findByText("🚀 Starting: Applied Job")).toBeInTheDocument();
    expect(screen.getByText("Starting all apply")).toBeInTheDocument();
    expect(screen.queryByText("collector noise")).not.toBeInTheDocument();
    expect(screen.getByTestId("run-cost")).toHaveTextContent('log.cost:{"cost":"0.123"}');
  });
});
