import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import Badge from "./Badge";

describe("Badge", () => {
  it("renders its children", () => {
    render(<Badge>Hello</Badge>);
    expect(screen.getByText("Hello")).toBeInTheDocument();
  });

  it("renders complex ReactNode children", () => {
    render(
      <Badge>
        <span data-testid="dot">●</span> Active
      </Badge>,
    );
    expect(screen.getByTestId("dot")).toBeInTheDocument();
    expect(screen.getByText(/Active/)).toBeInTheDocument();
  });

  it("applies the muted variant styles by default", () => {
    render(<Badge>Default</Badge>);
    const el = screen.getByText("Default");
    expect(el).toHaveClass("bg-[#F7F7F7]");
    expect(el).toHaveClass("text-muted-foreground");
  });

  it.each([
    ["success", "bg-[#F0FFF0]", "text-success"],
    ["error", "bg-[#FFF0F0]", "text-destructive"],
    ["warning", "bg-[#FFF8F0]", "text-warning"],
    ["info", "bg-[#F0F4FF]", "text-[#3B5998]"],
    ["muted", "bg-[#F7F7F7]", "text-muted-foreground"],
    ["primary", "bg-[#FFF0F3]", "text-primary"],
  ] as const)("applies %s variant classes", (variant, bg, text) => {
    render(<Badge variant={variant}>Tag</Badge>);
    const el = screen.getByText("Tag");
    expect(el).toHaveClass(bg);
    expect(el).toHaveClass(text);
  });

  it("merges a custom className", () => {
    render(<Badge className="custom-class">X</Badge>);
    const el = screen.getByText("X");
    expect(el).toHaveClass("custom-class");
    // base classes still present
    expect(el).toHaveClass("rounded-full");
    expect(el).toHaveClass("inline-flex");
  });

  it("renders as a span element", () => {
    render(<Badge>span check</Badge>);
    expect(screen.getByText("span check").tagName).toBe("SPAN");
  });
});
