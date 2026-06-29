import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import LoadingSpinner from "./LoadingSpinner";

describe("LoadingSpinner", () => {
  it("renders a spinning svg icon", () => {
    const { container } = render(<LoadingSpinner />);
    const svg = container.querySelector("svg");
    expect(svg).toBeInTheDocument();
    expect(svg).toHaveClass("animate-spin");
  });

  it("applies the default height class on the wrapper", () => {
    const { container } = render(<LoadingSpinner />);
    expect(container.firstChild).toHaveClass("h-64");
    expect(container.firstChild).toHaveClass("flex");
    expect(container.firstChild).toHaveClass("justify-center");
  });

  it("applies a custom className overriding the default", () => {
    const { container } = render(<LoadingSpinner className="h-12" />);
    expect(container.firstChild).toHaveClass("h-12");
    expect(container.firstChild).not.toHaveClass("h-64");
  });

  it("handles an empty className", () => {
    const { container } = render(<LoadingSpinner className="" />);
    expect(container.firstChild).toHaveClass("flex");
    expect(container.firstChild).not.toHaveClass("h-64");
  });
});
