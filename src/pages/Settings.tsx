import { useState, useEffect, useRef } from "react";
import { Save, FolderOpen, X, Upload, Trash2, Sun, Moon, Monitor, Download, AlertTriangle, KeyRound } from "lucide-react";
import { getSettings, saveSettings, getPlugins, togglePlugin, removePlugin, previewPlugin, importPlugin, deleteAllData, exportAllData, checkHealth } from "../lib/api";
import PluginReviewPanel from "../components/PluginReviewPanel";
import LoginCards from "../components/LoginCards";
import { setTelemetryEnabled as setAnalyticsTelemetry, hasTelemetryConsent } from "../lib/analytics";
import { clearLocalAppData, restartApp, exportFileName, downloadJson } from "../lib/privacy";
import { getStoredTheme, setTheme, type ThemeMode } from "../lib/theme";
import { open } from "@tauri-apps/plugin-dialog";
import { useTranslation } from "react-i18next";
import { PageHeader, LoadingSpinner, Section } from "../components/ui";
import TagInput from "../components/ui/TagInput";
import type { PluginConfig, PluginPreview } from "../lib/types";
import { LANGUAGE_NAMES, getSavedLanguage, saveLanguagePreference } from "../i18n/languageDetection";
import { loadLanguage } from "../i18n";

/** Allowed values for agent conversation log retention (days; 0 = don't save). */
const LOG_RETENTION_OPTIONS = [0, 7, 14, 30, 90] as const;
const DEFAULT_LOG_RETENTION_DAYS = 14;
const DEFAULT_DAILY_APPLY_CAP = 25;
const DEFAULT_MAX_RUN_COST_USD = 5;

function numberOr(value: unknown, fallback: number): number {
  const n = Number(value);
  return value === undefined || value === null || value === "" || !Number.isFinite(n) ? fallback : n;
}

/** Human-readable message from an `API Error <status>: {"error": {"message"}}` error. */
function apiErrorMessage(e: unknown): string {
  const raw = e instanceof Error ? e.message : String(e);
  const body = raw.replace(/^API Error \d+:\s*/, "");
  try {
    const parsed = JSON.parse(body);
    return parsed?.error?.message || parsed?.detail || body;
  } catch {
    return body;
  }
}

