import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Sidebar from "./Sidebar";
import { checkHealth } from "../../lib/api";

// Identity translator so assertions use raw i18n keys.
vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (k: string) => k,
    i18n: { changeLanguage: vi.fn(), dir: () => "ltr", language: "en" },
  }),
}));

vi.mock("../../lib/api", () => ({
  checkHealth: vi.fn(),
}));

const mockCheckHealth = vi.mocked(checkHealth);

function renderSidebar(initialEntries: string[] = ["/"]) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <Sidebar />
    </MemoryRouter>,
  );
}

describe("Sidebar", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    mockCheckHealth.mockResolvedValue({ build_id: "abc123" } as never);
  });

  afterEach(() => {
    vi.runOnlyPendingTimers();
    vi.useRealTimers();
  });

  it("renders the app title/tagline and all navigation items", () => {
    renderSidebar();
    expect(screen.getByText("app.title")).toBeInTheDocument();
    expect(screen.getByText("app.tagline")).toBeInTheDocument();

    const expectedNav = [
      "nav.dashboard",
      "nav.guide",
      "nav.profile",
      "nav.llmSettings",
      "nav.jobs",
      "nav.memory",
      "nav.qa",
      "nav.logs",
      "nav.settings",
      "nav.feedback",
    ];
    for (const key of expectedNav) {
      expect(screen.getByText(key)).toBeInTheDocument();
    }
  });

  it("renders nav items as links pointing at the right routes", () => {
    renderSidebar();
    expect(screen.getByRole("link", { name: "nav.dashboard" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: "nav.jobs" })).toHaveAttribute("href", "/jobs");
    expect(screen.getByRole("link", { name: "nav.settings" })).toHaveAttribute("href", "/settings");
  });

  it("marks the active route's NavLink (aria-current) based on the current location", () => {
    renderSidebar(["/jobs"]);
    const activeLink = screen.getByRole("link", { name: "nav.jobs" });
    expect(activeLink).toHaveAttribute("aria-current", "page");
    expect(activeLink).toHaveClass("bg-foreground");

    const inactiveLink = screen.getByRole("link", { name: "nav.dashboard" });
    expect(inactiveLink).not.toHaveAttribute("aria-current", "page");
  });

  it("shows connecting state initially then connected with build id after health check", async () => {
    renderSidebar();
    // Before the promise resolves, the connecting label is shown.
    expect(screen.getByText("status.connecting")).toBeInTheDocument();

    await waitFor(() =>
      expect(screen.getByText(/status\.connected/)).toBeInTheDocument(),
    );
    // Build id is appended.
    expect(screen.getByText(/abc123/)).toBeInTheDocument();
  });

  it("shows the starting-backend state when the health check fails", async () => {
    mockCheckHealth.mockRejectedValue(new Error("backend down"));
    renderSidebar();
    await waitFor(() =>
      expect(screen.getByText("status.startingBackend")).toBeInTheDocument(),
    );
  });

  it("renders connected without a build id when none is returned", async () => {
    mockCheckHealth.mockResolvedValue({ build_id: "" } as never);
    renderSidebar();
    await waitFor(() => expect(screen.getByText("status.connected")).toBeInTheDocument());
    expect(screen.queryByText(/·/)).not.toBeInTheDocument();
  });
});
