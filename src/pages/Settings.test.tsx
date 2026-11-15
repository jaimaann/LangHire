import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import SettingsPage from "./Settings";
import {
  getSettings,
  saveSettings,
  getPlugins,
  togglePlugin,
  removePlugin,
  importPlugin,
  deleteAllData,
  exportAllData,
} from "../lib/api";
import { setTelemetryEnabled, hasTelemetryConsent } from "../lib/analytics";
import { clearLocalAppData, restartApp, downloadJson } from "../lib/privacy";
import { open as openDialog } from "@tauri-apps/plugin-dialog";

// jsdom in this config does not provide a working localStorage; polyfill it.
function installLocalStorage() {
  const store = new Map<string, string>();
  vi.stubGlobal("localStorage", {
    getItem: (k: string) => (store.has(k) ? store.get(k)! : null),
    setItem: (k: string, v: string) => void store.set(k, String(v)),
    removeItem: (k: string) => void store.delete(k),
    clear: () => store.clear(),
    key: (i: number) => [...store.keys()][i] ?? null,
    get length() {
      return store.size;
    },
  });
}

// i18n: identity translator so assertions can use raw keys.
vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (k: string) => k, i18n: { changeLanguage: vi.fn() } }),
}));

vi.mock("../lib/analytics", () => ({
  setTelemetryEnabled: vi.fn(),
  hasTelemetryConsent: vi.fn(() => true),
}));

vi.mock("../lib/privacy", () => ({
  clearLocalAppData: vi.fn(),
  restartApp: vi.fn(),
  downloadJson: vi.fn(),
  exportFileName: () => "langhire-export-2026-11-14.json",
}));

// loadLanguage performs dynamic i18n resource loading — stub it out.
vi.mock("../i18n", () => ({
  loadLanguage: vi.fn(async () => {}),
}));

vi.mock("../lib/api", () => ({
  getSettings: vi.fn(),
  saveSettings: vi.fn(),
  getPlugins: vi.fn(),
  togglePlugin: vi.fn(),
  removePlugin: vi.fn(),
  importPlugin: vi.fn(),
  deleteAllData: vi.fn(),
  exportAllData: vi.fn(),
}));

const mockGetSettings = vi.mocked(getSettings);
const mockSaveSettings = vi.mocked(saveSettings);
const mockGetPlugins = vi.mocked(getPlugins);
const mockTogglePlugin = vi.mocked(togglePlugin);
const mockRemovePlugin = vi.mocked(removePlugin);
const mockImportPlugin = vi.mocked(importPlugin);
const mockSetTelemetry = vi.mocked(setTelemetryEnabled);
const mockOpenDialog = vi.mocked(openDialog);
const mockHasConsent = vi.mocked(hasTelemetryConsent);
const mockDeleteAllData = vi.mocked(deleteAllData);
const mockExportAllData = vi.mocked(exportAllData);
const mockClearLocal = vi.mocked(clearLocalAppData);
const mockRestartApp = vi.mocked(restartApp);
const mockDownloadJson = vi.mocked(downloadJson);

const baseSettings = {
  resume_path: "/home/me/resume.pdf",
  blocked_domains: ["spam.com"],
  sensitive_data: { email: "me@example.com", password: "secret" },
  max_failures: 8,
  data_dir: "/data",
  stagger_delay: 5,
  telemetry_enabled: true,
};

const builtinPlugin = {
  name: "linkedin",
  display_name: "LinkedIn",
  version: "1.0.0",
  author: "core",
  description: "LinkedIn jobs",
  countries: ["US", "GB"],
  website: "https://linkedin.com",
  requires_login: true,
  login_url: "https://linkedin.com/login",
  is_builtin: true,
  enabled: true,
  filters: [],
};

const communityPlugin = {
  ...builtinPlugin,
  name: "acme",
  display_name: "Acme Jobs",
  is_builtin: false,
  enabled: false,
};

