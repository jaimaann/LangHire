import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import BackendStatusBanner from "./BackendStatusBanner";
import { applyBackendStatus } from "../lib/backendStatus";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (k: string) => k }),
}));

afterEach(() => {
  act(() => applyBackendStatus({ status: "running", restarts: 0 }));
});

describe("BackendStatusBanner", () => {
  it("renders nothing while the backend is running", () => {
    act(() => applyBackendStatus({ status: "running" }));
    const { container } = render(<BackendStatusBanner />);
    expect(container).toBeEmptyDOMElement();
  });

  it("does not show during the initial start", () => {
    act(() => applyBackendStatus({ status: "starting", restarts: 0 }));
    const { container } = render(<BackendStatusBanner />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows the restarting message after a crash", () => {
    render(<BackendStatusBanner />);
    act(() => applyBackendStatus({ status: "crashed", restarts: 1 }));
    expect(screen.getByText("backend.restarting")).toBeInTheDocument();
    act(() => applyBackendStatus({ status: "starting", restarts: 1 }));
    expect(screen.getByText("backend.restarting")).toBeInTheDocument();
  });

  it("shows the failure message when restarts are exhausted", () => {
    render(<BackendStatusBanner />);
    act(() => applyBackendStatus({ status: "failed", restarts: 5 }));
    expect(screen.getByText("backend.failed")).toBeInTheDocument();
  });
});
