import { useState, useEffect, useRef, useCallback } from "react";
import { TestTube, CheckCircle, XCircle, Loader2, ChevronDown, ChevronUp, ExternalLink } from "lucide-react";
import { getLLMSettings, saveLLMSettings, testLLMConnection, fetchOllamaModels } from "../../lib/api";
import type { LLMProvider, LLMSettings } from "../../lib/types";

const PROVIDERS: { id: LLMProvider; name: string; description: string }[] = [
  { id: "openai", name: "OpenAI", description: "GPT-4o, GPT-4o-mini, and other OpenAI models" },
  { id: "anthropic", name: "Anthropic", description: "Claude Sonnet, Haiku, and Opus models (direct API)" },
  { id: "bedrock", name: "AWS Bedrock", description: "Claude and other models via AWS Bedrock" },
  { id: "ollama", name: "Ollama", description: "Run open-source models locally — no API key needed" },
  { id: "openrouter", name: "OpenRouter", description: "100+ models (GPT, Claude, Gemini, Llama, Mistral) via a single API key" },
];

const OPENAI_MODELS = ["gpt-5.4-nano", "gpt-5.4-mini", "gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"];
const ANTHROPIC_MODELS = ["claude-sonnet-4-20250514", "claude-haiku-4-20250414", "claude-opus-4-20250514"];
const OPENROUTER_MODELS = [
  "openai/gpt-4o",
  "openai/gpt-4.1",
  "openai/gpt-4.1-mini",
  "anthropic/claude-sonnet-4",
  "anthropic/claude-haiku-4",
  "google/gemini-2.5-pro-preview",
  "google/gemini-2.5-flash-preview",
  "meta-llama/llama-4-maverick",
  "mistralai/mistral-large-2411",
  "qwen/qwen2.5-vl-72b-instruct",
];
const BEDROCK_MODELS = [
  "us.anthropic.claude-sonnet-4-6",
  "us.anthropic.claude-haiku-4-6",
  "anthropic.claude-3-5-sonnet-20241022-v2:0",
  "anthropic.claude-3-haiku-20240307-v1:0",
];

const defaultSettings: LLMSettings = {
  provider: "openai",
  openai: { api_key: "", model: "gpt-4o" },
  anthropic: { api_key: "", model: "claude-sonnet-4-20250514" },
  bedrock: { access_key: "", secret_key: "", region: "us-west-2", model: "us.anthropic.claude-sonnet-4-6", auth_mode: "profile", profile_name: "default" },
  ollama: { base_url: "http://localhost:11434", model: "" },
  openrouter: { api_key: "", model: "openai/gpt-4o" },
};

interface LLMSettingsFormProps {
  onSaved?: () => void;
  compact?: boolean;
}

