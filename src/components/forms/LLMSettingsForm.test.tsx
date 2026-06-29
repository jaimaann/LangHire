import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import LLMSettingsForm from "./LLMSettingsForm";
import {
  getLLMSettings,
  saveLLMSettings,
  testLLMConnection,
  fetchOllamaModels,
} from "../../lib/api";
import { trackEvent } from "../../lib/analytics";

// i18n: identity translator so assertions can use raw keys.
vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (k: string) => k }),
}));

vi.mock("../../lib/analytics", () => ({
  trackEvent: vi.fn(),
}));

vi.mock("../../lib/api", () => ({
  getLLMSettings: vi.fn(),
  saveLLMSettings: vi.fn(),
  testLLMConnection: vi.fn(),
  fetchOllamaModels: vi.fn(),
}));

const mockGetLLMSettings = vi.mocked(getLLMSettings);
const mockSaveLLMSettings = vi.mocked(saveLLMSettings);
const mockTestLLMConnection = vi.mocked(testLLMConnection);
const mockFetchOllamaModels = vi.mocked(fetchOllamaModels);
const mockTrackEvent = vi.mocked(trackEvent);

const baseSettings = {
  provider: "openrouter",
  openai: { api_key: "", model: "gpt-4o" },
  anthropic: { api_key: "", model: "claude-sonnet-4-5" },
  gemini: { api_key: "", model: "gemini-2.5-pro" },
  bedrock: {
    access_key: "",
    secret_key: "",
    region: "us-west-2",
    model: "us.anthropic.claude-sonnet-4-6",
    auth_mode: "profile",
    profile_name: "default",
  },
  ollama: { base_url: "http://localhost:11434", model: "" },
  openrouter: { api_key: "", model: "qwen/qwen3.6-plus" },
  openai_compatible: { base_url: "", api_key: "", model: "" },
};

// Default global fetch stub → empty OpenRouter list → curated fallback renders.
function stubFetch(data: unknown = { data: [] }) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({ json: async () => data })) as unknown as typeof fetch,
  );
}

