import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import LoginCards from "./LoginCards";
import { getAuthStatus, launchLogin } from "../lib/api";

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
      linkedin: { logged_in: false },
      gmail: { logged_in: false },
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
});
