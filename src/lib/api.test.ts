/**
 * Tests for src/lib/api.ts — the FastAPI backend HTTP client.
 *
 * Strategy:
 *  - Global `fetch` is stubbed (vi.fn) so NO real network occurs.
 *  - Tauri `invoke` is mocked globally in src/test/setup.ts to return
 *    "test-token" for get_api_token. Some tests override it via vi.mocked.
 *  - api.ts holds module-scope state (backendPort + a cached tokenPromise).
 *    To keep tests isolated we `vi.resetModules()` and dynamically re-import a
 *    fresh copy of the module per test (and re-apply the invoke mock onto the
 *    fresh module's invoke reference).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

type ApiModule = typeof import("./api");

const DEFAULT_BASE = "http://127.0.0.1:8743";

let fetchMock: ReturnType<typeof vi.fn>;

/** Build a Response-like fetch result. */
function jsonResponse(body: unknown, status = 200): Response {
  const text = body === undefined ? "" : JSON.stringify(body);
  return new Response(text, {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/** Re-import a fresh api module so module-scope state is reset per test. */
async function loadApi(): Promise<ApiModule> {
  vi.resetModules();
  // Re-establish the invoke mock for the freshly-loaded module graph.
  const core = await import("@tauri-apps/api/core");
  vi.mocked(core.invoke).mockImplementation(async (cmd: string) => {
    if (cmd === "get_api_token") return "test-token";
    return undefined;
  });
  return import("./api");
}

beforeEach(() => {
  fetchMock = vi.fn(async () => jsonResponse({ ok: true }));
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("api — base url & port", () => {
  it("defaults to port 8743", async () => {
    const api = await loadApi();
    await api.checkHealth();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toBe(`${DEFAULT_BASE}/health`);
  });

  it("setBackendPort changes the base URL for subsequent requests", async () => {
    const api = await loadApi();
    api.setBackendPort(9999);
    await api.checkHealth();
    expect(fetchMock.mock.calls[0][0]).toBe("http://127.0.0.1:9999/health");
  });
});

describe("api — auth token", () => {
  it("sets the Authorization header using the invoke token", async () => {
    const api = await loadApi();
    await api.getProfile();
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    const headers = init.headers as Record<string, string>;
    expect(headers.Authorization).toBe("Bearer test-token");
    expect(headers["Content-Type"]).toBe("application/json");
  });

  it("caches the token: invoke is called once across multiple requests", async () => {
    const core = await import("@tauri-apps/api/core");
    const api = await loadApi();
    await api.getProfile();
    await api.getJobStats();
    await api.checkHealth();
    // tokenPromise is memoized -> get_api_token invoked exactly once.
    const tokenCalls = vi
      .mocked(core.invoke)
      .mock.calls.filter((c) => c[0] === "get_api_token");
    expect(tokenCalls).toHaveLength(1);
  });

  it("throws a wrapped error when the token cannot be read", async () => {
    const core = await import("@tauri-apps/api/core");
    const api = await loadApi();
    vi.mocked(core.invoke).mockRejectedValueOnce("denied");
    await expect(api.getProfile()).rejects.toThrow(
      /Failed to read API token: denied/
    );
    // fetch should never have been attempted.
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("does not permanently cache a failed token (retries invoke next call)", async () => {
    const core = await import("@tauri-apps/api/core");
    const api = await loadApi();
    vi.mocked(core.invoke).mockRejectedValueOnce("transient");
    await expect(api.getProfile()).rejects.toThrow(/Failed to read API token/);
    // Next call should succeed because tokenPromise was reset to null on failure.
    await api.getProfile();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});

describe("api — response handling", () => {
  it("parses JSON response bodies", async () => {
    const api = await loadApi();
    fetchMock.mockResolvedValueOnce(jsonResponse({ status: "ok", uptime: 5 }));
    const res = await api.checkHealth();
    expect(res).toEqual({ status: "ok", uptime: 5 });
  });

  it("returns an empty object for an empty (no body) response", async () => {
    const api = await loadApi();
    fetchMock.mockResolvedValueOnce(new Response("", { status: 200 }));
    const res = await api.completeOnboarding();
    expect(res).toEqual({});
  });

  it("throws on a non-OK response including status and body text", async () => {
    const api = await loadApi();
    fetchMock.mockResolvedValueOnce(
      new Response("boom details", { status: 500 })
    );
    await expect(api.getProfile()).rejects.toThrow(
      "API Error 500: boom details"
    );
  });

  it("throws an 'Invalid JSON' error when the body is not valid JSON", async () => {
    const api = await loadApi();
    fetchMock.mockResolvedValueOnce(
      new Response("not-json-at-all", { status: 200 })
    );
    await expect(api.getProfile()).rejects.toThrow(
      "Invalid JSON response from /profile"
    );
  });
});

describe("api — 401 retry behavior", () => {
  it("on 401 it clears the token cache, waits, refreshes the token, and retries once", async () => {
    vi.useFakeTimers();
    const core = await import("@tauri-apps/api/core");
    const api = await loadApi();

    // First fetch -> 401, second fetch (retry) -> 200.
    fetchMock
      .mockResolvedValueOnce(new Response("unauthorized", { status: 401 }))
      .mockResolvedValueOnce(jsonResponse({ recovered: true }));

    const promise = api.getProfile();
    // Advance past the 1000ms backoff in the retry path.
    await vi.advanceTimersByTimeAsync(1000);
    const res = await promise;

    expect(res).toEqual({ recovered: true });
    expect(fetchMock).toHaveBeenCalledTimes(2);
    // Token cache cleared -> invoke("get_api_token") called twice (initial + refresh).
    const tokenCalls = vi
      .mocked(core.invoke)
      .mock.calls.filter((c) => c[0] === "get_api_token");
    expect(tokenCalls).toHaveLength(2);
    vi.useRealTimers();
  });

  it("does NOT retry more than once: a second 401 surfaces as an error", async () => {
    vi.useFakeTimers();
    const api = await loadApi();
    fetchMock
      .mockResolvedValueOnce(new Response("unauthorized", { status: 401 }))
      .mockResolvedValueOnce(new Response("still unauthorized", { status: 401 }));

    const promise = api.getProfile();
    // Attach a rejection handler immediately so the rejection is observed and
    // not flagged as unhandled while timers advance.
    const assertion = expect(promise).rejects.toThrow(
      "API Error 401: still unauthorized"
    );
    await vi.advanceTimersByTimeAsync(1000);
    await assertion;
    expect(fetchMock).toHaveBeenCalledTimes(2);
    vi.useRealTimers();
  });
});

describe("api — endpoint method/path/body", () => {
  beforeEach(() => {
    // Default OK json for all endpoint shape tests.
    fetchMock.mockResolvedValue(jsonResponse({ success: true }));
  });

  /** Helper: read the (url, init) of the single fetch call. */
  function lastCall() {
    const [url, init] = fetchMock.mock.calls.at(-1) as [string, RequestInit];
    return { url, init, body: init.body ? JSON.parse(init.body as string) : undefined };
  }

  it("getLLMSettings -> GET /settings/llm", async () => {
    const api = await loadApi();
    await api.getLLMSettings();
    const { url, init } = lastCall();
    expect(url).toBe(`${DEFAULT_BASE}/settings/llm`);
    expect(init.method).toBeUndefined(); // GET (no method specified)
  });

  it("saveLLMSettings -> PUT /settings/llm with JSON body", async () => {
    const api = await loadApi();
    const settings = { provider: "ollama", model: "llama3" } as never;
    await api.saveLLMSettings(settings);
    const { url, init, body } = lastCall();
    expect(url).toBe(`${DEFAULT_BASE}/settings/llm`);
    expect(init.method).toBe("PUT");
    expect(body).toEqual({ provider: "ollama", model: "llama3" });
  });

  it("testLLMConnection -> POST /llm/test with settings body", async () => {
    const api = await loadApi();
    const settings = { provider: "openai" } as never;
    await api.testLLMConnection(settings);
    const { url, init, body } = lastCall();
    expect(url).toBe(`${DEFAULT_BASE}/llm/test`);
    expect(init.method).toBe("POST");
    expect(body).toEqual({ provider: "openai" });
  });

  it("fetchOllamaModels -> POST /llm/ollama-models with base_url", async () => {
    const api = await loadApi();
    await api.fetchOllamaModels("http://localhost:11434");
    const { url, init, body } = lastCall();
    expect(url).toBe(`${DEFAULT_BASE}/llm/ollama-models`);
    expect(init.method).toBe("POST");
    expect(body).toEqual({ base_url: "http://localhost:11434" });
  });

  it("saveProfile -> PUT /profile with profile body", async () => {
    const api = await loadApi();
    const profile = { full_name: "Ada" } as never;
    await api.saveProfile(profile);
    const { url, init, body } = lastCall();
    expect(url).toBe(`${DEFAULT_BASE}/profile`);
    expect(init.method).toBe("PUT");
    expect(body).toEqual({ full_name: "Ada" });
  });

  it("updateJobStatus -> PUT /jobs/status with url+status", async () => {
    const api = await loadApi();
    await api.updateJobStatus("https://job/1", "applied");
    const { url, init, body } = lastCall();
    expect(url).toBe(`${DEFAULT_BASE}/jobs/status`);
    expect(init.method).toBe("PUT");
    expect(body).toEqual({ url: "https://job/1", status: "applied" });
  });

  it("deleteJobs -> DELETE /jobs with urls body", async () => {
    const api = await loadApi();
    await api.deleteJobs(["a", "b"]);
    const { url, init, body } = lastCall();
    expect(url).toBe(`${DEFAULT_BASE}/jobs`);
    expect(init.method).toBe("DELETE");
    expect(body).toEqual({ urls: ["a", "b"] });
  });

  it("stopJobCollection -> POST /jobs/collect/stop with no body", async () => {
    const api = await loadApi();
    await api.stopJobCollection();
    const { url, init } = lastCall();
    expect(url).toBe(`${DEFAULT_BASE}/jobs/collect/stop`);
    expect(init.method).toBe("POST");
    expect(init.body).toBeUndefined();
  });

  it("updateQA -> PUT /qa/:id with answer body", async () => {
    const api = await loadApi();
    await api.updateQA(42, "my answer");
    const { url, init, body } = lastCall();
    expect(url).toBe(`${DEFAULT_BASE}/qa/42`);
    expect(init.method).toBe("PUT");
    expect(body).toEqual({ answer: "my answer" });
  });

  it("deleteQA -> DELETE /qa/:id", async () => {
    const api = await loadApi();
    await api.deleteQA(7);
    const { url, init } = lastCall();
    expect(url).toBe(`${DEFAULT_BASE}/qa/7`);
    expect(init.method).toBe("DELETE");
  });

  it("mergeQA -> POST /qa/:source/merge/:target", async () => {
    const api = await loadApi();
    await api.mergeQA(1, 2);
    const { url, init } = lastCall();
    expect(url).toBe(`${DEFAULT_BASE}/qa/1/merge/2`);
    expect(init.method).toBe("POST");
  });

  it("launchLogin -> POST /auth/login/:service", async () => {
    const api = await loadApi();
    await api.launchLogin("linkedin");
    const { url, init } = lastCall();
    expect(url).toBe(`${DEFAULT_BASE}/auth/login/linkedin`);
    expect(init.method).toBe("POST");
  });

  it("togglePlugin -> PUT /plugins/:name/toggle with enabled flag", async () => {
    const api = await loadApi();
    await api.togglePlugin("greenhouse", true);
    const { url, init, body } = lastCall();
    expect(url).toBe(`${DEFAULT_BASE}/plugins/greenhouse/toggle`);
    expect(init.method).toBe("PUT");
    expect(body).toEqual({ enabled: true });
  });

  it("tailorResumes -> POST /resume/tailor with job_urls + options", async () => {
    const api = await loadApi();
    await api.tailorResumes(["u1"], { foo: "bar" } as never);
    const { url, init, body } = lastCall();
    expect(url).toBe(`${DEFAULT_BASE}/resume/tailor`);
    expect(init.method).toBe("POST");
    expect(body).toEqual({ job_urls: ["u1"], options: { foo: "bar" } });
  });

  it("generateCoverLetter -> POST /cover-letter/generate with mapped fields", async () => {
    const api = await loadApi();
    await api.generateCoverLetter("desc", "Engineer", "Acme");
    const { url, body } = lastCall();
    expect(url).toBe(`${DEFAULT_BASE}/cover-letter/generate`);
    expect(body).toEqual({
      job_description: "desc",
      job_title: "Engineer",
      company: "Acme",
    });
  });
});

describe("api — query-string builders", () => {
  beforeEach(() => {
    fetchMock.mockResolvedValue(jsonResponse([]));
  });

  it("getJobs with no params hits /jobs (no query string)", async () => {
    const api = await loadApi();
    await api.getJobs();
    expect(fetchMock.mock.calls.at(-1)![0]).toBe(`${DEFAULT_BASE}/jobs`);
  });

  it("getJobs builds a query string from provided params", async () => {
    const api = await loadApi();
    await api.getJobs({ status: "new", search: "react dev", limit: 25 });
    const url = fetchMock.mock.calls.at(-1)![0] as string;
    expect(url.startsWith(`${DEFAULT_BASE}/jobs?`)).toBe(true);
    expect(url).toContain("status=new");
    expect(url).toContain("search=react+dev");
    expect(url).toContain("limit=25");
  });

  it("getJobs omits falsy params (e.g. limit 0 / empty status)", async () => {
    const api = await loadApi();
    await api.getJobs({ status: "", search: "", limit: 0 });
    expect(fetchMock.mock.calls.at(-1)![0]).toBe(`${DEFAULT_BASE}/jobs`);
  });

  it("getQAList sets unanswered=true only when flagged", async () => {
    const api = await loadApi();
    await api.getQAList({ unanswered: true });
    const url = fetchMock.mock.calls.at(-1)![0] as string;
    expect(url).toContain("unanswered=true");
  });

  it("searchMemories url-encodes the query", async () => {
    const api = await loadApi();
    await api.searchMemories("c++ & rust");
    const url = fetchMock.mock.calls.at(-1)![0] as string;
    expect(url).toBe(
      `${DEFAULT_BASE}/memory/search?q=${encodeURIComponent("c++ & rust")}`
    );
  });

  it("getMemoriesForDomain encodes the domain path segment", async () => {
    const api = await loadApi();
    await api.getMemoriesForDomain("a/b c");
    const url = fetchMock.mock.calls.at(-1)![0] as string;
    expect(url).toBe(
      `${DEFAULT_BASE}/memory/domain/${encodeURIComponent("a/b c")}`
    );
  });

  it("getMetricRuns uses default limit of 50", async () => {
    const api = await loadApi();
    await api.getMetricRuns();
    expect(fetchMock.mock.calls.at(-1)![0]).toBe(
      `${DEFAULT_BASE}/metrics/runs?limit=50`
    );
  });

  it("getRunLogs encodes the run id and includes limit", async () => {
    const api = await loadApi();
    await api.getRunLogs("run 1/2", 10);
    const url = fetchMock.mock.calls.at(-1)![0] as string;
    expect(url).toBe(
      `${DEFAULT_BASE}/logs/runs/${encodeURIComponent("run 1/2")}?limit=10`
    );
  });
});

describe("api — startJobCollection body assembly", () => {
  beforeEach(() => {
    fetchMock.mockResolvedValue(jsonResponse({ success: true, message: "ok" }));
  });

  it("includes only provided fields", async () => {
    const api = await loadApi();
    await api.startJobCollection("Engineer", 20, "linkedin", { remote: "true" });
    const body = JSON.parse(
      (fetchMock.mock.calls.at(-1)![1] as RequestInit).body as string
    );
    expect(body).toEqual({
      title: "Engineer",
      max_jobs: 20,
      source: "linkedin",
      filters: { remote: "true" },
    });
  });

  it("omits empty filters object and undefined args", async () => {
    const api = await loadApi();
    await api.startJobCollection(undefined, undefined, undefined, {});
    const body = JSON.parse(
      (fetchMock.mock.calls.at(-1)![1] as RequestInit).body as string
    );
    expect(body).toEqual({});
  });
});

describe("api — getChromiumStatus (bypasses request helper)", () => {
  it("calls /chromium/status without auth header and returns parsed json", async () => {
    const api = await loadApi();
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ state: "ready", message: "ok" })
    );
    const res = await api.getChromiumStatus();
    expect(res).toEqual({ state: "ready", message: "ok" });
    // This endpoint calls fetch directly with only the URL (no init object).
    expect(fetchMock.mock.calls.at(-1)![0]).toBe(`${DEFAULT_BASE}/chromium/status`);
    expect(fetchMock.mock.calls.at(-1)![1]).toBeUndefined();
  });
});
