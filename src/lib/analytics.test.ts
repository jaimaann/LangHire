/**
 * Tests for src/lib/analytics.ts — Google Analytics Measurement Protocol client.
 *
 * analytics.ts reads `import.meta.env.VITE_GA_MEASUREMENT_ID` / `VITE_GA_API_SECRET`
 * into module-scope constants AT IMPORT TIME. To exercise both the "no GA id"
 * (telemetry disabled) and the "configured" code paths we stub the env with
 * `vi.stubEnv`, reset the module registry, and dynamically re-import a fresh
 * copy of the module per scenario.
 *
 * The transport is global `fetch` — we stub it so NO real network occurs.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

const GA_ENDPOINT = "https://www.google-analytics.com/mp/collect";

type AnalyticsModule = typeof import("./analytics");

/** Re-import analytics with the given env applied, after resetting modules. */
async function loadAnalytics(env: {
  measurementId?: string;
  apiSecret?: string;
}): Promise<AnalyticsModule> {
  vi.resetModules();
  vi.stubEnv("VITE_GA_MEASUREMENT_ID", env.measurementId ?? "");
  vi.stubEnv("VITE_GA_API_SECRET", env.apiSecret ?? "");
  return import("./analytics");
}

let fetchMock: ReturnType<typeof vi.fn>;

