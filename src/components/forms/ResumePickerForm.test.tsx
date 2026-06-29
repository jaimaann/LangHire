import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { open } from "@tauri-apps/plugin-dialog";
import ResumePickerForm from "./ResumePickerForm";
import { getSettings, saveSettings } from "../../lib/api";

vi.mock("../../lib/api", () => ({
  getSettings: vi.fn(),
  saveSettings: vi.fn(),
}));

const mockGetSettings = vi.mocked(getSettings);
const mockSaveSettings = vi.mocked(saveSettings);
const mockOpen = vi.mocked(open);

describe("ResumePickerForm", () => {
  beforeEach(() => {
    mockGetSettings.mockResolvedValue({ resume_path: "" } as never);
    mockSaveSettings.mockResolvedValue({ success: true } as never);
    mockOpen.mockResolvedValue(null as never);
  });

  it("shows a loading spinner before settings resolve, then the input", async () => {
    render(<ResumePickerForm />);
    // While loading there is no labelled input yet.
    expect(screen.queryByText("Resume PDF Path")).not.toBeInTheDocument();

    expect(await screen.findByText("Resume PDF Path")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("/path/to/your/resume.pdf")).toBeInTheDocument();
  });

  it("pre-populates the input from existing settings", async () => {
    mockGetSettings.mockResolvedValue({ resume_path: "/home/me/cv.pdf" } as never);
    render(<ResumePickerForm />);

    const input = await screen.findByPlaceholderText("/path/to/your/resume.pdf");
    expect(input).toHaveValue("/home/me/cv.pdf");
  });

  it("debounce-saves a typed path and calls onSaved", async () => {
    const onSaved = vi.fn();
    const user = userEvent.setup();
    render(<ResumePickerForm onSaved={onSaved} />);

    const input = await screen.findByPlaceholderText("/path/to/your/resume.pdf");
    await user.type(input, "/docs/resume.pdf");

    await waitFor(
      () => {
        expect(mockSaveSettings).toHaveBeenCalledWith(
          expect.objectContaining({ resume_path: "/docs/resume.pdf" }),
        );
      },
      { timeout: 2000 },
    );
    expect(onSaved).toHaveBeenCalled();
    expect(await screen.findByText(/Saved/)).toBeInTheDocument();
  });

  it("does not save when the path matches the already-saved value", async () => {
    mockGetSettings.mockResolvedValue({ resume_path: "/same.pdf" } as never);
    const user = userEvent.setup();
    render(<ResumePickerForm />);

    const input = await screen.findByPlaceholderText("/path/to/your/resume.pdf");
    // Re-typing the identical existing value should be a no-op save.
    await user.clear(input);
    await user.type(input, "/same.pdf");

    // Wait past the debounce window.
    await new Promise((r) => setTimeout(r, 1000));
    expect(mockSaveSettings).not.toHaveBeenCalled();
  });

  it("opens the file dialog on Browse and saves the chosen file immediately", async () => {
    mockOpen.mockResolvedValue("/picked/resume.pdf" as never);
    const user = userEvent.setup();
    render(<ResumePickerForm />);

    await screen.findByText("Resume PDF Path");
    await user.click(screen.getByRole("button", { name: /Browse/i }));

    expect(mockOpen).toHaveBeenCalledWith({
      filters: [{ name: "PDF", extensions: ["pdf"] }],
    });

    const input = await screen.findByPlaceholderText("/path/to/your/resume.pdf");
    await waitFor(() => expect(input).toHaveValue("/picked/resume.pdf"));
    await waitFor(() =>
      expect(mockSaveSettings).toHaveBeenCalledWith(
        expect.objectContaining({ resume_path: "/picked/resume.pdf" }),
      ),
    );
  });

  it("does nothing when the Browse dialog is cancelled", async () => {
    mockOpen.mockResolvedValue(null as never);
    const user = userEvent.setup();
    render(<ResumePickerForm />);

    await screen.findByText("Resume PDF Path");
    await user.click(screen.getByRole("button", { name: /Browse/i }));

    await new Promise((r) => setTimeout(r, 100));
    expect(mockSaveSettings).not.toHaveBeenCalled();
    const input = screen.getByPlaceholderText("/path/to/your/resume.pdf");
    expect(input).toHaveValue("");
  });

  it("survives a getSettings failure on load (no crash, empty input)", async () => {
    mockGetSettings.mockRejectedValue(new Error("boom"));
    render(<ResumePickerForm />);

    const input = await screen.findByPlaceholderText("/path/to/your/resume.pdf");
    expect(input).toHaveValue("");
  });

  // ── Drag-and-drop ─────────────────────────────────────────────────────────
  const getDropZone = () =>
    screen.getByRole("button", { name: /Drop a PDF resume here/i });

  it("highlights the drop zone on drag-over", async () => {
    render(<ResumePickerForm />);
    await screen.findByText("Resume PDF Path");

    const zone = getDropZone();
    expect(zone.className).not.toContain("border-primary");
    expect(
      screen.getByText(/Drag & drop a PDF resume here/i),
    ).toBeInTheDocument();

    fireEvent.dragEnter(zone, { dataTransfer: { types: ["Files"] } });
    fireEvent.dragOver(zone, { dataTransfer: { types: ["Files"] } });

    expect(zone.className).toContain("border-primary");
    expect(screen.getByText(/Drop your PDF resume/i)).toBeInTheDocument();
  });

  it("removes the highlight on drag-leave", async () => {
    render(<ResumePickerForm />);
    await screen.findByText("Resume PDF Path");

    const zone = getDropZone();
    fireEvent.dragEnter(zone, { dataTransfer: { types: ["Files"] } });
    expect(zone.className).toContain("border-primary");

    fireEvent.dragLeave(zone, { dataTransfer: { types: ["Files"] } });
    expect(zone.className).not.toContain("border-primary");
  });

  it("saves and shows success when a PDF file is dropped", async () => {
    const onSaved = vi.fn();
    render(<ResumePickerForm onSaved={onSaved} />);
    await screen.findByText("Resume PDF Path");

    const zone = getDropZone();
    const file = new File(["%PDF-1.4"], "resume.pdf", {
      type: "application/pdf",
    });

    fireEvent.drop(zone, { dataTransfer: { files: [file], types: ["Files"] } });

    await waitFor(() =>
      expect(mockSaveSettings).toHaveBeenCalledWith(
        expect.objectContaining({ resume_path: "resume.pdf" }),
      ),
    );
    expect(onSaved).toHaveBeenCalled();
    expect(await screen.findByText(/Saved/)).toBeInTheDocument();
    const input = screen.getByPlaceholderText("/path/to/your/resume.pdf");
    expect(input).toHaveValue("resume.pdf");
  });

  it("uses the real filesystem path when the dropped File exposes one (Tauri)", async () => {
    render(<ResumePickerForm />);
    await screen.findByText("Resume PDF Path");

    const zone = getDropZone();
    const file = new File(["%PDF-1.4"], "resume.pdf", {
      type: "application/pdf",
    });
    Object.defineProperty(file, "path", { value: "/Users/me/resume.pdf" });

    fireEvent.drop(zone, { dataTransfer: { files: [file], types: ["Files"] } });

    await waitFor(() =>
      expect(mockSaveSettings).toHaveBeenCalledWith(
        expect.objectContaining({ resume_path: "/Users/me/resume.pdf" }),
      ),
    );
  });

  it("rejects a non-PDF drop with an error and does not save", async () => {
    render(<ResumePickerForm />);
    await screen.findByText("Resume PDF Path");

    const zone = getDropZone();
    const file = new File(["hello"], "notes.txt", { type: "text/plain" });

    fireEvent.drop(zone, { dataTransfer: { files: [file], types: ["Files"] } });

    expect(await screen.findByText(/Only PDF files are supported/i)).toBeInTheDocument();
    await new Promise((r) => setTimeout(r, 200));
    expect(mockSaveSettings).not.toHaveBeenCalled();
    const input = screen.getByPlaceholderText("/path/to/your/resume.pdf");
    expect(input).toHaveValue("");
  });

  it("accepts a .pdf file even when the MIME type is missing", async () => {
    render(<ResumePickerForm />);
    await screen.findByText("Resume PDF Path");

    const zone = getDropZone();
    const file = new File(["%PDF-1.4"], "MyResume.PDF", { type: "" });

    fireEvent.drop(zone, { dataTransfer: { files: [file], types: ["Files"] } });

    await waitFor(() =>
      expect(mockSaveSettings).toHaveBeenCalledWith(
        expect.objectContaining({ resume_path: "MyResume.PDF" }),
      ),
    );
  });
});
