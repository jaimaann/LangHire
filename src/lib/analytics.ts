const GA_ID = import.meta.env.VITE_GA_MEASUREMENT_ID || "";
const GA_ENDPOINT = "https://www.google-analytics.com/mp/collect";
const GA_API_SECRET = import.meta.env.VITE_GA_API_SECRET || "";

let initialized = false;
let telemetryEnabled = true;
let sessionStart = 0;
let clientId = "";

function getClientId(): string {
  if (clientId) return clientId;
  let stored = localStorage.getItem("langhire_ga_client_id");
  if (!stored) {
    stored = `${Date.now()}.${Math.random().toString(36).slice(2)}`;
    localStorage.setItem("langhire_ga_client_id", stored);
  }
  clientId = stored;
  return clientId;
}

function sendToGA(events: Array<{ name: string; params?: Record<string, unknown> }>): void {
  if (!initialized || !telemetryEnabled || !GA_ID) return;

  const payload = {
    client_id: getClientId(),
    events: events.map((e) => ({
      name: e.name,
      params: { ...e.params, engagement_time_msec: "100" },
    })),
  };

  const url = GA_API_SECRET
    ? `${GA_ENDPOINT}?measurement_id=${GA_ID}&api_secret=${GA_API_SECRET}`
    : `${GA_ENDPOINT}?measurement_id=${GA_ID}`;

  fetch(url, {
    method: "POST",
    body: JSON.stringify(payload),
    keepalive: true,
  }).catch(() => {});
}

export async function initAnalytics(enabled: boolean): Promise<void> {
  telemetryEnabled = enabled;
  if (!GA_ID || !enabled || initialized) return;

  initialized = true;
  sessionStart = Date.now();
  getClientId();

  setupCrashReporting();
  trackEvent("app_launch");

  window.addEventListener("beforeunload", () => {
    if (sessionStart) {
      trackEvent("app_close", {
        session_duration_seconds: Math.round((Date.now() - sessionStart) / 1000),
      });
    }
  });
}

export function setTelemetryEnabled(enabled: boolean): void {
  telemetryEnabled = enabled;
  localStorage.setItem("langhire_telemetry", String(enabled));
  if (enabled && !initialized && GA_ID) initAnalytics(true);
}

export function trackPageView(path: string): void {
  sendToGA([{ name: "page_view", params: { page_path: path } }]);
}

export function trackEvent(name: string, params?: Record<string, unknown>): void {
  sendToGA([{ name, params }]);
}

export function trackException(description: string, fatal = false): void {
  sendToGA([{ name: "exception", params: { description: description.slice(0, 500), fatal } }]);
}

function setupCrashReporting(): void {
  window.addEventListener("error", (event) => {
    trackException(`${event.message} at ${event.filename}:${event.lineno}`, true);
  });
  window.addEventListener("unhandledrejection", (event) => {
    const reason = event.reason instanceof Error ? event.reason.message : String(event.reason);
    trackException(`Unhandled: ${reason}`, true);
  });
}