export default function LLMSettingsForm({ onSaved, compact }: LLMSettingsFormProps) {
  const [settings, setSettings] = useState<LLMSettings>(defaultSettings);
  const [testStatus, setTestStatus] = useState<"idle" | "testing" | "success" | "error">("idle");
  const [testMessage, setTestMessage] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(true);
  const [showGuide, setShowGuide] = useState(false);
  const [ollamaModels, setOllamaModels] = useState<string[]>([]);
  const [ollamaFetching, setOllamaFetching] = useState(false);
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const ollamaFetchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    getLLMSettings()
      .then((data) => setSettings({ ...defaultSettings, ...data }))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    return () => {
      if (saveTimer.current) clearTimeout(saveTimer.current);
      if (ollamaFetchTimer.current) clearTimeout(ollamaFetchTimer.current);
    };
  }, []);

  const loadOllamaModels = useCallback((baseUrl: string) => {
    if (ollamaFetchTimer.current) clearTimeout(ollamaFetchTimer.current);
    ollamaFetchTimer.current = setTimeout(async () => {
      if (!baseUrl.trim()) return;
      setOllamaFetching(true);
      try {
        const result = await fetchOllamaModels(baseUrl);
        if (result.success) setOllamaModels(result.models);
      } catch { /* server unreachable */ }
      finally { setOllamaFetching(false); }
    }, 500);
  }, []);

  useEffect(() => {
    if (settings.provider === "ollama" && settings.ollama?.base_url) {
      loadOllamaModels(settings.ollama.base_url);
    }
  }, [settings.provider, settings.ollama?.base_url, loadOllamaModels]);

  // Autosave with debounce
  const autoSave = useCallback((newSettings: LLMSettings) => {
    setSaved(false);
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(async () => {
      setSaving(true);
      try {
        await saveLLMSettings(newSettings);
        setSaved(true);
        setTimeout(() => setSaved(false), 2000);
        onSaved?.();
      } catch { /* silent */ }
      finally { setSaving(false); }
    }, 800);
  }, [onSaved]);

  // Immediate save (for dropdown/radio changes)
  const immediateSave = useCallback(async (newSettings: LLMSettings) => {
    setSaving(true);
    setSaved(false);
    try {
      await saveLLMSettings(newSettings);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
      onSaved?.();
    } catch { /* silent */ }
    finally { setSaving(false); }
  }, [onSaved]);

  const updateProvider = (provider: LLMProvider) => {
    const ns = { ...settings, provider };
    setSettings(ns);
    setTestStatus("idle");
    immediateSave(ns);
  };

  const updateOpenAI = (field: string, value: string) => {
    const ns = { ...settings, openai: { ...settings.openai!, [field]: value } };
    setSettings(ns);
    if (field === "model") immediateSave(ns); else autoSave(ns);
  };

  const updateAnthropic = (field: string, value: string) => {
    const ns = { ...settings, anthropic: { ...settings.anthropic!, [field]: value } };
    setSettings(ns);
    if (field === "model") immediateSave(ns); else autoSave(ns);
  };

  const updateBedrock = (field: string, value: string) => {
    const ns = { ...settings, bedrock: { ...settings.bedrock!, [field]: value } };
    setSettings(ns);
    if (field === "auth_mode" || field === "model") immediateSave(ns); else autoSave(ns);
  };

  const updateOllama = (field: string, value: string) => {
    const ns = { ...settings, ollama: { ...settings.ollama!, [field]: value } };
    setSettings(ns);
    if (field === "model") immediateSave(ns); else autoSave(ns);
  };

  const updateOpenRouter = (field: string, value: string) => {
    const ns = { ...settings, openrouter: { ...settings.openrouter!, [field]: value } };
    setSettings(ns);
    if (field === "model") immediateSave(ns); else autoSave(ns);
  };

  const handleTest = async () => {
    setTestStatus("testing");
    setTestMessage("");
    try {
      const result = await testLLMConnection(settings);
      setTestStatus(result.success ? "success" : "error");
      setTestMessage(result.message || (result.success ? "Connection successful!" : "Connection failed."));
    } catch (e) {
      setTestStatus("error");
      setTestMessage(e instanceof Error ? e.message : "Connection failed.");
    }
  };

  if (loading) return <div className="flex justify-center py-4"><Loader2 className="w-5 h-5 animate-spin text-primary" /></div>;

  return (
    <div className="space-y-4">
      {/* API Key Guide — OpenAI & Anthropic only */}
      {(settings.provider === "openai" || settings.provider === "anthropic" || settings.provider === "openrouter") && (
        <div className="rounded-2xl border border-border overflow-hidden">
          <button
            onClick={() => setShowGuide(!showGuide)}
            className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-secondary/50 transition-colors"
          >
            <span className="text-[13px] font-semibold text-primary">
              How to get your {{ openai: "OpenAI", anthropic: "Anthropic", openrouter: "OpenRouter" }[settings.provider]} API key
            </span>
            {showGuide ? <ChevronUp className="w-4 h-4 text-muted-foreground" /> : <ChevronDown className="w-4 h-4 text-muted-foreground" />}
          </button>

          {showGuide && (
            <div className="px-4 pb-4 border-t border-border pt-3">
              {settings.provider === "openai" ? (
                <div className="space-y-4">
                  <div className="space-y-2.5">
                    {[
                      { step: 1, text: "Go to the OpenAI platform and create a free account (or sign in).", link: "https://platform.openai.com/signup", linkText: "platform.openai.com/signup" },
                      { step: 2, text: "Add a payment method under Settings > Billing. API access requires billing even if you have ChatGPT Plus.", link: "https://platform.openai.com/settings/organization/billing/overview", linkText: "Add billing" },
                      { step: 3, text: "Go to the API keys page.", link: "https://platform.openai.com/api-keys", linkText: "platform.openai.com/api-keys" },
                      { step: 4, text: 'Click "Create new secret key", give it a name, then click Create.' },
                      { step: 5, text: "Copy the key and paste it below. It starts with sk- and is only shown once." },
                    ].map(({ step, text, link, linkText }) => (
                      <div key={step} className="flex gap-3">
                        <div className="w-6 h-6 rounded-full bg-secondary flex items-center justify-center flex-shrink-0 mt-0.5">
                          <span className="text-xs font-bold text-foreground">{step}</span>
                        </div>
                        <div className="text-[13px] text-foreground leading-relaxed">
                          {text}
                          {link && (
                            <a href={link} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-primary font-semibold hover:underline ml-1">
                              {linkText} <ExternalLink className="w-3 h-3" />
                            </a>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className="bg-[#F7F7F7] rounded-xl p-3 text-[12px] text-muted-foreground">
                    <strong className="text-foreground">Note:</strong> This is separate from your ChatGPT subscription. The API has its own pay-as-you-go billing. GPT-4o costs roughly $0.01-0.03 per job application.
                  </div>
                </div>
              ) : settings.provider === "anthropic" ? (
                <div className="space-y-4">
                  <div className="space-y-2.5">
                    {[
                      { step: 1, text: "Go to the Anthropic console and create a free account (or sign in).", link: "https://console.anthropic.com/signup", linkText: "console.anthropic.com/signup" },
                      { step: 2, text: "Add a payment method under Settings > Billing. A small free trial credit may be available.", link: "https://console.anthropic.com/settings/billing", linkText: "Add billing" },
                      { step: 3, text: "Go to the API keys page.", link: "https://console.anthropic.com/settings/keys", linkText: "console.anthropic.com/settings/keys" },
                      { step: 4, text: 'Click "Create Key", give it a name, then click Create.' },
                      { step: 5, text: "Copy the key and paste it below. It starts with sk-ant- and is only shown once." },
                    ].map(({ step, text, link, linkText }) => (
                      <div key={step} className="flex gap-3">
                        <div className="w-6 h-6 rounded-full bg-secondary flex items-center justify-center flex-shrink-0 mt-0.5">
                          <span className="text-xs font-bold text-foreground">{step}</span>
                        </div>
                        <div className="text-[13px] text-foreground leading-relaxed">
                          {text}
                          {link && (
                            <a href={link} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-primary font-semibold hover:underline ml-1">
                              {linkText} <ExternalLink className="w-3 h-3" />
                            </a>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className="bg-[#F7F7F7] rounded-xl p-3 text-[12px] text-muted-foreground">
                    <strong className="text-foreground">Note:</strong> Claude Sonnet costs roughly $0.01-0.03 per job application. The API is pay-as-you-go.
                  </div>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="space-y-2.5">
                    {[
                      { step: 1, text: "Go to OpenRouter and create a free account (or sign in).", link: "https://openrouter.ai", linkText: "openrouter.ai" },
                      { step: 2, text: "Go to the API keys page.", link: "https://openrouter.ai/keys", linkText: "openrouter.ai/keys" },
                      { step: 3, text: 'Click "Create Key", give it a name, then click Create.' },
                      { step: 4, text: "Copy the key and paste it below. It starts with sk-or-v1-." },
                    ].map(({ step, text, link, linkText }) => (
                      <div key={step} className="flex gap-3">
                        <div className="w-6 h-6 rounded-full bg-secondary flex items-center justify-center flex-shrink-0 mt-0.5">
                          <span className="text-xs font-bold text-foreground">{step}</span>
                        </div>
                        <div className="text-[13px] text-foreground leading-relaxed">
                          {text}
                          {link && (
                            <a href={link} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-primary font-semibold hover:underline ml-1">
                              {linkText} <ExternalLink className="w-3 h-3" />
                            </a>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className="bg-[#F7F7F7] rounded-xl p-3 text-[12px] text-muted-foreground">
                    <strong className="text-foreground">Note:</strong> OpenRouter gives you access to 100+ models with a single key. Add credits at openrouter.ai/credits. Pricing varies per model.
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Provider Selection */}
      <div className={compact ? "" : "card"}>
        {!compact && <h3 className="text-sm font-bold text-foreground mb-4">Select Provider</h3>}
        <div className="space-y-2">
          {PROVIDERS.map(({ id, name, description }) => (
            <label key={id} className={`flex items-start gap-3 p-4 rounded-2xl border cursor-pointer transition-all ${settings.provider === id ? "border-foreground bg-secondary" : "border-border hover:border-gray-300"}`}>
              <input type="radio" name="provider" value={id} checked={settings.provider === id} onChange={() => updateProvider(id)} className="mt-1" />
              <div>
                <p className="text-sm font-medium text-foreground">{name}</p>
                <p className="text-xs text-muted-foreground">{description}</p>
              </div>
            </label>
          ))}
        </div>
      </div>

      {/* Provider Config */}
      <div className={compact ? "" : "card"}>
        {!compact && <h3 className="text-sm font-bold text-foreground mb-4">{{ openai: "OpenAI", anthropic: "Anthropic", bedrock: "AWS Bedrock", ollama: "Ollama", openrouter: "OpenRouter" }[settings.provider]} Configuration</h3>}

        {settings.provider === "openai" && (
          <div className="space-y-3">
            <div>
              <label className="block text-sm font-semibold text-foreground mb-1.5">API Key</label>
              <input type="password" value={settings.openai?.api_key || ""} onChange={(e) => updateOpenAI("api_key", e.target.value)} placeholder="sk-..." className="input-base font-mono" />
            </div>
            <div>
              <label className="block text-sm font-semibold text-foreground mb-1.5">Model</label>
              <select value={settings.openai?.model || "gpt-4o"} onChange={(e) => updateOpenAI("model", e.target.value)} className="input-base">
                {OPENAI_MODELS.map((m) => <option key={m} value={m}>{m}</option>)}
              </select>
            </div>
          </div>
        )}

        {settings.provider === "anthropic" && (
          <div className="space-y-3">
            <div>
              <label className="block text-sm font-semibold text-foreground mb-1.5">API Key</label>
              <input type="password" value={settings.anthropic?.api_key || ""} onChange={(e) => updateAnthropic("api_key", e.target.value)} placeholder="sk-ant-..." className="input-base font-mono" />
            </div>
            <div>
              <label className="block text-sm font-semibold text-foreground mb-1.5">Model</label>
              <select value={settings.anthropic?.model || "claude-sonnet-4-20250514"} onChange={(e) => updateAnthropic("model", e.target.value)} className="input-base">
                {ANTHROPIC_MODELS.map((m) => <option key={m} value={m}>{m}</option>)}
              </select>
            </div>
          </div>
        )}

        {settings.provider === "bedrock" && (
          <div className="space-y-3">
            <div>
              <label className="block text-sm font-medium text-foreground mb-2">Authentication</label>
              <div className="flex gap-2">
                <button onClick={() => updateBedrock("auth_mode", "profile")} className={`filter-tab ${(settings.bedrock?.auth_mode || "profile") === "profile" ? "filter-tab-active" : "filter-tab-inactive"}`}>AWS CLI Profile</button>
                <button onClick={() => updateBedrock("auth_mode", "keys")} className={`filter-tab ${settings.bedrock?.auth_mode === "keys" ? "filter-tab-active" : "filter-tab-inactive"}`}>Access Key / Secret Key</button>
              </div>
            </div>
            {(settings.bedrock?.auth_mode || "profile") === "profile" ? (
              <div>
                <label className="block text-sm font-semibold text-foreground mb-1.5">Profile Name</label>
                <input value={settings.bedrock?.profile_name || "default"} onChange={(e) => updateBedrock("profile_name", e.target.value)} className="input-base" />
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-semibold text-foreground mb-1.5">Access Key</label>
                  <input type="password" value={settings.bedrock?.access_key || ""} onChange={(e) => updateBedrock("access_key", e.target.value)} placeholder="AKIA..." className="input-base font-mono" />
                </div>
                <div>
                  <label className="block text-sm font-semibold text-foreground mb-1.5">Secret Key</label>
                  <input type="password" value={settings.bedrock?.secret_key || ""} onChange={(e) => updateBedrock("secret_key", e.target.value)} className="input-base font-mono" />
                </div>
              </div>
            )}
            <div>
              <label className="block text-sm font-semibold text-foreground mb-1.5">Region</label>
              <input value={settings.bedrock?.region || "us-west-2"} onChange={(e) => updateBedrock("region", e.target.value)} className="input-base" />
            </div>
            <div>
              <label className="block text-sm font-semibold text-foreground mb-1.5">Model</label>
              <select value={settings.bedrock?.model || ""} onChange={(e) => updateBedrock("model", e.target.value)} className="input-base">
                {BEDROCK_MODELS.map((m) => <option key={m} value={m}>{m}</option>)}
              </select>
            </div>
          </div>
        )}

        {settings.provider === "ollama" && (
          <div className="space-y-3">
            <div>
              <label className="block text-sm font-semibold text-foreground mb-1.5">Server URL</label>
              <input value={settings.ollama?.base_url || "http://localhost:11434"} onChange={(e) => updateOllama("base_url", e.target.value)} placeholder="http://localhost:11434" className="input-base font-mono" />
              <p className="text-xs text-muted-foreground mt-1">The URL where your Ollama server is running.</p>
            </div>
            <div>
              <label className="block text-sm font-semibold text-foreground mb-1.5">
                Model
                {ollamaFetching && <Loader2 className="w-3 h-3 animate-spin inline ml-2" />}
              </label>
              {ollamaModels.length > 0 ? (
                <select value={settings.ollama?.model || ""} onChange={(e) => updateOllama("model", e.target.value)} className="input-base">
                  <option value="">Select a model</option>
                  {ollamaModels.map((m) => <option key={m} value={m}>{m}</option>)}
                </select>
              ) : (
                <input value={settings.ollama?.model || ""} onChange={(e) => updateOllama("model", e.target.value)} placeholder="e.g. llama3.1" className="input-base" />
              )}
              <p className="text-xs text-muted-foreground mt-1">
                {ollamaModels.length > 0
                  ? `${ollamaModels.length} model${ollamaModels.length === 1 ? "" : "s"} found on your server.`
                  : "Enter a model name, or start your Ollama server to see available models."}
              </p>
            </div>
          </div>
        )}

        {settings.provider === "openrouter" && (
          <div className="space-y-3">
            <div>
              <label className="block text-sm font-semibold text-foreground mb-1.5">API Key</label>
              <input type="password" value={settings.openrouter?.api_key || ""} onChange={(e) => updateOpenRouter("api_key", e.target.value)} placeholder="sk-or-v1-..." className="input-base font-mono" />
              <p className="text-xs text-muted-foreground mt-1">
                Get your key at{" "}
                <a href="https://openrouter.ai/keys" target="_blank" rel="noopener noreferrer" className="text-primary font-semibold hover:underline">openrouter.ai/keys</a>
              </p>
            </div>
            <div>
              <label className="block text-sm font-semibold text-foreground mb-1.5">Model</label>
              <select value={settings.openrouter?.model || "openai/gpt-4o"} onChange={(e) => updateOpenRouter("model", e.target.value)} className="input-base">
                {OPENROUTER_MODELS.map((m) => <option key={m} value={m}>{m}</option>)}
              </select>
              <p className="text-xs text-muted-foreground mt-1">
                All models above support vision. Browse 100+ more at{" "}
                <a href="https://openrouter.ai/models" target="_blank" rel="noopener noreferrer" className="text-primary font-semibold hover:underline">openrouter.ai/models</a>
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Status + Test */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 h-5">
          {saving && <span className="flex items-center gap-1 text-xs text-muted-foreground"><Loader2 className="w-3 h-3 animate-spin" /> Saving...</span>}
          {saved && !saving && <span className="flex items-center gap-1 text-xs text-green-600"><CheckCircle className="w-3 h-3" /> Saved ✓</span>}
        </div>
        <button onClick={handleTest} disabled={testStatus === "testing"} className="btn-secondary disabled:opacity-50 ml-auto">
          {testStatus === "testing" ? <Loader2 className="w-4 h-4 animate-spin" /> : <TestTube className="w-4 h-4" />}
          {testStatus === "testing" ? "Testing..." : "Test Connection"}
        </button>
      </div>
      {testStatus === "success" && <div className="flex items-center gap-2 text-green-600"><CheckCircle className="w-4 h-4" /><span className="text-sm">{testMessage}</span></div>}
      {testStatus === "error" && <div className="flex items-center gap-2 text-red-600"><XCircle className="w-4 h-4" /><span className="text-sm">{testMessage}</span></div>}
    </div>
  );
}