describe("SettingsPage", () => {
  beforeEach(() => {
    installLocalStorage();
    mockGetSettings.mockResolvedValue(structuredClone(baseSettings) as never);
    mockSaveSettings.mockResolvedValue({ success: true } as never);
    mockGetPlugins.mockResolvedValue({
      success: true,
      plugins: [structuredClone(builtinPlugin), structuredClone(communityPlugin)],
    } as never);
    mockTogglePlugin.mockResolvedValue({ success: true } as never);
    mockRemovePlugin.mockResolvedValue({ success: true } as never);
    mockImportPlugin.mockResolvedValue({
      success: true,
      plugin: { name: "new", display_name: "New" },
    } as never);
    mockOpenDialog.mockResolvedValue(null as never);
    mockHasConsent.mockReturnValue(true);
    mockDeleteAllData.mockReset();
    mockExportAllData.mockReset();
    mockClearLocal.mockClear();
    mockRestartApp.mockClear();
    mockDownloadJson.mockClear();
    mockSaveSettings.mockClear();
    mockSetTelemetry.mockClear();
  });

  it("shows a loading spinner before settings load", () => {
    render(<SettingsPage />);
    // Save Settings button is not rendered while loading.
    expect(screen.queryByRole("button", { name: /Save Settings/ })).not.toBeInTheDocument();
  });

  it("loads and renders the settings values", async () => {
    render(<SettingsPage />);
    expect(await screen.findByDisplayValue("/home/me/resume.pdf")).toBeInTheDocument();
    expect(screen.getByDisplayValue("me@example.com")).toBeInTheDocument();
    expect(screen.getByDisplayValue("secret")).toBeInTheDocument();
    expect(screen.getByDisplayValue(8)).toBeInTheDocument();
    // Blocked domain tag renders.
    expect(screen.getByText("spam.com")).toBeInTheDocument();
  });

  it("renders plugins, builtin badge, and the community remove button", async () => {
    render(<SettingsPage />);
    expect(await screen.findByText("LinkedIn")).toBeInTheDocument();
    expect(screen.getByText("Acme Jobs")).toBeInTheDocument();
    expect(screen.getByText("Built-in")).toBeInTheDocument();
  });

  it("saves settings with the current field values", async () => {
    const user = userEvent.setup();
    render(<SettingsPage />);
    await screen.findByDisplayValue("/home/me/resume.pdf");

    await user.click(screen.getByRole("button", { name: /Save Settings/ }));

    await waitFor(() =>
      expect(mockSaveSettings).toHaveBeenCalledWith(
        expect.objectContaining({
          resume_path: "/home/me/resume.pdf",
          blocked_domains: ["spam.com"],
          sensitive_data: { email: "me@example.com", password: "secret" },
          max_failures: 8,
          telemetry_enabled: true,
        }),
      ),
    );
    // Button text flips to "Saved".
    expect(await screen.findByText("Saved")).toBeInTheDocument();
  });

  it("shows an error banner when saving fails", async () => {
    mockSaveSettings.mockRejectedValue(new Error("boom"));
    const user = userEvent.setup();
    render(<SettingsPage />);
    await screen.findByDisplayValue("/home/me/resume.pdf");

    await user.click(screen.getByRole("button", { name: /Save Settings/ }));
    expect(await screen.findByText("Failed to save settings. Please try again.")).toBeInTheDocument();
  });

  it("toggles telemetry and updates the analytics module", async () => {
    const user = userEvent.setup();
    render(<SettingsPage />);
    await screen.findByDisplayValue("/home/me/resume.pdf");

    // The telemetry toggle lives in the "Usage Analytics" section. Find the
    // checkbox in the same row as that label (avoids matching plugin toggles).
    const analyticsRow = screen.getByText("telemetry.usageAnalytics").closest("div")!
      .parentElement! as HTMLElement;
    const telemetryToggle = within(analyticsRow).getByRole("checkbox");
    expect(telemetryToggle).toBeChecked();
    await user.click(telemetryToggle);
    expect(mockSetTelemetry).toHaveBeenCalledWith(false);
    // Kept in sync with the backend immediately.
    await waitFor(() => expect(mockSaveSettings).toHaveBeenCalledWith({ telemetry_enabled: false }));
  });

  it("toggles a plugin on/off via the API", async () => {
    const user = userEvent.setup();
    render(<SettingsPage />);
    await screen.findByText("Acme Jobs");

    // The community plugin starts disabled (unchecked); toggle it on.
    const checkboxes = screen.getAllByRole("checkbox");
    const acmeToggle = checkboxes.find((c) => !(c as HTMLInputElement).checked);
    await user.click(acmeToggle!);
    await waitFor(() => expect(mockTogglePlugin).toHaveBeenCalledWith("acme", true));
  });

  it("removes a community plugin", async () => {
    const user = userEvent.setup();
    render(<SettingsPage />);
    await screen.findByText("Acme Jobs");

    // Only the community plugin has a remove (Trash) button.
    const acmeRow = screen.getByText("Acme Jobs").closest("div.flex.items-center.justify-between") as HTMLElement;
    const removeButtons = within(acmeRow)
      .getAllByRole("button")
      .filter((b) => b.querySelector("svg.lucide-trash2") || b.className.includes("text-destructive"));
    await user.click(removeButtons[0]);
    await waitFor(() => expect(mockRemovePlugin).toHaveBeenCalledWith("acme"));
    await waitFor(() => expect(screen.queryByText("Acme Jobs")).not.toBeInTheDocument());
  });

  it("adds a blocked domain via the tag input", async () => {
    const user = userEvent.setup();
    render(<SettingsPage />);
    await screen.findByDisplayValue("/home/me/resume.pdf");

    const tagInput = screen.getByPlaceholderText("example.com");
    await user.type(tagInput, "blocked.io{Enter}");
    expect(await screen.findByText("blocked.io")).toBeInTheDocument();
  });

  it("imports a plugin when a file is chosen", async () => {
    mockOpenDialog.mockResolvedValue("/path/to/plugin.yaml" as never);
    const user = userEvent.setup();
    render(<SettingsPage />);
    await screen.findByText("Acme Jobs");

    await user.click(screen.getByRole("button", { name: /Import Plugin/ }));
    await waitFor(() => expect(mockImportPlugin).toHaveBeenCalledWith("/path/to/plugin.yaml"));
    // Plugins reload after import.
    await waitFor(() => expect(mockGetPlugins).toHaveBeenCalledTimes(2));
  });

  it("browses for a resume file and updates the path", async () => {
    mockOpenDialog.mockResolvedValue("/new/resume.pdf" as never);
    const user = userEvent.setup();
    render(<SettingsPage />);
    await screen.findByDisplayValue("/home/me/resume.pdf");

    await user.click(screen.getByRole("button", { name: /Browse/ }));
    expect(await screen.findByDisplayValue("/new/resume.pdf")).toBeInTheDocument();
  });

  it("renders the theme toggle and persists a selection (#41)", async () => {
    const user = userEvent.setup();
    render(<SettingsPage />);
    await screen.findByDisplayValue("/home/me/resume.pdf");

    const dark = screen.getByRole("radio", { name: /appearance\.dark/ });
    expect(screen.getByRole("radio", { name: /appearance\.light/ })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /appearance\.system/ })).toBeInTheDocument();

    await user.click(dark);
    // Applies immediately and mirrors to the backend.
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    await waitFor(() => expect(mockSaveSettings).toHaveBeenCalledWith({ theme: "dark" }));
    expect(dark).toHaveAttribute("aria-checked", "true");

    // Clean up the global <html> class so other tests aren't affected.
    document.documentElement.classList.remove("dark");
  });

  it("applies a theme loaded from backend settings (#41)", async () => {
    mockGetSettings.mockResolvedValue({ ...baseSettings, theme: "dark" } as never);
    render(<SettingsPage />);
    await screen.findByDisplayValue("/home/me/resume.pdf");
    await waitFor(() => expect(document.documentElement.classList.contains("dark")).toBe(true));
    document.documentElement.classList.remove("dark");
  });

  it("shows telemetry OFF when the backend says on but this device never consented", async () => {
    mockHasConsent.mockReturnValue(false);
    render(<SettingsPage />);
    await screen.findByDisplayValue("/home/me/resume.pdf");
    expect(screen.getByRole("checkbox", { name: "telemetry.usageAnalytics" })).not.toBeChecked();
  });

  it("shows telemetry OFF when telemetry_enabled is absent (opt-in default)", async () => {
    const { telemetry_enabled: _omit, ...rest } = baseSettings;
    void _omit;
    mockGetSettings.mockResolvedValue(rest as never);
    render(<SettingsPage />);
    await screen.findByDisplayValue("/home/me/resume.pdf");
    expect(screen.getByRole("checkbox", { name: "telemetry.usageAnalytics" })).not.toBeChecked();
  });

  describe("Privacy & data", () => {
    it("defaults log retention to 14 days and persists a new choice", async () => {
      const user = userEvent.setup();
      render(<SettingsPage />);
      await screen.findByDisplayValue("/home/me/resume.pdf");

      const select = screen.getByLabelText("privacy.retentionLabel") as HTMLSelectElement;
      expect(select.value).toBe("14");
      expect(Array.from(select.options).map((o) => o.value)).toEqual(["0", "7", "14", "30", "90"]);

      await user.selectOptions(select, "0");
      await waitFor(() => expect(mockSaveSettings).toHaveBeenCalledWith({ log_retention_days: 0 }));
      expect(select.value).toBe("0");

      await user.selectOptions(select, "90");
      await waitFor(() => expect(mockSaveSettings).toHaveBeenCalledWith({ log_retention_days: 90 }));
    });

    it("loads a saved retention value and includes it in Save Settings", async () => {
      mockGetSettings.mockResolvedValue({ ...baseSettings, log_retention_days: 30 } as never);
      const user = userEvent.setup();
      render(<SettingsPage />);
      await screen.findByDisplayValue("/home/me/resume.pdf");
      expect((screen.getByLabelText("privacy.retentionLabel") as HTMLSelectElement).value).toBe("30");

      await user.click(screen.getByRole("button", { name: /Save Settings/ }));
      await waitFor(() =>
        expect(mockSaveSettings).toHaveBeenCalledWith(expect.objectContaining({ log_retention_days: 30 })),
      );
    });

    it("requires an in-page confirmation before deleting all data", async () => {
      const confirmSpy = vi.spyOn(window, "confirm");
      mockDeleteAllData.mockResolvedValue({ ok: true, deleted: ["profile", "jobs"] } as never);
      const user = userEvent.setup();
      render(<SettingsPage />);
      await screen.findByDisplayValue("/home/me/resume.pdf");

      await user.click(screen.getByRole("button", { name: /privacy\.deleteButton/ }));
      // First click only reveals the confirmation — nothing deleted yet.
      expect(mockDeleteAllData).not.toHaveBeenCalled();
      expect(screen.getByRole("alertdialog")).toBeInTheDocument();
      expect(screen.getByText("privacy.deleteConfirm")).toBeInTheDocument();

      await user.click(screen.getByRole("button", { name: /privacy\.deleteConfirmButton/ }));
      await waitFor(() => expect(mockDeleteAllData).toHaveBeenCalledTimes(1));
      await waitFor(() => expect(mockClearLocal).toHaveBeenCalled());
      expect(mockRestartApp).toHaveBeenCalled();
      expect(confirmSpy).not.toHaveBeenCalled();
    });

    it("cancel dismisses the confirmation without deleting", async () => {
      const user = userEvent.setup();
      render(<SettingsPage />);
      await screen.findByDisplayValue("/home/me/resume.pdf");

      await user.click(screen.getByRole("button", { name: /privacy\.deleteButton/ }));
      await user.click(screen.getByRole("button", { name: /privacy\.cancel/ }));
      expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
      expect(mockDeleteAllData).not.toHaveBeenCalled();
      expect(mockRestartApp).not.toHaveBeenCalled();
    });

    it("shows an error and keeps local data when deletion fails", async () => {
      mockDeleteAllData.mockRejectedValue(new Error("API Error 500"));
      const user = userEvent.setup();
      render(<SettingsPage />);
      await screen.findByDisplayValue("/home/me/resume.pdf");

      await user.click(screen.getByRole("button", { name: /privacy\.deleteButton/ }));
      await user.click(screen.getByRole("button", { name: /privacy\.deleteConfirmButton/ }));
      expect(await screen.findByText("privacy.deleteFailed")).toBeInTheDocument();
      expect(mockClearLocal).not.toHaveBeenCalled();
      expect(mockRestartApp).not.toHaveBeenCalled();
    });

    it("exports all data as a dated JSON file", async () => {
      const payload = { profile: { name: "A" }, jobs: [] };
      mockExportAllData.mockResolvedValue(payload as never);
      const user = userEvent.setup();
      render(<SettingsPage />);
      await screen.findByDisplayValue("/home/me/resume.pdf");

      await user.click(screen.getByRole("button", { name: /privacy\.exportButton/ }));
      await waitFor(() =>
        expect(mockDownloadJson).toHaveBeenCalledWith(payload, "langhire-export-2026-11-14.json"),
      );
    });

    it("surfaces an export failure", async () => {
      mockExportAllData.mockRejectedValue(new Error("nope"));
      const user = userEvent.setup();
      render(<SettingsPage />);
      await screen.findByDisplayValue("/home/me/resume.pdf");

      await user.click(screen.getByRole("button", { name: /privacy\.exportButton/ }));
      expect(await screen.findByText("privacy.exportFailed")).toBeInTheDocument();
      expect(mockDownloadJson).not.toHaveBeenCalled();
    });
  });
});
