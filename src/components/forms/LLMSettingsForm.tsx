import { useState, useEffect, useRef, useCallback } from "react";
import { TestTube, CheckCircle, XCircle, Loader2, ChevronDown, ChevronUp, ExternalLink } from "lucide-react";
import { getLLMSettings, saveLLMSettings, testLLMConnection, fetchOllamaModels } from "../../lib/api";
import { trackEvent } from "../../lib/analytics";
import type { LLMProvider, LLMSettings } from "../../lib/types";
import { useTranslation } from "react-i18next";

const PROVIDERS: { id: LLMProvider; nameKey: string; descKey: string }[] = [
  { id: "openrouter", nameKey: "providers.openrouter.name", descKey: "providers.openrouter.description" },
  { id: "openai", nameKey: "providers.openai.name", descKey: "providers.openai.description" },
  { id: "anthropic", nameKey: "providers.anthropic.name", descKey: "providers.anthropic.description" },
  { id: "bedrock", nameKey: "providers.bedrock.name", descKey: "providers.bedrock.description" },
  { id: "ollama", nameKey: "providers.ollama.name", descKey: "providers.ollama.description" },
];

const OPENAI_MODELS = ["gpt-5.4-nano", "gpt-5.4-mini", "gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"];
const ANTHROPIC_MODELS = ["claude-sonnet-4-5", "claude-haiku-4-5", "claude-opus-4-5"];
const OPENROUTER_FALLBACK_MODELS = [
  "qwen/qwen3.6-plus",
  "bytedance-seed/seed-2.0-lite",
  "bytedance-seed/seed-1.6",
  "qwen/qwen3.6-27b",
  "qwen/qwen3-vl-32b-instruct",
  "qwen/qwen2.5-vl-72b-instruct",
  "openai/gpt-4o",
  "openai/gpt-4.1",
  "openai/gpt-4.1-mini",
  "anthropic/claude-sonnet-4",
  "anthropic/claude-haiku-4",
  "google/gemini-2.5-pro-preview",
  "google/gemini-2.5-flash-preview",
  "meta-llama/llama-4-maverick",
  "mistralai/mistral-large-2411",
];
const BEDROCK_MODELS = [
  "us.anthropic.claude-sonnet-4-6",
  "us.anthropic.claude-haiku-4-6",
  "anthropic.claude-3-5-sonnet-20241022-v2:0",
  "anthropic.claude-3-haiku-20240307-v1:0",
];

const defaultSettings: LLMSettings = {
  provider: "openrouter",
  openai: { api_key: "", model: "gpt-4o" },
  anthropic: { api_key: "", model: "claude-sonnet-4-5" },
  bedrock: { access_key: "", secret_key: "", region: "us-west-2", model: "us.anthropic.claude-sonnet-4-6", auth_mode: "profile", profile_name: "default" },
  ollama: { base_url: "http://localhost:11434", model: "" },
  openrouter: { api_key: "", model: "qwen/qwen3.6-plus" },
};

const PROVIDER_DISPLAY_NAMES: Record<string, string> = {
  openai: "OpenAI",
  anthropic: "Anthropic",
  bedrock: "AWS Bedrock",
  ollama: "Ollama",
  openrouter: "OpenRouter",
};

interface LLMSettingsFormProps {
  onSaved?: () => void;
  compact?: boolean;
}

