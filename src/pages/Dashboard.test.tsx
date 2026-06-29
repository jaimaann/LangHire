import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import Dashboard from "./Dashboard";
import {
  getDashboardData,
  checkHealth,
  getSetupStatus,
  getChromiumStatus,
  getQAStats,
} from "../lib/api";
import { trackEvent } from "../lib/analytics";

const navigateMock = vi.fn();

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (k: string, o?: Record<string, unknown>) =>
      o ? `${k}:${JSON.stringify(o)}` : k,
    i18n: { changeLanguage: vi.fn() },
  }),
}));

vi.mock("react-router-dom", async (orig) => {
  const actual = await orig<typeof import("react-router-dom")>();
  return { ...actual, useNavigate: () => navigateMock };
});

vi.mock("../lib/analytics", () => ({ trackEvent: vi.fn() }));
vi.mock("../lib/perf", () => ({
  markStart: vi.fn(),
  measureAndTrack: vi.fn(),
}));

vi.mock("../lib/api", () => ({
  getDashboardData: vi.fn(),
  checkHealth: vi.fn(),
  getSetupStatus: vi.fn(),
  getChromiumStatus: vi.fn(),
  getQAStats: vi.fn(),
}));

const mockGetDashboardData = vi.mocked(getDashboardData);
const mockCheckHealth = vi.mocked(checkHealth);
const mockGetSetupStatus = vi.mocked(getSetupStatus);
const mockGetChromiumStatus = vi.mocked(getChromiumStatus);
const mockGetQAStats = vi.mocked(getQAStats);
const mockTrackEvent = vi.mocked(trackEvent);

const dashboardData = {
  jobs: { total: 10, pending: 3, applied: 6, failed: 1, blocked: 0, in_progress: 0 },
  memory: { total_memories: 42, unique_domains: 5, by_category: {} },
};

const setupIncomplete = {
  profile: true,
  llm: false,
  resume: false,
  chromium: true,
  linkedin: true,
  gmail: true,
  onboarding_completed: false,
  all_required_done: false,
};

function renderDashboard() {
  return render(
    <MemoryRouter>
      <Dashboard />
    </MemoryRouter>,
  );
}

describe("Dashboard page", () => {
  beforeEach(() => {
    mockCheckHealth.mockResolvedValue({} as never);
    mockGetDashboardData.mockResolvedValue(dashboardData as never);
    mockGetSetupStatus.mockResolvedValue(setupIncomplete as never);
    mockGetQAStats.mockResolvedValue({ total: 7, answered: 4, unanswered: 3 } as never);
    mockGetChromiumStatus.mockResolvedValue({ state: "ready", message: "" } as never);
  });

  it("renders the loading spinner header before data resolves", () => {
    // Keep the dashboard fetch pending so we observe the loading branch.
    mockGetDashboardData.mockReturnValue(new Promise(() => {}) as never);
    renderDashboard();
    expect(screen.getByText("title")).toBeInTheDocument();
    // The stats grid / quick actions only show after loading completes.
    expect(screen.queryByText("quickActions.title")).not.toBeInTheDocument();
  });

  it("renders stat cards computed from dashboard data after load", async () => {
    renderDashboard();
    // successRate = round(6/10*100) = 60%
    expect(await screen.findByText("60%")).toBeInTheDocument();
    expect(screen.getByText("10")).toBeInTheDocument(); // total jobs
    expect(screen.getByText("42")).toBeInTheDocument(); // memories
    expect(screen.getByText("cards.applied")).toBeInTheDocument();
  });

  it("tracks a dashboard_stats analytics event with aggregated counts", async () => {
    renderDashboard();
    await waitFor(() =>
      expect(mockTrackEvent).toHaveBeenCalledWith(
        "dashboard_stats",
        expect.objectContaining({
          jobs_collected: 10,
          jobs_applied: 6,
          memories_created: 42,
          questions_extracted: 7,
        }),
      ),
    );
  });

  it("navigates from quick action buttons", async () => {
    const user = userEvent.setup();
    renderDashboard();
    await screen.findByText("quickActions.title");

    await user.click(screen.getByRole("button", { name: /quickActions\.collectJobs/ }));
    expect(navigateMock).toHaveBeenCalledWith("/jobs");

    await user.click(screen.getByRole("button", { name: /quickActions\.startApplying/ }));
    expect(navigateMock).toHaveBeenCalledWith("/apply");
  });

  it("renders the setup checklist with a 'set up' link for incomplete required steps", async () => {
    const user = userEvent.setup();
    renderDashboard();
    await screen.findByText("setup.gettingStarted");

    // LLM not done → its set-up button navigates to /llm.
    const setUpButtons = await screen.findAllByRole("button", { name: "setup.setUp" });
    expect(setUpButtons.length).toBeGreaterThan(0);
    await user.click(setUpButtons[0]);
    expect(navigateMock).toHaveBeenCalledWith("/llm");
  });

  it("shows the all-done state when all required steps are complete", async () => {
    mockGetSetupStatus.mockResolvedValue({
      ...setupIncomplete,
      llm: true,
      resume: true,
      all_required_done: true,
    } as never);
    renderDashboard();
    expect(await screen.findByText("setup.allDone")).toBeInTheDocument();
    expect(screen.getByText("setup.complete")).toBeInTheDocument();
  });

  it("does not show the backend-not-connected banner when health is OK", async () => {
    renderDashboard();
    await screen.findByText("quickActions.title");
    // Healthy backend → the connection-error banner stays hidden.
    expect(screen.queryByText(/Backend not connected/i)).not.toBeInTheDocument();
  });

  it("renders the Chromium install progress card while installing", async () => {
    mockGetChromiumStatus.mockResolvedValue({
      state: "installing",
      message: "Downloading 45%",
    } as never);
    renderDashboard();
    expect(await screen.findByText("Downloading 45%")).toBeInTheDocument();
    expect(screen.getByText("chromium.installing")).toBeInTheDocument();
  });

  it("renders gracefully when getDashboardData rejects (defaults to zeros)", async () => {
    mockGetDashboardData.mockRejectedValue(new Error("500"));
    renderDashboard();
    // Loading completes and quick actions render even though dashboard data failed.
    expect(await screen.findByText("quickActions.title")).toBeInTheDocument();
    // Stat cards still render their labels with zeroed values.
    expect(screen.getByText("cards.successRate")).toBeInTheDocument();
    expect(screen.getAllByText("0%").length).toBeGreaterThan(0); // successRate with no jobs
  });
});
