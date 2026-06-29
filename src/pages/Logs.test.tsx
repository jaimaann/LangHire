import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Logs from "./Logs";
import { getRunsWithLogs, getRunLogs } from "../lib/api";
import type { RunWithLogs, RunLog } from "../lib/types";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (k: string, o?: Record<string, unknown>) =>
      o ? `${k}:${JSON.stringify(o)}` : k,
    i18n: { changeLanguage: vi.fn() },
  }),
}));

vi.mock("../lib/api", () => ({
  getRunsWithLogs: vi.fn(),
  getRunLogs: vi.fn(),
}));

const mockGetRunsWithLogs = vi.mocked(getRunsWithLogs);
const mockGetRunLogs = vi.mocked(getRunLogs);

function makeRun(over: Partial<RunWithLogs> = {}): RunWithLogs {
  return {
    id: 1,
    run_id: "run-abc",
    job_url: "https://job/1",
    job_title: "Backend Engineer",
    company: "Acme",
    website_domain: "greenhouse.io",
    ats_platform: "Greenhouse",
    success: true,
    error_message: null,
    started_at: "2026-01-01T00:00:00Z",
    finished_at: "2026-01-01T00:05:00Z",
    duration_seconds: 300,
    step_count: 12,
    memories_injected: 3,
    memories_extracted: 2,
    cost_usd: 0.01,
    created_at: "2026-01-01T00:00:00Z",
    log_count: 8,
    ...over,
  };
}

const runs: RunWithLogs[] = [
  makeRun({ id: 1, run_id: "run-abc", job_title: "Backend Engineer", success: true }),
  makeRun({
    id: 2,
    run_id: "run-def",
    job_title: "Frontend Engineer",
    company: "Globex",
    success: false,
  }),
];

const logs: RunLog[] = [
  {
    id: 100,
    run_id: "run-abc",
    job_url: "https://job/1",
    timestamp: "2026-01-01T00:01:00Z",
    level: "info",
    message: "✅ Applied successfully",
    created_at: "2026-01-01T00:01:00Z",
  },
  {
    id: 101,
    run_id: "run-abc",
    job_url: "https://job/1",
    timestamp: "2026-01-01T00:02:00Z",
    level: "info",
    message: "📍 Navigating to form",
    created_at: "2026-01-01T00:02:00Z",
  },
];

describe("Logs page", () => {
  beforeEach(() => {
    mockGetRunsWithLogs.mockResolvedValue(runs as never);
    mockGetRunLogs.mockResolvedValue(logs as never);
  });

  it("shows the loading spinner before runs resolve", () => {
    mockGetRunsWithLogs.mockReturnValue(new Promise(() => {}) as never);
    render(<Logs />);
    expect(screen.queryByText("title")).not.toBeInTheDocument();
  });

  it("renders the run list after load", async () => {
    render(<Logs />);
    expect(await screen.findByText("Backend Engineer")).toBeInTheDocument();
    expect(screen.getByText("Frontend Engineer")).toBeInTheDocument();
    // Company + domain detail line.
    expect(screen.getByText(/Acme/)).toBeInTheDocument();
  });

  it("shows the select-a-run prompt before any run is chosen", async () => {
    render(<Logs />);
    await screen.findByText("Backend Engineer");
    expect(screen.getByText("detail.selectFromPanel")).toBeInTheDocument();
  });

  it("selecting a run loads and renders its log lines", async () => {
    const user = userEvent.setup();
    render(<Logs />);
    await screen.findByText("Backend Engineer");

    await user.click(screen.getByText("Backend Engineer"));

    expect(await screen.findByText("✅ Applied successfully")).toBeInTheDocument();
    expect(screen.getByText("📍 Navigating to form")).toBeInTheDocument();
    expect(mockGetRunLogs).toHaveBeenCalledWith("run-abc");
  });

  it("renders a no-logs message when the selected run has no logs", async () => {
    mockGetRunLogs.mockResolvedValue([] as never);
    const user = userEvent.setup();
    render(<Logs />);
    await screen.findByText("Backend Engineer");

    await user.click(screen.getByText("Backend Engineer"));

    expect(await screen.findByText("detail.noLogs")).toBeInTheDocument();
  });

  it("refresh re-fetches the run list", async () => {
    const user = userEvent.setup();
    render(<Logs />);
    await screen.findByText("Backend Engineer");

    await user.click(screen.getByRole("button", { name: /refresh/ }));

    await waitFor(() => expect(mockGetRunsWithLogs).toHaveBeenCalledTimes(2));
  });

  it("renders the empty state when there are no runs", async () => {
    mockGetRunsWithLogs.mockResolvedValue([] as never);
    render(<Logs />);
    expect(await screen.findByText("runs.empty")).toBeInTheDocument();
  });

  it("renders gracefully when getRunsWithLogs rejects (empty list)", async () => {
    mockGetRunsWithLogs.mockRejectedValue(new Error("boom"));
    render(<Logs />);
    // Loading resolves via finally; empty state shown.
    expect(await screen.findByText("runs.empty")).toBeInTheDocument();
  });

  it("keeps the run list usable when getRunLogs rejects (no logs shown)", async () => {
    mockGetRunLogs.mockRejectedValue(new Error("boom"));
    const user = userEvent.setup();
    render(<Logs />);
    await screen.findByText("Backend Engineer");

    await user.click(screen.getByText("Backend Engineer"));

    expect(await screen.findByText("detail.noLogs")).toBeInTheDocument();
  });
});
