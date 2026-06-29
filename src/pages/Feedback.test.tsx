import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ComponentType } from "react";

// i18n: identity translator so assertions can use raw keys.
vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (k: string) => k, i18n: { changeLanguage: vi.fn() } }),
}));

// Feedback reads VITE_GITHUB_TOKEN into a module-level const at import time, so
// we must stub the env BEFORE importing the component. Use a fresh dynamic
// import per test (resetModules) so each test controls the captured token.
async function loadFeedback(token: string): Promise<ComponentType> {
  vi.stubEnv("VITE_GITHUB_TOKEN", token);
  vi.resetModules();
  const mod = await import("./Feedback");
  return mod.default;
}

// Feedback talks directly to the GitHub GraphQL API via global fetch.
function stubFetchSequence(...responses: unknown[]) {
  const fn = vi.fn();
  for (const r of responses) {
    fn.mockResolvedValueOnce({ json: async () => r });
  }
  vi.stubGlobal("fetch", fn as unknown as typeof fetch);
  return fn;
}

const REPO_OK = {
  data: {
    repository: {
      id: "repo-1",
      discussionCategories: {
        nodes: [
          { id: "cat-feat", name: "Feature Request" },
          { id: "cat-bug", name: "Bug Report" },
          { id: "cat-general", name: "General Feedback" },
        ],
      },
    },
  },
};

const MUTATION_OK = {
  data: { createDiscussion: { discussion: { url: "https://github.com/jaimaann/LangHire/discussions/42" } } },
};

describe("Feedback", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  it("renders the form with category buttons and inputs", async () => {
    const Feedback = await loadFeedback("ghp_test_token");
    render(<Feedback />);
    expect(screen.getByText("title")).toBeInTheDocument();
    expect(screen.getByText("categories.featureRequest")).toBeInTheDocument();
    expect(screen.getByText("categories.bugReport")).toBeInTheDocument();
    expect(screen.getByText("categories.generalFeedback")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("form.titlePlaceholder")).toBeInTheDocument();
  });

  it("disables submit until title and description are filled", async () => {
    const Feedback = await loadFeedback("ghp_test_token");
    const user = userEvent.setup();
    render(<Feedback />);
    const submit = screen.getByRole("button", { name: /form\.submit/ });
    expect(submit).toBeDisabled();

    await user.type(screen.getByPlaceholderText("form.titlePlaceholder"), "My title");
    expect(submit).toBeDisabled();

    await user.type(screen.getByPlaceholderText("form.descriptionPlaceholder"), "Details");
    expect(submit).toBeEnabled();
  });

  it("shows the not-configured error when no GitHub token is set", async () => {
    const Feedback = await loadFeedback("");
    const user = userEvent.setup();
    render(<Feedback />);

    await user.type(screen.getByPlaceholderText("form.titlePlaceholder"), "T");
    await user.type(screen.getByPlaceholderText("form.descriptionPlaceholder"), "D");
    await user.click(screen.getByRole("button", { name: /form\.submit/ }));

    expect(await screen.findByText("error.notConfigured")).toBeInTheDocument();
  });

  it("submits successfully and shows the success state with the discussion URL", async () => {
    const Feedback = await loadFeedback("ghp_test_token");
    const fetchFn = stubFetchSequence(REPO_OK, MUTATION_OK);
    const user = userEvent.setup();
    render(<Feedback />);

    await user.type(screen.getByPlaceholderText("form.titlePlaceholder"), "Great idea");
    await user.type(screen.getByPlaceholderText("form.descriptionPlaceholder"), "Please add X");
    await user.click(screen.getByRole("button", { name: /form\.submit/ }));

    expect(await screen.findByText("success.title")).toBeInTheDocument();
    const link = screen.getByRole("link", { name: /success\.viewDiscussion/ });
    expect(link).toHaveAttribute("href", MUTATION_OK.data.createDiscussion.discussion.url);
    expect(fetchFn).toHaveBeenCalledTimes(2);
  });

  it("lets the user submit another after success", async () => {
    const Feedback = await loadFeedback("ghp_test_token");
    stubFetchSequence(REPO_OK, MUTATION_OK);
    const user = userEvent.setup();
    render(<Feedback />);

    await user.type(screen.getByPlaceholderText("form.titlePlaceholder"), "Great idea");
    await user.type(screen.getByPlaceholderText("form.descriptionPlaceholder"), "Please add X");
    await user.click(screen.getByRole("button", { name: /form\.submit/ }));

    await screen.findByText("success.title");
    await user.click(screen.getByRole("button", { name: "success.submitAnother" }));

    // Back to the form.
    expect(screen.getByPlaceholderText("form.titlePlaceholder")).toBeInTheDocument();
  });

  it("surfaces a GraphQL error from the repository query", async () => {
    const Feedback = await loadFeedback("ghp_test_token");
    stubFetchSequence({ errors: [{ message: "Bad credentials" }] });
    const user = userEvent.setup();
    render(<Feedback />);

    await user.type(screen.getByPlaceholderText("form.titlePlaceholder"), "X");
    await user.type(screen.getByPlaceholderText("form.descriptionPlaceholder"), "Y");
    await user.click(screen.getByRole("button", { name: /form\.submit/ }));

    expect(await screen.findByText("Bad credentials")).toBeInTheDocument();
  });

  it("switches the selected category", async () => {
    const Feedback = await loadFeedback("ghp_test_token");
    const user = userEvent.setup();
    render(<Feedback />);
    const bugBtn = screen.getByRole("button", { name: "categories.bugReport" });
    await user.click(bugBtn);
    // The active button gets the dark/foreground class.
    await waitFor(() => expect(bugBtn.className).toContain("bg-foreground"));
  });
});
