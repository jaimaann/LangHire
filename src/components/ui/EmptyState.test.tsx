import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import EmptyState from "./EmptyState";
import { Inbox } from "lucide-react";

describe("EmptyState", () => {
  it("renders title and description", () => {
    render(
      <EmptyState icon={Inbox} title="No items" description="Nothing here yet." />,
    );
    expect(screen.getByRole("heading", { name: "No items" })).toBeInTheDocument();
    expect(screen.getByText("Nothing here yet.")).toBeInTheDocument();
  });

  it("renders the provided icon", () => {
    const { container } = render(
      <EmptyState icon={Inbox} title="T" description="D" />,
    );
    // lucide icons render an <svg>
    expect(container.querySelector("svg")).toBeInTheDocument();
  });

  it("does not render an action node when action is omitted", () => {
    render(<EmptyState icon={Inbox} title="T" description="D" />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("renders the action node when provided", () => {
    render(
      <EmptyState
        icon={Inbox}
        title="T"
        description="D"
        action={<button>Do thing</button>}
      />,
    );
    expect(screen.getByRole("button", { name: "Do thing" })).toBeInTheDocument();
  });

  it("handles empty string title and description", () => {
    const { container } = render(
      <EmptyState icon={Inbox} title="" description="" />,
    );
    const heading = container.querySelector("h3");
    expect(heading).toBeInTheDocument();
    expect(heading).toHaveTextContent("");
  });
});
