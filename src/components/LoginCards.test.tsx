import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import LoginCards from "./LoginCards";
import { getAuthStatus, launchLogin } from "../lib/api";

// i18n: a small English dictionary so assertions read like the real UI.
const EN: Record<string, string> = {
  "logins.loggedIn": "Logged in",
  "logins.notLoggedIn": "Not logged in",
  "logins.optional": "Optional",
  "logins.refresh": "Refresh status",
  "logins.opening": "Opening...",
  "logins.logInTo": "Log in to {{name}}",
  "logins.launchFailed": "Failed to launch browser",
  "logins.none": "No job sites need a login.",
  "logins.linkedinReason": "LinkedIn reason",
  "logins.gmailReason": "Gmail reason",
  "logins.gmailOptional": "Gmail optional reason",
  "logins.genericReason": "Apply on {{name}}",
};
vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (k: string, o?: Record<string, unknown>) =>
      (EN[k] ?? k).replace(/\{\{(\w+)\}\}/g, (_, n) => String(o?.[n] ?? "")),
  }),
}));

vi.mock("../lib/api", () => ({
  getAuthStatus: vi.fn(),
  launchLogin: vi.fn(),
}));

const mockGetAuthStatus = vi.mocked(getAuthStatus);
const mockLaunchLogin = vi.mocked(launchLogin);

