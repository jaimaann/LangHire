/**
 * API client for communicating with the Python backend sidecar.
 * The backend runs as a local FastAPI server on a dynamic port.
 */
import { invoke } from "@tauri-apps/api/core";
import type {
  CandidateProfile,
  LLMSettings,
  AppSettings,
  Job,
  JobStats,
  MemoryStats,
  Memory,
  HealthResponse,
  RunMetric,
  CollectionStatus,
  ApplyStatus,
  DashboardResponse,
  DomainInfo,
  RunLog,
  RunWithLogs,
} from "./types";

const DEFAULT_PORT = 8742;

let backendPort = DEFAULT_PORT;
let tokenPromise: Promise<string> | null = null;

export function setBackendPort(port: number) {
  backendPort = port;
}

function getBaseUrl(): string {
  return `http://127.0.0.1:${backendPort}`;
}

async function getToken(): Promise<string> {
  if (!tokenPromise) {
    tokenPromise = invoke<string>("get_api_token").catch((e) => {
      tokenPromise = null;
      throw new Error(`Failed to read API token: ${e}`);
    });
  }
  return tokenPromise;
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  _retried = false
): Promise<T> {
  const url = `${getBaseUrl()}${path}`;
  const token = await getToken();
  const res = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...options.headers,
    },
  });

  if (res.status === 401 && !_retried) {
    tokenPromise = null;
    await new Promise(r => setTimeout(r, 1000));
    return request<T>(path, options, true);
  }

  if (!res.ok) {
    const text = await res.text().catch(() => "Unknown error");
    throw new Error(`API Error ${res.status}: ${text}`);
  }

  const text = await res.text();
  if (!text) return {} as T;
  try {
    return JSON.parse(text) as T;
  } catch {
    throw new Error(`Invalid JSON response from ${path}`);
  }
}

// ── Health ────────────────────────────────────────────────────────────────
export async function checkHealth() {
  return request<HealthResponse>("/health");
}

export async function getChromiumStatus() {
  const res = await fetch(`${getBaseUrl()}/chromium/status`);
  return res.json() as Promise<{ state: string; message: string }>;
}

// ── Profile ───────────────────────────────────────────────────────────────
export async function getProfile() {
  return request<CandidateProfile>("/profile");
}

export async function saveProfile(profile: CandidateProfile) {
  return request<{ success: boolean }>("/profile", {
    method: "PUT",
    body: JSON.stringify(profile),
  });
}

// ── LLM Settings ──────────────────────────────────────────────────────────
export async function getLLMSettings() {
  return request<LLMSettings>("/settings/llm");
}

export async function saveLLMSettings(settings: LLMSettings) {
  return request<{ success: boolean }>("/settings/llm", {
    method: "PUT",
    body: JSON.stringify(settings),
  });
}

export async function testLLMConnection(settings: LLMSettings) {
  return request<{ success: boolean; message: string }>("/llm/test", {
    method: "POST",
    body: JSON.stringify(settings),
  });
}

// ── App Settings ──────────────────────────────────────────────────────────
export async function getSettings() {
  return request<AppSettings>("/settings");
}

export async function saveSettings(settings: Partial<AppSettings>) {
  return request<{ success: boolean }>("/settings", {
    method: "PUT",
    body: JSON.stringify(settings),
  });
}

// ── Jobs ──────────────────────────────────────────────────────────────────
export async function getJobs(params?: { status?: string; search?: string; limit?: number }) {
  const qs = new URLSearchParams();
  if (params?.status) qs.set("status", params.status);
  if (params?.search) qs.set("search", params.search);
  if (params?.limit) qs.set("limit", String(params.limit));
  const query = qs.toString();
  return request<Job[]>(`/jobs${query ? `?${query}` : ""}`);
}

export async function getJobStats() {
  return request<JobStats>("/jobs/stats");
}

export async function startJobCollection(title?: string, maxJobs?: number) {
  const body: Record<string, unknown> = {};
  if (title) body.title = title;
  if (maxJobs) body.max_jobs = maxJobs;
  return request<{ success: boolean; message: string }>("/jobs/collect", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function stopJobCollection() {
  return request<{ success: boolean }>("/jobs/collect/stop", { method: "POST" });
}

export async function getCollectionStatus() {
  return request<CollectionStatus>("/jobs/collect/status");
}

// ── Memory ────────────────────────────────────────────────────────────────
export async function getMemoryStats() {
  return request<MemoryStats>("/memory/stats");
}

export async function getMemoryDomains() {
  return request<DomainInfo[]>("/memory/domains");
}

export async function getMemoriesForDomain(domain: string) {
  return request<Memory[]>(
    `/memory/domain/${encodeURIComponent(domain)}`
  );
}

export async function searchMemories(query: string) {
  return request<Memory[]>(`/memory/search?q=${encodeURIComponent(query)}`);
}

export async function decayMemories(days = 30) {
  return request<{ success: boolean; affected: number }>("/memory/decay", {
    method: "POST",
    body: JSON.stringify({ days }),
  });
}

export async function cleanupMemories() {
  return request<{ success: boolean; deleted: number }>("/memory/cleanup", {
    method: "POST",
  });
}

export async function exportMemories() {
  return request<Memory[]>("/memory/export");
}

// ── Apply ─────────────────────────────────────────────────────────────────
export async function startApplying(params: { workers?: number; mode?: string; limit?: number; job_url?: string }) {
  return request<{ success: boolean; message: string }>("/apply/start", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export async function stopApplying() {
  return request<{ success: boolean }>("/apply/stop", { method: "POST" });
}

export async function getApplyStatus() {
  return request<ApplyStatus>("/apply/status");
}

// ── Dashboard / Metrics ───────────────────────────────────────────────────
export async function getDashboardData() {
  return request<DashboardResponse>("/dashboard");
}

export async function getMetricRuns(limit = 50) {
  return request<RunMetric[]>(`/metrics/runs?limit=${limit}`);
}

// ── Logs ─────────────────────────────────────────────────────────────────
export async function getRunLogs(runId: string, limit = 500) {
  return request<RunLog[]>(`/logs/runs/${encodeURIComponent(runId)}?limit=${limit}`);
}

export async function getRecentLogs(limit = 100) {
  return request<RunLog[]>(`/logs/recent?limit=${limit}`);
}

export async function getRunsWithLogs(limit = 50) {
  return request<RunWithLogs[]>(`/logs/runs?limit=${limit}`);
}

// ── Auth / Login Sessions ─────────────────────────────────────────────────
export async function getAuthStatus() {
  return request<{
    linkedin: { logged_in: boolean };
    gmail: { logged_in: boolean };
  }>("/auth/status");
}

export async function launchLogin(service: "linkedin" | "gmail") {
  return request<{ success: boolean; message: string }>(`/auth/login/${service}`, {
    method: "POST",
  });
}

// ── Setup / Onboarding ────────────────────────────────────────────────────
export interface SetupStatus {
  profile: boolean;
  llm: boolean;
  resume: boolean;
  chromium: boolean;
  linkedin: boolean;
  gmail: boolean;
  onboarding_completed: boolean;
  all_required_done: boolean;
}

export async function getSetupStatus() {
  return request<SetupStatus>("/setup/status");
}

export async function completeOnboarding() {
  return request<{ success: boolean }>("/setup/complete-onboarding", {
    method: "POST",
  });
}

export async function parseResumeToProfile() {
  return request<{
    success: boolean;
    message: string;
    profile?: Record<string, unknown>;
    fields_filled?: number;
  }>("/profile/parse-resume", { method: "POST" });
}
