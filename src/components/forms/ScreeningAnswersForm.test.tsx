import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ScreeningAnswersForm from "./ScreeningAnswersForm";
import { getCountries, getProfile, saveProfile } from "../../lib/api";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (k: string) => k }),
}));

vi.mock("../../lib/api", () => ({
  getProfile: vi.fn(),
  getCountries: vi.fn(),
  saveProfile: vi.fn(),
}));

const profile = {
  name: "Dhaval Patel", email: "d@example.com", phone: "", country: "IN",
  work_authorization: "", notice_period: "", current_compensation: "",
  visa_sponsorship_needed: false, willing_to_relocate: false,
  salary_expectation: { min: 0, max: 0, currency: "INR", period: "annual" },
};

describe("ScreeningAnswersForm", () => {
  beforeEach(() => {
    vi.mocked(getProfile).mockResolvedValue(profile as never);
    vi.mocked(getCountries).mockResolvedValue({
      success: true, notice_period_options: ["Immediate", "30 days"],
      countries: { IN: { work_auth_options: ["Citizen", "Work visa"], currency: "INR" } },
    } as never);
    vi.mocked(saveProfile).mockResolvedValue({ success: true });
  });

  it("outlines empty fields and saves the answers into the profile", async () => {
    const user = userEvent.setup();
    const onSaved = vi.fn();
    render(<ScreeningAnswersForm onSaved={onSaved} />);
    const phone = (await screen.findByText("personal.phone")).querySelector("input") as HTMLInputElement;
    expect(phone.className).toContain("border-amber-400");
    const name = screen.getByText("personal.fullName").querySelector("input") as HTMLInputElement;
    expect(name.className).not.toContain("border-amber-400");

    await waitFor(() => expect(screen.getByRole("option", { name: "Work visa" })).toBeInTheDocument());
    await user.selectOptions(screen.getByText("work.workAuth").querySelector("select") as HTMLSelectElement, "Work visa");
    await user.type(screen.getByText("salary.current").querySelector("input") as HTMLInputElement, "INR 3,60,000");
    await user.click(screen.getByText("work.willingToRelocate").querySelector("input") as HTMLInputElement);
    await user.click(screen.getByRole("button", { name: "screening.save" }));

    await waitFor(() => expect(saveProfile).toHaveBeenCalled());
    const saved = vi.mocked(saveProfile).mock.calls[0][0];
    expect(saved).toMatchObject({
      name: "Dhaval Patel", work_authorization: "Work visa",
      current_compensation: "INR 3,60,000", willing_to_relocate: true,
    });
    expect(onSaved).toHaveBeenCalled();
    expect(await screen.findByText("screening.saved")).toBeInTheDocument();
  });

  it("explains when the profile cannot be loaded", async () => {
    vi.mocked(getProfile).mockRejectedValue(new Error("offline"));
    render(<ScreeningAnswersForm />);
    expect(await screen.findByText("screening.unavailable")).toBeInTheDocument();
  });
});
