const GA_ID = import.meta.env.VITE_GA_MEASUREMENT_ID || "";

let initialized = false;
let telemetryEnabled = true;
let sessionStart = 0;

declare global {
  interface Window {
    dataLayer: unknown[];
    gtag: (...args: unknown[]) => void;
    [key: `ga-disable-${string}`]: boolean;
  }
}

export async function initAnalytics(enabled: boolean): Promise<void> {
  telemetryEnabled = enabled;
  if (!GA_ID || !enabled || initialized) return;

  const script = document.createElement("script");
  script.async = true;
  script.src = `https://www.googletagmanager.com/gtag/js?id=${GA_ID}`;
  document.head.appendChild(script);

  window.dataLayer = window.dataLayer || [];
  // eslint-disable-next-line prefer-rest-params
  window.gtag = function () { window.dataLayer.push(arguments); };
  window.gtag("js", new Date());
  window.gtag("config", GA_ID, { send_page_view: false });

  initialized = true;
  sessionStart = Date.now();

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

  if (GA_ID) {
    if (!enabled) {
      window[`ga-disable-${GA_ID}`] = true;
    } else {
      window[`ga-disable-${GA_ID}`] = false;
      if (!initialized) initAnalytics(true);
    }
  }
}

export function trackPageView(path: string): void {
  if (!initialized || !telemetryEnabled) return;
  window.gtag("event", "page_view", { page_path: path });
}

export function trackEvent(name: string, params?: Record<string, unknown>): void {
  if (!initialized || !telemetryEnabled) return;
  window.gtag("event", name, params);
}

export function trackException(description: string, fatal = false): void {
  if (!initialized || !telemetryEnabled) return;
  window.gtag("event", "exception", { description: description.slice(0, 500), fatal });
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