export default function SettingsPage() {
  const { t } = useTranslation("settings");
  const [resumePath, setResumePath] = useState("");
  const [blockedDomains, setBlockedDomains] = useState<string[]>([]);
  const [newDomain, setNewDomain] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [maxFailures, setMaxFailures] = useState(8);
  const [telemetryEnabled, setTelemetryEnabled] = useState(false);
  const [logRetentionDays, setLogRetentionDays] = useState<number>(DEFAULT_LOG_RETENTION_DAYS);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState(false);
  const [theme, setThemeState] = useState<ThemeMode>(getStoredTheme());
  const [currentLanguage, setCurrentLanguage] = useState<string>(getSavedLanguage() || "");
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [plugins, setPlugins] = useState<PluginConfig[]>([]);
  // Plugin import review
  const [reviewPath, setReviewPath] = useState<string | null>(null);
  const [reviewPlugin, setReviewPlugin] = useState<PluginPreview | null>(null);
  const [installing, setInstalling] = useState(false);
  const [pluginError, setPluginError] = useState<string | null>(null);
  // Automation
  const [dailyApplyCap, setDailyApplyCap] = useState<number>(DEFAULT_DAILY_APPLY_CAP);
  const [maxRunCost, setMaxRunCost] = useState<number>(DEFAULT_MAX_RUN_COST_USD);
  const [browserCdpUrl, setBrowserCdpUrl] = useState("");
  const [emailOtpViaGmail, setEmailOtpViaGmail] = useState(false);
  const [testMode, setTestMode] = useState(false);
  const [secretsBackend, setSecretsBackend] = useState<"keychain" | "file" | null>(null);

  const handleLanguageChange = async (lang: string) => {
    setCurrentLanguage(lang);
    saveLanguagePreference(lang);
    await loadLanguage(lang || "en");
  };

  useEffect(() => {
    Promise.all([
      getSettings().then((data) => {
        setResumePath(data.resume_path || "");
        setBlockedDomains(data.blocked_domains || []);
        setMaxFailures(data.max_failures || 8);
        // Opt-in: on only if the backend says so AND this device has consent.
        setTelemetryEnabled(data.telemetry_enabled === true && hasTelemetryConsent());
        const retention = Number(data.log_retention_days);
        setLogRetentionDays(
          (LOG_RETENTION_OPTIONS as readonly number[]).includes(retention) ? retention : DEFAULT_LOG_RETENTION_DAYS,
        );
        // Reconcile theme: a value saved on the backend wins over the local
        // default and is applied immediately.
        if (data.theme && data.theme !== getStoredTheme()) {
          setThemeState(data.theme);
          setTheme(data.theme);
        }
        const sens = data.sensitive_data || { email: "", password: "" };
        setEmail(sens.email || "");
        setPassword(sens.password || "");
        setDailyApplyCap(numberOr(data.daily_apply_cap, DEFAULT_DAILY_APPLY_CAP));
        setMaxRunCost(numberOr(data.max_run_cost_usd, DEFAULT_MAX_RUN_COST_USD));
        setBrowserCdpUrl(data.browser_cdp_url || "");
        setEmailOtpViaGmail(data.email_otp_via_gmail === true);
        setTestMode(data.test_mode === true);
      }),
      getPlugins().then((res) => setPlugins(res.plugins || [])),
    ])
      .catch(() => {})
      .finally(() => setLoading(false));
    // Where API keys live (OS keychain vs. a local file); informational only.
    Promise.resolve()
      .then(() => checkHealth())
      .then((h) => {
        if (h && (h.secrets_backend === "keychain" || h.secrets_backend === "file")) {
          setSecretsBackend(h.secrets_backend);
        }
      })
      .catch(() => {});
  }, []);

  const handleTogglePlugin = async (name: string, enabled: boolean) => {
    setPluginError(null);
    try {
      await togglePlugin(name, enabled);
      setPlugins((prev) => prev.map((p) => p.name === name ? { ...p, enabled } : p));
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setPluginError(msg.includes("409") ? t("plugins.tamperedToggle") : t("plugins.toggleFailed"));
    }
  };

  const handleRemovePlugin = async (name: string) => {
    await removePlugin(name);
    setPlugins((prev) => prev.filter((p) => p.name !== name));
  };

  const closeReview = () => {
    setReviewPath(null);
    setReviewPlugin(null);
    setPluginError(null);
  };

  /** Step 1: pick a file and show what it would do, without installing it. */
  const handleImportPlugin = async () => {
    setPluginError(null);
    const file = await open({ filters: [{ name: "YAML Plugin", extensions: ["yaml", "yml"] }] });
    if (!file) return;
    try {
      const res = await previewPlugin(file as string);
      if (!res || !res.plugin) throw new Error("no preview");
      setReviewPath(file as string);
      setReviewPlugin(res.plugin);
    } catch (e) {
      setPluginError(t("plugins.previewFailed", { error: apiErrorMessage(e) }));
    }
  };

  /** Step 2: install exactly the reviewed file (the backend checks the hash). */
  const handleInstallPlugin = async () => {
    if (!reviewPath || !reviewPlugin) return;
    setInstalling(true);
    setPluginError(null);
    try {
      const res = await importPlugin(reviewPath, reviewPlugin.sha256);
      if (!res.success) {
        // The file changed between preview and install: show the new version.
        if ("needs_review" in res && res.plugin) setReviewPlugin(res.plugin);
        setPluginError(t("plugins.changedDuringReview"));
        return;
      }
      const list = await getPlugins();
      setPlugins(list.plugins || []);
      closeReview();
    } catch (e) {
      setPluginError(t("plugins.importFailed", { error: apiErrorMessage(e) }));
    } finally {
      setInstalling(false);
    }
  };

  const handleThemeChange = (mode: ThemeMode) => {
    setThemeState(mode);
    setTheme(mode); // apply + persist locally immediately
    saveSettings({ theme: mode }).catch(() => {}); // mirror to backend
  };

  const handleTelemetryChange = (enabled: boolean) => {
    setTelemetryEnabled(enabled);
    setAnalyticsTelemetry(enabled);
    saveSettings({ telemetry_enabled: enabled }).catch(() => {});
  };

  const handleTestModeChange = (enabled: boolean) => {
    setTestMode(enabled);
    saveSettings({ test_mode: enabled }).catch(() => {});
  };

  const handleRetentionChange = (days: number) => {
    setLogRetentionDays(days);
    saveSettings({ log_retention_days: days }).catch(() => {});
  };

  const handleExportData = async () => {
    setExporting(true);
    setExportError(false);
    try {
      const data = await exportAllData();
      downloadJson(data, exportFileName());
    } catch {
      setExportError(true);
    } finally {
      setExporting(false);
    }
  };

  const handleDeleteAllData = async () => {
    setDeleting(true);
    setDeleteError(false);
    try {
      const res = await deleteAllData();
      if (!res || res.ok !== true) throw new Error("delete failed");
      clearLocalAppData();
      restartApp();
    } catch {
      setDeleteError(true);
      setDeleting(false);
    }
  };

  const addDomain = () => {
    if (newDomain.trim() && !blockedDomains.includes(newDomain.trim())) {
      setBlockedDomains([...blockedDomains, newDomain.trim()]);
      setNewDomain("");
    }
  };

  const removeDomain = (d: string) => {
    setBlockedDomains(blockedDomains.filter((x) => x !== d));
  };

  // Every field autosaves (the page used to mix instant toggles with fields that
  // silently needed "Save Settings"). The button stays as an explicit save.
  const loadedRef = useRef(false);
  useEffect(() => {
    if (loading) return;
    if (!loadedRef.current) {
      loadedRef.current = true; // the values that just loaded are not an edit
      return;
    }
    const timer = setTimeout(() => void handleSave(), 900);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading, resumePath, blockedDomains, email, password, maxFailures, dailyApplyCap, maxRunCost,
      browserCdpUrl, emailOtpViaGmail]);

  const handleSave = async () => {
    try {
      setSaveError(null);
      await saveSettings({
        resume_path: resumePath,
        blocked_domains: blockedDomains,
        sensitive_data: { email, password },
        max_failures: maxFailures,
        telemetry_enabled: telemetryEnabled,
        log_retention_days: logRetentionDays,
        theme,
        daily_apply_cap: dailyApplyCap,
        max_run_cost_usd: maxRunCost,
        browser_cdp_url: browserCdpUrl.trim(),
        email_otp_via_gmail: emailOtpViaGmail,
        test_mode: testMode,
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (e) {
      setSaveError("Failed to save settings. Please try again.");
      console.error("Failed to save settings:", e);
    }
  };

  if (loading) return <LoadingSpinner />;

  return (
    <div className="max-w-2xl">
      <PageHeader
        title="Settings"
        subtitle="General application settings"
        actions={
          <button onClick={handleSave} className="btn-primary">
            <Save className="w-4 h-4" />
            {saved ? "Saved" : "Save Settings"}
          </button>
        }
      />
      {saveError && (
        <div className="error-banner mb-5 flex items-center justify-between">
          {saveError}
          <button onClick={() => setSaveError(null)} className="text-destructive hover:text-destructive/80"><X className="w-4 h-4" /></button>
        </div>
      )}

      {/* Language */}
      <Section title={t("language.title")}>
        <div>
          <label className="block text-sm font-semibold text-foreground mb-1.5">{t("language.label")}</label>
          <select
            value={currentLanguage}
            onChange={(e) => handleLanguageChange(e.target.value)}
            className="w-full px-3 py-2 border border-border rounded-lg text-sm bg-card max-w-xs"
          >
            <option value="">{t("language.auto")}</option>
            {Object.entries(LANGUAGE_NAMES).map(([code, name]) => (
              <option key={code} value={code}>{name}</option>
            ))}
          </select>
          <p className="text-[13px] text-muted-foreground mt-1.5">{t("language.description")}</p>
        </div>
      </Section>

      {/* Appearance / Theme */}
      <Section title={t("appearance.title", "Appearance")}>
        <label className="block text-sm font-semibold text-foreground mb-2">{t("appearance.theme", "Theme")}</label>
        <div className="flex gap-2" role="radiogroup" aria-label={t("appearance.theme", "Theme")}>
          {([
            { mode: "light" as const, label: t("appearance.light", "Light"), Icon: Sun },
            { mode: "dark" as const, label: t("appearance.dark", "Dark"), Icon: Moon },
            { mode: "system" as const, label: t("appearance.system", "System"), Icon: Monitor },
          ]).map(({ mode, label, Icon }) => (
            <button
              key={mode}
              role="radio"
              aria-checked={theme === mode}
              onClick={() => handleThemeChange(mode)}
              className={`filter-tab flex items-center gap-1.5 ${theme === mode ? "filter-tab-active" : "filter-tab-inactive"}`}
            >
              <Icon className="w-3.5 h-3.5" /> {label}
            </button>
          ))}
        </div>
        <p className="text-[13px] text-muted-foreground mt-2">{t("appearance.description", "Choose light, dark, or follow your system setting.")}</p>
      </Section>

      {/* Resume */}
      <Section title="Resume">
        <div className="flex gap-2">
          <input value={resumePath} onChange={(e) => setResumePath(e.target.value)}
            placeholder="/path/to/your/resume.pdf"
            className="input-base flex-1" />
          <button onClick={async () => {
              const file = await open({ filters: [{ name: "Resume (PDF or Word)", extensions: ["pdf", "docx"] }] });
              if (file) setResumePath(file as string);
            }}
            className="btn-secondary">
            <FolderOpen className="w-4 h-4" /> Browse
          </button>
        </div>
        <p className="text-[13px] text-muted-foreground mt-2">PDF or Word (.docx) resume used for applications. Tailoring needs a PDF.</p>
      </Section>

      {/* Sensitive Data */}
      <Section title="Account Credentials">
        <p className="text-[13px] text-muted-foreground mb-4">
          Used for creating accounts on external ATS platforms during applications.
          Prefer using SSO (Sign in with LinkedIn/Google) when possible.
        </p>
        {secretsBackend === "keychain" && (
          <p data-testid="secrets-backend" className="text-[13px] text-green-700 mb-4 flex items-center gap-1.5">
            <KeyRound className="w-4 h-4 flex-shrink-0" /> {t("secrets.keychain")}
          </p>
        )}
        {secretsBackend === "file" && (
          <p data-testid="secrets-backend" role="alert" className="text-[13px] text-amber-800 bg-amber-50 border border-amber-200 rounded-lg p-2.5 mb-4 flex items-start gap-1.5">
            <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" /> {t("secrets.file")}
          </p>
        )}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-semibold text-foreground mb-1.5">Email</label>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
              className="input-base" />
          </div>
          <div>
            <label className="block text-sm font-semibold text-foreground mb-1.5">Password</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
              className="input-base" />
          </div>
        </div>
      </Section>

      {/* Agent Settings */}
      <Section title="Agent Settings">
        <div>
          <label className="block text-sm font-semibold text-foreground mb-1.5">Max Failures Per Job</label>
          <input type="number" value={maxFailures} onChange={(e) => {
              const val = Number(e.target.value);
              setMaxFailures(Math.max(1, Math.min(50, isNaN(val) ? 8 : val)));
            }}
            min={1} max={50} className="input-base !w-32" />
          <p className="text-[13px] text-muted-foreground mt-1.5">
            Agent stops trying after this many consecutive failures on a single job.
          </p>
        </div>
      </Section>

      {/* Automation */}
      <Section title={t("automation.title")}>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label htmlFor="daily-apply-cap" className="block text-sm font-semibold text-foreground mb-1.5">
              {t("automation.dailyApplyCap")}
            </label>
            <input
              id="daily-apply-cap"
              type="number"
              min={0}
              max={500}
              value={dailyApplyCap}
              onChange={(e) => {
                const val = Number(e.target.value);
                setDailyApplyCap(Math.max(0, Math.min(500, Number.isFinite(val) ? Math.round(val) : 0)));
              }}
              className="input-base !w-32"
            />
            <p className="text-[13px] text-muted-foreground mt-1.5">{t("automation.dailyApplyCapHelp")}</p>
          </div>
          <div>
            <label htmlFor="max-run-cost" className="block text-sm font-semibold text-foreground mb-1.5">
              {t("automation.maxRunCost")}
            </label>
            <input
              id="max-run-cost"
              type="number"
              min={0}
              max={1000}
              step={0.5}
              value={maxRunCost}
              onChange={(e) => {
                const val = Number(e.target.value);
                setMaxRunCost(Math.max(0, Math.min(1000, Number.isFinite(val) ? val : 0)));
              }}
              className="input-base !w-32"
            />
            <p className="text-[13px] text-muted-foreground mt-1.5">{t("automation.maxRunCostHelp")}</p>
          </div>
        </div>

        <div className="mt-5 pt-5 border-t border-border">
          <label htmlFor="browser-cdp-url" className="block text-sm font-semibold text-foreground mb-1.5">
            {t("automation.browserCdpUrl")}
          </label>
          <input
            id="browser-cdp-url"
            type="text"
            value={browserCdpUrl}
            onChange={(e) => setBrowserCdpUrl(e.target.value)}
            placeholder="http://127.0.0.1:9222"
            className="input-base"
          />
          <p className="text-[13px] text-muted-foreground mt-1.5">{t("automation.browserCdpUrlHelp")}</p>
        </div>

        <div className="mt-5 pt-5 border-t border-border flex items-center justify-between">
          <div>
            <p className="text-sm font-semibold text-foreground">{t("automation.emailOtp")}</p>
            <p className="text-[13px] text-muted-foreground mt-1">{t("automation.emailOtpHelp")}</p>
          </div>
          <label className="relative inline-flex items-center cursor-pointer flex-shrink-0 ml-4">
            <input
              type="checkbox"
              aria-label={t("automation.emailOtp")}
              checked={emailOtpViaGmail}
              onChange={(e) => setEmailOtpViaGmail(e.target.checked)}
              className="sr-only peer"
            />
            <div className="w-11 h-6 bg-secondary peer-focus:ring-2 peer-focus:ring-primary/20 rounded-full peer peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary"></div>
          </label>
        </div>

        <div className="mt-5 pt-5 border-t border-border flex items-center justify-between">
          <div>
            <p className="text-sm font-semibold text-foreground">{t("automation.testMode")}</p>
            <p className="text-[13px] text-muted-foreground mt-1">{t("automation.testModeHelp")}</p>
          </div>
          <label className="relative inline-flex items-center cursor-pointer flex-shrink-0 ml-4">
            <input
              type="checkbox"
              aria-label={t("automation.testMode")}
              checked={testMode}
              onChange={(e) => handleTestModeChange(e.target.checked)}
              className="sr-only peer"
            />
            <div className="w-11 h-6 bg-secondary peer-focus:ring-2 peer-focus:ring-primary/20 rounded-full peer peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary"></div>
          </label>
        </div>
      </Section>

      {/* Job site logins */}
      <Section title={t("logins.title")}>
        <p className="text-[13px] text-muted-foreground mb-4">{t("logins.description")}</p>
        <LoginCards gmailEnabled={emailOtpViaGmail} />
      </Section>

      {/* Privacy & data */}
      <Section title={t("privacy.title")}>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-semibold text-foreground">{t("telemetry.usageAnalytics")}</p>
            <p className="text-[13px] text-muted-foreground mt-1">{t("telemetry.description")}</p>
          </div>
          <label className="relative inline-flex items-center cursor-pointer flex-shrink-0 ml-4">
            <input
              type="checkbox"
              aria-label={t("telemetry.usageAnalytics")}
              checked={telemetryEnabled}
              onChange={(e) => handleTelemetryChange(e.target.checked)}
              className="sr-only peer"
            />
            <div className="w-11 h-6 bg-secondary peer-focus:ring-2 peer-focus:ring-primary/20 rounded-full peer peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary"></div>
          </label>
        </div>

        <div className="mt-5 pt-5 border-t border-border">
          <label htmlFor="log-retention" className="block text-sm font-semibold text-foreground mb-1.5">
            {t("privacy.retentionLabel")}
          </label>
          <select
            id="log-retention"
            value={logRetentionDays}
            onChange={(e) => handleRetentionChange(Number(e.target.value))}
            className="w-full px-3 py-2 border border-border rounded-lg text-sm bg-card max-w-xs"
          >
            {LOG_RETENTION_OPTIONS.map((days) => (
              <option key={days} value={days}>
                {days === 0 ? t("privacy.retentionNone") : t("privacy.retentionDays", { days })}
              </option>
            ))}
          </select>
          <p className="text-[13px] text-muted-foreground mt-1.5">{t("privacy.retentionDescription")}</p>
        </div>

        <div className="mt-5 pt-5 border-t border-border flex items-center justify-between gap-4">
          <div>
            <p className="text-sm font-semibold text-foreground">{t("privacy.exportTitle")}</p>
            <p className="text-[13px] text-muted-foreground mt-1">{t("privacy.exportDescription")}</p>
            {exportError && <p className="text-[13px] text-destructive mt-1" role="alert">{t("privacy.exportFailed")}</p>}
          </div>
          <button onClick={handleExportData} disabled={exporting} className="btn-secondary flex-shrink-0">
            <Download className="w-4 h-4" /> {exporting ? t("privacy.exporting") : t("privacy.exportButton")}
          </button>
        </div>

        <div className="mt-5 pt-5 border-t border-border">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-sm font-semibold text-destructive">{t("privacy.deleteTitle")}</p>
              <p className="text-[13px] text-muted-foreground mt-1">{t("privacy.deleteDescription")}</p>
            </div>
            {!confirmingDelete && (
              <button
                onClick={() => { setConfirmingDelete(true); setDeleteError(false); }}
                className="btn-secondary flex-shrink-0 !text-destructive !border-destructive/40"
              >
                <Trash2 className="w-4 h-4" /> {t("privacy.deleteButton")}
              </button>
            )}
          </div>
          {confirmingDelete && (
            <div role="alertdialog" aria-label={t("privacy.deleteTitle")}
              className="mt-3 p-4 rounded-lg border border-destructive/40 bg-destructive/5">
              <p className="text-sm text-foreground flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 text-destructive flex-shrink-0 mt-0.5" />
                {t("privacy.deleteConfirm")}
              </p>
              {deleteError && <p className="text-[13px] text-destructive mt-2" role="alert">{t("privacy.deleteFailed")}</p>}
              <div className="flex gap-2 mt-3 justify-end">
                <button onClick={() => setConfirmingDelete(false)} disabled={deleting} className="btn-secondary">
                  {t("privacy.cancel")}
                </button>
                <button
                  onClick={handleDeleteAllData}
                  disabled={deleting}
                  className="btn-primary !bg-destructive hover:!bg-destructive/90"
                >
                  <Trash2 className="w-4 h-4" /> {deleting ? t("privacy.deleting") : t("privacy.deleteConfirmButton")}
                </button>
              </div>
            </div>
          )}
        </div>
      </Section>

      {/* Blocked Domains */}
      <Section title={t("blockedDomains.title")} className="">
        <p className="text-[13px] text-muted-foreground mb-4">{t("blockedDomains.description")}</p>
        <TagInput
          tags={blockedDomains}
          value={newDomain}
          onChange={setNewDomain}
          onAdd={addDomain}
          onRemove={removeDomain}
          placeholder="example.com"
          variant="destructive"
        />
        {blockedDomains.length === 0 && (
          <p className="text-[13px] text-muted-foreground mt-2">{t("blockedDomains.none")}</p>
        )}
      </Section>

      {/* Plugins */}
      <Section title="Job Source Plugins">
        <p className="text-[13px] text-muted-foreground mb-4">
          Manage job source plugins. Built-in plugins provide LinkedIn, Indeed, SEEK, Naukri, Reed, and StepStone.
          Import community plugins (.yaml files) for additional job sites.
        </p>
        <div className="space-y-3 mb-4">
          {plugins.map((plugin) => (
            <div key={plugin.name} className="flex items-center justify-between p-3 border border-border rounded-lg">
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-foreground">{plugin.display_name}</span>
                  <span className="text-[11px] px-1.5 py-0.5 rounded bg-secondary text-muted-foreground">
                    v{plugin.version}
                  </span>
                  {plugin.is_builtin && (
                    <span className="text-[11px] px-1.5 py-0.5 rounded bg-primary/10 text-primary">Built-in</span>
                  )}
                  {plugin.tampered && (
                    <span
                      data-testid={`plugin-tampered-${plugin.name}`}
                      className="inline-flex items-center gap-1 text-[11px] px-1.5 py-0.5 rounded bg-amber-100 text-amber-800 font-semibold"
                    >
                      <AlertTriangle className="w-3 h-3" /> {t("plugins.tampered")}
                    </span>
                  )}
                </div>
                <p className="text-[12px] text-muted-foreground mt-0.5">
                  {plugin.description} &middot; {plugin.countries.join(", ")}
                </p>
              </div>
              <div className="flex items-center gap-2 ml-4">
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    aria-label={plugin.display_name}
                    checked={plugin.enabled && !plugin.tampered}
                    onChange={(e) => handleTogglePlugin(plugin.name, e.target.checked)}
                    className="sr-only peer"
                  />
                  <div className="w-9 h-5 bg-secondary peer-focus:ring-2 peer-focus:ring-primary/20 rounded-full peer peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-primary"></div>
                </label>
                {!plugin.is_builtin && (
                  <button onClick={() => handleRemovePlugin(plugin.name)} className="text-destructive hover:text-destructive/80">
                    <Trash2 className="w-4 h-4" />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
        {pluginError && !reviewPlugin && (
          <p className="text-[13px] text-destructive mb-3" role="alert">{pluginError}</p>
        )}
        {!reviewPlugin && (
          <button onClick={handleImportPlugin} className="btn-secondary">
            <Upload className="w-4 h-4" /> Import Plugin
          </button>
        )}
        {reviewPlugin && (
          <PluginReviewPanel
            plugin={reviewPlugin}
            installing={installing}
            error={pluginError}
            onInstall={handleInstallPlugin}
            onCancel={closeReview}
          />
        )}
      </Section>
    </div>
  );
}
