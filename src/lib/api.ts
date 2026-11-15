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
  QAEntry,
  QAStats,
  ApplicationRecord,
  AuthStatus,
  PluginPreview,
  RunEvent,
} from "./types";

const DEFAULT_PORT = 8743;

/** Connection details returned by the Rust `get_backend_info` command. */
export interface BackendInfo {
  /** Port the backend listens on (random per launch when managed). */
  port: number;
  /** Bearer token for the backend API. */
  token: string;
  /** True when the Tauri host spawned and supervises the sidecar. */
  managed: boolean;
  /** Last sidecar status known to the host (starting|running|crashed|failed). */
  status?: string;
}

/** Explicit port override (setBackendPort); wins over the host-provided port. */
let portOverride: number | null = null;
let infoPromise: Promise<BackendInfo> | null = null;

export function setBackendPort(port: number) {
  portOverride = port;
}

/**
 * Fetch (once) the backend port + token from the Tauri host. The promise is
 * cached; a failure clears the cache so the next call retries.
 */
export function getBackendInfo(): Promise<BackendInfo> {
  // Dev only: run the UI in a normal browser against a hand-started backend
  // (`VITE_DEV_BACKEND_TOKEN=... npm run dev`). Never active in production builds.
  const devToken = import.meta.env.DEV ? import.meta.env.VITE_DEV_BACKEND_TOKEN : undefined;
  if (!infoPromise && devToken) {
    infoPromise = Promise.resolve({
      port: Number(import.meta.env.VITE_DEV_BACKEND_PORT) || DEFAULT_PORT,
      token: devToken,
      managed: false,
    });
  }
  if (!infoPromise) {
    infoPromise = invoke<BackendInfo | undefined>("get_backend_info")
      .then((info) => {
        if (!info || typeof info.token !== "string" || !info.token) {
          throw new Error("backend info unavailable");
        }
        return info;
      })
      .catch((e) => {
        infoPromise = null;
        throw new Error(`Failed to read API token: ${e instanceof Error ? e.message : e}`);
      });
  }
  return infoPromise;
}

/** Drop the cached backend info so the next request re-invokes the host. */
function invalidateBackendInfo() {
  infoPromise = null;
}

function baseUrlFor(info: BackendInfo): string {
  return `http://127.0.0.1:${portOverride ?? info.port ?? DEFAULT_PORT}`;
}

async function getBaseUrl(): Promise<string> {
  return baseUrlFor(await getBackendInfo());
}

async function getToken(): Promise<string> {
  return (await getBackendInfo()).token;
}

/**
 * Open a local file (e.g. a tailored resume PDF) with the OS default app.
 * The host validates the path (must exist, be a file, and live in the data
 * dir or have a document/image extension).
 */
export async function openLocalFile(path: string): Promise<void> {
  await invoke("open_file", { path });
}

export { onBackendStatus, useBackendStatus, type BackendStatus } from "./backendStatus";

