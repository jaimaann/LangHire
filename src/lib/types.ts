// ── Candidate Profile ──────────────────────────────────────────────────────
export interface Address {
  street: string;
  city: string;
  state: string;
  zip: string;
  country: string;
}

export interface Education {
  degree: string;
  school: string;
  graduation: string;
}

export interface SalaryExpectation {
  min: number;
  max: number;
  currency: string;
  period: "annual" | "monthly";
}

export interface CandidateProfile {
  name: string;
  email: string;
  phone: string;
  phone_country_code: string;
  country: string;
  address: Address;
  work_authorization: string;
  visa_sponsorship_needed: boolean;
  willing_to_relocate: boolean;
  preferred_work_mode: string;
  years_of_experience: number;
  education: Education;
  current_role: string;
  target_job_titles: string[];
  target_locations: string[];
  languages: string[];
  skills: string[];
  salary_expectation: SalaryExpectation;
  current_compensation?: string;
  notice_period: string;
  nationality: string;
  date_of_birth: string;
  cover_letter: string;
  date_format: string;
  notes: string;
}

// ── LLM Settings ──────────────────────────────────────────────────────────
export type LLMProvider = "openai" | "anthropic" | "gemini" | "bedrock" | "ollama" | "openrouter" | "openai_compatible";

export interface LLMSettings {
  provider: LLMProvider;
  /** Optional USD per 1M tokens, for models the app has no price data for. */
  pricing?: { input?: number; cached?: number; output?: number };
  openai?: {
    api_key: string;
    model: string;
  };
  anthropic?: {
    api_key: string;
    model: string;
  };
  gemini?: {
    api_key: string;
    model: string;
  };
  bedrock?: {
    auth_mode: string;
    profile_name: string;
    access_key: string;
    secret_key: string;
    region: string;
    model: string;
  };
  ollama?: {
    base_url: string;
    model: string;
  };
  openrouter?: {
    api_key: string;
    model: string;
  };
  openai_compatible?: {
    base_url: string;
    api_key: string;
    model: string;
  };
}

// ── App Settings ──────────────────────────────────────────────────────────
export interface AppSettings {
  resume_path: string;
  blocked_domains: string[];
  sensitive_data: {
    email: string;
    password: string;
  };
  max_failures: number;
  stagger_delay: number;
  data_dir: string;
  telemetry_enabled: boolean;
  theme?: "light" | "dark" | "system";
  /** Days to keep agent conversation logs; 0 = don't save. Default 14. */
  log_retention_days?: number;
  /** Max applications per job site per day; 0 = no cap. Default 25. */
  daily_apply_cap?: number;
  /** Stop a run after this much LLM spend (USD). Default 5. */
  max_run_cost_usd?: number;
  /** Chrome DevTools address of the user's own browser; empty = LangHire's browser. */
  browser_cdp_url?: string;
  /** Let the agent read the newest verification-code email in Gmail. */
  email_otp_via_gmail?: boolean;
  /** Fill and click Submit, but stop the request in the browser (nothing is sent). */
  test_mode?: boolean;
}

// ── Privacy & data ────────────────────────────────────────────────────────
export interface DeleteAllDataResponse {
  ok: boolean;
  deleted: string[];
}

/** Full user-data export returned by GET /data/export (shape owned by the backend). */
export type DataExport = Record<string, unknown>;

// ── Job ───────────────────────────────────────────────────────────────────
export interface Job {
  url: string;
  title: string;
  company: string;
  location: string;
  easy_apply: boolean | null;
  status: JobStatus;
  source?: string;
  search_title?: string;
  collected_at?: string;
  applied_at?: string;
  error?: string;
  description?: string;
  tailored_resume_path?: string;
  /** How well the job fits the profile, 0-100 (null when not scored yet). */
  match_score?: number | null;
}

// ── Application records ──────────────────────────────────────────────────
export interface ApplicationAnswer {
  question: string;
  answer: string;
  field_type?: string;
  /** Where the answer came from, e.g. "profile", "qa", "memory", "inferred". */
  source?: string;
  confidence?: number | null;
}

export interface ApplicationRecord {
  job_url?: string;
  outcome: string;
  reason?: string | null;
  confirmation?: string | null;
  answers: ApplicationAnswer[];
  missing_info: string[];
  resume_path?: string | null;
  screenshot_path?: string | null;
  cost_usd?: number | null;
  steps?: number | null;
  ats?: string | null;
  /** Test mode: application requests stopped in the browser. */
  intercepted?: number | null;
  /** Test mode: how many times Submit was clicked. */
  submit_clicks?: number | null;
  /** Exact LLM token counts reported by the provider for this application. */
  prompt_tokens?: number | null;
  cached_tokens?: number | null;
  completion_tokens?: number | null;
  llm_model?: string | null;
  created_at: string;
}

/** LLM token totals for a whole run (apply or collect). */
export interface RunUsage {
  prompt_tokens: number;
  cached_tokens: number;
  completion_tokens: number;
  llm_model?: string;
}

// ── Resume Tailoring ─────────────────────────────────────────────────────
export interface TailorOptions {
  skills: boolean;
  title: boolean;
  overview: boolean;
  experience: boolean;
}

export interface TailorResult {
  url: string;
  status: "done" | "error";
  path?: string;
  content?: string;
  message?: string;
}

// ── Plugins ──────────────────────────────────────────────────────────────
export interface PluginFilter {
  key: string;
  label: string;
  type: "select" | "text";
  options: { value: string; label: string }[];
  url_param: string;
  default: string;
}