/**
 * The bundled jsdom in this project exposes `localStorage` as a bare object
 * without the Storage API methods (getItem/setItem/etc are undefined), so the
 * analytics module — which calls localStorage.getItem/setItem — would throw.
 * Install a minimal in-memory Storage shim for these tests.
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

describe("analytics — telemetry disabled (no GA measurement id)", () => {
  it("trackEvent does NOT hit the network when GA_ID is empty", async () => {
    const analytics = await loadAnalytics({ measurementId: "" });
    analytics.trackEvent("some_event", { foo: "bar" });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("initAnalytics is a no-op (no app_launch, no fetch) when GA_ID is empty", async () => {
    const analytics = await loadAnalytics({ measurementId: "" });
    await analytics.initAnalytics(true);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("trackPageView / trackException also short-circuit without GA_ID", async () => {
    const analytics = await loadAnalytics({ measurementId: "" });
    analytics.trackPageView("/dashboard");
    analytics.trackException("boom", true);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("analytics — configured GA, not yet initialized", () => {
  it("trackEvent does NOT send until initAnalytics() has run", async () => {
    const analytics = await loadAnalytics({ measurementId: "G-TEST123" });
    // `initialized` is false at this point.
    analytics.trackEvent("premature");
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("analytics — configured GA, initialized", () => {
  it("initAnalytics sends an app_launch event to the GA endpoint", async () => {
    const analytics = await loadAnalytics({ measurementId: "G-TEST123" });
    await analytics.initAnalytics(true);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain(GA_ENDPOINT);
    expect(url).toContain("measurement_id=G-TEST123");
    expect(opts.method).toBe("POST");
    expect(opts.keepalive).toBe(true);

    const payload = JSON.parse(opts.body as string);
    expect(payload.client_id).toBeTruthy();
    expect(payload.events).toHaveLength(1);
    expect(payload.events[0].name).toBe("app_launch");
    // engagement_time_msec is appended to every event's params.
    expect(payload.events[0].params.engagement_time_msec).toBe("100");
  });

  it("does not re-initialize / re-send app_launch on a second init call", async () => {
    const analytics = await loadAnalytics({ measurementId: "G-TEST123" });
    await analytics.initAnalytics(true);
    fetchMock.mockClear();
    await analytics.initAnalytics(true);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("trackEvent sends the named event with merged params after init", async () => {
    const analytics = await loadAnalytics({ measurementId: "G-TEST123" });
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
    const analytics = await loadAnalytics({ measurementId: "G-TEST123" });
    await analytics.initAnalytics(true);
    fetchMock.mockClear();

    analytics.trackPageView("/settings");
    const payload = JSON.parse(fetchMock.mock.calls[0][1].body as string);
    expect(payload.events[0].name).toBe("page_view");
    expect(payload.events[0].params.page_path).toBe("/settings");
  });

  it("trackException sends an exception event and truncates long descriptions to 500 chars", async () => {
    const analytics = await loadAnalytics({ measurementId: "G-TEST123" });
    await analytics.initAnalytics(true);
    fetchMock.mockClear();

    const longDesc = "x".repeat(900);
    analytics.trackException(longDesc, true);
    const payload = JSON.parse(fetchMock.mock.calls[0][1].body as string);
    expect(payload.events[0].name).toBe("exception");
    expect(payload.events[0].params.fatal).toBe(true);
    expect(payload.events[0].params.description).toHaveLength(500);
  });

  it("appends api_secret to the URL when configured", async () => {
    const analytics = await loadAnalytics({
      measurementId: "G-TEST123",
      apiSecret: "secret-abc",
    });
    await analytics.initAnalytics(true);
    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toContain("api_secret=secret-abc");
    expect(url).toContain("measurement_id=G-TEST123");
  });

  it("swallows fetch rejections (no unhandled error escapes)", async () => {
    const analytics = await loadAnalytics({ measurementId: "G-TEST123" });
    await analytics.initAnalytics(true);
    fetchMock.mockClear();
    fetchMock.mockRejectedValueOnce(new Error("network down"));

    // Should not throw despite the rejected fetch (.catch(() => {})).
    expect(() => analytics.trackEvent("after_failure")).not.toThrow();
    // Give the microtask queue a tick to settle the rejected promise.
    await Promise.resolve();
  });

  it("does not send when telemetry is disabled even though GA is configured", async () => {
    const analytics = await loadAnalytics({ measurementId: "G-TEST123" });
    // initAnalytics(false) sets telemetryEnabled=false and returns early
    // (so `initialized` stays false too).
    await analytics.initAnalytics(false);
    analytics.trackEvent("should_be_suppressed");
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("analytics — client id persistence", () => {
  it("persists a generated client id in localStorage and reuses it", async () => {
    const analytics = await loadAnalytics({ measurementId: "G-TEST123" });
    await analytics.initAnalytics(true);

    const stored = localStorage.getItem("langhire_ga_client_id");
    expect(stored).toBeTruthy();

    fetchMock.mockClear();
    analytics.trackEvent("again");
    const payload = JSON.parse(fetchMock.mock.calls[0][1].body as string);
    expect(payload.client_id).toBe(stored);
  });

  it("uses a pre-existing client id from localStorage", async () => {
    localStorage.setItem("langhire_ga_client_id", "preset-client-id");
    const analytics = await loadAnalytics({ measurementId: "G-TEST123" });
    await analytics.initAnalytics(true);
    const payload = JSON.parse(fetchMock.mock.calls[0][1].body as string);
    expect(payload.client_id).toBe("preset-client-id");
  });
});

describe("analytics — setTelemetryEnabled", () => {
  it("writes the preference to localStorage", async () => {
    const analytics = await loadAnalytics({ measurementId: "G-TEST123" });
    analytics.setTelemetryEnabled(false);
    expect(localStorage.getItem("langhire_telemetry")).toBe("false");

    analytics.setTelemetryEnabled(true);
    expect(localStorage.getItem("langhire_telemetry")).toBe("true");
  });

  it("auto-initializes analytics when enabled and GA is configured but not yet initialized", async () => {
    const analytics = await loadAnalytics({ measurementId: "G-TEST123" });
    // Not initialized yet; enabling should kick off initAnalytics -> app_launch.
    analytics.setTelemetryEnabled(true);
    // initAnalytics is async; allow it to resolve.
    await Promise.resolve();
    await Promise.resolve();
    expect(fetchMock).toHaveBeenCalled();
    const payload = JSON.parse(fetchMock.mock.calls[0][1].body as string);
    expect(payload.events[0].name).toBe("app_launch");
  });

  it("does NOT auto-initialize when GA is not configured", async () => {
    const analytics = await loadAnalytics({ measurementId: "" });
    analytics.setTelemetryEnabled(true);
    await Promise.resolve();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
