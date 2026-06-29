import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import Section from "./Section";

describe("Section", () => {
  it("renders the title as a heading", () => {
    render(
      <Section title="Settings">
        <p>body</p>
      </Section>,
    );
    expect(screen.getByRole("heading", { name: "Settings" })).toBeInTheDocument();
  });

  it("renders its children", () => {
    render(
      <Section title="Settings">
        <p>child content</p>
      </Section>,
    );
    expect(screen.getByText("child content")).toBeInTheDocument();
  });

  it("applies the default margin className along with card", () => {
    const { container } = render(
      <Section title="T">
        <span />
      </Section>,
    );
    expect(container.firstChild).toHaveClass("card");
    expect(container.firstChild).toHaveClass("mb-5");
  });

  it("overrides the default className", () => {
    const { container } = render(
      <Section title="T" className="mt-2">
        <span />
      </Section>,
    );
    expect(container.firstChild).toHaveClass("card");
    expect(container.firstChild).toHaveClass("mt-2");
    expect(container.firstChild).not.toHaveClass("mb-5");
  });
});
