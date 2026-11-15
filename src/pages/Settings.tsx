import { useState, useEffect } from "react";
import { Save, FolderOpen, X, Upload, Trash2, Sun, Moon, Monitor, Download, AlertTriangle } from "lucide-react";
import { getSettings, saveSettings, getPlugins, togglePlugin, removePlugin, importPlugin, deleteAllData, exportAllData } from "../lib/api";
import { setTelemetryEnabled as setAnalyticsTelemetry, hasTelemetryConsent } from "../lib/analytics";
import { clearLocalAppData, restartApp, exportFileName, downloadJson } from "../lib/privacy";
import { getStoredTheme, setTheme, type ThemeMode } from "../lib/theme";
import { open } from "@tauri-apps/plugin-dialog";
import { useTranslation } from "react-i18next";
import { PageHeader, LoadingSpinner, Section } from "../components/ui";
import TagInput from "../components/ui/TagInput";
import type { PluginConfig } from "../lib/types";
import { LANGUAGE_NAMES, getSavedLanguage, saveLanguagePreference } from "../i18n/languageDetection";
import { loadLanguage } from "../i18n";

/** Allowed values for agent conversation log retention (days; 0 = don't save). */
const LOG_RETENTION_OPTIONS = [0, 7, 14, 30, 90] as const;
const DEFAULT_LOG_RETENTION_DAYS = 14;

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
      }),
      getPlugins().then((res) => setPlugins(res.plugins || [])),
    ])
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleTogglePlugin = async (name: string, enabled: boolean) => {
    await togglePlugin(name, enabled);
    setPlugins((prev) => prev.map((p) => p.name === name ? { ...p, enabled } : p));
  };

  const handleRemovePlugin = async (name: string) => {
    await removePlugin(name);
    setPlugins((prev) => prev.filter((p) => p.name !== name));
  };

  const handleImportPlugin = async () => {
    const file = await open({ filters: [{ name: "YAML Plugin", extensions: ["yaml", "yml"] }] });
    if (file) {
      try {
        await importPlugin(file as string);
        const res = await getPlugins();
        setPlugins(res.plugins || []);
      } catch (e) {
        alert(e instanceof Error ? e.message : "Failed to import plugin");
      }
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
              const file = await open({ filters: [{ name: "PDF", extensions: ["pdf"] }] });
              if (file) setResumePath(file as string);
            }}
            className="btn-secondary">
            <FolderOpen className="w-4 h-4" /> Browse
          </button>
        </div>
        <p className="text-[13px] text-muted-foreground mt-2">PDF resume file used for job applications</p>
      </Section>

      {/* Sensitive Data */}
      <Section title="Account Credentials">
        <p className="text-[13px] text-muted-foreground mb-4">
          Used for creating accounts on external ATS platforms during applications.
          Stored locally in plaintext. Prefer using SSO (Sign in with LinkedIn/Google) when possible.
        </p>
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
          <p className="text-[13px] text-muted-foreground mt-2">No blocked domains</p>
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
                </div>
                <p className="text-[12px] text-muted-foreground mt-0.5">
                  {plugin.description} &middot; {plugin.countries.join(", ")}
                </p>
              </div>
              <div className="flex items-center gap-2 ml-4">
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={plugin.enabled}
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
        <button onClick={handleImportPlugin} className="btn-secondary">
          <Upload className="w-4 h-4" /> Import Plugin
        </button>
      </Section>
    </div>
  );
}
