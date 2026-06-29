import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import HistoryTab from "./HistoryTab";
import {
  stopApplying,
  getApplyStatus,
  getJobs,
  getMetricRuns,
  getSettings,
} from "../../lib/api";

// i18n: identity translator so assertions can use raw keys.
vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (k: string) => k, i18n: { changeLanguage: vi.fn() } }),
}));

vi.mock("../../lib/analytics", () => ({ trackEvent: vi.fn() }));

vi.mock("../../lib/api", () => ({
  stopApplying: vi.fn(),
  getApplyStatus: vi.fn(),
  getJobs: vi.fn(),
  getMetricRuns: vi.fn(),
  getSettings: vi.fn(),
}));

const mockStopApplying = vi.mocked(stopApplying);
const mockGetApplyStatus = vi.mocked(getApplyStatus);
const mockGetJobs = vi.mocked(getJobs);
const mockGetMetricRuns = vi.mocked(getMetricRuns);
const mockGetSettings = vi.mocked(getSettings);

const idleApply = { running: false, mode: null, workers: 0, log: [], error: null, finished_at: null };

const appliedJob = {
  url: "https://job.example.com/applied",
  title: "Senior Engineer",
  company: "Acme",
  location: "Remote",
  easy_apply: true,
  status: "applied" as const,
  applied_at: "2026-06-01T10:00:00Z",
  collected_at: "2026-05-31T10:00:00Z",
};

const failedJob = {
  url: "https://job.example.com/failed",
  title: "Staff Engineer",
  company: "Globex",
  location: "NYC",
  easy_apply: false,
  status: "failed" as const,
  applied_at: "2026-06-02T10:00:00Z",
  error: "Captcha blocked",
};

const metric = {
  id: 1,
  job_url: "https://job.example.com/applied",
  job_title: "Senior Engineer",
  company: "Acme",
  website_domain: "example.com",
  ats_platform: null,
  success: true,
  error_message: null,
  started_at: "2026-06-01T10:00:00Z",
  finished_at: "2026-06-01T10:02:00Z",
  duration_seconds: 125,
  step_count: 12,
  memories_injected: 4,
  memories_extracted: 2,
  cost_usd: 0.0123,
  created_at: "2026-06-01T10:02:00Z",
};

describe("HistoryTab", () => {
  let onJobsChanged: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    onJobsChanged = vi.fn();
    mockGetApplyStatus.mockResolvedValue(structuredClone(idleApply) as never);
    mockGetJobs.mockImplementation(async (params?: { status?: string }) => {
      if (params?.status === "applied") return [structuredClone(appliedJob)] as never;
      if (params?.status === "failed") return [structuredClone(failedJob)] as never;
      return [] as never;
    });
    mockGetMetricRuns.mockResolvedValue([structuredClone(metric)] as never);
    mockGetSettings.mockResolvedValue({ resume_path: "/r.pdf" } as never);
    mockStopApplying.mockResolvedValue({ success: true } as never);
  });

  it("shows a spinner then renders the applied jobs list", async () => {
    render(<HistoryTab onJobsChanged={onJobsChanged} />);
    expect(await screen.findByText("Senior Engineer")).toBeInTheDocument();
    expect(screen.getByText("Staff Engineer")).toBeInTheDocument();
    // Both applied + failed jobs counted.
    expect(screen.getByText("(2)")).toBeInTheDocument();
  });

  it("renders the empty state when there are no applied/failed jobs", async () => {
    mockGetJobs.mockResolvedValue([] as never);
    render(<HistoryTab onJobsChanged={onJobsChanged} />);
    expect(
      await screen.findByText("No applications yet. Start applying to see results here."),
    ).toBeInTheDocument();
  });

  it("expands a job row to show metrics detail", async () => {
    const user = userEvent.setup();
    render(<HistoryTab onJobsChanged={onJobsChanged} />);
    const row = await screen.findByText("Senior Engineer");

    await user.click(row);
    // Metric fields appear after expanding.
    expect(await screen.findByText("Memories Injected")).toBeInTheDocument();
    expect(screen.getByText("Steps (LLM Calls)")).toBeInTheDocument();
    expect(screen.getByText("$0.0123")).toBeInTheDocument();
  });

  it("shows the failed-job error message in the expanded detail", async () => {
    const user = userEvent.setup();
    render(<HistoryTab onJobsChanged={onJobsChanged} />);
    const row = await screen.findByText("Staff Engineer");

    await user.click(row);
    expect(await screen.findByText("Captcha blocked")).toBeInTheDocument();
  });

  it("renders the live log and a stop button when applying is running", async () => {
    mockGetApplyStatus.mockResolvedValue({
      ...idleApply,
      running: true,
      log: ["Applying to job..."],
    } as never);
    const user = userEvent.setup();
    render(<HistoryTab onJobsChanged={onJobsChanged} />);

    expect(await screen.findByText("Applying to job...")).toBeInTheDocument();
    const stopBtn = screen.getByRole("button", { name: /controls\.stop/ });
    await user.click(stopBtn);
    expect(mockStopApplying).toHaveBeenCalled();
  });

  it("does not crash when loadAppliedJobs rejects", async () => {
    mockGetJobs.mockRejectedValue(new Error("db down"));
    render(<HistoryTab onJobsChanged={onJobsChanged} />);
    // Falls through to the empty-state card.
    await waitFor(() => expect(mockGetJobs).toHaveBeenCalled());
    expect(
      await screen.findByText("No applications yet. Start applying to see results here."),
    ).toBeInTheDocument();
  });
});
