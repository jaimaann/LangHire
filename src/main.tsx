import * as Sentry from "@sentry/browser";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { HashRouter } from "react-router-dom";
import "./index.css";
import "./i18n";
import App from "./App";
import { initTheme } from "./lib/theme";
import { hasTelemetryConsent, registerCrashReporter } from "./lib/analytics";
import { scrubBreadcrumb, scrubSentryEvent } from "./lib/scrub";

// Apply the persisted theme before first paint to avoid a flash of light mode.
initTheme();

const SENTRY_DSN = import.meta.env.VITE_SENTRY_DSN;
if (SENTRY_DSN) {
  // Crash reporting is opt-in: registerCrashReporter only runs this init once
  // the user has consented (now, or later when they enable it in Settings).
  registerCrashReporter(() => Sentry.init({
    dsn: SENTRY_DSN,
    environment: import.meta.env.MODE,
    release: `langhire@${__APP_VERSION__}`,
    tracesSampleRate: 0.1,
    sendDefaultPii: false,
    beforeBreadcrumb(breadcrumb) {
      return scrubBreadcrumb(breadcrumb);
    },
    beforeSend(event) {
      // Consent can be withdrawn after init — drop everything from then on.
      if (!hasTelemetryConsent()) return null;
      // Filter transient network errors during startup (backend not ready yet)
      const msg = event.exception?.values?.[0]?.value || "";
      if (msg.includes("Load failed") && msg.includes("127.0.0.1")) return null;
      if (msg.includes("Failed to fetch") && msg.includes("127.0.0.1")) return null;
      // Filter shell.open validation errors (fixed in v1.8.1+)
      if (msg.includes("failed regex validation")) return null;
      return scrubSentryEvent(event);
    },
  }));
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <HashRouter>
      <App />
    </HashRouter>
  </StrictMode>
);
