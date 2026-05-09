import { useState, useEffect, useCallback } from "react";
import {
  BookOpen,
  User,
  Cpu,
  FileText,
  LogIn,
  Briefcase,
  Play,
  Brain,
  Settings,
  CheckCircle,
  XCircle,
  ChevronDown,
  ChevronRight,
  ArrowRight,
  RefreshCw,
  Loader2,
  Wand2,
} from "lucide-react";
import { getSetupStatus, type SetupStatus } from "../lib/api";
import { useNavigate } from "react-router-dom";
import { PageHeader } from "../components/ui";
import { useTranslation } from "react-i18next";

// ── Accordion Section ────────────────────────────────────────────────────
function AccordionSection({
  title,
  icon: Icon,
  children,
  defaultOpen = false,
}: {
  title: string;
  icon: typeof BookOpen;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="bg-white rounded-2xl border border-border overflow-hidden shadow-sm">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-3 px-5 py-4 text-left hover:bg-gray-50/50 transition-colors"
      >
        <Icon className="w-4 h-4 text-primary flex-shrink-0" />
        <span className="text-sm font-semibold text-foreground flex-1">
          {title}
        </span>
        {open ? (
          <ChevronDown className="w-4 h-4 text-muted-foreground" />
        ) : (
          <ChevronRight className="w-4 h-4 text-muted-foreground" />
        )}
      </button>
      {open && (
        <div className="px-5 pb-5 pt-0 border-t border-border">
          <div className="pt-4 text-sm text-foreground/80 leading-relaxed space-y-3">
            {children}
          </div>
        </div>
      )}
    </div>
  );
}

