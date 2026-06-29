import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import Analytics from "./Analytics";
import { getJobs, getMetricRuns } from "../lib/api";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (_k: string, d?: string) => d ?? _k, i18n: { changeLanguage: vi.fn() } }),
}));

vi.mock("../lib/api", () => ({
  getJobs: vi.fn(),
  getMetricRuns: vi.fn(),
}));

const mockGetJobs = vi.mocked(getJobs);
const mockGetMetricRuns = vi.mocked(getMetricRuns);

const jobs = [
  { url: "u1", title: "Eng", company: "Acme", location: "Remote", easy_apply: true, status: "applied", source: "linkedin", applied_at: "2026-06-20T10:00:00Z", collected_at: "2026-06-19T10:00:00Z" },
  { url: "u2", title: "Eng2", company: "Acme", location: "NYC", easy_apply: false, status: "applied", source: "indeed", applied_at: "2026-06-21T10:00:00Z", collected_at: "2026-06-20T10:00:00Z" },
  { url: "u3", title: "Eng3", company: "Globex", location: "LA", easy_apply: true, status: "failed", source: "linkedin", applied_at: "2026-06-22T10:00:00Z", collected_at: "2026-06-21T10:00:00Z" },
  { url: "u4", title: "Eng4", company: "Initech", location: "SF", easy_apply: true, status: "pending", source: "indeed", collected_at: "2026-06-22T10:00:00Z" },
];

const runs = [
  { id: 1, job_url: "u1", job_title: "Eng", company: "Acme", website_domain: "acme.com", ats_platform: null, success: true, error_message: null, started_at: "2026-06-20T10:00:00Z", finished_at: "2026-06-20T10:02:00Z", duration_seconds: 120, step_count: 10, memories_injected: 1, memories_extracted: 1, cost_usd: 0.01, created_at: "2026-06-20T10:02:00Z" },
];

describe("Analytics", () => {
  beforeEach(() => {
    mockGetJobs.mockResolvedValue(structuredClone(jobs) as never);
    mockGetMetricRuns.mockResolvedValue(structuredClone(runs) as never);
  });

  it("shows a spinner then renders headline stats", async () => {
    render(<Analytics />);
    // 4 total jobs, 2 applied, 1 failed, success rate = 2/(2+1) = 67%
    expect(await screen.findByText("Total jobs")).toBeInTheDocument();
    expect(screen.getByText("Success rate")).toBeInTheDocument();
    expect(screen.getByText("67%")).toBeInTheDocument();
  });

  it("renders source, company, and status breakdowns", async () => {
    render(<Analytics />);
    await screen.findByText("Total jobs");
    expect(screen.getByText("By status")).toBeInTheDocument();
    expect(screen.getByText("By source")).toBeInTheDocument();
    expect(screen.getByText("Top companies")).toBeInTheDocument();
    // Acme appears as a top company (2 jobs)
    expect(screen.getByText("Acme")).toBeInTheDocument();
    // Sources present
    expect(screen.getByText("linkedin")).toBeInTheDocument();
    expect(screen.getByText("indeed")).toBeInTheDocument();
  });

  it("shows an empty state when there are no jobs", async () => {
    mockGetJobs.mockResolvedValue([] as never);
    render(<Analytics />);
    expect(await screen.findByText("No data yet")).toBeInTheDocument();
  });

  it("does not crash when the API rejects", async () => {
    mockGetJobs.mockRejectedValue(new Error("down"));
    mockGetMetricRuns.mockRejectedValue(new Error("down"));
    render(<Analytics />);
    // Falls back to the empty state (no data loaded).
    expect(await screen.findByText("No data yet")).toBeInTheDocument();
  });
});
