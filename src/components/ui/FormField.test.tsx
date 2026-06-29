import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import FormField, { InputField } from "./FormField";

describe("FormField", () => {
  it("renders the label and children", () => {
    render(
      <FormField label="Email">
        <input aria-label="email-input" />
      </FormField>,
    );
    expect(screen.getByText("Email")).toBeInTheDocument();
    expect(screen.getByLabelText("email-input")).toBeInTheDocument();
  });

  it("renders the hint when provided", () => {
    render(
      <FormField label="Email" hint="We won't share it">
        <input />
      </FormField>,
    );
    expect(screen.getByText("We won't share it")).toBeInTheDocument();
  });

  it("does not render a hint paragraph when hint is omitted", () => {
    const { container } = render(
      <FormField label="Email">
        <input />
      </FormField>,
    );
    expect(container.querySelector("p")).not.toBeInTheDocument();
  });

  it("does not render hint paragraph for empty-string hint (falsy)", () => {
    const { container } = render(
      <FormField label="Email" hint="">
        <input />
      </FormField>,
    );
    expect(container.querySelector("p")).not.toBeInTheDocument();
  });

  it("renders label inside a <label> element", () => {
    render(
      <FormField label="My Label">
        <input />
      </FormField>,
    );
    expect(screen.getByText("My Label").tagName).toBe("LABEL");
  });

  it("applies a custom className to the wrapper", () => {
    const { container } = render(
      <FormField label="L" className="my-wrap">
        <input />
      </FormField>,
    );
    expect(container.firstChild).toHaveClass("my-wrap");
  });
});

describe("InputField", () => {
  it("renders label and current value", () => {
    render(<InputField label="Name" value="Jamie" onChange={() => {}} />);
    expect(screen.getByText("Name")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Jamie")).toBeInTheDocument();
  });

  it("calls onChange with the new string value as the user types", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<InputField label="Name" value="" onChange={onChange} />);
    await user.type(screen.getByRole("textbox"), "a");
    expect(onChange).toHaveBeenCalledWith("a");
  });

  it("applies the placeholder", () => {
    render(
      <InputField
        label="Name"
        value=""
        onChange={() => {}}
        placeholder="Type here"
      />,
    );
    expect(screen.getByPlaceholderText("Type here")).toBeInTheDocument();
  });

  it("honors the type prop", () => {
    render(
      <InputField label="Password" value="" onChange={() => {}} type="password" />,
    );
    // password inputs have no textbox role; query by label text association via DOM
    const input = screen.getByText("Password").parentElement?.querySelector("input");
    expect(input).toHaveAttribute("type", "password");
  });

  it("defaults to type text", () => {
    render(<InputField label="Name" value="" onChange={() => {}} />);
    expect(screen.getByRole("textbox")).toHaveAttribute("type", "text");
  });

  it("disables the input when disabled is true and blocks typing", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<InputField label="Name" value="" onChange={onChange} disabled />);
    const input = screen.getByRole("textbox");
    expect(input).toBeDisabled();
    await user.type(input, "x");
    expect(onChange).not.toHaveBeenCalled();
  });
});
