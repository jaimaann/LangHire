import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AutomationDialog from "./AutomationDialog";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (k: string) => k, i18n: { changeLanguage: vi.fn() } }),
}));

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
    expect(screen.getByText("automation.slowTitle")).toBeInTheDocument();
    expect(screen.getByText("automation.loginTitle")).toBeInTheDocument();
    expect(screen.getByText("automation.windowTitle")).toBeInTheDocument();
  });

  it("calls onConfirm when the start button is clicked", async () => {
    const user = userEvent.setup();
    const { onConfirm, onCancel } = renderDialog();
    await user.click(screen.getByRole("button", { name: "automation.start" }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(onCancel).not.toHaveBeenCalled();
  });

  it("calls onCancel when the Cancel button is clicked", async () => {
    const user = userEvent.setup();
    const { onCancel, onConfirm } = renderDialog();
    // the X close button shares the accessible name; the footer button is the last one
    const cancels = screen.getAllByRole("button", { name: "automation.cancel" });
    await user.click(cancels[cancels.length - 1]);
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
    await user.click(screen.getByText("automation.slowTitle"));
    expect(onCancel).not.toHaveBeenCalled();
  });
});
