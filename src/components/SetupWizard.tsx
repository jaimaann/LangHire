import { useState, useEffect, useCallback } from "react";
import {
  ChevronRight,
  ChevronLeft,
  X,
  User,
  Cpu,
  FileText,
  Rocket,
  CheckCircle,
  XCircle,
  Loader2,
  Briefcase,
  Sparkles,
  Key,
  Search,
  BookOpen,
} from "lucide-react";
import {
  getSetupStatus,
  completeOnboarding,
  parseResumeToProfile,
  type SetupStatus,
} from "../lib/api";
import { trackEvent } from "../lib/analytics";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import LLMSettingsForm from "./forms/LLMSettingsForm";
import ResumePickerForm from "./forms/ResumePickerForm";

interface SetupWizardProps {
  onClose: () => void;
  onNavigateAway: (currentStep: number) => void;
  initialStep?: number;
}

const STEPS = [
  { id: "welcome", icon: Rocket },
  { id: "llm", icon: Cpu },
  { id: "resume", icon: FileText },
  { id: "profile", icon: User },
  { id: "ready", icon: CheckCircle },
];

export default function SetupWizard({ onClose, onNavigateAway, initialStep = 0 }: SetupWizardProps) {
  const { t } = useTranslation("wizard");
  const [step, setStep] = useState(initialStep);
  const [status, setStatus] = useState<SetupStatus | null>(null);
  const [parsing, setParsing] = useState(false);
  const [parseResult, setParseResult] = useState<{
    success: boolean;
    message: string;
    fields_filled?: number;
  } | null>(null);
  const navigate = useNavigate();

  const stepLabels = [
    t("steps.welcome"),
    t("steps.llm"),
    t("steps.resume"),
    t("steps.profile"),
    t("steps.ready"),
  ];

  const fetchStatus = useCallback(async () => {
    try {
      const s = await getSetupStatus();
      setStatus(s);
    } catch { /* backend not ready */ }
  }, []);

  useEffect(() => { fetchStatus(); }, [fetchStatus]);

  const handleParseResume = async () => {
    setParsing(true);
    setParseResult(null);
    try {
      const result = await parseResumeToProfile();
      setParseResult(result);
      if (result.success) await fetchStatus();
    } catch (e) {
      setParseResult({ success: false, message: e instanceof Error ? e.message : "Failed to parse resume" });
    } finally {
      setParsing(false);
    }
  };

  const handleFinish = async () => {
    try { await completeOnboarding(); } catch { /* non-fatal */ }
    trackEvent("onboarding_completed");
    onClose();
  };

  const next = () => { fetchStatus(); setStep((s) => Math.min(s + 1, STEPS.length - 1)); };
  const prev = () => setStep((s) => Math.max(s - 1, 0));

  return (
    <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-white rounded-3xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-6 pt-5 pb-4 border-b border-border flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-primary rounded-xl flex items-center justify-center">
              <Briefcase className="w-4 h-4 text-white" />
            </div>
            <h2 className="text-lg font-bold text-foreground">{t("title")}</h2>
          </div>
          <button onClick={onClose} className="p-2 text-muted-foreground hover:text-foreground rounded-xl hover:bg-secondary transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Step Indicators */}
        <div className="px-6 py-3 border-b border-border bg-gray-50/50">
          <div className="flex items-center justify-between">
            {STEPS.map((s, i) => {
              const Icon = s.icon;
              const isActive = i === step;
              const isDone = i < step;
              return (
                <div key={s.id} className="flex items-center gap-1.5">
                  <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs ${isDone ? "bg-green-100 text-green-700" : isActive ? "bg-primary text-primary-foreground" : "bg-gray-100 text-gray-400"}`}>
                    {isDone ? <CheckCircle className="w-4 h-4" /> : <Icon className="w-3.5 h-3.5" />}
                  </div>
                  <span className={`text-xs font-medium hidden sm:inline ${isActive ? "text-foreground" : isDone ? "text-green-700" : "text-muted-foreground"}`}>{stepLabels[i]}</span>
                  {i < STEPS.length - 1 && <div className={`w-4 h-px mx-1 ${isDone ? "bg-green-300" : "bg-gray-200"}`} />}
                </div>
              );
            })}
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-6 py-6">

          {/* Step 0: Welcome */}
          {step === 0 && (
            <div className="text-center py-4">
              <div className="w-16 h-16 bg-primary/10 rounded-2xl flex items-center justify-center mx-auto mb-4">
                <Briefcase className="w-8 h-8 text-primary" />
              </div>
              <h3 className="text-2xl font-bold text-foreground mb-2">{t("welcome.heading")}</h3>
              <p className="text-muted-foreground mb-6 max-w-md mx-auto">
                {t("welcome.description")}
              </p>
              <div className="bg-gray-50 rounded-xl p-5 max-w-md mx-auto text-left">
                <h4 className="text-sm font-semibold text-foreground mb-3">{t("welcome.howItWorks")}</h4>
                <div className="space-y-3">
                  {[
                    { icon: Cpu, title: t("welcome.items.configureAi"), desc: t("welcome.items.configureAiDesc") },
                    { icon: FileText, title: t("welcome.items.uploadResume"), desc: t("welcome.items.uploadResumeDesc") },
                    { icon: User, title: t("welcome.items.reviewProfile"), desc: t("welcome.items.reviewProfileDesc") },
                    { icon: Key, title: t("welcome.items.loginLinkedIn"), desc: t("welcome.items.loginLinkedInDesc") },
                  ].map((item) => (
                    <div key={item.title} className="flex items-start gap-3">
                      <div className="w-8 h-8 rounded-xl bg-secondary flex items-center justify-center flex-shrink-0">
                        <item.icon className="w-4 h-4 text-foreground" />
                      </div>
                      <div>
                        <p className="text-sm font-medium text-foreground">{item.title}</p>
                        <p className="text-xs text-muted-foreground">{item.desc}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Step 1: LLM Provider — INLINE FORM */}
          {step === 1 && (
            <div>
              <h3 className="text-xl font-bold text-foreground mb-2">{t("llmStep.heading")}</h3>
              <p className="text-sm text-muted-foreground mb-4">
                {t("llmStep.description")}
              </p>
              <LLMSettingsForm compact onSaved={fetchStatus} />
            </div>
          )}

          {/* Step 2: Resume + Auto-Fill Profile — INLINE FORM */}
          {step === 2 && (
            <div>
              <h3 className="text-xl font-bold text-foreground mb-2">{t("resumeStep.heading")}</h3>
              <p className="text-sm text-muted-foreground mb-4">
                {t("resumeStep.description")}
              </p>

              {/* Inline resume picker */}
              <div className="bg-gray-50 rounded-xl p-4 mb-4">
                <ResumePickerForm onSaved={fetchStatus} />
              </div>

              {/* Auto-Fill Button */}
              {status?.resume && status?.llm && (
                <div className="bg-indigo-50 rounded-xl p-5 border border-indigo-200">
                  <div className="flex items-center gap-2 mb-2">
                    <Sparkles className="w-5 h-5 text-indigo-600" />
                    <h4 className="text-sm font-semibold text-indigo-900">{t("resumeStep.autoFill.title")}</h4>
                  </div>
                  <p className="text-xs text-indigo-700 mb-4">
                    {t("resumeStep.autoFill.description")}
                  </p>
                  {!parseResult && (
                    <button onClick={handleParseResume} disabled={parsing}
                      className="flex items-center gap-2 px-5 py-2.5 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50">
                      {parsing ? <><Loader2 className="w-4 h-4 animate-spin" /> {t("resumeStep.autoFill.parsing")}</> : <><Sparkles className="w-4 h-4" /> {t("resumeStep.autoFill.button")}</>}
                    </button>
                  )}
                  {parseResult && (
                    <div className={`flex items-start gap-2 p-3 rounded-lg ${parseResult.success ? "bg-green-50 border border-green-200" : "bg-red-50 border border-red-200"}`}>
                      {parseResult.success ? <CheckCircle className="w-5 h-5 text-green-600 mt-0.5 flex-shrink-0" /> : <XCircle className="w-5 h-5 text-red-600 mt-0.5 flex-shrink-0" />}
                      <div>
                        <p className={`text-sm font-medium ${parseResult.success ? "text-green-700" : "text-red-700"}`}>{parseResult.message}</p>
                        {parseResult.success && <p className="text-xs text-green-600 mt-1">{t("resumeStep.autoFill.nextHint")}</p>}
                        {!parseResult.success && <button onClick={() => setParseResult(null)} className="text-xs text-red-600 underline mt-1">{t("resumeStep.autoFill.tryAgain")}</button>}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {(!status?.llm || !status?.resume) && (
                <div className="bg-amber-50 rounded-lg p-4 border border-amber-200 mt-4">
                  <p className="text-xs text-amber-700"><strong>{t("resumeStep.prerequisiteLabel")}</strong> {t("resumeStep.prerequisite")}</p>
                </div>
              )}
            </div>
          )}

          {/* Step 3: Review Profile */}
          {step === 3 && (
            <div>
              <h3 className="text-xl font-bold text-foreground mb-2">{t("profileStep.heading")}</h3>
              <p className="text-sm text-muted-foreground mb-4">
                {parseResult?.success
                  ? t("profileStep.descriptionParsed")
                  : t("profileStep.descriptionManual")}
              </p>
              <div className="bg-gray-50 rounded-xl p-5 mb-4">
                <div className="flex items-center gap-3 mb-3">
                  {status?.profile ? <CheckCircle className="w-5 h-5 text-green-600" /> : <XCircle className="w-5 h-5 text-amber-500" />}
                  <span className="text-sm font-medium text-foreground">{status?.profile ? t("profileStep.profileConfigured") : t("profileStep.profileNeeded")}</span>
                </div>
                <p className="text-xs text-muted-foreground mb-3">{t("profileStep.keyFields")}</p>
                <button onClick={() => { onNavigateAway(step); navigate("/profile"); }}
                  className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90">
                  <User className="w-4 h-4" /> {status?.profile ? t("profileStep.reviewEdit") : t("profileStep.goToProfile")}
                </button>
              </div>
              {parseResult?.success && (
                <div className="bg-green-50 rounded-lg p-4 border border-green-200">
                  <p className="text-xs text-green-700"><strong>{t("profileStep.autoFilledLabel")}</strong> {t("profileStep.autoFilledHint")}</p>
                </div>
              )}
            </div>
          )}

          {/* Step 4: Ready */}
          {step === 4 && (
            <div className="text-center py-4">
              <div className="w-16 h-16 bg-green-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
                <CheckCircle className="w-8 h-8 text-green-600" />
              </div>
              <h3 className="text-2xl font-bold text-foreground mb-2">{t("readyStep.heading")}</h3>
              <p className="text-muted-foreground mb-6 max-w-md mx-auto">
                {status?.all_required_done ? t("readyStep.descriptionDone") : t("readyStep.descriptionIncomplete")}
              </p>
              <div className="bg-gray-50 rounded-xl p-5 max-w-sm mx-auto mb-6 text-left">
                <h4 className="text-sm font-semibold text-foreground mb-3">{t("readyStep.setupStatus")}</h4>
                <div className="space-y-2">
                  {[
                    { label: t("readyStep.aiProvider"), done: status?.llm },
                    { label: t("readyStep.resume"), done: status?.resume },
                    { label: t("readyStep.profile"), done: status?.profile },
                  ].map((item) => (
                    <div key={item.label} className="flex items-center gap-2">
                      {item.done ? <CheckCircle className="w-4 h-4 text-green-600" /> : <XCircle className="w-4 h-4 text-amber-500" />}
                      <span className={`text-sm ${item.done ? "text-green-700" : "text-muted-foreground"}`}>{item.label}</span>
                    </div>
                  ))}
                </div>
              </div>
              <div className="flex gap-3 justify-center">
                <button onClick={() => { handleFinish(); navigate("/jobs"); }} className="btn-primary"><Search className="w-4 h-4" /> {t("readyStep.collectJobs")}</button>
                <button onClick={() => { handleFinish(); navigate("/guide"); }} className="btn-secondary"><BookOpen className="w-4 h-4" /> {t("readyStep.viewGuide")}</button>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-border flex items-center justify-between bg-gray-50/50">
          <div>
            {step > 0 && step < STEPS.length - 1 && (
              <button onClick={prev} className="flex items-center gap-1 px-3 py-2 text-sm text-muted-foreground hover:text-foreground">
                <ChevronLeft className="w-4 h-4" /> {t("nav.back")}
              </button>
            )}
          </div>
          <div className="flex items-center gap-2">
            {step < STEPS.length - 1 && <button onClick={onClose} className="px-3 py-2 text-sm text-muted-foreground hover:text-foreground">{t("nav.skipForNow")}</button>}
            {step < STEPS.length - 1 ? (
              <button onClick={next} disabled={parsing} className="flex items-center gap-1 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-50">
                {step === 0 ? t("nav.letsGo") : t("nav.next")} <ChevronRight className="w-4 h-4" />
              </button>
            ) : (
              <button onClick={handleFinish} className="flex items-center gap-1 px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700">
                {t("nav.finishSetup")} <CheckCircle className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
