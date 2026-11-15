import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { CheckCircle, Loader2 } from "lucide-react";
import { getCountries, getProfile, saveProfile } from "../../lib/api";
import type { CandidateProfile, CountryConfig } from "../../lib/types";

/**
 * The answers application forms ask for most often, edited in place.
 *
 * Seen in real runs: every first application stopped with "needs your answer"
 * on work authorization, sponsorship, notice period or current CTC. Asking
 * here, once, saves a stalled run per question. Fields applications need
 * that are still empty get an amber outline.
 */
export default function ScreeningAnswersForm({ onSaved }: { onSaved?: () => void }) {
  const { t } = useTranslation("profile");
  const { t: tw } = useTranslation("wizard");
  const [profile, setProfile] = useState<CandidateProfile | null>(null);
  const [countries, setCountries] = useState<Record<string, CountryConfig>>({});
  const [noticeOptions, setNoticeOptions] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    getProfile()
      .then(setProfile)
      .catch(() => setProfile(null))
      .finally(() => setLoaded(true));
    getCountries()
      .then((d) => {
        setCountries(d.countries || {});
        setNoticeOptions(d.notice_period_options || []);
      })
      .catch(() => {});
  }, []);

  if (!loaded) return <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />;
  if (!profile) {
    return <p className="text-xs text-muted-foreground">{tw("screening.unavailable")}</p>;
  }

  const country = profile.country ? countries[profile.country] : undefined;
  const update = <K extends keyof CandidateProfile>(key: K, value: CandidateProfile[K]) => {
    setProfile((p) => (p ? { ...p, [key]: value } : p));
    setSaved(false);
  };
  const salary = profile.salary_expectation || { min: 0, max: 0, currency: "", period: "annual" as const };
  const missing = (v: unknown) => (v === "" || v === 0 || v == null ? "border-amber-400 ring-1 ring-amber-300" : "border-border");
  const inputCls = (v: unknown) => `w-full px-3 py-2 border rounded-lg text-sm bg-card ${missing(v)}`;

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      await saveProfile(profile);
      setSaved(true);
      onSaved?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-3" data-testid="screening-answers">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <label className="text-xs font-semibold text-foreground">
          {t("personal.fullName")}
          <input className={inputCls(profile.name)} value={profile.name} onChange={(e) => update("name", e.target.value)} />
        </label>
        <label className="text-xs font-semibold text-foreground">
          {t("personal.email")}
          <input className={inputCls(profile.email)} value={profile.email} onChange={(e) => update("email", e.target.value)} />
        </label>
        <label className="text-xs font-semibold text-foreground">
          {t("personal.phone")}
          <input className={inputCls(profile.phone)} value={profile.phone} onChange={(e) => update("phone", e.target.value)} />
        </label>
        <label className="text-xs font-semibold text-foreground">
          {t("work.workAuth")}
          {country?.work_auth_options?.length ? (
            <select
              className={inputCls(profile.work_authorization)}
              value={profile.work_authorization}
              onChange={(e) => update("work_authorization", e.target.value)}
            >
              <option value="">{t("work.workAuthPlaceholder")}</option>
              {country.work_auth_options.map((o) => (
                <option key={o} value={o}>{o}</option>
              ))}
            </select>
          ) : (
            <input
              className={inputCls(profile.work_authorization)}
              value={profile.work_authorization}
              onChange={(e) => update("work_authorization", e.target.value)}
            />
          )}
        </label>
        <label className="text-xs font-semibold text-foreground">
          {t("work.noticePeriod")}
          {noticeOptions.length ? (
            <select
              className={inputCls(profile.notice_period)}
              value={profile.notice_period}
              onChange={(e) => update("notice_period", e.target.value)}
            >
              <option value="">{t("work.noticePeriodPlaceholder")}</option>
              {noticeOptions.map((o) => (
                <option key={o} value={o}>{o}</option>
              ))}
            </select>
          ) : (
            <input
              className={inputCls(profile.notice_period)}
              value={profile.notice_period}
              onChange={(e) => update("notice_period", e.target.value)}
            />
          )}
        </label>
        <label className="text-xs font-semibold text-foreground">
          {t("salary.current")}
          <input
            className={inputCls(profile.current_compensation || "")}
            value={profile.current_compensation || ""}
            placeholder={t("salary.currentHint")}
            onChange={(e) => update("current_compensation", e.target.value)}
          />
        </label>
        <label className="text-xs font-semibold text-foreground">
          {t("salary.title")} — {t("salary.minimum")} ({salary.currency || country?.currency || ""})
          <input
            type="number"
            min={0}
            className={inputCls(salary.min)}
            value={salary.min || ""}
            onChange={(e) => update("salary_expectation", { ...salary, min: Number(e.target.value) || 0 })}
          />
        </label>
        <label className="text-xs font-semibold text-foreground">
          {t("salary.title")} — {t("salary.maximum")}
          <input
            type="number"
            min={0}
            className={inputCls(salary.max)}
            value={salary.max || ""}
            onChange={(e) => update("salary_expectation", { ...salary, max: Number(e.target.value) || 0 })}
          />
        </label>
      </div>
      <div className="flex flex-wrap gap-4">
        <label className="flex items-center gap-2 text-sm text-foreground">
          <input
            type="checkbox"
            className="h-4 w-4 accent-primary"
            checked={!!profile.visa_sponsorship_needed}
            onChange={(e) => update("visa_sponsorship_needed", e.target.checked)}
          />
          {t("work.visaSponsorship")}
        </label>
        <label className="flex items-center gap-2 text-sm text-foreground">
          <input
            type="checkbox"
            className="h-4 w-4 accent-primary"
            checked={!!profile.willing_to_relocate}
            onChange={(e) => update("willing_to_relocate", e.target.checked)}
          />
          {t("work.willingToRelocate")}
        </label>
      </div>
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={save}
          disabled={saving}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
        >
          {saving && <Loader2 className="w-4 h-4 animate-spin" />}
          {tw("screening.save")}
        </button>
        {saved && (
          <span className="flex items-center gap-1 text-xs text-green-700">
            <CheckCircle className="w-4 h-4" /> {tw("screening.saved")}
          </span>
        )}
        {error && <span className="text-xs text-destructive">{error}</span>}
      </div>
    </div>
  );
}
