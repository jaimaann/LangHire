import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import LogLine, { getLogLineColor } from "./LogLine";

describe("getLogLineColor", () => {
  it.each([
    ["✅ done", "text-green-400"],
    ["💾 saved", "text-green-400"],
    ["❌ failed", "text-red-400"],
    ["📍 location", "text-cyan-400 font-semibold mt-2"],
    ["🎯 target", "text-yellow-300"],
    ["👍 good", "text-green-300"],
    ["🧠 thinking", "text-purple-400"],
    ["▶️ start", "text-gray-500"],
    ["🖱️ click", "text-gray-500"],
    ["⚠️ warn", "text-amber-400"],
    ["🤖 bot", "text-blue-400"],
  ])("maps %s to its color class", (line, expected) => {
    expect(getLogLineColor(line)).toBe(expected);
  });

  it("returns an empty string for a plain line", () => {
    expect(getLogLineColor("just text")).toBe("");
  });

  it("returns an empty string for an empty line", () => {
    expect(getLogLineColor("")).toBe("");
  });

  it("prioritizes success (✅/💾) over later checks", () => {
    // Contains both ✅ and ❌ — success is checked first.
    expect(getLogLineColor("✅ then ❌")).toBe("text-green-400");
  });
});

describe("LogLine component", () => {
  it("renders the line text", () => {
    render(<LogLine line="hello world" />);
    expect(screen.getByText("hello world")).toBeInTheDocument();
  });

  it("applies the color class for a matching emoji", () => {
    render(<LogLine line="❌ broke" />);
    expect(screen.getByText("❌ broke")).toHaveClass("text-red-400");
  });

  it("always applies the leading-relaxed base class", () => {
    render(<LogLine line="plain line" />);
    expect(screen.getByText("plain line")).toHaveClass("leading-relaxed");
  });

  it("renders an empty line without crashing", () => {
    const { container } = render(<LogLine line="" />);
    const div = container.firstChild as HTMLElement;
    expect(div).toBeInTheDocument();
    expect(div).toHaveClass("leading-relaxed");
  });
});
