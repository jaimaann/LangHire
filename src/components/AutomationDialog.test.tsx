import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AutomationDialog from "./AutomationDialog";

function renderDialog(overrides: Partial<React.ComponentProps<typeof AutomationDialog>> = {}) {
  const onConfirm = vi.fn();
  const onCancel = vi.fn();
  const props = {
    open: true,
    title: "Start Automation",
    onConfirm,
    onCancel,
    ...overrides,
  };
  render(<AutomationDialog {...props} />);
  return { onConfirm, onCancel };
}

describe("AutomationDialog", () => {
  it("renders nothing when open is false", () => {
    const { onConfirm, onCancel } = renderDialog({ open: false });
    expect(screen.queryByRole("heading")).not.toBeInTheDocument();
    expect(onConfirm).not.toHaveBeenCalled();
    expect(onCancel).not.toHaveBeenCalled();
  });

  it("renders the title and informational sections when open", () => {
    renderDialog({ title: "Apply to Jobs" });
    expect(screen.getByRole("heading", { name: "Apply to Jobs" })).toBeInTheDocument();
    expect(screen.getByText("This may take a while")).toBeInTheDocument();
    expect(screen.getByText("First-time login required")).toBeInTheDocument();
    expect(screen.getByText("Keep the browser window open")).toBeInTheDocument();
  });

  it("calls onConfirm when the start button is clicked", async () => {
    const user = userEvent.setup();
    const { onConfirm, onCancel } = renderDialog();
    await user.click(screen.getByRole("button", { name: "Got it, Start" }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(onCancel).not.toHaveBeenCalled();
  });

  it("calls onCancel when the Cancel button is clicked", async () => {
    const user = userEvent.setup();
    const { onCancel, onConfirm } = renderDialog();
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("calls onCancel when the X (close) button is clicked", async () => {
    const user = userEvent.setup();
    const { onCancel } = renderDialog();
    // The X button is the first button (icon-only, no accessible name beyond the svg).
    const buttons = screen.getAllByRole("button");
    // Close (X), Cancel, Got it, Start
    await user.click(buttons[0]);
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("calls onCancel when clicking the backdrop overlay", async () => {
    const user = userEvent.setup();
    const { onCancel } = renderDialog();
    // Backdrop is the outermost container; clicking the heading region must NOT close.
    const heading = screen.getByRole("heading", { name: "Start Automation" });
    const backdrop = heading.closest("div.fixed");
    expect(backdrop).not.toBeNull();
    await user.click(backdrop as HTMLElement);
    expect(onCancel).toHaveBeenCalled();
  });

  it("does NOT call onCancel when clicking inside the dialog body (stopPropagation)", async () => {
    const user = userEvent.setup();
    const { onCancel } = renderDialog();
    await user.click(screen.getByText("This may take a while"));
    expect(onCancel).not.toHaveBeenCalled();
  });
});
