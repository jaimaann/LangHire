import { useState, useEffect, useRef } from "react";
import { FolderOpen, CheckCircle, Loader2 } from "lucide-react";
import { getSettings, saveSettings } from "../../lib/api";
import { open } from "@tauri-apps/plugin-dialog";

interface ResumePickerFormProps {
  onSaved?: () => void;
}

export default function ResumePickerForm({ onSaved }: ResumePickerFormProps) {
  const [resumePath, setResumePath] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(true);
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastSaved = useRef("");

  useEffect(() => {
    getSettings()
      .then((data) => {
        const path = data.resume_path || "";
        setResumePath(path);
        lastSaved.current = path;
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    return () => { if (saveTimer.current) clearTimeout(saveTimer.current); };
  }, []);

  const doSave = async (path: string) => {
    if (path === lastSaved.current || !path.trim()) return;
    setSaving(true);
    try {
      const current = await getSettings();
      await saveSettings({ ...current, resume_path: path });
      lastSaved.current = path;
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
      onSaved?.();
    } catch { /* silent */ }
    finally { setSaving(false); }
  };

  const handleChange = (path: string) => {
    setResumePath(path);
    setSaved(false);
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => doSave(path), 800);
  };

  const handleBrowse = async () => {
    try {
      const file = await open({ filters: [{ name: "PDF", extensions: ["pdf"] }] });
      if (file) {
        setResumePath(file as string);
        doSave(file as string); // Save immediately on browse
      }
    } catch { /* Dialog cancelled */ }
  };

  if (loading) return <div className="flex justify-center py-4"><Loader2 className="w-5 h-5 animate-spin text-primary" /></div>;

  return (
    <div className="space-y-2">
      <label className="block text-sm font-medium text-foreground">Resume PDF Path</label>
      <div className="flex gap-2">
        <input
          value={resumePath}
          onChange={(e) => handleChange(e.target.value)}
          placeholder="/path/to/your/resume.pdf"
          className="flex-1 px-3 py-2 border border-border rounded-lg text-sm"
        />
        <button onClick={handleBrowse} className="flex items-center gap-2 px-3 py-2 border border-border rounded-lg text-sm hover:bg-secondary">
          <FolderOpen className="w-4 h-4" /> Browse
        </button>
      </div>
      <div className="flex items-center gap-2 h-5">
        {saving && <span className="flex items-center gap-1 text-xs text-muted-foreground"><Loader2 className="w-3 h-3 animate-spin" /> Saving...</span>}
        {saved && <span className="flex items-center gap-1 text-xs text-green-600"><CheckCircle className="w-3 h-3" /> Saved ✓</span>}
        {!saving && !saved && resumePath && <span className="text-xs text-muted-foreground">PDF file used for job applications</span>}
      </div>
    </div>
  );
}