export interface PluginConfig {
  name: string;
  display_name: string;
  version: string;
  author: string;
  description: string;
  countries: string[];
  website: string;
  requires_login: boolean;
  login_url: string;
  is_builtin: boolean;
  enabled: boolean;
  filters: PluginFilter[];
  /** SHA-256 of the plugin file the user approved (community plugins). */
  sha256?: string | null;
  /** True when the file changed since it was approved; it stays disabled until re-imported. */
  tampered?: boolean;
}

/** What /plugins/preview (and /plugins/import without a hash) returns for review. */
export interface PluginPreview {
  name: string;
  display_name: string;
  version: string;
  author: string;
  website: string;
  requires_login: boolean;
  sha256: string;
  collection_prompt: string;
  apply_prompt: string;
  warnings: string[];
}

// ── Country Config ───────────────────────────────────────────────────────
export interface CountryConfig {
  name: string;
  flag: string;
  date_format: string;
  currency: string;
  salary_period: "annual" | "monthly";
  address_labels: { state: string; zip: string };
  work_auth_options: string[];
  show_notice_period: boolean;
  show_nationality: boolean;
  show_cover_letter: boolean;
  show_photo: boolean;
  show_date_of_birth: boolean;
  phone_prefix: string;
  default_sources: string[];
}

export type CountryCode = string;

// ── Memory ────────────────────────────────────────────────────────────────
export interface Memory {
  id: number;
  website_domain: string;
  ats_platform: string | null;
  category: string;
  content: string;
  success: boolean;
  confidence: number;
  job_url: string;
  created_at: string;
  updated_at: string;
  access_count: number;
}

export interface MemoryStats {
  total_memories: number;
  unique_domains: number;
  by_category: Record<string, number>;
}

// ── Metrics / Dashboard ───────────────────────────────────────────────────
export interface OverallStats {
  total_runs: number;
  successes: number;
  failures: number;
  success_rate: number;
  avg_duration: number;
  avg_steps: number;
  total_cost: number;
  first_run: string;
  last_run: string;
}

export interface RunMetric {
  id: number;
  job_url: string;
  job_title: string;
  company: string;
  website_domain: string;
  ats_platform: string | null;
  success: boolean;
  error_message: string | null;
  started_at: string;
  finished_at: string;
  duration_seconds: number;
  step_count: number;
  memories_injected: number;
  memories_extracted: number;
  cost_usd: number | null;
  created_at: string;
}

// ── API Response ──────────────────────────────────────────────────────────
export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
}

export interface HealthChecks {
  database: boolean;
  chromium: boolean;
  chromium_installing: boolean;
  llm_configured: boolean;
  worker_running: boolean;
}

export interface HealthResponse {
  status: "ok" | "degraded";
  version: string;
  frozen: boolean;
  checks: HealthChecks;
  build_id?: string;
  /** Where API keys and passwords are stored. */
  secrets_backend?: "keychain" | "file";
}

// ── Status Responses ─────────────────────────────────────────────────────
export interface CollectionStatus {
  running: boolean;
  title: string | null;
  log: string[];
  collected: number;
  usage?: RunUsage;
  max_jobs: number;
  error: string | null;
  finished_at: string | null;
}

export interface ApplyStatus {
  running: boolean;
  mode: string | null;
  workers: number;
  log: string[];
  error: string | null;
  finished_at: string | null;
  /** LLM spend of the current/last run so far (USD). */
  cost_usd?: number;
  usage?: RunUsage;
  stats?: Record<string, unknown>;
}

export type JobStatus =
  | "pending"
  | "in_progress"
  | "applied"
  | "failed"
  | "blocked"
  | "skipped"
  | "needs_input"
  | "test_passed";

export interface JobStats {
  total: number;
  pending: number;
  applied: number;
  failed: number;
  blocked: number;
  in_progress: number;
  skipped?: number;
  needs_input?: number;
  test_passed?: number;
}

/** Success rate and average cost per applicant tracking system. */
export interface AtsStat {
  ats: string;
  attempts: number;
  submitted: number;
  /** Fraction 0-1. */
  success_rate: number;
  avg_cost_usd: number;
}

export interface DashboardMetrics {
  ats?: AtsStat[];
  cost_7d_usd?: number;
  [key: string]: unknown;
}

export interface DashboardResponse {
  jobs: JobStats;
  memory: MemoryStats;
  metrics?: DashboardMetrics;
}

// ── Live run events (GET /events, Server-Sent Events) ───────────────────
export type RunKind = "collect" | "apply";

export interface RunEvent {
  id: number;
  run_id: string;
  kind: RunKind;
  type: string;
  level: string;
  message: string;
  data: Record<string, unknown>;
}

// ── Login sessions (GET /auth/status) ────────────────────────────────────
export interface ServiceLoginStatus {
  logged_in: boolean;
  display_name?: string;
}

export type AuthStatus = Record<string, ServiceLoginStatus>;

export interface DomainInfo {
  website_domain: string;
  ats_platform: string | null;
  count: number;
  avg_confidence: number;
  success_count: number;
  failure_count: number;
}

export interface SetupStatus {
  onboarding_completed: boolean;
  has_profile: boolean;
  has_llm: boolean;
  has_resume: boolean;
  has_jobs: boolean;
}

// ── Q&A Repository ───────────────────────────────────────────────────────
export interface QAEntry {
  id: number;
  question: string;
  normalized: string;
  answer: string;
  question_type: string;
  source_domain: string;
  times_seen: number;
  merged_into_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface QAStats {
  total: number;
  answered: number;
  unanswered: number;
}

// ── Run Logs ─────────────────────────────────────────────────────────────
export interface RunLog {
  id: number;
  run_id: string;
  job_url: string | null;
  timestamp: string;
  level: string;
  message: string;
  created_at: string;
}

export interface RunWithLogs extends RunMetric {
  run_id: string | null;
  log_count: number;
}
