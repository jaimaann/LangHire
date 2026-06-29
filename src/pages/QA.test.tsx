import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import QA from "./QA";
import {
  getQAList,
  getQAStats,
  updateQA,
  deleteQA,
  mergeQA,
  autoSquashQA,
  smartSquashQA,
} from "../lib/api";
import { trackEvent } from "../lib/analytics";
import type { QAEntry } from "../lib/types";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (k: string, o?: Record<string, unknown>) =>
      o ? `${k}:${JSON.stringify(o)}` : k,
    i18n: { changeLanguage: vi.fn() },
  }),
}));

vi.mock("../lib/analytics", () => ({ trackEvent: vi.fn() }));

vi.mock("../lib/api", () => ({
  getQAList: vi.fn(),
  getQAStats: vi.fn(),
  updateQA: vi.fn(),
  deleteQA: vi.fn(),
  mergeQA: vi.fn(),
  autoSquashQA: vi.fn(),
  smartSquashQA: vi.fn(),
}));

const mockGetQAList = vi.mocked(getQAList);
const mockGetQAStats = vi.mocked(getQAStats);
const mockUpdateQA = vi.mocked(updateQA);
const mockDeleteQA = vi.mocked(deleteQA);
const mockMergeQA = vi.mocked(mergeQA);
const mockAutoSquashQA = vi.mocked(autoSquashQA);
const mockSmartSquashQA = vi.mocked(smartSquashQA);
const mockTrackEvent = vi.mocked(trackEvent);

function makeEntry(over: Partial<QAEntry> = {}): QAEntry {
  return {
    id: 1,
    question: "Why do you want this job?",
    normalized: "why do you want this job",
    answer: "Because I love it.",
    question_type: "freeform",
    source_domain: "greenhouse.io",
    times_seen: 2,
    merged_into_id: null,
    created_at: "2026-01-01",
    updated_at: "2026-01-02",
    ...over,
  };
}

const entries: QAEntry[] = [
  makeEntry({ id: 1, question: "Why do you want this job?" }),
  makeEntry({ id: 2, question: "What is your expected salary?", answer: "", times_seen: 1 }),
];

describe("QA page", () => {
  beforeEach(() => {
    mockGetQAList.mockResolvedValue(entries as never);
    mockGetQAStats.mockResolvedValue({ total: 2, answered: 1, unanswered: 1 } as never);
    mockUpdateQA.mockResolvedValue({ success: true } as never);
    mockDeleteQA.mockResolvedValue({ success: true } as never);
    mockMergeQA.mockResolvedValue({ success: true } as never);
    mockAutoSquashQA.mockResolvedValue({ success: true, merged: 3 } as never);
    mockSmartSquashQA.mockResolvedValue({ success: true, merged: 1 } as never);
  });

  it("shows the loading spinner before the list resolves", () => {
    mockGetQAList.mockReturnValue(new Promise(() => {}) as never);
    render(<QA />);
    expect(screen.queryByText("title")).not.toBeInTheDocument();
  });

  it("renders the question list after load", async () => {
    render(<QA />);
    expect(await screen.findByText("Why do you want this job?")).toBeInTheDocument();
    expect(screen.getByText("What is your expected salary?")).toBeInTheDocument();
    // times_seen badge for the first entry.
    expect(screen.getByText("2x")).toBeInTheDocument();
  });

  it("filters to unanswered, re-fetching with the unanswered flag", async () => {
    const user = userEvent.setup();
    render(<QA />);
    await screen.findByText("Why do you want this job?");

    await user.click(screen.getByRole("button", { name: /filter\.unanswered/ }));

    await waitFor(() =>
      expect(mockGetQAList).toHaveBeenCalledWith(
        expect.objectContaining({ unanswered: true }),
      ),
    );
  });

  it("searching re-fetches the list with the search term", async () => {
    const user = userEvent.setup();
    render(<QA />);
    await screen.findByText("Why do you want this job?");

    await user.type(screen.getByPlaceholderText("searchPlaceholder"), "salary");

    await waitFor(() =>
      expect(mockGetQAList).toHaveBeenCalledWith(
        expect.objectContaining({ search: "salary" }),
      ),
    );
  });

  it("editing an answer debounce-saves via updateQA", async () => {
    const user = userEvent.setup();
    render(<QA />);
    await screen.findByText("Why do you want this job?");

    const textareas = screen.getAllByPlaceholderText("card.answerPlaceholder");
    await user.type(textareas[0], "!");

    await waitFor(
      () => expect(mockUpdateQA).toHaveBeenCalledWith(1, expect.stringContaining("Because I love it.!")),
      { timeout: 2000 },
    );
    expect(mockTrackEvent).toHaveBeenCalledWith("qa_answer_updated");
  });

  it("deleting a question calls deleteQA and refetches", async () => {
    const user = userEvent.setup();
    render(<QA />);
    await screen.findByText("Why do you want this job?");

    const firstCard = screen.getByText("Why do you want this job?").closest(".card") as HTMLElement;
    await user.click(within(firstCard).getByTitle("card.deleteTitle"));

    await waitFor(() => expect(mockDeleteQA).toHaveBeenCalledWith(1));
    // fetchData runs again after delete (≥ the initial load).
    expect(mockGetQAList.mock.calls.length).toBeGreaterThanOrEqual(2);
  });

  it("auto-squash calls the API and shows a result toast", async () => {
    const user = userEvent.setup();
    render(<QA />);
    await screen.findByText("Why do you want this job?");

    await user.click(screen.getByRole("button", { name: /actions\.autoSquash/ }));

    await waitFor(() => expect(mockAutoSquashQA).toHaveBeenCalled());
    expect(await screen.findByText(/toast\.squashResult/)).toBeInTheDocument();
  });

  it("smart-squash calls the API and tracks the event", async () => {
    const user = userEvent.setup();
    render(<QA />);
    await screen.findByText("Why do you want this job?");

    await user.click(screen.getByRole("button", { name: /actions\.smartSquash/ }));

    await waitFor(() => expect(mockSmartSquashQA).toHaveBeenCalled());
    expect(mockTrackEvent).toHaveBeenCalledWith("qa_smart_squash", { merged: 1 });
  });

  it("merge flow: starting merge shows a banner; picking a target calls mergeQA", async () => {
    const user = userEvent.setup();
    render(<QA />);
    await screen.findByText("Why do you want this job?");

    const firstCard = screen.getByText("Why do you want this job?").closest(".card") as HTMLElement;
    await user.click(within(firstCard).getByTitle("card.mergeTitle"));

    // Merge banner appears.
    expect(await screen.findByText("mergeMode.label")).toBeInTheDocument();

    // Clicking the OTHER card (a merge target) triggers mergeQA(source=1, target=2).
    const secondCard = screen.getByText("What is your expected salary?").closest(".card") as HTMLElement;
    await user.click(secondCard);

    await waitFor(() => expect(mockMergeQA).toHaveBeenCalledWith(1, 2));
  });

  it("renders an empty state when there are no questions", async () => {
    mockGetQAList.mockResolvedValue([] as never);
    mockGetQAStats.mockResolvedValue({ total: 0, answered: 0, unanswered: 0 } as never);
    render(<QA />);
    expect(await screen.findByText("emptyState.noQuestions")).toBeInTheDocument();
  });

  it("shows an error banner when the load fails", async () => {
    mockGetQAList.mockRejectedValue(new Error("API Error 500: boom"));
    render(<QA />);
    expect(await screen.findByText("API Error 500: boom")).toBeInTheDocument();
  });
});
