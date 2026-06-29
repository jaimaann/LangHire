import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Jobs from "./Jobs";
import { getJobStats } from "../lib/api";

// i18n: identity translator so assertions can use raw keys.
vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (k: string) => k, i18n: { changeLanguage: vi.fn() } }),
}));

// Mock the child tabs so this test focuses on the Jobs shell (tab switching + stats).
vi.mock("./jobs/CollectTab", () => ({
  default: ({ onJobsChanged }: { onJobsChanged: () => void }) => (
    <div data-testid="collect-tab">
      <button onClick={onJobsChanged}>collect-refresh</button>
    </div>
  ),
}));
vi.mock("./jobs/PendingTab", () => ({
  default: () => <div data-testid="pending-tab" />,
}));
vi.mock("./jobs/HistoryTab", () => ({
  default: () => <div data-testid="history-tab" />,
}));

vi.mock("../lib/api", () => ({
  getJobStats: vi.fn(),
}));

const mockGetJobStats = vi.mocked(getJobStats);

const stats = {
  total: 10,
  pending: 4,
  applied: 3,
  failed: 2,
  blocked: 1,
  in_progress: 0,
};

describe("Jobs", () => {
  beforeEach(() => {
    mockGetJobStats.mockResolvedValue(structuredClone(stats) as never);
  });

  it("fetches stats on mount and renders the header", async () => {
    render(<Jobs />);
    expect(screen.getByText("title")).toBeInTheDocument();
    await waitFor(() => expect(mockGetJobStats).toHaveBeenCalled());
  });

  it("renders the Collect tab by default", async () => {
    render(<Jobs />);
    expect(await screen.findByTestId("collect-tab")).toBeInTheDocument();
    expect(screen.queryByTestId("pending-tab")).not.toBeInTheDocument();
  });

  it("switches to the Pending tab", async () => {
    const user = userEvent.setup();
    render(<Jobs />);
    await waitFor(() => expect(mockGetJobStats).toHaveBeenCalled());

    await user.click(screen.getByRole("button", { name: /Review & Apply/ }));
    expect(await screen.findByTestId("pending-tab")).toBeInTheDocument();
    expect(screen.queryByTestId("collect-tab")).not.toBeInTheDocument();
  });

  it("switches to the History tab", async () => {
    const user = userEvent.setup();
    render(<Jobs />);
    await waitFor(() => expect(mockGetJobStats).toHaveBeenCalled());

    await user.click(screen.getByRole("button", { name: /History/ }));
    expect(await screen.findByTestId("history-tab")).toBeInTheDocument();
  });

  it("re-fetches stats when a child reports jobs changed", async () => {
    const user = userEvent.setup();
    render(<Jobs />);
    await waitFor(() => expect(mockGetJobStats).toHaveBeenCalledTimes(1));

    await user.click(screen.getByRole("button", { name: "collect-refresh" }));
    await waitFor(() => expect(mockGetJobStats).toHaveBeenCalledTimes(2));
  });

  it("renders tab count badges derived from stats", async () => {
    render(<Jobs />);
    await waitFor(() => expect(mockGetJobStats).toHaveBeenCalled());
    // collect count = total (10); pending tab = pending + failed (6); history = applied (3)
    // The count badges carry a rounded-full class distinguishing them from the step number circles.
    await screen.findByText("10");
    const badges = screen
      .getAllByText(/^(10|6|3)$/)
      .filter((el) => el.className.includes("rounded-full") && el.className.includes("px-1.5"));
    const counts = badges.map((b) => b.textContent).sort();
    expect(counts).toEqual(["10", "3", "6"]);
  });

  it("does not crash when getJobStats rejects", async () => {
    mockGetJobStats.mockRejectedValue(new Error("down"));
    render(<Jobs />);
    expect(await screen.findByTestId("collect-tab")).toBeInTheDocument();
  });
});