export default function Guide() {
  const { t } = useTranslation("guide");
  const [status, setStatus] = useState<SetupStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  const fetchStatus = useCallback(async () => {
    try {
      const s = await getSetupStatus();
      setStatus(s);
    } catch {
      /* backend not ready */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  const setupSteps = [
    {
      label: t("checklist.configureAi"),
      done: status?.llm,
      path: "/llm",
      icon: Cpu,
      required: true,
    },
    {
      label: t("checklist.setResume"),
      done: status?.resume,
      path: "/settings",
      icon: FileText,
      required: true,
    },
    {
      label: t("checklist.setupProfile"),
      done: status?.profile,
      path: "/profile",
      icon: User,
      required: true,
    },
  ];

  const allRequiredDone = status?.all_required_done;

  return (
    <div className="max-w-3xl">
      <PageHeader title={t("title")} subtitle={t("subtitle")} />

      {/* ── How It Works — Visual Pipeline ─────────────────────────────── */}
      <div className="card mb-6">
        <h3 className="text-lg font-semibold text-foreground mb-4">
          {t("howItWorks.title")}
        </h3>
        <div className="flex items-center justify-between gap-1">
          {[
            { icon: User, label: t("howItWorks.steps.profile"), color: "bg-[#FFF0F3] text-primary" },
            { icon: Cpu, label: t("howItWorks.steps.aiSetup"), color: "bg-purple-50 text-purple-600" },
            { icon: Briefcase, label: t("howItWorks.steps.collect"), color: "bg-amber-50 text-amber-600" },
            { icon: Play, label: t("howItWorks.steps.apply"), color: "bg-green-50 text-green-600" },
            { icon: Brain, label: t("howItWorks.steps.learn"), color: "bg-indigo-50 text-indigo-600" },
            { icon: RefreshCw, label: t("howItWorks.steps.improve"), color: "bg-pink-50 text-pink-600" },
          ].map((step, i) => {
            const Icon = step.icon;
            return (
              <div key={step.label} className="flex items-center gap-1">
                <div className="flex flex-col items-center gap-1.5">
                  <div
                    className={`w-10 h-10 rounded-xl flex items-center justify-center ${step.color}`}
                  >
                    <Icon className="w-5 h-5" />
                  </div>
                  <span className="text-[10px] font-medium text-muted-foreground">
                    {step.label}
                  </span>
                </div>
                {i < 5 && (
                  <ArrowRight className="w-3.5 h-3.5 text-gray-300 mx-0.5 mb-4" />
                )}
              </div>
            );
          })}
        </div>
        <p className="text-xs text-muted-foreground mt-4 text-center">
          {t("howItWorks.pipelineDescription")}
        </p>
      </div>

      {/* ── Live Setup Checklist ───────────────────────────────────────── */}
      <div className="card mb-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-foreground">
            {t("checklist.title")}
          </h3>
          <button
            onClick={fetchStatus}
            className="p-1 text-muted-foreground hover:text-foreground"
            title={t("checklist.refreshStatus")}
          >
            {loading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <RefreshCw className="w-4 h-4" />
            )}
          </button>
        </div>

        {allRequiredDone && (
          <div className="bg-green-50 rounded-lg p-3 mb-4 flex items-center gap-2">
            <CheckCircle className="w-4 h-4 text-green-600" />
            <span className="text-sm text-green-700 font-medium">
              {t("checklist.allDone")}
            </span>
          </div>
        )}

        <div className="space-y-2">
          {setupSteps.map((step) => {
            const Icon = step.icon;
            return (
              <div
                key={step.label}
                className="flex items-center justify-between py-2"
              >
                <div className="flex items-center gap-3">
                  {step.done ? (
                    <CheckCircle className="w-4 h-4 text-green-600" />
                  ) : (
                    <XCircle className="w-4 h-4 text-amber-500" />
                  )}
                  <Icon className="w-4 h-4 text-muted-foreground" />
                  <span
                    className={`text-sm ${
                      step.done ? "text-green-700" : "text-foreground"
                    }`}
                  >
                    {step.label}
                    {!step.required && (
                      <span className="text-xs text-muted-foreground ml-1">
                        {t("checklist.optional")}
                      </span>
                    )}
                  </span>
                </div>
                {!step.done && (
                  <button
                    onClick={() => navigate(step.path)}
                    className="text-xs text-primary font-medium hover:underline"
                  >
                    {t("checklist.setUp")}
                  </button>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* ── Step-by-Step Guide (Accordion) ─────────────────────────────── */}
      <div className="mb-6">
        <h3 className="text-lg font-semibold text-foreground mb-3">
          {t("stepByStep.title")}
        </h3>
        <div className="space-y-2">
          <AccordionSection title={t("sections.profile.title")} icon={User}>
            <p>
              {t("sections.profile.intro")}{" "}
              <button
                onClick={() => navigate("/profile")}
                className="text-primary font-medium hover:underline"
              >
                {t("sections.profile.linkText")}
              </button>{" "}
              {t("sections.profile.introEnd")}
            </p>
            <p>
              <strong>{t("sections.profile.essential")}</strong> {t("sections.profile.essentialDesc")}
            </p>
            <p>
              <strong>{t("sections.profile.targetTitles")}</strong> {t("sections.profile.targetTitlesDesc")}
            </p>
            <p>
              <strong>{t("sections.profile.targetLocations")}</strong> {t("sections.profile.targetLocationsDesc")}
            </p>
            <p>
              <strong>{t("sections.profile.skills")}</strong> {t("sections.profile.skillsDesc")}
            </p>
            <p>
              <strong>{t("sections.profile.notes")}</strong> {t("sections.profile.notesDesc")}
            </p>
          </AccordionSection>

          <AccordionSection title={t("sections.aiProvider.title")} icon={Cpu}>
            <p>
              {t("sections.aiProvider.intro")}{" "}
              <button
                onClick={() => navigate("/llm")}
                className="text-primary font-medium hover:underline"
              >
                {t("sections.aiProvider.linkText")}
              </button>{" "}
              {t("sections.aiProvider.introEnd")}
            </p>
            <p>
              <strong>{t("sections.aiProvider.recommended")}</strong> {t("sections.aiProvider.recommendedDesc")}
            </p>
            <p>
              <strong>{t("sections.aiProvider.bedrock")}</strong> {t("sections.aiProvider.bedrockDesc")}
            </p>
            <p>
              <strong>{t("sections.aiProvider.testConnection")}</strong> {t("sections.aiProvider.testConnectionDesc")}
            </p>
          </AccordionSection>

          <AccordionSection
            title={t("sections.login.title")}
            icon={LogIn}
          >
            <p>
              {t("sections.login.intro")} <strong>{t("sections.login.introBold")}</strong> {t("sections.login.introEnd")}
            </p>
            <p>
              <strong>{t("sections.login.howItWorks")}</strong> {t("sections.login.howItWorksDesc")}
            </p>
            <p>
              <strong>{t("sections.login.firstTime")}</strong> {t("sections.login.firstTimeDesc")}
            </p>
            <p>
              <strong>{t("sections.login.gmail")}</strong> {t("sections.login.gmailDesc")}
            </p>
            <p>
              <strong>{t("sections.login.sessionExpired")}</strong> {t("sections.login.sessionExpiredDesc")}
            </p>
          </AccordionSection>

          <AccordionSection
            title={t("sections.collecting.title")}
            icon={Briefcase}
          >
            <p>
              {t("sections.collecting.intro")}{" "}
              <button
                onClick={() => navigate("/jobs")}
                className="text-primary font-medium hover:underline"
              >
                {t("sections.collecting.linkText")}
              </button>{" "}
              {t("sections.collecting.introEnd")}
            </p>
            <p>
              <strong>{t("sections.collecting.howItWorks")}</strong> {t("sections.collecting.howItWorksDesc")}
            </p>
            <p>
              <strong>{t("sections.collecting.timing")}</strong> {t("sections.collecting.timingDesc")}
            </p>
            <p>
              <strong>{t("sections.collecting.maxJobs")}</strong> {t("sections.collecting.maxJobsDesc")}
            </p>
            <p>
              <strong>{t("sections.collecting.singleTitle")}</strong> {t("sections.collecting.singleTitleDesc")}
            </p>
          </AccordionSection>

          <AccordionSection title={t("sections.applying.title")} icon={Play}>
            <p>
              {t("sections.applying.intro")}{" "}
              <button
                onClick={() => navigate("/apply")}
                className="text-primary font-medium hover:underline"
              >
                {t("sections.applying.linkText")}
              </button>{" "}
              {t("sections.applying.introEnd")}
            </p>
            <p>
              <strong>{t("sections.applying.easyApply")}</strong> {t("sections.applying.easyApplyDesc")}
            </p>
            <p>
              <strong>{t("sections.applying.externalSites")}</strong> {t("sections.applying.externalSitesDesc")}
            </p>
            <p>
              <strong>{t("sections.applying.tailoredResumes")}</strong> {t("sections.applying.tailoredResumesDesc")}
            </p>
            <p>
              <strong>{t("sections.applying.limit")}</strong> {t("sections.applying.limitDesc")}
            </p>
            <p>
              <strong>{t("sections.applying.blockedDomains")}</strong> {t("sections.applying.blockedDomainsDesc")}{" "}
              <button
                onClick={() => navigate("/settings")}
                className="text-primary font-medium hover:underline"
              >
                {t("sections.applying.blockedDomainsLink")}
              </button>
              {t("sections.applying.blockedDomainsEnd")}
            </p>
          </AccordionSection>

          <AccordionSection
            title={t("sections.memory.title")}
            icon={Brain}
          >
            <p>
              {t("sections.memory.intro")}{" "}
              <strong>{t("sections.memory.introBold")}</strong>{t("sections.memory.introEnd")}
            </p>
            <p>
              <strong>{t("sections.memory.howItWorks")}</strong> {t("sections.memory.howItWorksDesc")}
            </p>
            <p>
              <strong>{t("sections.memory.atsNormalization")}</strong> {t("sections.memory.atsNormalizationDesc")}
            </p>
            <p>
              <strong>{t("sections.memory.categories")}</strong>
            </p>
            <ul className="list-disc list-inside space-y-1 pl-2">
              <li>
                <strong>{t("sections.memory.categoryNavigation")}</strong> {t("sections.memory.categoryNavigationDesc")}
              </li>
              <li>
                <strong>{t("sections.memory.categoryFormStrategy")}</strong> {t("sections.memory.categoryFormStrategyDesc")}
              </li>
              <li>
                <strong>{t("sections.memory.categoryElement")}</strong> {t("sections.memory.categoryElementDesc")}
              </li>
              <li>
                <strong>{t("sections.memory.categoryFailure")}</strong> {t("sections.memory.categoryFailureDesc")}
              </li>
              <li>
                <strong>{t("sections.memory.categorySiteStructure")}</strong> {t("sections.memory.categorySiteStructureDesc")}
              </li>
              <li>
                <strong>{t("sections.memory.categoryQA")}</strong> {t("sections.memory.categoryQADesc")}
              </li>
            </ul>
            <p>
              <strong>{t("sections.memory.maintenance")}</strong> {t("sections.memory.maintenanceDesc")}{" "}
              <button
                onClick={() => navigate("/memory")}
                className="text-primary font-medium hover:underline"
              >
                {t("sections.memory.maintenanceLink")}
              </button>{" "}
              {t("sections.memory.maintenanceEnd")}
            </p>
          </AccordionSection>

          <AccordionSection
            title={t("sections.tips.title")}
            icon={Settings}
          >
            <p>
              <strong>{t("sections.tips.oneOperation")}</strong> {t("sections.tips.oneOperationDesc")}
            </p>
            <p>
              <strong>{t("sections.tips.nonDeterministic")}</strong> {t("sections.tips.nonDeterministicDesc")}
            </p>
            <p>
              <strong>{t("sections.tips.rateLimits")}</strong> {t("sections.tips.rateLimitsDesc")}
            </p>
            <p>
              <strong>{t("sections.tips.browserStuck")}</strong> {t("sections.tips.browserStuckDesc")}
            </p>
            <p>
              <strong>{t("sections.tips.loginExpired")}</strong> {t("sections.tips.loginExpiredDesc")}
            </p>
            <p>
              <strong>{t("sections.tips.resumeUpload")}</strong> {t("sections.tips.resumeUploadDesc")}
            </p>
            <p>
              <strong>{t("sections.tips.backendNotConnecting")}</strong> {t("sections.tips.backendNotConnectingDesc")}{" "}
              <code className="bg-gray-100 px-1.5 py-0.5 rounded text-xs">
                {t("sections.tips.backendCommand")}
              </code>
            </p>
            <p>
              <strong>{t("sections.tips.costs")}</strong> {t("sections.tips.costsDesc")}
            </p>
          </AccordionSection>
        </div>
      </div>

      {/* ── Re-run Setup Wizard ────────────────────────────────────────── */}
      <div className="card mb-6">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-foreground">
              {t("setupWizard.title")}
            </h3>
            <p className="text-xs text-muted-foreground mt-1">
              {t("setupWizard.description")}
            </p>
          </div>
          <button
            onClick={() => {
              // Dispatch a custom event that App.tsx listens for
              window.dispatchEvent(new CustomEvent("open-setup-wizard"));
            }}
            className="btn-secondary"
          >
            <Wand2 className="w-4 h-4" />
            {t("setupWizard.button")}
          </button>
        </div>
      </div>
    </div>
  );
}
