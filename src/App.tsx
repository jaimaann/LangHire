import { useState, useEffect, useCallback, lazy, Suspense } from "react";
import { Routes, Route } from "react-router-dom";
import Sidebar from "./components/layout/Sidebar";
import ErrorBoundary from "./components/ErrorBoundary";
import SetupWizard from "./components/SetupWizard";
import { getSetupStatus } from "./lib/api";
import { Wand2, Loader2 } from "lucide-react";

const Dashboard = lazy(() => import("./pages/Dashboard"));
const Profile = lazy(() => import("./pages/Profile"));
const LLMSettings = lazy(() => import("./pages/LLMSettings"));
const Jobs = lazy(() => import("./pages/Jobs"));
const Apply = lazy(() => import("./pages/Apply"));
const Memory = lazy(() => import("./pages/Memory"));
const SettingsPage = lazy(() => import("./pages/Settings"));
const Logs = lazy(() => import("./pages/Logs"));
const Guide = lazy(() => import("./pages/Guide"));
const Feedback = lazy(() => import("./pages/Feedback"));

function PageLoader() {
  return (
    <div className="flex items-center justify-center h-64">
      <Loader2 className="w-8 h-8 animate-spin text-primary" />
    </div>
  );
}

export default function App() {
  const [showWizard, setShowWizard] = useState(false);
  const [wizardChecked, setWizardChecked] = useState(false);
  const [wizardPaused, setWizardPaused] = useState(false);
  const [wizardStep, setWizardStep] = useState(0);

  useEffect(() => {
    let cancelled = false;
    async function check() {
      for (let i = 0; i < 15; i++) {
        try {
          const status = await getSetupStatus();
          if (!cancelled) {
            if (!status.onboarding_completed) {
              setShowWizard(true);
            }
            setWizardChecked(true);
          }
          return;
        } catch {
          await new Promise((r) => setTimeout(r, 1500));
        }
      }
      if (!cancelled) setWizardChecked(true);
    }
    check();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    const handler = () => {
      setWizardStep(0);
      setWizardPaused(false);
      setShowWizard(true);
    };
    window.addEventListener("open-setup-wizard", handler);
    return () => window.removeEventListener("open-setup-wizard", handler);
  }, []);

  const handleWizardNavigateAway = useCallback((currentStep: number) => {
    setWizardStep(currentStep);
    setShowWizard(false);
    setWizardPaused(true);
  }, []);

  const handleResumeWizard = useCallback(() => {
    setWizardPaused(false);
    setShowWizard(true);
  }, []);

  const handleWizardClose = useCallback(() => {
    setShowWizard(false);
    setWizardPaused(false);
    setWizardStep(0);
  }, []);

  return (
    <div className="flex min-h-screen bg-white">
      <Sidebar />
      <main className="flex-1 ml-60 px-10 py-8">
        <ErrorBoundary>
          <Suspense fallback={<PageLoader />}>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/profile" element={<Profile />} />
              <Route path="/llm" element={<LLMSettings />} />
              <Route path="/jobs" element={<Jobs />} />
              <Route path="/apply" element={<Apply />} />
              <Route path="/memory" element={<Memory />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="/logs" element={<Logs />} />
              <Route path="/guide" element={<Guide />} />
              <Route path="/feedback" element={<Feedback />} />
            </Routes>
          </Suspense>
        </ErrorBoundary>
      </main>

      {wizardChecked && showWizard && (
        <SetupWizard
          onClose={handleWizardClose}
          onNavigateAway={handleWizardNavigateAway}
          initialStep={wizardStep}
        />
      )}

      {wizardPaused && !showWizard && (
        <button
          onClick={handleResumeWizard}
          className="fixed bottom-6 right-6 z-40 flex items-center gap-2 px-4 py-3 bg-primary text-primary-foreground rounded-xl shadow-lg hover:bg-primary/90 transition-all hover:scale-105 text-sm font-medium"
        >
          <Wand2 className="w-4 h-4" />
          Resume Setup Wizard
        </button>
      )}
    </div>
  );
}
