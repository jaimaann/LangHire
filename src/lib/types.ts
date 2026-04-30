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
}

export interface CandidateProfile {
  name: string;
  email: string;
  phone: string;
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
  notes: string;
}

// ── LLM Settings ──────────────────────────────────────────────────────────
export type LLMProvider = "openai" | "anthropic" | "bedrock";

export interface LLMSettings {
  provider: LLMProvider;
  openai?: {
    api_key: string;
    model: string;
  };
  anthropic?: {
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
}

// ── Job ───────────────────────────────────────────────────────────────────
export interface Job {
  url: string;
  title: string;
  company: string;
  location: string;
  easy_apply: boolean | null;
  status: "pending" | "in_progress" | "applied" | "failed" | "blocked";
  search_title?: string;
  collected_at?: string;
  applied_at?: string;
  error?: string;
  description?: string;
}

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
}

// ── Status Responses ─────────────────────────────────────────────────────
export interface CollectionStatus {
  running: boolean;
  title: string | null;
  log: string[];
  collected: number;
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
}

export type JobStatus = "pending" | "in_progress" | "applied" | "failed" | "blocked";

export interface JobStats {
  total: number;
  pending: number;
  applied: number;
  failed: number;
  blocked: number;
  in_progress: number;
}

export interface DashboardResponse {
  jobs: JobStats;
  memory: MemoryStats;
  metrics?: Record<string, unknown>;
}

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