async function request<T>(
  path: string,
  options: RequestInit = {},
  _retried = false
): Promise<T> {
  const info = await getBackendInfo();
  const url = `${baseUrlFor(info)}${path}`;
  const token = info.token;
  const res = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...options.headers,
    },
  });

  if (res.status === 401 && !_retried) {
    invalidateBackendInfo();
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
  const res = await fetch(`${await getBaseUrl()}/chromium/status`);
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

export async function fetchOllamaModels(baseUrl: string) {
  return request<{ success: boolean; models: string[]; message?: string }>("/llm/ollama-models", {
    method: "POST",
    body: JSON.stringify({ base_url: baseUrl }),
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

/** Fetch the jobs export as CSV text (authenticated). Caller triggers the download. */
export async function exportJobsCsv(): Promise<string> {
  const token = await getToken();
  const res = await fetch(`${await getBaseUrl()}/jobs/export`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "Unknown error");
    throw new Error(`API Error ${res.status}: ${text}`);
  }
  return res.text();
}

export async function startJobCollection(title?: string, maxJobs?: number, source?: string, filters?: Record<string, string>) {
  const body: Record<string, unknown> = {};
  if (title) body.title = title;
  if (maxJobs) body.max_jobs = maxJobs;
  if (source) body.source = source;
  if (filters && Object.keys(filters).length > 0) body.filters = filters;
  return request<{ success: boolean; message: string }>("/jobs/collect", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function updateJobStatus(url: string, status: string) {
  return request<{ success: boolean }>("/jobs/status", {
    method: "PUT",
    body: JSON.stringify({ url, status }),
  });
}

export async function addJob(url: string, title?: string, company?: string, source?: string) {
  return request<{ success: boolean }>("/jobs/add", {
    method: "POST",
    body: JSON.stringify({ url, title, company, source }),
  });
}

export async function deleteJobs(urls: string[]) {
  return request<{ success: boolean; deleted: number }>("/jobs", {
    method: "DELETE",
    body: JSON.stringify({ urls }),
  });
}

/** Recompute match scores for all jobs (e.g. after the profile changed). */
export async function rescoreJobs() {
  return request<{ success: boolean; rescored: number }>("/jobs/rescore", { method: "POST" });
}

/** Application records (answers given, resume, screenshot, outcome, cost), newest first. */
export async function getApplications(params?: { jobUrl?: string; limit?: number }) {
  const qs = new URLSearchParams();
  if (params?.jobUrl) qs.set("job_url", params.jobUrl);
  if (params?.limit) qs.set("limit", String(params.limit));
  const query = qs.toString();
  return request<ApplicationRecord[]>(`/applications${query ? `?${query}` : ""}`);
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
export async function startApplying(params: { workers?: number; mode?: string; limit?: number; job_url?: string; job_urls?: string[] }) {
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
/** Login state for every source plugin with a login page, plus Gmail. */
export async function getAuthStatus() {
  return request<AuthStatus>("/auth/status");
}

export async function launchLogin(service: string) {
  return request<{ success: boolean; message: string }>(`/auth/login/${encodeURIComponent(service)}`, {
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

// ── Q&A Repository ────────────────────────────────────────────────────────
export async function getQAList(params?: { search?: string; unanswered?: boolean }) {
  const qs = new URLSearchParams();
  if (params?.search) qs.set("search", params.search);
  if (params?.unanswered) qs.set("unanswered", "true");
  const query = qs.toString();
  return request<QAEntry[]>(`/qa${query ? `?${query}` : ""}`);
}

export async function getQAStats() {
  return request<QAStats>("/qa/stats");
}

export async function updateQA(id: number, answer: string) {
  return request<{ success: boolean; requeued?: number }>(`/qa/${id}`, {
    method: "PUT",
    body: JSON.stringify({ answer }),
  });
}

export async function deleteQA(id: number) {
  return request<{ success: boolean }>(`/qa/${id}`, { method: "DELETE" });
}

export async function mergeQA(sourceId: number, targetId: number) {
  return request<{ success: boolean }>(`/qa/${sourceId}/merge/${targetId}`, { method: "POST" });
}

export async function autoSquashQA() {
  return request<{ success: boolean; merged: number }>("/qa/auto-squash", { method: "POST" });
}

export async function smartSquashQA() {
  return request<{ success: boolean; merged: number }>("/qa/smart-squash", { method: "POST" });
}

// ── Resume Tailoring ─────────────────────────────────────────────────────
export async function tailorResumes(jobUrls: string[], options: import("./types").TailorOptions) {
  return request<{ success: boolean; results: import("./types").TailorResult[] }>("/resume/tailor", {
    method: "POST",
    body: JSON.stringify({ job_urls: jobUrls, options }),
  });
}

export async function refineTailoredResume(jobUrl: string, instruction: string) {
  return request<{ success: boolean; content: string; path: string }>("/resume/tailor/refine", {
    method: "POST",
    body: JSON.stringify({ job_url: jobUrl, instruction }),
  });
}

export async function getTailoredResumeContent(jobUrl: string) {
  return request<{ success: boolean; content: string; path: string | null }>("/resume/tailor/get-by-url", {
    method: "POST",
    body: JSON.stringify({ job_url: jobUrl }),
  });
}

// ── Cover Letter ─────────────────────────────────────────────────────────
export async function generateCoverLetter(jobDescription: string, jobTitle: string, company: string) {
  return request<{ success: boolean; cover_letter: string }>("/cover-letter/generate", {
    method: "POST",
    body: JSON.stringify({ job_description: jobDescription, job_title: jobTitle, company: company }),
  });
}

// ── Countries ────────────────────────────────────────────────────────────
export async function getCountries() {
  return request<{ success: boolean; countries: Record<string, import("./types").CountryConfig>; notice_period_options: string[] }>("/countries");
}

export async function getCountryConfig(code: string) {
  return request<{ success: boolean; config: import("./types").CountryConfig }>(`/countries/${code}`);
}

// ── Plugins ──────────────────────────────────────────────────────────────
export async function getPlugins(country?: string) {
  const params = country ? `?country=${country}` : "";
  return request<{ success: boolean; plugins: import("./types").PluginConfig[] }>(`/plugins${params}`);
}

/** Parse a plugin file without installing it, so the user can review it. */
export async function previewPlugin(filePath: string) {
  return request<{ success: boolean; plugin: PluginPreview }>("/plugins/preview", {
    method: "POST",
    body: JSON.stringify({ file_path: filePath }),
  });
}

export type ImportPluginResponse =
  | { success: true; plugin: { name: string; display_name: string } }
  | { success: false; needs_review: true; plugin: PluginPreview };

/**
 * Install a community plugin. Pass the SHA-256 the user approved in the
 * review panel; without it the backend only returns the preview.
 */
export async function importPlugin(filePath: string, approvedSha256?: string) {
  const body: Record<string, string> = { file_path: filePath };
  if (approvedSha256) body.approved_sha256 = approvedSha256;
  return request<ImportPluginResponse>("/plugins/import", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function togglePlugin(name: string, enabled: boolean) {
  return request<{ success: boolean }>(`/plugins/${name}/toggle`, {
    method: "PUT",
    body: JSON.stringify({ enabled }),
  });
}

export async function removePlugin(name: string) {
  return request<{ success: boolean }>(`/plugins/${name}`, { method: "DELETE" });
}

export async function reloadPlugins() {
  return request<{ success: boolean; count: number }>("/plugins/reload", { method: "POST" });
}

// ── Privacy & data ────────────────────────────────────────────────────────
/** Permanently delete all locally stored user data on the backend. */
export async function deleteAllData() {
  return request<import("./types").DeleteAllDataResponse>("/data/delete", {
    method: "POST",
    body: JSON.stringify({ confirm: true }),
  });
}

/** Export everything the backend stores about the user as a JSON object. */
export async function exportAllData() {
  return request<import("./types").DataExport>("/data/export");
}

// ── Live events (Server-Sent Events) ──────────────────────────────────────

/**
 * Incremental parser for a `text/event-stream` body. Feed it decoded text
 * chunks (which may split lines anywhere); it returns the `data` payload of
 * every event completed by that chunk. Comments, `id:`, `event:` and `retry:`
 * fields are ignored: the JSON payload carries everything we need.
 */
export class SseParser {
  private buffer = "";
  private dataLines: string[] = [];

  push(chunk: string): string[] {
    this.buffer += chunk;
    const out: string[] = [];
    for (;;) {
      const nl = this.buffer.search(/\r\n|\r|\n/);
      if (nl < 0) break;
      const isCr = this.buffer[nl] === "\r";
      // A trailing "\r" may be the first half of "\r\n": wait for more data.
      if (isCr && nl === this.buffer.length - 1) break;
      const sepLen = isCr && this.buffer[nl + 1] === "\n" ? 2 : 1;
      const line = this.buffer.slice(0, nl);
      this.buffer = this.buffer.slice(nl + sepLen);
      if (line === "") {
        if (this.dataLines.length > 0) out.push(this.dataLines.join("\n"));
        this.dataLines = [];
      } else if (line.startsWith("data:")) {
        const v = line.slice(5);
        this.dataLines.push(v.startsWith(" ") ? v.slice(1) : v);
      }
    }
    return out;
  }
}

/** Parse one SSE data payload into a RunEvent (null when it isn't one). */
export function parseRunEvent(data: string): RunEvent | null {
  try {
    const e = JSON.parse(data) as Partial<RunEvent> | null;
    if (!e || typeof e !== "object" || typeof e.type !== "string") return null;
    return {
      id: typeof e.id === "number" ? e.id : 0,
      run_id: String(e.run_id ?? ""),
      kind: e.kind === "collect" ? "collect" : "apply",
      type: e.type,
      level: typeof e.level === "string" ? e.level : "info",
      message: typeof e.message === "string" ? e.message : "",
      data: e.data && typeof e.data === "object" ? (e.data as Record<string, unknown>) : {},
    };
  } catch {
    return null;
  }
}

export interface SubscribeEventsOptions {
  /** Called whenever the stream (re)connects. */
  onOpen?: () => void;
  /** First reconnect delay in ms (doubles up to maxDelayMs). */
  initialDelayMs?: number;
  maxDelayMs?: number;
}

/**
 * Subscribe to the backend's live run events (`GET /events`). Uses fetch +
 * ReadableStream because EventSource can't send the Authorization header.
 * Reconnects with exponential backoff until the returned function is called.
 */
export function subscribeEvents(
  onEvent: (event: RunEvent) => void,
  options: SubscribeEventsOptions = {},
): () => void {
  const initialDelay = options.initialDelayMs ?? 1000;
  const maxDelay = options.maxDelayMs ?? 30000;
  let stopped = false;
  let controller: AbortController | null = null;
  let timer: ReturnType<typeof setTimeout> | null = null;
  let delay = initialDelay;

  const scheduleReconnect = () => {
    if (stopped) return;
    timer = setTimeout(() => void connect(), delay);
    delay = Math.min(delay * 2, maxDelay);
  };

  async function connect() {
    if (stopped) return;
    controller = new AbortController();
    try {
      const info = await getBackendInfo();
      const res = await fetch(`${baseUrlFor(info)}/events`, {
        headers: { Authorization: `Bearer ${info.token}`, Accept: "text/event-stream" },
        signal: controller.signal,
      });
      if (res.status === 401) invalidateBackendInfo();
      if (!res.ok || !res.body) throw new Error(`Event stream unavailable (${res.status})`);
      delay = initialDelay;
      options.onOpen?.();
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      const parser = new SseParser();
      for (;;) {
        const { value, done } = await reader.read();
        if (done || stopped) break;
        for (const data of parser.push(decoder.decode(value, { stream: true }))) {
          const event = parseRunEvent(data);
          if (!event) continue;
          try {
            onEvent(event);
          } catch (err) {
            console.warn("Event handler failed:", err);
          }
        }
      }
    } catch {
      /* network error or abort: reconnect below unless stopped */
    }
    scheduleReconnect();
  }

  void connect();
  return () => {
    stopped = true;
    if (timer) clearTimeout(timer);
    controller?.abort();
  };
}

