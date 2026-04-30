import { useState, useEffect } from "react";
import { Save, FolderOpen, X } from "lucide-react";
import { getSettings, saveSettings } from "../lib/api";
import { open } from "@tauri-apps/plugin-dialog";
import { PageHeader, LoadingSpinner, Section } from "../components/ui";
import TagInput from "../components/ui/TagInput";

export default function SettingsPage() {
  const [resumePath, setResumePath] = useState("");
  const [blockedDomains, setBlockedDomains] = useState<string[]>([]);
  const [newDomain, setNewDomain] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [maxFailures, setMaxFailures] = useState(8);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getSettings()
      .then((data) => {
        setResumePath(data.resume_path || "");
        setBlockedDomains(data.blocked_domains || []);
        setMaxFailures(data.max_failures || 8);
        const sens = data.sensitive_data || { email: "", password: "" };
        setEmail(sens.email || "");
        setPassword(sens.password || "");
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

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

      {/* Blocked Domains */}
      <Section title="Blocked Domains" className="">
        <p className="text-[13px] text-muted-foreground mb-4">Jobs on these domains will be automatically skipped.</p>
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
    </div>
  );
}