describe("LoginCards", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    mockGetAuthStatus.mockResolvedValue({
      linkedin: { logged_in: false, display_name: "LinkedIn" },
      gmail: { logged_in: false, display_name: "Gmail" },
    } as never);
    mockLaunchLogin.mockResolvedValue({ success: true, message: "ok" } as never);
  });

  afterEach(() => {
    vi.runOnlyPendingTimers();
    vi.useRealTimers();
  });

  it("renders nothing while loading (before first status resolves)", () => {
    // Keep the promise pending so loading stays true.
    mockGetAuthStatus.mockReturnValue(new Promise(() => {}) as never);
    const { container } = render(<LoginCards />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders both service cards as not-logged-in with login buttons", async () => {
    render(<LoginCards />);
    expect(await screen.findByText("LinkedIn")).toBeInTheDocument();
    expect(screen.getByText("Gmail")).toBeInTheDocument();

    expect(screen.getAllByText("Not logged in")).toHaveLength(2);
    expect(screen.getByRole("button", { name: /Log in to LinkedIn/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Log in to Gmail/ })).toBeInTheDocument();
  });

  it("shows logged-in badge and hides the login button when a service is authenticated", async () => {
    mockGetAuthStatus.mockResolvedValue({
      linkedin: { logged_in: true },
      gmail: { logged_in: false },
    } as never);
    render(<LoginCards />);

    expect(await screen.findByText("Logged in")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Log in to LinkedIn/ })).not.toBeInTheDocument();
    // Gmail still offers login.
    expect(screen.getByRole("button", { name: /Log in to Gmail/ })).toBeInTheDocument();
  });

  it("calls launchLogin with the correct service when its login button is clicked", async () => {
    const user = userEvent.setup();
    render(<LoginCards />);
    await screen.findByText("LinkedIn");

    await user.click(screen.getByRole("button", { name: /Log in to LinkedIn/ }));
    await waitFor(() => expect(mockLaunchLogin).toHaveBeenCalledWith("linkedin"));
  });

  it("alerts when launchLogin returns success: false", async () => {
    const alertSpy = vi.spyOn(window, "alert").mockImplementation(() => {});
    mockLaunchLogin.mockResolvedValue({ success: false, message: "no browser" } as never);
    const user = userEvent.setup();
    render(<LoginCards />);
    await screen.findByText("Gmail");

    await user.click(screen.getByRole("button", { name: /Log in to Gmail/ }));
    await waitFor(() => expect(alertSpy).toHaveBeenCalledWith("no browser"));
    alertSpy.mockRestore();
  });

  it("alerts the error message when launchLogin throws", async () => {
    const alertSpy = vi.spyOn(window, "alert").mockImplementation(() => {});
    mockLaunchLogin.mockRejectedValue(new Error("boom"));
    const user = userEvent.setup();
    render(<LoginCards />);
    await screen.findByText("LinkedIn");

    await user.click(screen.getByRole("button", { name: /Log in to LinkedIn/ }));
    await waitFor(() => expect(alertSpy).toHaveBeenCalledWith("boom"));
    alertSpy.mockRestore();
  });

  it("refreshes status when a card's refresh button is clicked", async () => {
    const user = userEvent.setup();
    render(<LoginCards />);
    await screen.findByText("LinkedIn");
    const callsBefore = mockGetAuthStatus.mock.calls.length;

    const refreshButtons = screen.getAllByTitle("Refresh status");
    await user.click(refreshButtons[0]);
    await waitFor(() =>
      expect(mockGetAuthStatus.mock.calls.length).toBeGreaterThan(callsBefore),
    );
  });

  it("disables login buttons while a launch is in flight", async () => {
    let resolveLaunch: (v: { success: boolean; message: string }) => void = () => {};
    mockLaunchLogin.mockReturnValue(
      new Promise((res) => {
        resolveLaunch = res;
      }) as never,
    );
    const user = userEvent.setup();
    render(<LoginCards />);
    await screen.findByText("LinkedIn");

    const linkedinBtn = screen.getByRole("button", { name: /Log in to LinkedIn/ });
    await user.click(linkedinBtn);

    // Shows "Opening..." and is disabled while pending.
    await waitFor(() => expect(within(linkedinBtn).queryByText("Opening...")).toBeInTheDocument());
    expect(linkedinBtn).toBeDisabled();
    expect(screen.getByRole("button", { name: /Log in to Gmail/ })).toBeDisabled();

    resolveLaunch({ success: true, message: "ok" });
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /Log in to LinkedIn/ })).not.toBeDisabled(),
    );
  });

  it("renders a card per source plugin from /auth/status, LinkedIn first and Gmail last", async () => {
    mockGetAuthStatus.mockResolvedValue({
      gmail: { logged_in: false, display_name: "Gmail" },
      indeed: { logged_in: true, display_name: "Indeed" },
      linkedin: { logged_in: false, display_name: "LinkedIn" },
      seek: { logged_in: false, display_name: "SEEK" },
    } as never);
    const user = userEvent.setup();
    const { container } = render(<LoginCards />);
    await screen.findByText("Indeed");

    const order = [...container.querySelectorAll("[data-testid^='login-card-']")].map((el) =>
      el.getAttribute("data-testid"),
    );
    expect(order).toEqual(["login-card-linkedin", "login-card-indeed", "login-card-seek", "login-card-gmail"]);
    expect(screen.getByText("Apply on SEEK")).toBeInTheDocument();
    // Indeed is logged in: no login button for it.
    expect(screen.queryByRole("button", { name: /Log in to Indeed/ })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Log in to SEEK/ }));
    await waitFor(() => expect(mockLaunchLogin).toHaveBeenCalledWith("seek"));
  });

  it("marks Gmail optional unless email OTP via Gmail is enabled", async () => {
    const { unmount } = render(<LoginCards />);
    const gmail = await screen.findByTestId("login-card-gmail");
    expect(within(gmail).getByText("Optional")).toBeInTheDocument();
    expect(within(gmail).getByText("Gmail optional reason")).toBeInTheDocument();
    unmount();

    render(<LoginCards gmailEnabled />);
    const enabled = await screen.findByTestId("login-card-gmail");
    expect(within(enabled).queryByText("Optional")).not.toBeInTheDocument();
    expect(within(enabled).getByText("Gmail reason")).toBeInTheDocument();
  });

  it("falls back to the service id when display_name is missing", async () => {
    mockGetAuthStatus.mockResolvedValue({ reed: { logged_in: false } } as never);
    render(<LoginCards />);
    expect(await screen.findByText("reed")).toBeInTheDocument();
  });

  it("shows a note when no service needs a login", async () => {
    mockGetAuthStatus.mockResolvedValue({} as never);
    render(<LoginCards />);
    expect(await screen.findByText("No job sites need a login.")).toBeInTheDocument();
  });
});