export default function LLMSettingsForm({ onSaved, compact }: LLMSettingsFormProps) {
  const { t } = useTranslation("llm");
  const [settings, setSettings] = useState<LLMSettings>(defaultSettings);
  const [testStatus, setTestStatus] = useState<"idle" | "testing" | "success" | "error">("idle");
  const [testMessage, setTestMessage] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(true);
  const [showGuide, setShowGuide] = useState(false);
  const [ollamaModels, setOllamaModels] = useState<string[]>([]);
  const [ollamaFetching, setOllamaFetching] = useState(false);
  const [openrouterModels, setOpenrouterModels] = useState<{ id: string; name: string; context: number; promptPrice: string; completionPrice: string }[]>([]);
  const [openrouterFetching, setOpenrouterFetching] = useState(false);
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

  useEffect(() => {
    if (settings.provider !== "openrouter" || openrouterModels.length > 0) return;
    setOpenrouterFetching(true);
    fetch("https://openrouter.ai/api/v1/models")
      .then(r => r.json())
      .then(data => {
        const formatPrice = (p: string | number | undefined) => {
          if (!p) return "free";
          const n = typeof p === "string" ? parseFloat(p) : p;
          if (n === 0) return "free";
          const perMillion = n * 1_000_000;
          return perMillion < 1 ? `$${perMillion.toFixed(2)}/M` : `$${perMillion.toFixed(1)}/M`;
        };
        const vision = (data.data || [])
          .filter((m: { architecture?: { input_modalities?: string[] } }) =>
            m.architecture?.input_modalities?.includes("image")
          )
          .map((m: { id: string; name: string; context_length?: number; pricing?: { prompt?: string; completion?: string } }) => ({
            id: m.id,
            name: m.name,
            context: m.context_length || 0,
            promptPrice: formatPrice(m.pricing?.prompt),
            completionPrice: formatPrice(m.pricing?.completion),
          }))
          .sort((a: { id: string }, b: { id: string }) => a.id.localeCompare(b.id));
        if (vision.length > 0) setOpenrouterModels(vision);
      })
      .catch(() => {})
      .finally(() => setOpenrouterFetching(false));
  }, [settings.provider, openrouterModels.length]);

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
      trackEvent("llm_provider_configured", { provider: newSettings.provider });
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
      setTestMessage(result.message || (result.success ? t("status.connectionSuccessful") : t("status.connectionFailed")));
    } catch (e) {
      setTestStatus("error");
      setTestMessage(e instanceof Error ? e.message : t("status.connectionFailed"));
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
              {t("guide.howToGetKey", { provider: PROVIDER_DISPLAY_NAMES[settings.provider] })}
            </span>
            {showGuide ? <ChevronUp className="w-4 h-4 text-muted-foreground" /> : <ChevronDown className="w-4 h-4 text-muted-foreground" />}
          </button>

          {showGuide && (
            <div className="px-4 pb-4 border-t border-border pt-3">
              {settings.provider === "openai" ? (
                <div className="space-y-4">
                  <div className="space-y-2.5">
                    {[
                      { step: 1, text: t("guide.openai.step1"), link: "https://platform.openai.com/signup", linkText: t("guide.openai.step1Link") },
                      { step: 2, text: t("guide.openai.step2"), link: "https://platform.openai.com/settings/organization/billing/overview", linkText: t("guide.openai.step2Link") },
                      { step: 3, text: t("guide.openai.step3"), link: "https://platform.openai.com/api-keys", linkText: t("guide.openai.step3Link") },
                      { step: 4, text: t("guide.openai.step4") },
                      { step: 5, text: t("guide.openai.step5") },
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
                    <strong className="text-foreground">{t("guide.note")}</strong> {t("guide.openai.note")}
                  </div>
                </div>
              ) : settings.provider === "anthropic" ? (
                <div className="space-y-4">
                  <div className="space-y-2.5">
                    {[
                      { step: 1, text: t("guide.anthropic.step1"), link: "https://console.anthropic.com/signup", linkText: t("guide.anthropic.step1Link") },
                      { step: 2, text: t("guide.anthropic.step2"), link: "https://console.anthropic.com/settings/billing", linkText: t("guide.anthropic.step2Link") },
                      { step: 3, text: t("guide.anthropic.step3"), link: "https://console.anthropic.com/settings/keys", linkText: t("guide.anthropic.step3Link") },
                      { step: 4, text: t("guide.anthropic.step4") },
                      { step: 5, text: t("guide.anthropic.step5") },
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
                    <strong className="text-foreground">{t("guide.note")}</strong> {t("guide.anthropic.note")}
                  </div>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="space-y-2.5">
                    {[
                      { step: 1, text: t("guide.openrouter.step1"), link: "https://openrouter.ai", linkText: t("guide.openrouter.step1Link") },
                      { step: 2, text: t("guide.openrouter.step2"), link: "https://openrouter.ai/keys", linkText: t("guide.openrouter.step2Link") },
                      { step: 3, text: t("guide.openrouter.step3") },
                      { step: 4, text: t("guide.openrouter.step4") },
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
                    <strong className="text-foreground">{t("guide.note")}</strong> {t("guide.openrouter.note")}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Provider Selection */}
      <div className={compact ? "" : "card"}>
        {!compact && <h3 className="text-sm font-bold text-foreground mb-4">{t("selectProvider")}</h3>}
        <div className="space-y-2">
          {PROVIDERS.map(({ id, nameKey, descKey }) => (
            <label key={id} className={`flex items-start gap-3 p-4 rounded-2xl border cursor-pointer transition-all ${settings.provider === id ? "border-foreground bg-secondary" : "border-border hover:border-gray-300"}`}>
              <input type="radio" name="provider" value={id} checked={settings.provider === id} onChange={() => updateProvider(id)} className="mt-1" />
              <div>
                <p className="text-sm font-medium text-foreground">{t(nameKey)}</p>
                <p className="text-xs text-muted-foreground">{t(descKey)}</p>
              </div>
            </label>
          ))}
        </div>
      </div>

      {/* Provider Config */}
      <div className={compact ? "" : "card"}>
        {!compact && <h3 className="text-sm font-bold text-foreground mb-4">{t("configuration", { provider: PROVIDER_DISPLAY_NAMES[settings.provider] })}</h3>}

        {settings.provider === "openai" && (
          <div className="space-y-3">
            <div>
              <label className="block text-sm font-semibold text-foreground mb-1.5">{t("labels.apiKey")}</label>
              <input type="password" value={settings.openai?.api_key || ""} onChange={(e) => updateOpenAI("api_key", e.target.value)} placeholder="sk-..." className="input-base font-mono" />
            </div>
            <div>
              <label className="block text-sm font-semibold text-foreground mb-1.5">{t("labels.model")}</label>
              <select value={settings.openai?.model || "gpt-4o"} onChange={(e) => updateOpenAI("model", e.target.value)} className="input-base">
                {OPENAI_MODELS.map((m) => <option key={m} value={m}>{m}</option>)}
              </select>
            </div>
          </div>
        )}

        {settings.provider === "anthropic" && (
          <div className="space-y-3">
            <div>
              <label className="block text-sm font-semibold text-foreground mb-1.5">{t("labels.apiKey")}</label>
              <input type="password" value={settings.anthropic?.api_key || ""} onChange={(e) => updateAnthropic("api_key", e.target.value)} placeholder="sk-ant-..." className="input-base font-mono" />
            </div>
            <div>
              <label className="block text-sm font-semibold text-foreground mb-1.5">{t("labels.model")}</label>
<select value={settings.anthropic?.model || "claude-sonnet-4-5"} onChange={(e) => updateAnthropic("model", e.target.value)} className="input-base">
                {ANTHROPIC_MODELS.map((m) => <option key={m} value={m}>{m}</option>)}
              </select>
            </div>
          </div>
        )}

        {settings.provider === "bedrock" && (
          <div className="space-y-3">
            <div>
              <label className="block text-sm font-medium text-foreground mb-2">{t("labels.authentication")}</label>
              <div className="flex gap-2">
                <button onClick={() => updateBedrock("auth_mode", "profile")} className={`filter-tab ${(settings.bedrock?.auth_mode || "profile") === "profile" ? "filter-tab-active" : "filter-tab-inactive"}`}>{t("labels.awsCliProfile")}</button>
                <button onClick={() => updateBedrock("auth_mode", "keys")} className={`filter-tab ${settings.bedrock?.auth_mode === "keys" ? "filter-tab-active" : "filter-tab-inactive"}`}>{t("labels.accessKeySecretKey")}</button>
              </div>
            </div>
            {(settings.bedrock?.auth_mode || "profile") === "profile" ? (
              <div>
                <label className="block text-sm font-semibold text-foreground mb-1.5">{t("labels.profileName")}</label>
                <input value={settings.bedrock?.profile_name || "default"} onChange={(e) => updateBedrock("profile_name", e.target.value)} className="input-base" />
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-semibold text-foreground mb-1.5">{t("labels.accessKey")}</label>
                  <input type="password" value={settings.bedrock?.access_key || ""} onChange={(e) => updateBedrock("access_key", e.target.value)} placeholder="AKIA..." className="input-base font-mono" />
                </div>
                <div>
                  <label className="block text-sm font-semibold text-foreground mb-1.5">{t("labels.secretKey")}</label>
                  <input type="password" value={settings.bedrock?.secret_key || ""} onChange={(e) => updateBedrock("secret_key", e.target.value)} className="input-base font-mono" />
                </div>
              </div>
            )}
            <div>
              <label className="block text-sm font-semibold text-foreground mb-1.5">{t("labels.region")}</label>
              <input value={settings.bedrock?.region || "us-west-2"} onChange={(e) => updateBedrock("region", e.target.value)} className="input-base" />
            </div>
            <div>
              <label className="block text-sm font-semibold text-foreground mb-1.5">{t("labels.model")}</label>
              <select value={settings.bedrock?.model || ""} onChange={(e) => updateBedrock("model", e.target.value)} className="input-base">
                {BEDROCK_MODELS.map((m) => <option key={m} value={m}>{m}</option>)}
              </select>
            </div>
          </div>
        )}

        {settings.provider === "ollama" && (
          <div className="space-y-3">
            <div>
              <label className="block text-sm font-semibold text-foreground mb-1.5">{t("labels.serverUrl")}</label>
              <input value={settings.ollama?.base_url || "http://localhost:11434"} onChange={(e) => updateOllama("base_url", e.target.value)} placeholder="http://localhost:11434" className="input-base font-mono" />
              <p className="text-xs text-muted-foreground mt-1">{t("ollama.serverUrlHint")}</p>
            </div>
            <div>
              <label className="block text-sm font-semibold text-foreground mb-1.5">
                {t("labels.model")}
                {ollamaFetching && <Loader2 className="w-3 h-3 animate-spin inline ml-2" />}
              </label>
              {ollamaModels.length > 0 ? (
                <select value={settings.ollama?.model || ""} onChange={(e) => updateOllama("model", e.target.value)} className="input-base">
                  <option value="">{t("labels.selectModel")}</option>
                  {ollamaModels.map((m) => <option key={m} value={m}>{m}</option>)}
                </select>
              ) : (
                <input value={settings.ollama?.model || ""} onChange={(e) => updateOllama("model", e.target.value)} placeholder="e.g. llama3.1" className="input-base" />
              )}
              <p className="text-xs text-muted-foreground mt-1">
                {ollamaModels.length > 0
                  ? t("ollama.modelsFound", { count: ollamaModels.length })
                  : t("ollama.noModelsHint")}
              </p>
            </div>
          </div>
        )}

        {settings.provider === "openrouter" && (
          <div className="space-y-3">
            <div>
              <label className="block text-sm font-semibold text-foreground mb-1.5">{t("labels.apiKey")}</label>
              <input type="password" value={settings.openrouter?.api_key || ""} onChange={(e) => updateOpenRouter("api_key", e.target.value)} placeholder="sk-or-v1-..." className="input-base font-mono" />
              <p className="text-xs text-muted-foreground mt-1">
                {t("openrouter.keyHint")}{" "}
                <a href="https://openrouter.ai/keys" target="_blank" rel="noopener noreferrer" className="text-primary font-semibold hover:underline">openrouter.ai/keys</a>
              </p>
            </div>
            <div>
              <label className="block text-sm font-semibold text-foreground mb-1.5">
                {t("labels.modelVision")}
                {openrouterFetching && <Loader2 className="w-3 h-3 animate-spin inline ml-2" />}
              </label>
              <select value={settings.openrouter?.model || "openai/gpt-4o"} onChange={(e) => updateOpenRouter("model", e.target.value)} className="input-base">
                {openrouterModels.length > 0
                  ? openrouterModels.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name} — in: {m.promptPrice} · out: {m.completionPrice} · {m.context >= 1000 ? `${Math.round(m.context / 1000)}K` : m.context} ctx
                    </option>
                  ))
                  : OPENROUTER_FALLBACK_MODELS.map(m => <option key={m} value={m}>{m}</option>)
                }
              </select>
              {openrouterModels.length > 0 && (() => {
                const selected = openrouterModels.find(m => m.id === (settings.openrouter?.model || "openai/gpt-4o"));
                return selected ? (
                  <div className="flex gap-3 mt-2 text-[11px] text-muted-foreground">
                    <span>Input: <strong className="text-foreground">{selected.promptPrice}</strong></span>
                    <span>Output: <strong className="text-foreground">{selected.completionPrice}</strong></span>
                    <span>Context: <strong className="text-foreground">{selected.context >= 1000 ? `${Math.round(selected.context / 1000)}K tokens` : `${selected.context} tokens`}</strong></span>
                  </div>
                ) : null;
              })()}
              <p className="text-xs text-muted-foreground mt-1.5">
                {openrouterModels.length > 0
                  ? t("openrouter.modelsAvailable", { count: openrouterModels.length })
                  : t("openrouter.curatedList")}
                {" "}{t("openrouter.browseAt")}{" "}
                <a href="https://openrouter.ai/models" target="_blank" rel="noopener noreferrer" className="text-primary font-semibold hover:underline">openrouter.ai/models</a>
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Status + Test */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 h-5">
          {saving && <span className="flex items-center gap-1 text-xs text-muted-foreground"><Loader2 className="w-3 h-3 animate-spin" /> {t("status.saving")}</span>}
          {saved && !saving && <span className="flex items-center gap-1 text-xs text-green-600"><CheckCircle className="w-3 h-3" /> {t("status.saved")}</span>}
        </div>
        <button onClick={handleTest} disabled={testStatus === "testing"} className="btn-secondary disabled:opacity-50 ml-auto">
          {testStatus === "testing" ? <Loader2 className="w-4 h-4 animate-spin" /> : <TestTube className="w-4 h-4" />}
          {testStatus === "testing" ? t("status.testing") : t("status.testConnection")}
        </button>
      </div>
      {testStatus === "success" && <div className="flex items-center gap-2 text-green-600"><CheckCircle className="w-4 h-4" /><span className="text-sm">{testMessage}</span></div>}
      {testStatus === "error" && <div className="flex items-center gap-2 text-red-600"><XCircle className="w-4 h-4" /><span className="text-sm">{testMessage}</span></div>}
    </div>
  );
}
