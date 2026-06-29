import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import PageHeader from "./PageHeader";

describe("PageHeader", () => {
  it("renders the title as a heading", () => {
    render(<PageHeader title="Dashboard" />);
    expect(screen.getByRole("heading", { name: "Dashboard" })).toBeInTheDocument();
  });

  it("renders the subtitle when provided", () => {
    render(<PageHeader title="Dashboard" subtitle="Overview of activity" />);
    expect(screen.getByText("Overview of activity")).toBeInTheDocument();
  });

  it("does not render a subtitle paragraph when omitted", () => {
    const { container } = render(<PageHeader title="Dashboard" />);
    expect(container.querySelector("p")).not.toBeInTheDocument();
  });

  it("does not render subtitle for empty-string subtitle (falsy)", () => {
    const { container } = render(<PageHeader title="Dashboard" subtitle="" />);
    expect(container.querySelector("p")).not.toBeInTheDocument();
  });

  it("renders actions when provided", () => {
    render(
      <PageHeader title="Dashboard" actions={<button>New</button>} />,
    );
    expect(screen.getByRole("button", { name: "New" })).toBeInTheDocument();
  });

  it("does not render an actions container when omitted", () => {
    render(<PageHeader title="Dashboard" />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("renders both subtitle and actions together", () => {
    render(
      <PageHeader
        title="Dashboard"
        subtitle="Sub"
        actions={<button>Act</button>}
      />,
    );
    expect(screen.getByText("Sub")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Act" })).toBeInTheDocument();
  });
});
