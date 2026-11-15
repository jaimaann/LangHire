/**
 * Tests for src/lib/analytics.ts — opt-in usage analytics + crash-reporting gate.
 *
 * analytics.ts reads `import.meta.env.VITE_ANALYTICS_ENDPOINT` into a
 * module-scope constant AT IMPORT TIME. To exercise both the "no endpoint"
 * (silent no-op) and the "configured" code paths we stub the env with
 * `vi.stubEnv`, reset the module registry, and dynamically re-import a fresh
 * copy of the module per scenario.
 *
 * The transport is global `fetch` — we stub it so NO real network occurs.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

const ENDPOINT = "https://telemetry.example.test/collect";

type AnalyticsModule = typeof import("./analytics");

/** Re-import analytics with the given env applied, after resetting modules. */
async function loadAnalytics(env: { endpoint?: string } = {}): Promise<AnalyticsModule> {
  vi.resetModules();
  vi.stubEnv("VITE_ANALYTICS_ENDPOINT", env.endpoint ?? "");
  return import("./analytics");
}

/** Simulate an explicit opt-in recorded on this device. */
function grantConsent(): void {
  localStorage.setItem("langhire_telemetry", "true");
}

let fetchMock: ReturnType<typeof vi.fn>;

/**
 * The bundled jsdom in this project exposes `localStorage` as a bare object
 * without the Storage API methods, so install a minimal in-memory shim.
 */
function installLocalStorage(): void {
  const store = new Map<string, string>();
  const shim: Storage = {
    get length() {
      return store.size;
    },
    clear: () => store.clear(),
    getItem: (k: string) => (store.has(k) ? store.get(k)! : null),
    setItem: (k: string, v: string) => {
      store.set(k, String(v));
    },
    removeItem: (k: string) => {
      store.delete(k);
    },
    key: (i: number) => Array.from(store.keys())[i] ?? null,
  };
  vi.stubGlobal("localStorage", shim);
}

