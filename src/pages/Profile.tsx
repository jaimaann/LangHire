import { useState, useEffect } from "react";
import { Save } from "lucide-react";
import { getProfile, saveProfile } from "../lib/api";
import type { CandidateProfile } from "../lib/types";
import { PageHeader, LoadingSpinner, Section } from "../components/ui";
import TagInputShared from "../components/ui/TagInput";

const defaultProfile: CandidateProfile = {
  name: "",
  email: "",
  phone: "",
  address: { street: "", city: "", state: "", zip: "", country: "USA" },
  work_authorization: "Authorized to work in the US",
  visa_sponsorship_needed: false,
  willing_to_relocate: false,
  preferred_work_mode: "hybrid",
  years_of_experience: 0,
  education: { degree: "", school: "", graduation: "" },
  current_role: "",
  target_job_titles: [],
  target_locations: [],
  languages: ["English"],
  skills: [],
  salary_expectation: { min: 50000, max: 100000, currency: "USD" },
  notes: "",
};

export default function Profile() {
  const [profile, setProfile] = useState<CandidateProfile>(defaultProfile);
  const [newTitle, setNewTitle] = useState("");
  const [newSkill, setNewSkill] = useState("");
  const [newLocation, setNewLocation] = useState("");
  const [newLanguage, setNewLanguage] = useState("");
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getProfile()
      .then((data) => setProfile({ ...defaultProfile, ...data }))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const update = (field: string, value: unknown) => {
    setProfile((p) => ({ ...p, [field]: value }));
    setSaved(false);
  };

  const updateNested = (parent: keyof Pick<CandidateProfile, "address" | "education" | "salary_expectation">, field: string, value: unknown) => {
    setProfile((p) => {
      const current = p[parent];
      if (typeof current === "object" && current !== null) {
        return { ...p, [parent]: { ...current, [field]: value } };
      }
      return p;
    });
    setSaved(false);
  };

  const addToList = (field: keyof CandidateProfile, value: string, setter: (v: string) => void) => {
    if (!value.trim()) return;
    const list = profile[field] as string[];
    if (!list.includes(value.trim())) {
      update(field, [...list, value.trim()]);
    }
    setter("");
  };

  const removeFromList = (field: keyof CandidateProfile, value: string) => {
    update(field, (profile[field] as string[]).filter((v) => v !== value));
  };

  const handleSave = async () => {
    try {
      setSaveError(null);
      await saveProfile(profile);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (e) {
      setSaveError("Failed to save profile. Please try again.");
      console.error("Failed to save profile:", e);
    }
  };

  if (loading) return <LoadingSpinner />;

  return (
    <div className="max-w-3xl">
      <PageHeader
        title="Candidate Profile"
        subtitle="Your personal information used for job applications"
        actions={
          <button onClick={handleSave} className="btn-primary">
            <Save className="w-4 h-4" />
            {saved ? "Saved" : "Save Profile"}
          </button>
        }
      />
      {saveError && (
        <div className="error-banner mb-5">{saveError}</div>
      )}

      {/* Personal Info */}
      <Section title="Personal Information">
        <div className="grid grid-cols-2 gap-4">
          <Input label="Full Name" value={profile.name} onChange={(v) => update("name", v)} />
          <Input label="Email" type="email" value={profile.email} onChange={(v) => update("email", v)} />
          <Input label="Phone" value={profile.phone} onChange={(v) => update("phone", v)} />
          <Input label="Current Role" value={profile.current_role} onChange={(v) => update("current_role", v)} />
        </div>
      </Section>

      {/* Address */}
      <Section title="Address">
        <div className="grid grid-cols-2 gap-4">
          <Input label="Street" value={profile.address.street} onChange={(v) => updateNested("address", "street", v)} className="col-span-2" />
          <Input label="City" value={profile.address.city} onChange={(v) => updateNested("address", "city", v)} />
          <Input label="State" value={profile.address.state} onChange={(v) => updateNested("address", "state", v)} />
          <Input label="ZIP" value={profile.address.zip} onChange={(v) => updateNested("address", "zip", v)} />
          <Input label="Country" value={profile.address.country} onChange={(v) => updateNested("address", "country", v)} />
        </div>
      </Section>

      {/* Work Preferences */}
      <Section title="Work Preferences">
        <div className="grid grid-cols-2 gap-4">
          <Input label="Work Authorization" value={profile.work_authorization} onChange={(v) => update("work_authorization", v)} />
          <div>
            <label className="block text-sm font-medium text-foreground mb-1">Work Mode</label>
            <select
              value={profile.preferred_work_mode}
              onChange={(e) => update("preferred_work_mode", e.target.value)}
              className="w-full px-3 py-2 border border-border rounded-lg text-sm bg-white"
            >
              <option value="remote">Remote</option>
              <option value="hybrid">Hybrid</option>
              <option value="onsite">On-site</option>
            </select>
          </div>
          <Checkbox label="Visa Sponsorship Needed" checked={profile.visa_sponsorship_needed} onChange={(v) => update("visa_sponsorship_needed", v)} />
          <Checkbox label="Willing to Relocate" checked={profile.willing_to_relocate} onChange={(v) => update("willing_to_relocate", v)} />
          <Input label="Years of Experience" type="number" value={String(profile.years_of_experience)} onChange={(v) => update("years_of_experience", Number(v))} />
        </div>
      </Section>

      {/* Education */}
      <Section title="Education">
        <div className="grid grid-cols-2 gap-4">
          <Input label="Degree" value={profile.education.degree} onChange={(v) => updateNested("education", "degree", v)} />
          <Input label="School" value={profile.education.school} onChange={(v) => updateNested("education", "school", v)} />
          <Input label="Graduation" value={profile.education.graduation} onChange={(v) => updateNested("education", "graduation", v)} />
        </div>
      </Section>

      {/* Salary */}
      <Section title="Salary Expectation">
        <div className="grid grid-cols-3 gap-4">
          <Input label="Minimum ($)" type="number" value={String(profile.salary_expectation.min)} onChange={(v) => updateNested("salary_expectation", "min", Number(v))} />
          <Input label="Maximum ($)" type="number" value={String(profile.salary_expectation.max)} onChange={(v) => updateNested("salary_expectation", "max", Number(v))} />
          <Input label="Currency" value={profile.salary_expectation.currency} onChange={(v) => updateNested("salary_expectation", "currency", v)} />
        </div>
      </Section>

      {/* Tag Lists */}
      <Section title="Target Job Titles">
        <TagInputShared tags={profile.target_job_titles} value={newTitle} onChange={setNewTitle}
          onAdd={() => addToList("target_job_titles", newTitle, setNewTitle)}
          onRemove={(v) => removeFromList("target_job_titles", v)} placeholder="Add a job title..." />
      </Section>

      <Section title="Target Locations">
        <TagInputShared tags={profile.target_locations} value={newLocation} onChange={setNewLocation}
          onAdd={() => addToList("target_locations", newLocation, setNewLocation)}
          onRemove={(v) => removeFromList("target_locations", v)} placeholder="Add a location..." />
      </Section>

      <Section title="Skills">
        <TagInputShared tags={profile.skills} value={newSkill} onChange={setNewSkill}
          onAdd={() => addToList("skills", newSkill, setNewSkill)}
          onRemove={(v) => removeFromList("skills", v)} placeholder="Add a skill..." />
      </Section>

      <Section title="Languages">
        <TagInputShared tags={profile.languages} value={newLanguage} onChange={setNewLanguage}
          onAdd={() => addToList("languages", newLanguage, setNewLanguage)}
          onRemove={(v) => removeFromList("languages", v)} placeholder="Add a language..." />
      </Section>

      {/* Notes */}
      <Section title="Notes">
        <textarea value={profile.notes} onChange={(e) => update("notes", e.target.value)}
          rows={3} className="input-base"
          placeholder="Any special instructions for the AI agent..." />
      </Section>
    </div>
  );
}

function Input({ label, value, onChange, type = "text", className = "" }: {
  label: string; value: string; onChange: (v: string) => void; type?: string; className?: string;
}) {
  return (
    <div className={className}>
      <label className="block text-sm font-semibold text-foreground mb-1.5">{label}</label>
      <input type={type} value={value} onChange={(e) => onChange(e.target.value)}
        className="input-base" />
    </div>
  );
}

function Checkbox({ label, checked, onChange }: {
  label: string; checked: boolean; onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex items-center gap-2.5 cursor-pointer">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)}
        className="w-4 h-4 rounded-md border-border accent-primary" />
      <span className="text-sm text-foreground">{label}</span>
    </label>
  );
}

