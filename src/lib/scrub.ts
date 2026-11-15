/**
 * PII / secret scrubbing for crash reports.
 *
 * Everything that leaves the machine through Sentry passes through
 * `scrubSentryEvent` / `scrubBreadcrumb` first. The goal is defensive: even if
 * an error message happens to contain an email address, a phone number, an API
 * key or the user's home directory, it must not reach the crash reporter.
 */
import type { Breadcrumb, ErrorEvent } from "@sentry/browser";

export const REDACTED = "[redacted]";

const PATTERNS: Array<[RegExp, string]> = [
  // Filesystem home paths: keep the structure after the user name, drop the name.
  [/([A-Za-z]:[\\/]+(?:Users|Documents and Settings)[\\/]+)[^\\/\s"'`:]+/gi, `$1${REDACTED}`],
  [/(\/(?:Users|home)\/)[^/\s"'`:]+/g, `$1${REDACTED}`],
  [/(\/root)(?=\/|\b)/g, REDACTED],
  // Email addresses.
  [/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g, "[email]"],
  // Provider API keys: OpenAI/Anthropic style (sk-..., sk-ant-...), AWS access keys,
  // Google API keys, GitHub tokens, Slack tokens, bearer tokens.
  [/\bsk-[A-Za-z0-9_-]{8,}/g, "[key]"],
  [/\b(?:AKIA|ASIA)[A-Z0-9]{12,}\b/g, "[key]"],
  [/\bAIza[0-9A-Za-z_-]{20,}/g, "[key]"],
  [/\b(?:ghp|gho|ghu|ghs|ghr|github_pat)_[A-Za-z0-9_]{16,}/g, "[key]"],
  [/\bxox[abprs]-[A-Za-z0-9-]{10,}/g, "[key]"],
  [/(Bearer\s+)[A-Za-z0-9._~+/=-]{8,}/gi, `$1[key]`],
  // Long hex tokens (>= 32 hex chars) and long base64/base64url-ish tokens
  // (>= 32 chars, must mix letters and digits so ordinary long words survive).
  // "/" is deliberately excluded so URL/file paths in stack frames survive.
  [/\b[A-Fa-f0-9]{32,}\b/g, "[token]"],
  [/(?<![A-Za-z0-9+_-])(?=[A-Za-z0-9+_-]*\d)(?=[A-Za-z0-9+_-]*[A-Za-z])[A-Za-z0-9+_-]{32,}={0,2}/g, "[token]"],
];

/** Phone-number heuristic: at least 9 digits in a separator-joined run. */
function scrubPhones(input: string): string {
  return input.replace(/(?<![\w./:-])\+?\(?\d[\d\s().-]{7,}\d(?![\w/:-])/g, (m) => {
    const digits = m.replace(/\D/g, "");
    if (digits.length < 9 || digits.length > 15) return m;
    // Leave things that look like ISO dates / times / versions alone.
    if (/^\d{4}-\d{2}-\d{2}/.test(m.trim())) return m;
    return "[phone]";
  });
}

/** Scrub a single string of emails, phones, API keys, tokens and home paths. */
export function scrubString(input: string): string {
  if (!input) return input;
  let out = input;
  for (const [re, replacement] of PATTERNS) {
    out = out.replace(re, replacement);
  }
  return scrubPhones(out);
}

/** Deep-scrub every string inside a JSON-ish value (bounded depth). */
export function scrubValue<T>(value: T, depth = 0): T {
  if (depth > 8 || value == null) return value;
  if (typeof value === "string") return scrubString(value) as T;
  if (Array.isArray(value)) return value.map((v) => scrubValue(v, depth + 1)) as T;
  if (typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      out[k] = scrubValue(v, depth + 1);
    }
    return out as T;
  }
  return value;
}

/** Scrub a breadcrumb's message and data. */
export function scrubBreadcrumb(crumb: Breadcrumb): Breadcrumb {
  const out: Breadcrumb = { ...crumb };
  if (out.message) out.message = scrubString(out.message);
  if (out.data) out.data = scrubValue(out.data);
  return out;
}

/**
 * Remove user info, request headers/cookies and scrub free text from a Sentry
 * event. Returns a new event; the input is not mutated.
 */
export function scrubSentryEvent(event: ErrorEvent): ErrorEvent {
  const out: ErrorEvent = { ...event };

  delete out.user;
  delete out.server_name;

  if (out.request) {
    const req = { ...out.request };
    delete req.headers;
    delete req.cookies;
    delete req.data;
    delete req.env;
    if (req.url) req.url = scrubString(req.url.split("?")[0]);
    delete req.query_string;
    out.request = req;
  }

  if (out.message) out.message = scrubString(out.message);

  if (out.exception?.values) {
    out.exception = {
      ...out.exception,
      values: out.exception.values.map((ex) => ({
        ...ex,
        value: ex.value ? scrubString(ex.value) : ex.value,
        stacktrace: ex.stacktrace
          ? {
              ...ex.stacktrace,
              frames: ex.stacktrace.frames?.map((f) => ({
                ...f,
                filename: f.filename ? scrubString(f.filename) : f.filename,
                abs_path: f.abs_path ? scrubString(f.abs_path) : f.abs_path,
                vars: undefined,
              })),
            }
          : ex.stacktrace,
      })),
    };
  }

  if (out.breadcrumbs) out.breadcrumbs = out.breadcrumbs.map(scrubBreadcrumb);
  if (out.extra) out.extra = scrubValue(out.extra);
  if (out.contexts) out.contexts = scrubValue(out.contexts);
  if (out.tags) out.tags = scrubValue(out.tags);

  return out;
}
