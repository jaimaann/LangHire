import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import JobStatusBadge from "./JobStatusBadge";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (k: string) => k }),
}));

describe("JobStatusBadge", () => {
  it("renders test_passed with its own label and style", () => {
    render(<JobStatusBadge status="test_passed" />);
    const badge = screen.getByTestId("status-badge-test_passed");
    expect(badge).toHaveTextContent("status.testPassed");
    expect(badge.className).toContain("bg-sky-50");
  });

  it("falls back to pending for unknown statuses", () => {
    render(<JobStatusBadge status={"weird" as never} />);
    expect(screen.getByTestId("status-badge-pending")).toBeInTheDocument();
  });
});
