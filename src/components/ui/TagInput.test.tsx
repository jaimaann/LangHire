import { describe, it, expect, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import TagInput from "./TagInput";

/**
 * A controlled wrapper that mirrors how TagInput is used in the app:
 * the parent owns `tags` + the input `value` and wires up add/remove with
 * duplicate prevention. This lets us exercise the real interaction flow.
 */
function ControlledTagInput({
  initialTags = [],
  variant,
}: {
  initialTags?: string[];
  variant?: "default" | "destructive";
}) {
  const [tags, setTags] = useState<string[]>(initialTags);
  const [value, setValue] = useState("");

  const handleAdd = () => {
    const trimmed = value.trim();
    if (!trimmed) return;
    if (tags.includes(trimmed)) {
      setValue("");
      return;
    }
    setTags([...tags, trimmed]);
    setValue("");
  };

  const handleRemove = (tag: string) => setTags(tags.filter((t) => t !== tag));

  return (
    <TagInput
      tags={tags}
      value={value}
      onChange={setValue}
      onAdd={handleAdd}
      onRemove={handleRemove}
      variant={variant}
    />
  );
}

describe("TagInput", () => {
  it("renders existing tags", () => {
    render(<ControlledTagInput initialTags={["react", "vite"]} />);
    expect(screen.getByText("react")).toBeInTheDocument();
    expect(screen.getByText("vite")).toBeInTheDocument();
  });

  it("calls onChange as the user types", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(
      <TagInput
        tags={[]}
        value=""
        onChange={onChange}
        onAdd={() => {}}
        onRemove={() => {}}
      />,
    );
    await user.type(screen.getByRole("textbox"), "x");
    expect(onChange).toHaveBeenCalledWith("x");
  });

  it("adds a tag when Enter is pressed", async () => {
    const user = userEvent.setup();
    render(<ControlledTagInput />);
    const input = screen.getByRole("textbox");
    await user.type(input, "typescript{Enter}");
    expect(screen.getByText("typescript")).toBeInTheDocument();
    // input cleared after add
    expect(input).toHaveValue("");
  });

  it("adds a tag when the add button is clicked", async () => {
    const user = userEvent.setup();
    render(<ControlledTagInput />);
    await user.type(screen.getByRole("textbox"), "golang");
    await user.click(screen.getByRole("button"));
    expect(screen.getByText("golang")).toBeInTheDocument();
  });

  it("prevents duplicate tags", async () => {
    const user = userEvent.setup();
    render(<ControlledTagInput initialTags={["react"]} />);
    await user.type(screen.getByRole("textbox"), "react{Enter}");
    expect(screen.getAllByText("react")).toHaveLength(1);
  });

  it("removes a tag when its remove button is clicked", async () => {
    const user = userEvent.setup();
    render(<ControlledTagInput initialTags={["react", "vite"]} />);
    // the tag span containing "vite" — find its remove button
    const tagSpan = screen.getByText("vite").closest("span") as HTMLElement;
    const removeBtn = within(tagSpan).getByRole("button");
    await user.click(removeBtn);
    expect(screen.queryByText("vite")).not.toBeInTheDocument();
    expect(screen.getByText("react")).toBeInTheDocument();
  });

  it("does not add when Enter pressed with empty/whitespace input", async () => {
    const user = userEvent.setup();
    render(<ControlledTagInput />);
    const input = screen.getByRole("textbox");
    await user.type(input, "   {Enter}");
    // no tag chips rendered (only the add button remains)
    const buttons = screen.getAllByRole("button");
    expect(buttons).toHaveLength(1); // just the "+" add button
  });

  it("renders the provided placeholder", () => {
    render(
      <TagInput
        tags={[]}
        value=""
        onChange={() => {}}
        onAdd={() => {}}
        onRemove={() => {}}
        placeholder="Add a skill"
      />,
    );
    expect(screen.getByPlaceholderText("Add a skill")).toBeInTheDocument();
  });

  it("uses the default placeholder when none given", () => {
    render(
      <TagInput
        tags={[]}
        value=""
        onChange={() => {}}
        onAdd={() => {}}
        onRemove={() => {}}
      />,
    );
    expect(screen.getByPlaceholderText("Add...")).toBeInTheDocument();
  });

  it("calls onAdd when add button clicked (raw, uncontrolled)", async () => {
    const onAdd = vi.fn();
    const user = userEvent.setup();
    render(
      <TagInput
        tags={[]}
        value="something"
        onChange={() => {}}
        onAdd={onAdd}
        onRemove={() => {}}
      />,
    );
    await user.click(screen.getByRole("button"));
    expect(onAdd).toHaveBeenCalledTimes(1);
  });

  it("applies destructive variant styles to tags", () => {
    render(<ControlledTagInput initialTags={["danger"]} variant="destructive" />);
    const tagSpan = screen.getByText("danger").closest("span");
    expect(tagSpan).toHaveClass("bg-[#FFF0F0]");
    expect(tagSpan).toHaveClass("text-destructive");
  });

  it("applies default variant styles to tags", () => {
    render(<ControlledTagInput initialTags={["safe"]} />);
    const tagSpan = screen.getByText("safe").closest("span");
    expect(tagSpan).toHaveClass("bg-secondary");
    expect(tagSpan).toHaveClass("text-foreground");
  });
});
