import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import SetupWizard from "./SetupWizard";
import {
  getSetupStatus,
  completeOnboarding,
  parseResumeToProfile,
} from "../lib/api";
import { trackEvent } from "../lib/analytics";

// ── Mocks ───────────────────────────────────────────────────────────────────
const mockNavigate = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return { ...actual, useNavigate: () => mockNavigate };
});

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (k: string) => k,
    i18n: { changeLanguage: vi.fn(), dir: () => "ltr", language: "en" },
  }),
}));

vi.mock("../lib/api", () => ({
  getSetupStatus: vi.fn(),
  completeOnboarding: vi.fn(),
  parseResumeToProfile: vi.fn(),
}));

vi.mock("../lib/analytics", () => ({
  trackEvent: vi.fn(),
}));

// Stub the inline child forms — out of scope; keeps the wizard test focused.
vi.mock("./forms/LLMSettingsForm", () => ({
  default: () => <div data-testid="llm-settings-form" />,
}));
vi.mock("./forms/ResumePickerForm", () => ({
  default: () => <div data-testid="resume-picker-form" />,
}));

const mockGetSetupStatus = vi.mocked(getSetupStatus);
const mockCompleteOnboarding = vi.mocked(completeOnboarding);
const mockParseResume = vi.mocked(parseResumeToProfile);
const mockTrackEvent = vi.mocked(trackEvent);

const baseStatus = {
  profile: false,
  llm: false,
  resume: false,
  chromium: false,
  linkedin: false,
  gmail: false,
  onboarding_completed: false,
  all_required_done: false,
};

function renderWizard(props: Partial<React.ComponentProps<typeof SetupWizard>> = {}) {
  const onClose = vi.fn();
  const onNavigateAway = vi.fn();
  render(
    <MemoryRouter>
      <SetupWizard onClose={onClose} onNavigateAway={onNavigateAway} {...props} />
    </MemoryRouter>,
  );
  return { onClose, onNavigateAway };
}

