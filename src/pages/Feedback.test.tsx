import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (k: string) => k, i18n: { changeLanguage: vi.fn() } }),
}));

const openUrl = vi.fn();
vi.mock("@tauri-apps/plugin-opener", () => ({ openUrl: (u: string) => openUrl(u) }));

import Feedback from "./Feedback";
import { buildDiscussionUrl } from "../lib/feedbackUrl";

describe("Feedback", () => {
  beforeEach(() => {
    openUrl.mockReset();
    openUrl.mockResolvedValue(undefined);
  });

  it("renders the form with category buttons and inputs", () => {
    render(<Feedback />);
    expect(screen.getByText("title")).toBeInTheDocument();
    expect(screen.getByText("categories.featureRequest")).toBeInTheDocument();
    expect(screen.getByText("categories.bugReport")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("form.titlePlaceholder")).toBeInTheDocument();
  });

  it("disables submit until title and description are filled", async () => {
    const user = userEvent.setup();
    render(<Feedback />);
    const submit = screen.getByRole("button", { name: /form\.submit/ });
    expect(submit).toBeDisabled();
    await user.type(screen.getByPlaceholderText("form.titlePlaceholder"), "My title");
    expect(submit).toBeDisabled();
    await user.type(screen.getByPlaceholderText("form.descriptionPlaceholder"), "Details");
    expect(submit).toBeEnabled();
  });

  it("builds a prefilled discussion URL (no token in the app)", () => {
    const url = new URL(buildDiscussionUrl("Great idea", "Please add X & Y", "bugReport"));
    expect(url.origin + url.pathname).toBe("https://github.com/jaimaann/LangHire/discussions/new");
    expect(url.searchParams.get("category")).toBe("bug-report");
    expect(url.searchParams.get("title")).toBe("Great idea");
    expect(url.searchParams.get("body")).toBe("Please add X & Y");
  });

  it("opens GitHub in the browser and shows the success state", async () => {
    const user = userEvent.setup();
    render(<Feedback />);
    await user.type(screen.getByPlaceholderText("form.titlePlaceholder"), "Great idea");
    await user.type(screen.getByPlaceholderText("form.descriptionPlaceholder"), "Please add X");
    await user.click(screen.getByRole("button", { name: /form\.submit/ }));

    expect(await screen.findByText("success.title")).toBeInTheDocument();
    expect(openUrl).toHaveBeenCalledTimes(1);
    const opened = openUrl.mock.calls[0][0] as string;
    expect(opened).toContain("/discussions/new?");
    const link = screen.getByRole("link", { name: /success\.viewDiscussion/ });
    expect(link).toHaveAttribute("href", opened);
  });

  it("lets the user submit another after success", async () => {
    const user = userEvent.setup();
    render(<Feedback />);
    await user.type(screen.getByPlaceholderText("form.titlePlaceholder"), "Great idea");
    await user.type(screen.getByPlaceholderText("form.descriptionPlaceholder"), "Please add X");
    await user.click(screen.getByRole("button", { name: /form\.submit/ }));
    await screen.findByText("success.title");
    await user.click(screen.getByRole("button", { name: "success.submitAnother" }));
    expect(screen.getByPlaceholderText("form.titlePlaceholder")).toBeInTheDocument();
  });

  it("switches the selected category", async () => {
    const user = userEvent.setup();
    render(<Feedback />);
    const bugBtn = screen.getByRole("button", { name: "categories.bugReport" });
    await user.click(bugBtn);
    await waitFor(() => expect(bugBtn.className).toContain("bg-foreground"));
  });
});