describe("LLMSettingsForm", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
    mockGetLLMSettings.mockResolvedValue(structuredClone(baseSettings) as never);
    mockSaveLLMSettings.mockResolvedValue({ success: true } as never);
    mockTestLLMConnection.mockResolvedValue({ success: true, message: "ok" } as never);
    mockFetchOllamaModels.mockResolvedValue({ success: true, models: [] } as never);
    stubFetch();
  });

  it("renders a loading spinner before settings load", async () => {
    render(<LLMSettingsForm />);
    // The provider radios are not present while loading.
    expect(screen.queryByRole("radio")).not.toBeInTheDocument();
    await waitFor(() => expect(mockGetLLMSettings).toHaveBeenCalled());
    await screen.findByText("selectProvider");
  });

  it("renders all provider radios and starts with openrouter selected", async () => {
    render(<LLMSettingsForm />);
    await screen.findByText("selectProvider");

    const radios = screen.getAllByRole("radio");
    expect(radios).toHaveLength(7);
    const openrouter = screen.getByRole("radio", { name: /providers\.openrouter/ });
    expect(openrouter).toBeChecked();
    // OpenRouter config field (api key) is present.
    expect(screen.getByPlaceholderText("sk-or-v1-...")).toBeInTheDocument();
  });

  it("switches provider via radio, renders that provider's config, and immediate-saves", async () => {
    const user = userEvent.setup();
    render(<LLMSettingsForm />);
    await screen.findByText("selectProvider");

    await user.click(screen.getByRole("radio", { name: /providers\.openai\b/ }));

    // OpenAI key placeholder appears.
    expect(await screen.findByPlaceholderText("sk-...")).toBeInTheDocument();
    await waitFor(() =>
      expect(mockSaveLLMSettings).toHaveBeenCalledWith(
        expect.objectContaining({ provider: "openai" }),
      ),
    );
    expect(mockTrackEvent).toHaveBeenCalledWith("llm_provider_configured", {
      provider: "openai",
    });
  });

  it("debounce-saves api key edits (autosave path)", async () => {
    const user = userEvent.setup();
    render(<LLMSettingsForm />);
    await screen.findByText("selectProvider");

    const keyInput = screen.getByPlaceholderText("sk-or-v1-...");
    await user.type(keyInput, "sk-or-v1-abc");

    await waitFor(
      () =>
        expect(mockSaveLLMSettings).toHaveBeenCalledWith(
          expect.objectContaining({
            openrouter: expect.objectContaining({ api_key: "sk-or-v1-abc" }),
          }),
        ),
      { timeout: 2000 },
    );
  });

  it("Test Connection success shows the returned message", async () => {
    mockTestLLMConnection.mockResolvedValue({
      success: true,
      message: "Connected!",
    } as never);
    const user = userEvent.setup();
    render(<LLMSettingsForm />);
    await screen.findByText("selectProvider");

    await user.click(screen.getByRole("button", { name: /status\.testConnection/ }));

    expect(await screen.findByText("Connected!")).toBeInTheDocument();
    expect(mockTestLLMConnection).toHaveBeenCalled();
  });

  it("Test Connection failure shows an error message", async () => {
    mockTestLLMConnection.mockResolvedValue({
      success: false,
      message: "Bad key",
    } as never);
    const user = userEvent.setup();
    render(<LLMSettingsForm />);
    await screen.findByText("selectProvider");

    await user.click(screen.getByRole("button", { name: /status\.testConnection/ }));

    expect(await screen.findByText("Bad key")).toBeInTheDocument();
  });

  it("Test Connection shows the backend's friendly invalid-key message (#48)", async () => {
    mockTestLLMConnection.mockResolvedValue({
      success: false,
      message: "Invalid API key. Please check your key and try again.",
    } as never);
    const user = userEvent.setup();
    render(<LLMSettingsForm />);
    await screen.findByText("selectProvider");

    await user.click(screen.getByRole("button", { name: /status\.testConnection/ }));
    expect(
      await screen.findByText("Invalid API key. Please check your key and try again."),
    ).toBeInTheDocument();
  });

  it("Test Connection rejection surfaces the thrown error message", async () => {
    mockTestLLMConnection.mockRejectedValue(new Error("timeout"));
    const user = userEvent.setup();
    render(<LLMSettingsForm />);
    await screen.findByText("selectProvider");

    await user.click(screen.getByRole("button", { name: /status\.testConnection/ }));
    expect(await screen.findByText("timeout")).toBeInTheDocument();
  });

  describe("OpenRouter custom model", () => {
    it("renders the curated fallback list plus the custom option", async () => {
      render(<LLMSettingsForm />);
      await screen.findByText("selectProvider");

      const select = screen.getByDisplayValue("qwen/qwen3.6-plus");
      const options = within(select).getAllByRole("option");
      // Fallback models + the custom option.
      expect(options.some((o) => o.getAttribute("value") === "__custom__")).toBe(true);
      expect(options.some((o) => o.getAttribute("value") === "openai/gpt-4o")).toBe(true);
    });

    it("selecting the custom option reveals a text input and saves a typed model", async () => {
      const user = userEvent.setup();
      render(<LLMSettingsForm />);
      await screen.findByText("selectProvider");

      const select = screen.getByDisplayValue("qwen/qwen3.6-plus");
      await user.selectOptions(select, "__custom__");

      // Custom text input appears (placeholder is the example custom tag).
      const customInput = await screen.findByPlaceholderText("openai/gpt-oss-120b:free");
      expect(customInput).toBeInTheDocument();
      // Input is bound to the current model value, so clear before typing.
      await user.clear(customInput);
      await user.type(customInput, "openai/gpt-oss-120b:free");

      await waitFor(() =>
        expect(mockSaveLLMSettings).toHaveBeenCalledWith(
          expect.objectContaining({
            openrouter: expect.objectContaining({
              model: "openai/gpt-oss-120b:free",
            }),
          }),
        ),
      );
    });

    it("loading a saved model that is NOT in the known list starts in custom mode", async () => {
      const custom = structuredClone(baseSettings);
      custom.openrouter.model = "some/unknown-model:free";
      mockGetLLMSettings.mockResolvedValue(custom as never);

      render(<LLMSettingsForm />);
      await screen.findByText("selectProvider");

      // The custom input is visible and pre-filled with the unknown model.
      const customInput = await screen.findByPlaceholderText("openai/gpt-oss-120b:free");
      expect(customInput).toHaveValue("some/unknown-model:free");
      // Select reflects the custom sentinel value.
      const select = screen.getByDisplayValue("openrouter.customOption");
      expect(select).toBeInTheDocument();
    });

    it("uses the live vision-model list when the OpenRouter API returns models", async () => {
      stubFetch({
        data: [
          {
            id: "vendor/vision-a",
            name: "Vision A",
            context_length: 32000,
            architecture: { input_modalities: ["text", "image"] },
            pricing: { prompt: "0.000001", completion: "0.000002" },
          },
          {
            id: "vendor/text-only",
            name: "Text Only",
            context_length: 8000,
            architecture: { input_modalities: ["text"] },
            pricing: { prompt: "0", completion: "0" },
          },
        ],
      });

      render(<LLMSettingsForm />);
      await screen.findByText("selectProvider");

      // Vision model should render; text-only filtered out.
      await waitFor(() => {
        expect(screen.getByText(/Vision A/)).toBeInTheDocument();
      });
      expect(screen.queryByText(/Text Only/)).not.toBeInTheDocument();
    });
  });

  describe("provider config fields", () => {
    it("bedrock: toggling auth mode to keys reveals access/secret key inputs", async () => {
      const user = userEvent.setup();
      render(<LLMSettingsForm />);
      await screen.findByText("selectProvider");

      await user.click(screen.getByRole("radio", { name: /providers\.bedrock/ }));
      // Profile mode renders first (profile name input present).
      await screen.findByText("labels.profileName");

      // Switch to access/secret key auth.
      await user.click(screen.getByRole("button", { name: "labels.accessKeySecretKey" }));
      expect(await screen.findByPlaceholderText("AKIA...")).toBeInTheDocument();
    });

    it("ollama: shows a model dropdown when models are discovered", async () => {
      mockFetchOllamaModels.mockResolvedValue({
        success: true,
        models: ["llama3.1", "mistral"],
      } as never);
      const user = userEvent.setup();
      render(<LLMSettingsForm />);
      await screen.findByText("selectProvider");

      await user.click(screen.getByRole("radio", { name: /providers\.ollama/ }));

      // The debounced ollama fetch (500ms) populates a select with options.
      await waitFor(
        () => expect(screen.getByRole("option", { name: "llama3.1" })).toBeInTheDocument(),
        { timeout: 2000 },
      );
    });

    it("gemini: renders API key + model fields and saves on selection", async () => {
      const user = userEvent.setup();
      render(<LLMSettingsForm />);
      await screen.findByText("selectProvider");

      await user.click(screen.getByRole("radio", { name: /providers\.gemini/ }));

      // API key password field appears.
      expect(await screen.findByPlaceholderText("AIza...")).toBeInTheDocument();
      // Model select offers the Gemini models.
      expect(screen.getByRole("option", { name: "gemini-2.5-pro" })).toBeInTheDocument();
      expect(screen.getByRole("option", { name: "gemini-2.5-flash" })).toBeInTheDocument();
      // Switching provider immediate-saves with provider=gemini.
      await waitFor(() =>
        expect(mockSaveLLMSettings).toHaveBeenCalledWith(
          expect.objectContaining({ provider: "gemini" }),
        ),
      );
    });

    it("gemini: editing the API key debounce-saves", async () => {
      const user = userEvent.setup();
      render(<LLMSettingsForm />);
      await screen.findByText("selectProvider");

      await user.click(screen.getByRole("radio", { name: /providers\.gemini/ }));
      const keyInput = await screen.findByPlaceholderText("AIza...");
      await user.type(keyInput, "AIzaABC");

      await waitFor(
        () =>
          expect(mockSaveLLMSettings).toHaveBeenCalledWith(
            expect.objectContaining({
              gemini: expect.objectContaining({ api_key: "AIzaABC" }),
            }),
          ),
        { timeout: 2000 },
      );
    });

    it("openai_compatible: renders base URL and model inputs", async () => {
      const user = userEvent.setup();
      render(<LLMSettingsForm />);
      await screen.findByText("selectProvider");

      await user.click(
        screen.getByRole("radio", { name: /providers\.openai_compatible/ }),
      );
      expect(
        await screen.findByPlaceholderText("https://api.together.xyz/v1"),
      ).toBeInTheDocument();
      expect(
        screen.getByPlaceholderText("meta-llama/Llama-3-70b-chat-hf"),
      ).toBeInTheDocument();
    });
  });
});
