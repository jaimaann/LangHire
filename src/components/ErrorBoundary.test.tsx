import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// Mock the analytics + Sentry side-effects so componentDidCatch is inert.
const trackException = vi.fn();
vi.mock("../lib/analytics", () => ({
  trackException: (...args: unknown[]) => trackException(...args),
}));
const captureException = vi.fn();
vi.mock("@sentry/browser", () => ({
  captureException: (...args: unknown[]) => captureException(...args),
}));

import ErrorBoundary from "./ErrorBoundary";

/** A component that throws on render when `boom` is true. */
function Boom({ boom, message }: { boom: boolean; message?: string }) {
  if (boom) throw new Error(message ?? "kaboom");
  return <div>safe child</div>;
}

describe("ErrorBoundary", () => {
  let errorSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    // React logs the caught error to console.error; silence the expected noise.
    errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    errorSpy.mockRestore();
  });

  it("renders children normally when no error is thrown", () => {
    render(
      <ErrorBoundary>
        <Boom boom={false} />
      </ErrorBoundary>,
    );
    expect(screen.getByText("safe child")).toBeInTheDocument();
    expect(screen.queryByText("Something went wrong")).not.toBeInTheDocument();
  });

  it("renders the fallback UI when a child throws", () => {
    render(
      <ErrorBoundary>
        <Boom boom message="explosion" />
      </ErrorBoundary>,
    );
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
    // the thrown error's message is surfaced
    expect(screen.getByText("explosion")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Try Again/i })).toBeInTheDocument();
  });

  it("reports the error via analytics and Sentry", () => {
    render(
      <ErrorBoundary>
        <Boom boom message="reported" />
      </ErrorBoundary>,
    );
    expect(trackException).toHaveBeenCalledTimes(1);
    expect(trackException).toHaveBeenCalledWith(
      expect.stringContaining("reported"),
      true,
    );
    expect(captureException).toHaveBeenCalledTimes(1);
  });

  it("falls back to a generic message when the error has no message", () => {
    render(
      <ErrorBoundary>
        <Boom boom message="" />
      </ErrorBoundary>,
    );
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
    expect(
      screen.getByText("An unexpected error occurred."),
    ).toBeInTheDocument();
  });

  it("clears its error state and re-renders children when Try Again is clicked", async () => {
    const user = userEvent.setup();

    // An external switch controls whether the child throws. It stays `true`
    // (including through React 19's render-retry on error) so the fallback is
    // committed, then we flip it to `false` before resetting the boundary so
    // the subsequent re-render of children succeeds.
    const control = { throw: true };
    function FlakyChild() {
      if (control.throw) throw new Error("transient failure");
      return <div>recovered child</div>;
    }

    render(
      <ErrorBoundary>
        <FlakyChild />
      </ErrorBoundary>,
    );
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();

    // Simulate the underlying problem being fixed before retrying.
    control.throw = false;
    await user.click(screen.getByRole("button", { name: /Try Again/i }));

    expect(screen.getByText("recovered child")).toBeInTheDocument();
    expect(screen.queryByText("Something went wrong")).not.toBeInTheDocument();
  });
});
