/**
 * Opt-in usage analytics and crash reporting.
 *
 * Privacy contract:
 * - Telemetry is OFF by default. The only thing that turns it on is an explicit
 *   user choice, persisted as localStorage `langhire_telemetry === "true"`
 *   (absent or any other value = off). Nothing is sent before that.
 * - Usage events go to a maintainer-run proxy (`VITE_ANALYTICS_ENDPOINT`) that
 *   adds any analytics secret server-side. No secret is shipped in the client
 *   bundle. If the endpoint is unset, analytics is a silent no-op.
 * - Crash reporting (Sentry) is only initialised once consent is given; see
 *   `registerCrashReporter` / `initCrashReporting`.
 */

const ANALYTICS_ENDPOINT: string = import.meta.env.VITE_ANALYTICS_ENDPOINT || "";

export const TELEMETRY_STORAGE_KEY = "langhire_telemetry";
const CLIENT_ID_KEY = "langhire_ga_client_id";

let initialized = false;
let telemetryEnabled = false;
let sessionStart = 0;
let clientId = "";
let listenersInstalled = false;

let crashReporterInit: (() => void) | null = null;
let crashReportingStarted = false;

function readStorage(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeStorage(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* storage unavailable — consent simply won't persist */
  }
}

/** True only when the user has explicitly opted in on this device. */
export function hasTelemetryConsent(): boolean {
  return readStorage(TELEMETRY_STORAGE_KEY) === "true";
}

function isActive(): boolean {
  return telemetryEnabled && hasTelemetryConsent();
}

function getClientId(): string {
  if (clientId) return clientId;
  let stored = readStorage(CLIENT_ID_KEY);
  if (!stored) {
    stored = `${Date.now()}.${Math.random().toString(36).slice(2)}`;
    writeStorage(CLIENT_ID_KEY, stored);
  }
  clientId = stored;
  return clientId;
}

function send(events: Array<{ name: string; params?: Record<string, unknown> }>): void {
  if (!initialized || !isActive() || !ANALYTICS_ENDPOINT) return;

  const payload = {
    client_id: getClientId(),
    events: events.map((e) => ({
      name: e.name,
      params: { ...e.params, engagement_time_msec: "100" },
    })),
  };

  try {
    fetch(ANALYTICS_ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      keepalive: true,
    }).catch(() => {});
  } catch {
    /* never let analytics break the app */
  }
}

/**
 * Start analytics if — and only if — `enabled` is true AND the user has given
 * explicit consent on this device. Callers may pass the backend's
 * `telemetry_enabled` value; it can only further restrict, never grant.
 */
export async function initAnalytics(enabled: boolean): Promise<void> {
  telemetryEnabled = enabled && hasTelemetryConsent();
  if (!telemetryEnabled) return;

  initCrashReporting();

  if (!ANALYTICS_ENDPOINT || initialized) return;

  initialized = true;
  sessionStart = Date.now();
  getClientId();

  if (!listenersInstalled) {
    listenersInstalled = true;
    setupErrorListeners();
    window.addEventListener("beforeunload", () => {
      if (sessionStart) {
        trackEvent("app_close", {
          session_duration_seconds: Math.round((Date.now() - sessionStart) / 1000),
        });
      }
    });
  }
  trackEvent("app_launch");
}

/**
 * Record the user's explicit consent choice. `true` opts in (and lazily starts
 * analytics + crash reporting); `false` opts out immediately.
 */
export function setTelemetryEnabled(enabled: boolean): void {
  writeStorage(TELEMETRY_STORAGE_KEY, enabled ? "true" : "false");
  telemetryEnabled = enabled;
  if (enabled) void initAnalytics(true);
}

export function trackPageView(path: string): void {
  send([{ name: "page_view", params: { page_path: path } }]);
}

export function trackEvent(name: string, params?: Record<string, unknown>): void {
  send([{ name, params }]);
}

export function trackException(description: string, fatal = false): void {
  send([{ name: "exception", params: { description: description.slice(0, 500), fatal } }]);
}

function setupErrorListeners(): void {
  window.addEventListener("error", (event) => {
    trackException(`${event.message} at ${event.filename}:${event.lineno}`, true);
  });
  window.addEventListener("unhandledrejection", (event) => {
    const reason = event.reason instanceof Error ? event.reason.message : String(event.reason);
    trackException(`Unhandled: ${reason}`, true);
  });
}

/**
 * Register the function that initialises the crash reporter (Sentry). It is
 * invoked at most once, and only when consent is present — immediately if the
 * user has already opted in, otherwise later when they do.
 */
export function registerCrashReporter(init: () => void): void {
  crashReporterInit = init;
  initCrashReporting();
}

/** Initialise crash reporting if consent is given and it hasn't started yet. */
export function initCrashReporting(): boolean {
  if (crashReportingStarted || !crashReporterInit || !hasTelemetryConsent()) {
    return crashReportingStarted;
  }
  crashReportingStarted = true;
  try {
    crashReporterInit();
  } catch {
    /* a broken crash reporter must never break the app */
  }
  return true;
}
