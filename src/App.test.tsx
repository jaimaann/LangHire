import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import App from "./App";
import { getSetupStatus, getSettings } from "./lib/api";
import { initAnalytics, trackPageView } from "./lib/analytics";

// ── i18n / direction hook ────────────────────────────────────────────────────
vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (k: string) => k,
    i18n: { changeLanguage: vi.fn(), dir: () => "ltr", language: "en" },
  }),
}));
vi.mock("./i18n/useDirection", () => ({ useDirection: vi.fn() }));

// ── perf / analytics ─────────────────────────────────────────────────────────
vi.mock("./lib/perf", () => ({
  markStart: vi.fn(),
  markEnd: vi.fn(),
  trackTiming: vi.fn(),
  measureAndTrack: vi.fn(),
  getTimeSinceAppStart: vi.fn(() => 0),
  trackStartupComplete: vi.fn(),
}));
vi.mock("./lib/analytics", () => ({
  initAnalytics: vi.fn(),
  trackPageView: vi.fn(),
  trackEvent: vi.fn(),
  setTelemetryEnabled: vi.fn(),
  trackException: vi.fn(),
}));

// ── api ──────────────────────────────────────────────────────────────────────
vi.mock("./lib/api", () => ({
  getSetupStatus: vi.fn(),
  getSettings: vi.fn(),
}));

// ── Heavy children: stub Sidebar + SetupWizard, and lazy pages ────────────────
vi.mock("./components/layout/Sidebar", () => ({
  default: () => <nav data-testid="sidebar" />,
}));
vi.mock("./components/SetupWizard", () => ({
  default: ({ onClose }: { onClose: () => void }) => (
    <div data-testid="setup-wizard">
      <button onClick={onClose}>close-wizard</button>
    </div>
  ),
}));
vi.mock("./pages/Dashboard", () => ({ default: () => <div>Dashboard Page</div> }));
vi.mock("./pages/Profile", () => ({ default: () => <div>Profile Page</div> }));
vi.mock("./pages/LLMSettings", () => ({ default: () => <div>LLM Page</div> }));
vi.mock("./pages/Jobs", () => ({ default: () => <div>Jobs Page</div> }));
vi.mock("./pages/Memory", () => ({ default: () => <div>Memory Page</div> }));
vi.mock("./pages/Settings", () => ({ default: () => <div>Settings Page</div> }));
vi.mock("./pages/Logs", () => ({ default: () => <div>Logs Page</div> }));
vi.mock("./pages/Guide", () => ({ default: () => <div>Guide Page</div> }));
vi.mock("./pages/Feedback", () => ({ default: () => <div>Feedback Page</div> }));
vi.mock("./pages/QA", () => ({ default: () => <div>QA Page</div> }));

const mockGetSetupStatus = vi.mocked(getSetupStatus);
const mockGetSettings = vi.mocked(getSettings);
const mockInitAnalytics = vi.mocked(initAnalytics);
const mockTrackPageView = vi.mocked(trackPageView);

const completedStatus = {
  profile: true,
  llm: true,
  resume: true,
  chromium: true,
  linkedin: true,
  gmail: true,
  onboarding_completed: true,
  all_required_done: true,
};

function renderApp(initialEntries: string[] = ["/"]) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <App />
    </MemoryRouter>,
  );
}

describe("App", () => {
  beforeEach(() => {
    mockGetSettings.mockResolvedValue({ telemetry_enabled: true } as never);
    mockGetSetupStatus.mockResolvedValue(structuredClone(completedStatus) as never);
  });

  it("renders the sidebar shell and the default Dashboard route", async () => {
    renderApp(["/"]);
    expect(screen.getByTestId("sidebar")).toBeInTheDocument();
    expect(await screen.findByText("Dashboard Page")).toBeInTheDocument();
  });

  it("renders the route matching the current location (lazy-loaded)", async () => {
    renderApp(["/jobs"]);
    expect(await screen.findByText("Jobs Page")).toBeInTheDocument();
  });

  it("redirects /apply to /jobs", async () => {
    renderApp(["/apply"]);
    expect(await screen.findByText("Jobs Page")).toBeInTheDocument();
  });

  it("initializes analytics from settings on mount", async () => {
    renderApp(["/"]);
    await waitFor(() => expect(mockGetSettings).toHaveBeenCalled());
    await waitFor(() => expect(mockInitAnalytics).toHaveBeenCalledWith(true));
  });

  it("falls back to initAnalytics(true) when getSettings rejects", async () => {
    mockGetSettings.mockRejectedValue(new Error("offline"));
    renderApp(["/"]);
    await waitFor(() => expect(mockInitAnalytics).toHaveBeenCalledWith(true));
  });

  it("tracks a page view for the current path", async () => {
    renderApp(["/profile"]);
    await waitFor(() => expect(mockTrackPageView).toHaveBeenCalledWith("/profile"));
  });

  it("does NOT show the setup wizard when onboarding is completed", async () => {
    renderApp(["/"]);
    await screen.findByText("Dashboard Page");
    // Give the setup-status check a chance to run.
    await waitFor(() => expect(mockGetSetupStatus).toHaveBeenCalled());
    expect(screen.queryByTestId("setup-wizard")).not.toBeInTheDocument();
  });

  it("shows the setup wizard when onboarding is NOT completed", async () => {
    mockGetSetupStatus.mockResolvedValue({
      ...completedStatus,
      onboarding_completed: false,
    } as never);
    renderApp(["/"]);
    expect(await screen.findByTestId("setup-wizard")).toBeInTheDocument();
  });

  it("hides the wizard after onClose and reveals the resume button", async () => {
    mockGetSetupStatus.mockResolvedValue({
      ...completedStatus,
      onboarding_completed: false,
    } as never);
    const user = userEvent.setup();
    renderApp(["/"]);

    await screen.findByTestId("setup-wizard");
    await user.click(screen.getByText("close-wizard"));
    // handleWizardClose resets wizardPaused=false, so no resume button.
    expect(screen.queryByTestId("setup-wizard")).not.toBeInTheDocument();
  });

  it("opens the wizard on the 'open-setup-wizard' window event", async () => {
    renderApp(["/"]);
    await screen.findByText("Dashboard Page");
    await waitFor(() => expect(mockGetSetupStatus).toHaveBeenCalled());
    expect(screen.queryByTestId("setup-wizard")).not.toBeInTheDocument();

    window.dispatchEvent(new Event("open-setup-wizard"));
    expect(await screen.findByTestId("setup-wizard")).toBeInTheDocument();
  });

  it("does not crash and still shows the shell when getSetupStatus keeps failing", async () => {
    mockGetSetupStatus.mockRejectedValue(new Error("backend down"));
    renderApp(["/"]);
    expect(screen.getByTestId("sidebar")).toBeInTheDocument();
    expect(await screen.findByText("Dashboard Page")).toBeInTheDocument();
    // Wizard never shows because status was never obtained.
    expect(screen.queryByTestId("setup-wizard")).not.toBeInTheDocument();
  });
});
