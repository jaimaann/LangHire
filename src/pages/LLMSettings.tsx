import LLMSettingsForm from "../components/forms/LLMSettingsForm";
import { PageHeader } from "../components/ui";

export default function LLMSettingsPage() {
  return (
    <div className="max-w-2xl">
      <PageHeader title="LLM Settings" subtitle="Configure your AI model provider for job applications" />
      <LLMSettingsForm />
    </div>
  );
}
