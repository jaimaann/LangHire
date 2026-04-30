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
      label: "Configure AI provider",
      done: status?.llm,
      path: "/llm",
      icon: Cpu,
      required: true,
    },
    {
      label: "Set resume path",
      done: status?.resume,
      path: "/settings",
      icon: FileText,
      required: true,
    },
    {
      label: "Set up your profile",
      done: status?.profile,
      path: "/profile",
      icon: User,
      required: true,
    },
  ];

  const allRequiredDone = status?.all_required_done;

  return (
    <div className="max-w-3xl">
      <PageHeader title="Guide" subtitle="Learn how to use Job Applicant and reference this anytime" />

      {/* ── How It Works — Visual Pipeline ─────────────────────────────── */}
      <div className="card mb-6">
        <h3 className="text-lg font-semibold text-foreground mb-4">
          How It Works
        </h3>
        <div className="flex items-center justify-between gap-1">
          {[
            { icon: User, label: "Profile", color: "bg-[#FFF0F3] text-primary" },
            { icon: Cpu, label: "AI Setup", color: "bg-purple-50 text-purple-600" },
            { icon: Briefcase, label: "Collect", color: "bg-amber-50 text-amber-600" },
            { icon: Play, label: "Apply", color: "bg-green-50 text-green-600" },
            { icon: Brain, label: "Learn", color: "bg-indigo-50 text-indigo-600" },
            { icon: RefreshCw, label: "Improve", color: "bg-pink-50 text-pink-600" },
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
          Set up your profile → Configure AI → Collect jobs from LinkedIn →
          Agent applies automatically → Learns from each run → Gets better over
          time
        </p>
      </div>

      {/* ── Live Setup Checklist ───────────────────────────────────────── */}
      <div className="card mb-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-foreground">
            Setup Checklist
          </h3>
          <button
            onClick={fetchStatus}
            className="p-1 text-muted-foreground hover:text-foreground"
            title="Refresh status"
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
              All required steps are complete! You're ready to go.
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
                        (optional)
                      </span>
                    )}
                  </span>
                </div>
                {!step.done && (
                  <button
                    onClick={() => navigate(step.path)}
                    className="text-xs text-primary font-medium hover:underline"
                  >
                    Set up →
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
          Step-by-Step Guide
        </h3>
        <div className="space-y-2">
          <AccordionSection title="Setting up your profile" icon={User}>
            <p>
              Your candidate profile is the core information the AI agent uses
              when filling out job applications. Go to{" "}
              <button
                onClick={() => navigate("/profile")}
                className="text-primary font-medium hover:underline"
              >
                Profile
              </button>{" "}
              to set it up.
            </p>
            <p>
              <strong>Essential fields:</strong> Name, Email, Phone — these
              appear on every application.
            </p>
            <p>
              <strong>Target Job Titles:</strong> These are the search terms
              used when collecting jobs from LinkedIn. Add multiple titles to
              cast a wider net (e.g., "Data Analyst", "Business Analyst",
              "Junior Data Scientist").
            </p>
            <p>
              <strong>Target Locations:</strong> Geographic preferences for job
              search (e.g., "San Francisco, CA", "Remote").
            </p>
            <p>
              <strong>Skills:</strong> These help the agent answer
              skills-related questions on application forms.
            </p>
            <p>
              <strong>Notes:</strong> Free-text instructions for the AI agent.
              Use this for special instructions like "Only apply to fully
              remote positions" or "I prefer companies under 500 employees."
            </p>
          </AccordionSection>

          <AccordionSection title="Configuring your AI provider" icon={Cpu}>
            <p>
              The AI model is the "brain" that drives the browser automation.
              It reads web pages, decides what to click, fills in form fields,
              and answers application questions. Go to{" "}
              <button
                onClick={() => navigate("/llm")}
                className="text-primary font-medium hover:underline"
              >
                LLM Settings
              </button>{" "}
              to configure it.
            </p>
            <p>
              <strong>Recommended:</strong> OpenAI GPT-4o or Anthropic Claude
              Sonnet — both work well. Cost is typically $0.02–0.10 per
              application depending on form complexity.
            </p>
            <p>
              <strong>AWS Bedrock:</strong> If you have AWS credentials, you
              can use Claude through Bedrock. Supports both AWS CLI profiles
              and access key/secret key authentication.
            </p>
            <p>
              <strong>Test Connection:</strong> Always click "Test Connection"
              after entering your credentials to verify everything works
              before running operations.
            </p>
          </AccordionSection>

          <AccordionSection
            title="Logging into LinkedIn & Gmail"
            icon={LogIn}
          >
            <p>
              Login is handled <strong>automatically by the agent</strong> within its browser window.
              No separate login step is needed.
            </p>
            <p>
              <strong>How it works:</strong> When you start collecting or applying,
              the agent opens a browser and checks if you're logged into LinkedIn.
              If not, it waits for you to log in manually in that same browser window.
              Once it detects you're logged in (the LinkedIn feed loads), it proceeds
              automatically.
            </p>
            <p>
              <strong>First time:</strong> You'll need to log in once when the browser
              opens. After that, your session is saved in the browser profile and
              persists across runs.
            </p>
            <p>
              <strong>Gmail (for OTP):</strong> If an external job site sends a
              verification code, the agent will open Gmail in a new tab to retrieve
              the code. You may need to log into Gmail the first time this happens.
            </p>
            <p>
              <strong>Session expired?</strong> If LinkedIn logs you out (rare),
              the agent will detect the login page and wait for you to log in again.
              Watch the live log — it will say "Login required."
            </p>
          </AccordionSection>

          <AccordionSection
            title="Collecting jobs"
            icon={Briefcase}
          >
            <p>
              Job collection searches LinkedIn for listings matching your
              target job titles and locations. Go to{" "}
              <button
                onClick={() => navigate("/jobs")}
                className="text-primary font-medium hover:underline"
              >
                Jobs
              </button>{" "}
              and click "Collect Jobs."
            </p>
            <p>
              <strong>How it works:</strong> An AI agent opens LinkedIn,
              searches for each of your target job titles, scrolls through
              results, and saves every job it finds (title, company, location,
              URL, Easy Apply status).
            </p>
            <p>
              <strong>Timing:</strong> Collection typically takes 3–10 minutes
              per job title, depending on how many results there are. You can
              watch the live log to see progress.
            </p>
            <p>
              <strong>Max jobs:</strong> Set a limit (e.g., 20) to stop
              after a certain number. Leave blank to collect all available
              results.
            </p>
            <p>
              <strong>Single title:</strong> Enter a specific title in the
              search box, or leave blank to search all titles from your
              profile.
            </p>
          </AccordionSection>

          <AccordionSection title="Applying to jobs" icon={Play}>
            <p>
              Once you've collected jobs, go to{" "}
              <button
                onClick={() => navigate("/apply")}
                className="text-primary font-medium hover:underline"
              >
                Apply
              </button>{" "}
              to start automated applications.
            </p>
            <p>
              <strong>Easy Apply:</strong> LinkedIn's built-in application
              form. The agent fills in your profile info, uploads your resume,
              answers questions, and submits — all within a modal dialog on
              LinkedIn.
            </p>
            <p>
              <strong>External Sites:</strong> For jobs that redirect to an
              external ATS (Workday, Greenhouse, Lever, etc.), the agent
              navigates to the external site, creates an account if needed,
              and fills out the full application.
            </p>
            <p>
              <strong>Tailored Resumes:</strong> In "Tailored" mode, the agent
              first reads the job description, extracts key skills, and
              creates a customized version of your resume with those skills
              added before applying.
            </p>
            <p>
              <strong>Limit:</strong> Set a number to cap how many jobs to
              apply to in one session. Leave blank for no limit.
            </p>
            <p>
              <strong>Blocked domains:</strong> If certain sites cause issues,
              add them to the blocked list in{" "}
              <button
                onClick={() => navigate("/settings")}
                className="text-primary font-medium hover:underline"
              >
                Settings
              </button>
              . The agent will skip jobs on those domains.
            </p>
          </AccordionSection>

          <AccordionSection
            title="Understanding the Memory system"
            icon={Brain}
          >
            <p>
              The memory system is what makes the agent get{" "}
              <strong>smarter over time</strong>. After each application
              attempt, the agent extracts procedural learnings about the
              website and stores them for future use.
            </p>
            <p>
              <strong>How it works:</strong> Before each job, memories for
              that website are injected into the agent's prompt. The agent
              then knows things like "Workday requires creating an account
              first" or "LinkedIn Easy Apply opens in a modal, don't navigate
              away."
            </p>
            <p>
              <strong>ATS normalization:</strong> Learnings from one Workday
              site (e.g., goodyear.wd1.myworkdayjobs.com) automatically help
              on ALL Workday sites. The system recognizes 20+ ATS platforms.
            </p>
            <p>
              <strong>Memory categories:</strong>
            </p>
            <ul className="list-disc list-inside space-y-1 pl-2">
              <li>
                <strong>Navigation:</strong> How to find and reach the
                application form
              </li>
              <li>
                <strong>Form strategy:</strong> Overall approach to completing
                the form
              </li>
              <li>
                <strong>Element interaction:</strong> Specific UI quirks
                (checkboxes, modals, scrolling)
              </li>
              <li>
                <strong>Failure recovery:</strong> How to handle errors and
                blockers
              </li>
              <li>
                <strong>Site structure:</strong> General layout of the
                application flow
              </li>
              <li>
                <strong>Q&A pattern:</strong> Common question types and input
                formats
              </li>
            </ul>
            <p>
              <strong>Maintenance:</strong> Over time, memories can become
              stale (websites update their UI). Use "Decay" to reduce
              confidence of old memories and "Cleanup" to remove low-confidence
              ones. View and manage all memories on the{" "}
              <button
                onClick={() => navigate("/memory")}
                className="text-primary font-medium hover:underline"
              >
                Memory
              </button>{" "}
              page.
            </p>
          </AccordionSection>

          <AccordionSection
            title="Tips & Troubleshooting"
            icon={Settings}
          >
            <p>
              <strong>Only one operation at a time:</strong> The app uses a
              shared browser profile, so only one browser operation (collect,
              apply, or login) can run at a time.
            </p>
            <p>
              <strong>Agent is non-deterministic:</strong> The AI may succeed
              or fail on the same job across different runs. If a job fails,
              it stays in your queue for the next attempt.
            </p>
            <p>
              <strong>LinkedIn rate limits:</strong> LinkedIn may temporarily
              block Easy Apply if too many applications are submitted in a
              short time. Space out your application sessions.
            </p>
            <p>
              <strong>Browser stuck?</strong> If an operation seems frozen,
              click "Stop" — this kills the browser process. Then try again.
            </p>
            <p>
              <strong>Login expired?</strong> If the agent encounters auth
              errors, go back to the Dashboard and log in again. Sessions
              occasionally expire.
            </p>
            <p>
              <strong>Resume not uploading?</strong> Make sure the file path
              in Settings points to an actual PDF file on your computer.
            </p>
            <p>
              <strong>Backend not connecting?</strong> In development mode,
              make sure the Python backend is running:{" "}
              <code className="bg-gray-100 px-1.5 py-0.5 rounded text-xs">
                uv run python backend/main.py
              </code>
            </p>
            <p>
              <strong>Costs:</strong> Each application costs ~$0.02–0.10 in
              LLM API calls depending on form complexity. Monitor your
              provider's usage dashboard.
            </p>
          </AccordionSection>
        </div>
      </div>

      {/* ── Re-run Setup Wizard ────────────────────────────────────────── */}
      <div className="card mb-6">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-foreground">
              Need to re-run the setup?
            </h3>
            <p className="text-xs text-muted-foreground mt-1">
              Open the Setup Wizard again to walk through configuration
              step-by-step.
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
            Open Setup Wizard
          </button>
        </div>
      </div>
    </div>
  );
}
