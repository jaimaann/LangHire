import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import LLMSettingsPage from "./LLMSettings";

// i18n: identity translator so assertions can use raw keys.
vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (k: string) => k, i18n: { changeLanguage: vi.fn() } }),
}));

// LLMSettings is a thin wrapper around the heavy LLMSettingsForm component.
// Mock the child so this test focuses on the page shell (header) only.
vi.mock("../components/forms/LLMSettingsForm", () => ({
  default: () => <div data-testid="llm-settings-form" />,
}));

describe("LLMSettingsPage", () => {
  it("renders the page header (title + subtitle keys)", () => {
    render(<LLMSettingsPage />);
    expect(screen.getByText("title")).toBeInTheDocument();
    expect(screen.getByText("subtitle")).toBeInTheDocument();
  });

  it("renders the LLMSettingsForm child", () => {
    render(<LLMSettingsPage />);
    expect(screen.getByTestId("llm-settings-form")).toBeInTheDocument();
  });
});
