import { describe, it, expect } from "vitest";
import type { ErrorEvent } from "@sentry/browser";
import { scrubString, scrubSentryEvent, scrubBreadcrumb } from "./scrub";

describe("scrubString", () => {
  it("redacts email addresses", () => {
    expect(scrubString("failed for jane.doe+jobs@example.co.uk today")).toBe("failed for [email] today");
  });

  it("redacts phone numbers in common formats", () => {
    for (const phone of ["+1 (415) 555-0132", "+44 20 7946 0958", "415-555-0132", "+919876543210"]) {
      const out = scrubString(`call ${phone} now`);
      expect(out).toBe("call [phone] now");
    }
  });

  it("leaves short numbers, ports, dates and versions alone", () => {
    const s = "Error 404 at http://127.0.0.1:8743/jobs on 2026-11-14 v1.8.1 (count 12345)";
    expect(scrubString(s)).toBe(s);
  });

  it("redacts OpenAI/Anthropic style keys", () => {
    expect(scrubString("key=sk-proj-AbCdEf1234567890xyz")).toBe("key=[key]");
    expect(scrubString("sk-ant-api03-abcDEF123456_-ghi")).toBe("[key]");
  });

  it("redacts AWS access key ids", () => {
    expect(scrubString("using AKIAIOSFODNN7EXAMPLE for s3")).toBe("using [key] for s3");
  });

  it("redacts bearer tokens and long hex / base64 tokens", () => {
    expect(scrubString("Authorization: Bearer abc.def-ghi_123456")).toBe("Authorization: Bearer [key]");
    expect(scrubString("token 0123456789abcdef0123456789abcdef01")).toBe("token [token]");
    expect(scrubString("t=dGhpc2lzYXZlcnlsb25nc2VjcmV0dG9rZW4xMjM0NTY=")).toBe("t=[token]");
  });

  it("keeps ordinary long words and file paths", () => {
    const s = "Uncaught TypeError in /assets/index-Bx12abc.js: internationalizationconfiguration";
    expect(scrubString(s)).toBe(s);
  });

  it("redacts the user name in home directory paths", () => {
    expect(scrubString("C:\\Users\\nitin\\Documents\\cv.pdf")).toBe("C:\\Users\\[redacted]\\Documents\\cv.pdf");
    expect(scrubString("open /Users/jane/resume.pdf failed")).toBe("open /Users/[redacted]/resume.pdf failed");
    expect(scrubString("ENOENT /home/bob/.langhire/data.db")).toBe("ENOENT /home/[redacted]/.langhire/data.db");
  });
});

describe("scrubSentryEvent", () => {
  const event = {
    event_id: "e1",
    message: "Login failed for me@example.com",
    user: { id: "u1", email: "me@example.com", ip_address: "1.2.3.4" },
    server_name: "nitin-laptop",
    request: {
      url: "http://127.0.0.1:8743/settings?email=me@example.com",
      headers: { Authorization: "Bearer secret-token-value", Cookie: "session=abc" },
      cookies: { session: "abc" },
      query_string: "email=me@example.com",
      data: { password: "hunter2" },
    },
    exception: {
      values: [
        {
          type: "Error",
          value: "API key sk-live1234567890abcdef rejected for /Users/jane/x",
          stacktrace: { frames: [{ filename: "/Users/jane/app/main.js", abs_path: "C:\\Users\\jane\\app.js" }] },
        },
      ],
    },
    breadcrumbs: [
      { category: "console", message: "phone +1 415 555 0132 saved" },
      { category: "fetch", data: { url: "http://127.0.0.1:8743/x?key=sk-abcdefgh12345678" } },
    ],
    extra: { note: "contact jane@corp.com" },
  } as unknown as ErrorEvent;

  const out = scrubSentryEvent(event);
  const json = JSON.stringify(out);

  it("drops user info, server name and request headers/cookies/body/query", () => {
    expect(out.user).toBeUndefined();
    expect(out.server_name).toBeUndefined();
    expect(out.request?.headers).toBeUndefined();
    expect(out.request?.cookies).toBeUndefined();
    expect(out.request?.data).toBeUndefined();
    expect(out.request?.query_string).toBeUndefined();
    expect(out.request?.url).toBe("http://127.0.0.1:8743/settings");
  });

  it("scrubs PII from message, exceptions, frames, breadcrumbs and extra", () => {
    expect(json).not.toContain("me@example.com");
    expect(json).not.toContain("jane@corp.com");
    expect(json).not.toContain("sk-live");
    expect(json).not.toContain("sk-abcdefgh");
    expect(json).not.toContain("555");
    expect(json).not.toContain("jane");
    expect(json).not.toContain("hunter2");
    expect(json).not.toContain("secret-token-value");
    expect(out.message).toBe("Login failed for [email]");
  });

  it("does not mutate the original event", () => {
    expect(event.user).toBeDefined();
    expect(event.message).toContain("me@example.com");
  });
});

describe("scrubBreadcrumb", () => {
  it("scrubs message and nested data", () => {
    const crumb = scrubBreadcrumb({ message: "user a@b.io", data: { nested: { path: "/home/al/x" } } });
    expect(crumb.message).toBe("user [email]");
    expect(crumb.data).toEqual({ nested: { path: "/home/[redacted]/x" } });
  });
});
