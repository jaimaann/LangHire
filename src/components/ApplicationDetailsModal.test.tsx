import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ApplicationDetailsModal from "./ApplicationDetailsModal";
import { getApplications, openLocalFile } from "../lib/api";
import type { ApplicationRecord, Job } from "../lib/types";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (k: string, o?: Record<string, unknown>) => (o ? `${k}:${JSON.stringify(o)}` : k),
  }),
}));

vi.mock("../lib/api", () => ({
  getApplications: vi.fn(),
  openLocalFile: vi.fn(),
}));

const job: Job = {
  url: "https://jobs.example.com/1",
  title: "Data Analyst",
  company: "Acme",
  location: "Remote",
  easy_apply: false,
  status: "applied",
};

const record: ApplicationRecord = {
  outcome: "submitted",
  reason: "Application sent",
  confirmation: "Thanks for applying!",
  answers: [
    { question: "Email", answer: "me@example.com", field_type: "email", source: "profile", confidence: 1 },
    { question: "Years of SQL?", answer: "4", field_type: "number", source: "inferred", confidence: 0.9 },
    { question: "Start date", answer: "ASAP", field_type: "text", source: "qa", confidence: 0.4 },
  ],
  missing_info: [],
  resume_path: "/data/resumes/tailored.pdf",
  screenshot_path: "/data/screens/1.png",
  cost_usd: 0.0312,
  steps: 14,
  ats: "greenhouse",
  created_at: "2026-11-14T10:00:00Z",
};

describe("ApplicationDetailsModal", () => {
  beforeEach(() => {
    vi.mocked(getApplications).mockResolvedValue([structuredClone(record)] as never);
    vi.mocked(openLocalFile).mockResolvedValue(undefined as never);
  });

  it("loads the latest record for the job and shows outcome, cost, resume and answers", async () => {
    render(<ApplicationDetailsModal job={job} onClose={vi.fn()} />);
    expect(await screen.findByTestId("application-outcome")).toHaveTextContent("details.outcomes.submitted");
    expect(getApplications).toHaveBeenCalledWith({ jobUrl: job.url, limit: 1 });
    expect(screen.getByText("$0.0312")).toBeInTheDocument();
    expect(screen.getByText("/data/resumes/tailored.pdf")).toBeInTheDocument();
    expect(screen.getByText('details.ats:{"ats":"greenhouse"}')).toBeInTheDocument();
    expect(screen.getByText("me@example.com")).toBeInTheDocument();
  });

  it("flags inferred and low-confidence answers", async () => {
    render(<ApplicationDetailsModal job={job} onClose={vi.fn()} />);
    await screen.findByText("me@example.com");
    const flagged = screen.getAllByTestId("answer-flagged");
    expect(flagged).toHaveLength(2);
    expect(within(flagged[0]).getByText("Years of SQL?")).toBeInTheDocument();
    expect(within(flagged[1]).getByText("Start date")).toBeInTheDocument();
    expect(within(flagged[1]).getByText("details.checkAnswer")).toBeInTheDocument();
    expect(screen.getAllByTestId("answer-row")).toHaveLength(1);
  });

  it("opens the screenshot and resume with openLocalFile", async () => {
    const user = userEvent.setup();
    render(<ApplicationDetailsModal job={job} onClose={vi.fn()} />);
    await user.click(await screen.findByRole("button", { name: /details.openScreenshot/ }));
    expect(openLocalFile).toHaveBeenCalledWith("/data/screens/1.png");
    await user.click(screen.getByRole("button", { name: /details.openResume/ }));
    expect(openLocalFile).toHaveBeenCalledWith("/data/resumes/tailored.pdf");
  });

  it("shows an error when the file can't be opened", async () => {
    vi.mocked(openLocalFile).mockRejectedValue(new Error("nope"));
    const user = userEvent.setup();
    render(<ApplicationDetailsModal job={job} onClose={vi.fn()} />);
    await user.click(await screen.findByRole("button", { name: /details.openScreenshot/ }));
    expect(await screen.findByText("details.openFailed")).toBeInTheDocument();
  });

  it("shows missing info with an answer-and-retry link for needs_input records", async () => {
    vi.mocked(getApplications).mockResolvedValue([
      { ...record, outcome: "needs_input", missing_info: ["Notice period"], screenshot_path: null },
    ] as never);
    render(<ApplicationDetailsModal job={job} onClose={vi.fn()} />);
    expect(await screen.findByTestId("application-outcome")).toHaveTextContent("details.outcomes.needsInput");
    expect(screen.getByText("Notice period")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "needsInput.answerAndRetry" })).toHaveAttribute("href", "#/qa");
    expect(screen.queryByRole("button", { name: /details.openScreenshot/ })).not.toBeInTheDocument();
  });

  it("shows an empty state when there is no record, and closes on Escape", async () => {
    vi.mocked(getApplications).mockResolvedValue([] as never);
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(<ApplicationDetailsModal job={job} onClose={onClose} />);
    expect(await screen.findByText("details.none")).toBeInTheDocument();
    await user.keyboard("{Escape}");
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it("shows an error when loading fails", async () => {
    vi.mocked(getApplications).mockRejectedValue(new Error("500"));
    render(<ApplicationDetailsModal job={job} onClose={vi.fn()} />);
    expect(await screen.findByText("details.loadFailed")).toBeInTheDocument();
  });
});