describe("SetupWizard", () => {
  beforeEach(() => {
    mockGetSetupStatus.mockResolvedValue(structuredClone(baseStatus) as never);
    mockCompleteOnboarding.mockResolvedValue({ success: true } as never);
    mockParseResume.mockResolvedValue({ success: true, message: "Filled 12 fields", fields_filled: 12 } as never);
  });

  it("renders the wizard header and the welcome step by default", async () => {
    renderWizard();
    expect(screen.getByRole("heading", { name: "title" })).toBeInTheDocument();
    expect(screen.getByText("welcome.heading")).toBeInTheDocument();
    // Fetches setup status on mount.
    await waitFor(() => expect(mockGetSetupStatus).toHaveBeenCalled());
  });

  it("respects initialStep prop by rendering that step's content", async () => {
    renderWizard({ initialStep: 1 });
    expect(screen.getByText("llmStep.heading")).toBeInTheDocument();
    expect(screen.getByTestId("llm-settings-form")).toBeInTheDocument();
  });

  it("calls onClose when the header X button is clicked", async () => {
    const user = userEvent.setup();
    const { onClose } = renderWizard();
    // The X button is icon-only; it is the first button in the header.
    const buttons = screen.getAllByRole("button");
    await user.click(buttons[0]);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("calls onClose when 'skip for now' is clicked", async () => {
    const user = userEvent.setup();
    const { onClose } = renderWizard();
    await user.click(screen.getByRole("button", { name: "nav.skipForNow" }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("advances through steps with Next and goes back with Back", async () => {
    const user = userEvent.setup();
    renderWizard();
    expect(screen.getByText("welcome.heading")).toBeInTheDocument();

    // Step 0 -> 1
    await user.click(screen.getByRole("button", { name: /nav\.letsGo/ }));
    expect(await screen.findByText("llmStep.heading")).toBeInTheDocument();

    // Step 1 -> 2
    await user.click(screen.getByRole("button", { name: /nav\.next/ }));
    expect(await screen.findByText("resumeStep.heading")).toBeInTheDocument();

    // Back: 2 -> 1
    await user.click(screen.getByRole("button", { name: /nav\.back/ }));
    expect(await screen.findByText("llmStep.heading")).toBeInTheDocument();
  });

  it("refetches setup status on each Next", async () => {
    const user = userEvent.setup();
    renderWizard();
    await waitFor(() => expect(mockGetSetupStatus).toHaveBeenCalledTimes(1));

    await user.click(screen.getByRole("button", { name: /nav\.letsGo/ }));
    await waitFor(() => expect(mockGetSetupStatus).toHaveBeenCalledTimes(2));
  });

  it("shows the auto-fill button only when both resume and llm are ready, and parses on click", async () => {
    mockGetSetupStatus.mockResolvedValue({ ...baseStatus, resume: true, llm: true } as never);
    const user = userEvent.setup();
    renderWizard({ initialStep: 2 });

    const parseBtn = await screen.findByRole("button", { name: /resumeStep\.autoFill\.button/ });
    await user.click(parseBtn);

    await waitFor(() => expect(mockParseResume).toHaveBeenCalled());
    expect(await screen.findByText("Filled 12 fields")).toBeInTheDocument();
  });

  it("shows a prerequisite warning on the resume step when llm/resume are not done", async () => {
    renderWizard({ initialStep: 2 });
    expect(await screen.findByText("resumeStep.prerequisite")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /resumeStep\.autoFill\.button/ })).not.toBeInTheDocument();
  });

  it("surfaces an error message when resume parsing throws", async () => {
    mockGetSetupStatus.mockResolvedValue({ ...baseStatus, resume: true, llm: true } as never);
    mockParseResume.mockRejectedValue(new Error("parse failed"));
    const user = userEvent.setup();
    renderWizard({ initialStep: 2 });

    await user.click(await screen.findByRole("button", { name: /resumeStep\.autoFill\.button/ }));
    expect(await screen.findByText("parse failed")).toBeInTheDocument();
  });

  it("profile step 'go to profile' navigates away and calls onNavigateAway with the step", async () => {
    const user = userEvent.setup();
    const { onNavigateAway } = renderWizard({ initialStep: 3 });

    await user.click(await screen.findByRole("button", { name: /profileStep\.goToProfile/ }));
    expect(onNavigateAway).toHaveBeenCalledWith(3);
    expect(mockNavigate).toHaveBeenCalledWith("/profile");
  });

  it("final step finish completes onboarding, tracks the event, closes, and navigates", async () => {
    const user = userEvent.setup();
    const { onClose } = renderWizard({ initialStep: 4 });

    // The footer finish button.
    await user.click(screen.getByRole("button", { name: /nav\.finishSetup/ }));
    await waitFor(() => expect(mockCompleteOnboarding).toHaveBeenCalled());
    expect(mockTrackEvent).toHaveBeenCalledWith("onboarding_completed");
    expect(onClose).toHaveBeenCalled();
  });

  it("ready step 'collect jobs' finishes and navigates to /jobs", async () => {
    const user = userEvent.setup();
    const { onClose } = renderWizard({ initialStep: 4 });

    await user.click(screen.getByRole("button", { name: /readyStep\.collectJobs/ }));
    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith("/jobs"));
    expect(onClose).toHaveBeenCalled();
  });

  it("reflects done/not-done setup status on the ready step", async () => {
    mockGetSetupStatus.mockResolvedValue({
      ...baseStatus,
      llm: true,
      resume: true,
      profile: false,
      all_required_done: false,
    } as never);
    renderWizard({ initialStep: 4 });

    await waitFor(() => expect(mockGetSetupStatus).toHaveBeenCalled());
    expect(await screen.findByText("readyStep.descriptionIncomplete")).toBeInTheDocument();
    expect(screen.getByText("readyStep.aiProvider")).toBeInTheDocument();
  });
});
