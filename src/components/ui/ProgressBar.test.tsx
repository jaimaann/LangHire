import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import ProgressBar from "./ProgressBar";

/** Returns the inner (filled) bar element which carries the width style. */
function getFillBar(container: HTMLElement): HTMLElement {
  const fill = container.querySelector(".bg-primary") as HTMLElement;
  return fill;
}

describe("ProgressBar", () => {
  it("sets the fill width to the percent value", () => {
    const { container } = render(<ProgressBar percent={42} />);
    expect(getFillBar(container)).toHaveStyle({ width: "42%" });
  });

  it("rounds the displayed percentage", () => {
    render(<ProgressBar percent={42.6} />);
    expect(screen.getByText("43%")).toBeInTheDocument();
  });

  it("clamps values above 100 to 100", () => {
    const { container } = render(<ProgressBar percent={150} />);
    expect(getFillBar(container)).toHaveStyle({ width: "100%" });
    expect(screen.getByText("100%")).toBeInTheDocument();
  });

  it("clamps negative values to 0", () => {
    const { container } = render(<ProgressBar percent={-25} />);
    expect(getFillBar(container)).toHaveStyle({ width: "0%" });
    expect(screen.getByText("0%")).toBeInTheDocument();
  });

  it("handles exactly 0", () => {
    const { container } = render(<ProgressBar percent={0} />);
    expect(getFillBar(container)).toHaveStyle({ width: "0%" });
    expect(screen.getByText("0%")).toBeInTheDocument();
  });

  it("handles exactly 100", () => {
    const { container } = render(<ProgressBar percent={100} />);
    expect(getFillBar(container)).toHaveStyle({ width: "100%" });
    expect(screen.getByText("100%")).toBeInTheDocument();
  });

  it("shows the percent label by default", () => {
    render(<ProgressBar percent={50} />);
    expect(screen.getByText("50%")).toBeInTheDocument();
  });

  it("hides the percent when showPercent is false and no label", () => {
    render(<ProgressBar percent={50} showPercent={false} />);
    expect(screen.queryByText("50%")).not.toBeInTheDocument();
  });

  it("renders a label when provided", () => {
    render(<ProgressBar percent={50} label="Uploading" />);
    expect(screen.getByText("Uploading")).toBeInTheDocument();
    expect(screen.getByText("50%")).toBeInTheDocument();
  });

  it("renders the label even when showPercent is false", () => {
    render(<ProgressBar percent={50} label="Uploading" showPercent={false} />);
    expect(screen.getByText("Uploading")).toBeInTheDocument();
    expect(screen.queryByText("50%")).not.toBeInTheDocument();
  });

  it("does not render the header row when no label and showPercent false", () => {
    const { container } = render(
      <ProgressBar percent={50} showPercent={false} />,
    );
    // header row uses justify-between; only the track div should remain
    expect(container.querySelector(".justify-between")).not.toBeInTheDocument();
  });
});
