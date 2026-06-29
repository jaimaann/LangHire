import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import CollectTab from "./CollectTab";
import {
  startJobCollection,
  stopJobCollection,
  getCollectionStatus,
  getPlugins,
  getProfile,
  addJob,
} from "../../lib/api";
import { trackEvent } from "../../lib/analytics";

// i18n: identity translator so assertions can use raw keys.
vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (k: string) => k, i18n: { changeLanguage: vi.fn() } }),
}));

vi.mock("../../lib/analytics", () => ({ trackEvent: vi.fn() }));

vi.mock("../../lib/api", () => ({
  startJobCollection: vi.fn(),
  stopJobCollection: vi.fn(),
  getCollectionStatus: vi.fn(),
  getPlugins: vi.fn(),
  getProfile: vi.fn(),
  addJob: vi.fn(),
}));

const mockStart = vi.mocked(startJobCollection);
const mockStop = vi.mocked(stopJobCollection);
const mockStatus = vi.mocked(getCollectionStatus);
const mockGetPlugins = vi.mocked(getPlugins);
const mockGetProfile = vi.mocked(getProfile);
const mockAddJob = vi.mocked(addJob);
const mockTrackEvent = vi.mocked(trackEvent);

const idleStatus = {
  running: false,
  title: null,
  log: [],
  collected: 0,
  max_jobs: 0,
  error: null,
  finished_at: null,
};

const linkedinPlugin = {
  name: "linkedin",
  display_name: "LinkedIn",
  version: "1.0.0",
  author: "core",
  description: "LinkedIn",
  countries: ["US"],
  website: "x",
  requires_login: true,
  login_url: "x",
  is_builtin: true,
  enabled: true,
  filters: [],
};
const indeedPlugin = { ...linkedinPlugin, name: "indeed", display_name: "Indeed" };

describe("CollectTab", () => {
  let onJobsChanged: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.stubGlobal("alert", vi.fn());
    onJobsChanged = vi.fn();
    mockGetProfile.mockResolvedValue({ country: "US" } as never);
    mockGetPlugins.mockResolvedValue({
      success: true,
      plugins: [structuredClone(linkedinPlugin), structuredClone(indeedPlugin)],
    } as never);
    mockStatus.mockResolvedValue(structuredClone(idleStatus) as never);
    mockStart.mockResolvedValue({ success: true, message: "started" } as never);
    mockStop.mockResolvedValue({ success: true } as never);
    mockAddJob.mockResolvedValue({ success: true } as never);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders the collector panel and loads source plugins", async () => {
    render(<CollectTab onJobsChanged={onJobsChanged} />);
    expect(screen.getByText("collector.title")).toBeInTheDocument();
    await waitFor(() => expect(mockGetProfile).toHaveBeenCalled());
    // >1 source → source selector buttons render.
    expect(await screen.findByRole("button", { name: "LinkedIn" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Indeed" })).toBeInTheDocument();
  });

  it("opens the confirm dialog and starts collection on confirm", async () => {
    const user = userEvent.setup();
    render(<CollectTab onJobsChanged={onJobsChanged} />);
    await screen.findByRole("button", { name: "LinkedIn" });

    await user.type(screen.getByPlaceholderText("collector.jobTitlePlaceholder"), "Engineer");
    await user.click(screen.getByRole("button", { name: /collector\.start/ }));

    // AutomationDialog appears.
    const confirm = await screen.findByRole("button", { name: "Got it, Start" });
    await user.click(confirm);

    await waitFor(() =>
      expect(mockStart).toHaveBeenCalledWith("Engineer", 20, "linkedin", {}),
    );
    expect(mockTrackEvent).toHaveBeenCalledWith(
      "collection_started",
      expect.objectContaining({ source: "linkedin" }),
    );
  });

  it("alerts when starting collection rejects", async () => {
    mockStart.mockRejectedValue(new Error("no login"));
    const user = userEvent.setup();
    render(<CollectTab onJobsChanged={onJobsChanged} />);
    await screen.findByRole("button", { name: "LinkedIn" });

    await user.click(screen.getByRole("button", { name: /collector\.start/ }));
    await user.click(await screen.findByRole("button", { name: "Got it, Start" }));

    await waitFor(() => expect(window.alert).toHaveBeenCalledWith("no login"));
  });

  it("switches the active source", async () => {
    const user = userEvent.setup();
    render(<CollectTab onJobsChanged={onJobsChanged} />);
    const indeed = await screen.findByRole("button", { name: "Indeed" });
    await user.click(indeed);
    await waitFor(() => expect(indeed.className).toContain("border-primary"));
  });

  it("resumes display when a collection is already running on mount", async () => {
    mockStatus.mockResolvedValue({
      ...idleStatus,
      running: true,
      collected: 5,
      log: ["line 1"],
    } as never);
    render(<CollectTab onJobsChanged={onJobsChanged} />);
    // Stop button (destructive) shows when running.
    expect(await screen.findByRole("button", { name: /collector\.stop/ })).toBeInTheDocument();
    expect(screen.getByText("line 1")).toBeInTheDocument();
  });

  it("stops a running collection", async () => {
    mockStatus.mockResolvedValue({ ...idleStatus, running: true } as never);
    const user = userEvent.setup();
    render(<CollectTab onJobsChanged={onJobsChanged} />);

    await user.click(await screen.findByRole("button", { name: /collector\.stop/ }));
    expect(mockStop).toHaveBeenCalled();
  });

  it("adds a job manually via the add-job form", async () => {
    const user = userEvent.setup();
    render(<CollectTab onJobsChanged={onJobsChanged} />);
    await screen.findByRole("button", { name: "LinkedIn" });

    await user.click(screen.getByRole("button", { name: /Add Job/ }));
    await user.type(
      screen.getByPlaceholderText("Job URL (required)"),
      "https://jobs.example.com/1",
    );
    await user.type(screen.getByPlaceholderText("Job title (optional)"), "Dev");

    // Submit the add-job form.
    const addButtons = screen.getAllByRole("button", { name: /Add Job/ });
    await user.click(addButtons[addButtons.length - 1]);

    await waitFor(() =>
      expect(mockAddJob).toHaveBeenCalledWith("https://jobs.example.com/1", "Dev", undefined),
    );
    expect(onJobsChanged).toHaveBeenCalled();
  });

  it("falls back to no-country plugins when getProfile rejects", async () => {
    mockGetProfile.mockRejectedValue(new Error("no profile"));
    render(<CollectTab onJobsChanged={onJobsChanged} />);
    await waitFor(() => expect(mockGetPlugins).toHaveBeenCalled());
    expect(await screen.findByRole("button", { name: "LinkedIn" })).toBeInTheDocument();
  });
});