beforeEach(() => {
  installLocalStorage();
  fetchMock = vi.fn(async () => new Response(null, { status: 204 }));
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("analytics — consent is required (opt-in default)", () => {
  it("hasTelemetryConsent is false when nothing is stored", async () => {
    const analytics = await loadAnalytics({ endpoint: ENDPOINT });
    expect(analytics.hasTelemetryConsent()).toBe(false);
  });

  it("only the exact value 'true' counts as consent", async () => {
    const analytics = await loadAnalytics({ endpoint: ENDPOINT });
    for (const v of ["false", "1", "yes", "TRUE", ""]) {
      localStorage.setItem("langhire_telemetry", v);
      expect(analytics.hasTelemetryConsent()).toBe(false);
    }
    localStorage.setItem("langhire_telemetry", "true");
    expect(analytics.hasTelemetryConsent()).toBe(true);
  });

  it("initAnalytics(true) sends NOTHING without stored consent", async () => {
    const analytics = await loadAnalytics({ endpoint: ENDPOINT });
    await analytics.initAnalytics(true);
    analytics.trackEvent("some_event");
    analytics.trackPageView("/dashboard");
    analytics.trackException("boom", true);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("a backend 'false' wins even if the device has consent", async () => {
    grantConsent();
    const analytics = await loadAnalytics({ endpoint: ENDPOINT });
    await analytics.initAnalytics(false);
    analytics.trackEvent("should_be_suppressed");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("does not start crash reporting without consent", async () => {
    const analytics = await loadAnalytics({ endpoint: ENDPOINT });
    const init = vi.fn();
    analytics.registerCrashReporter(init);
    await analytics.initAnalytics(true);
    expect(init).not.toHaveBeenCalled();
    expect(analytics.initCrashReporting()).toBe(false);
  });
});

describe("analytics — no endpoint configured (silent no-op)", () => {
  it("never hits the network even with consent", async () => {
    grantConsent();
    const analytics = await loadAnalytics({ endpoint: "" });
    await analytics.initAnalytics(true);
    analytics.trackEvent("some_event", { foo: "bar" });
    analytics.trackPageView("/dashboard");
    analytics.trackException("boom", true);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("setTelemetryEnabled(true) does not send without an endpoint", async () => {
    const analytics = await loadAnalytics({ endpoint: "" });
    analytics.setTelemetryEnabled(true);
    await Promise.resolve();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("analytics — consented and configured", () => {
  it("does NOT send until initAnalytics() has run", async () => {
    grantConsent();
    const analytics = await loadAnalytics({ endpoint: ENDPOINT });
    analytics.trackEvent("premature");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("initAnalytics posts {client_id, events} JSON to the proxy endpoint", async () => {
    grantConsent();
    const analytics = await loadAnalytics({ endpoint: ENDPOINT });
    await analytics.initAnalytics(true);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toBe(ENDPOINT);
    expect(opts.method).toBe("POST");
    expect(opts.keepalive).toBe(true);
    expect(opts.headers).toMatchObject({ "Content-Type": "application/json" });

    const payload = JSON.parse(opts.body as string);
    expect(Object.keys(payload).sort()).toEqual(["client_id", "events"]);
    expect(payload.client_id).toBeTruthy();
    expect(payload.events).toHaveLength(1);
    expect(payload.events[0].name).toBe("app_launch");
    expect(payload.events[0].params.engagement_time_msec).toBe("100");
  });

  it("never puts an api_secret or measurement id in the request", async () => {
    grantConsent();
    vi.stubEnv("VITE_GA_API_SECRET", "secret-abc");
    const analytics = await loadAnalytics({ endpoint: ENDPOINT });
    await analytics.initAnalytics(true);
    const [url, opts] = fetchMock.mock.calls[0];
    expect(String(url)).not.toContain("api_secret");
    expect(String(url)).not.toContain("secret-abc");
    expect(String(opts.body)).not.toContain("secret-abc");
  });

  it("does not re-initialize / re-send app_launch on a second init call", async () => {
    grantConsent();
    const analytics = await loadAnalytics({ endpoint: ENDPOINT });
    await analytics.initAnalytics(true);
    fetchMock.mockClear();
    await analytics.initAnalytics(true);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("trackEvent sends the named event with merged params after init", async () => {
    grantConsent();
    const analytics = await loadAnalytics({ endpoint: ENDPOINT });
    await analytics.initAnalytics(true);
    fetchMock.mockClear();

    analytics.trackEvent("job_applied", { count: 3 });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const payload = JSON.parse(fetchMock.mock.calls[0][1].body as string);
    expect(payload.events[0]).toMatchObject({
      name: "job_applied",
      params: { count: 3, engagement_time_msec: "100" },
    });
  });

  it("trackPageView sends a page_view event with page_path", async () => {
    grantConsent();
    const analytics = await loadAnalytics({ endpoint: ENDPOINT });
    await analytics.initAnalytics(true);
    fetchMock.mockClear();

    analytics.trackPageView("/settings");
    const payload = JSON.parse(fetchMock.mock.calls[0][1].body as string);
    expect(payload.events[0].name).toBe("page_view");
    expect(payload.events[0].params.page_path).toBe("/settings");
  });

  it("trackException truncates long descriptions to 500 chars", async () => {
    grantConsent();
    const analytics = await loadAnalytics({ endpoint: ENDPOINT });
    await analytics.initAnalytics(true);
    fetchMock.mockClear();

    analytics.trackException("x".repeat(900), true);
    const payload = JSON.parse(fetchMock.mock.calls[0][1].body as string);
    expect(payload.events[0].name).toBe("exception");
    expect(payload.events[0].params.fatal).toBe(true);
    expect(payload.events[0].params.description).toHaveLength(500);
  });

  it("swallows fetch rejections (no unhandled error escapes)", async () => {
    grantConsent();
    const analytics = await loadAnalytics({ endpoint: ENDPOINT });
    await analytics.initAnalytics(true);
    fetchMock.mockClear();
    fetchMock.mockRejectedValueOnce(new Error("network down"));
    expect(() => analytics.trackEvent("after_failure")).not.toThrow();
    await Promise.resolve();
  });

  it("stops sending immediately after opting out", async () => {
    grantConsent();
    const analytics = await loadAnalytics({ endpoint: ENDPOINT });
    await analytics.initAnalytics(true);
    fetchMock.mockClear();

    analytics.setTelemetryEnabled(false);
    analytics.trackEvent("after_opt_out");
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("analytics — client id persistence", () => {
  it("persists a generated client id in localStorage and reuses it", async () => {
    grantConsent();
    const analytics = await loadAnalytics({ endpoint: ENDPOINT });
    await analytics.initAnalytics(true);

    const stored = localStorage.getItem("langhire_ga_client_id");
    expect(stored).toBeTruthy();

    fetchMock.mockClear();
    analytics.trackEvent("again");
    const payload = JSON.parse(fetchMock.mock.calls[0][1].body as string);
    expect(payload.client_id).toBe(stored);
  });

  it("does not create a client id before consent", async () => {
    const analytics = await loadAnalytics({ endpoint: ENDPOINT });
    await analytics.initAnalytics(true);
    expect(localStorage.getItem("langhire_ga_client_id")).toBeNull();
  });
});

describe("analytics — setTelemetryEnabled", () => {
  it("writes the explicit choice to localStorage", async () => {
    const analytics = await loadAnalytics({ endpoint: ENDPOINT });
    analytics.setTelemetryEnabled(false);
    expect(localStorage.getItem("langhire_telemetry")).toBe("false");
    analytics.setTelemetryEnabled(true);
    expect(localStorage.getItem("langhire_telemetry")).toBe("true");
  });

  it("opting in lazily starts analytics (app_launch)", async () => {
    const analytics = await loadAnalytics({ endpoint: ENDPOINT });
    analytics.setTelemetryEnabled(true);
    await Promise.resolve();
    await Promise.resolve();
    expect(fetchMock).toHaveBeenCalled();
    const payload = JSON.parse(fetchMock.mock.calls[0][1].body as string);
    expect(payload.events[0].name).toBe("app_launch");
  });

  it("opting in lazily initialises crash reporting exactly once", async () => {
    const analytics = await loadAnalytics({ endpoint: "" });
    const init = vi.fn();
    analytics.registerCrashReporter(init);
    expect(init).not.toHaveBeenCalled();

    analytics.setTelemetryEnabled(true);
    await Promise.resolve();
    expect(init).toHaveBeenCalledTimes(1);

    analytics.setTelemetryEnabled(false);
    analytics.setTelemetryEnabled(true);
    await Promise.resolve();
    expect(init).toHaveBeenCalledTimes(1);
  });

  it("registerCrashReporter initialises immediately when consent already exists", async () => {
    grantConsent();
    const analytics = await loadAnalytics({ endpoint: "" });
    const init = vi.fn();
    analytics.registerCrashReporter(init);
    expect(init).toHaveBeenCalledTimes(1);
  });
});
