import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Guide from "./Guide";
import { getSetupStatus } from "../lib/api";

// i18n: identity translator so assertions can use raw keys.
vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (k: string) => k, i18n: { changeLanguage: vi.fn() } }),
}));

const mockNavigate = vi.fn();
vi.mock("react-router-dom", () => ({
  useNavigate: () => mockNavigate,
}));

vi.mock("../lib/api", () => ({
  getSetupStatus: vi.fn(),
}));

const mockGetSetupStatus = vi.mocked(getSetupStatus);

const baseStatus = {
  profile: false,
  llm: false,
  resume: false,
  chromium: true,
  linkedin: false,
  gmail: false,
  onboarding_completed: false,
  all_required_done: false,
};

describe("Guide", () => {
  beforeEach(() => {
    mockGetSetupStatus.mockResolvedValue(structuredClone(baseStatus) as never);
  });

  it("renders the header and the how-it-works pipeline", async () => {
    render(<Guide />);
    expect(screen.getByText("title")).toBeInTheDocument();
    expect(screen.getByText("howItWorks.title")).toBeInTheDocument();
    await waitFor(() => expect(mockGetSetupStatus).toHaveBeenCalled());
  });

  it("renders setup checklist steps and shows Set Up for incomplete required steps", async () => {
    render(<Guide />);
    await waitFor(() => expect(mockGetSetupStatus).toHaveBeenCalled());

    expect(screen.getByText("checklist.configureAi")).toBeInTheDocument();
    expect(screen.getByText("checklist.setResume")).toBeInTheDocument();
    expect(screen.getByText("checklist.setupProfile")).toBeInTheDocument();
    // All three incomplete → three "Set Up" buttons.
    const setUpButtons = screen.getAllByRole("button", { name: "checklist.setUp" });
    expect(setUpButtons).toHaveLength(3);
  });

  it("navigates to the step path when Set Up is clicked", async () => {
    const user = userEvent.setup();
    render(<Guide />);
    await waitFor(() => expect(mockGetSetupStatus).toHaveBeenCalled());

    const setUpButtons = screen.getAllByRole("button", { name: "checklist.setUp" });
    await user.click(setUpButtons[0]); // configureAi → /llm
    expect(mockNavigate).toHaveBeenCalledWith("/llm");
  });

  it("shows the all-done banner and no Set Up buttons when all required are complete", async () => {
    mockGetSetupStatus.mockResolvedValue({
      ...baseStatus,
      profile: true,
      llm: true,
      resume: true,
      all_required_done: true,
    } as never);

    render(<Guide />);
    expect(await screen.findByText("checklist.allDone")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "checklist.setUp" })).not.toBeInTheDocument();
  });

  it("refetches status when the refresh button is clicked", async () => {
    const user = userEvent.setup();
    render(<Guide />);
    await waitFor(() => expect(mockGetSetupStatus).toHaveBeenCalledTimes(1));

    await user.click(screen.getByRole("button", { name: "checklist.refreshStatus" }));
    await waitFor(() => expect(mockGetSetupStatus).toHaveBeenCalledTimes(2));
  });

  it("expands an accordion section to reveal its content", async () => {
    const user = userEvent.setup();
    render(<Guide />);
    await waitFor(() => expect(mockGetSetupStatus).toHaveBeenCalled());

    // Accordion content is collapsed by default; expanding reveals nested keys.
    // The "essential" label is a standalone <strong> inside the panel.
    expect(screen.queryByText("sections.profile.essential")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /sections\.profile\.title/ }));
    expect(await screen.findByText("sections.profile.essential")).toBeInTheDocument();
  });

  it("dispatches the open-setup-wizard event from the re-run wizard button", async () => {
    const listener = vi.fn();
    window.addEventListener("open-setup-wizard", listener);
    const user = userEvent.setup();
    render(<Guide />);
    await waitFor(() => expect(mockGetSetupStatus).toHaveBeenCalled());

    await user.click(screen.getByRole("button", { name: /setupWizard\.button/ }));
    expect(listener).toHaveBeenCalledTimes(1);
    window.removeEventListener("open-setup-wizard", listener);
  });

  it("does not crash when getSetupStatus rejects (backend not ready)", async () => {
    mockGetSetupStatus.mockRejectedValue(new Error("backend down"));
    render(<Guide />);
    // Header still renders; checklist labels still render with no status.
    expect(await screen.findByText("checklist.configureAi")).toBeInTheDocument();
  });
});
