/**
 * Tests for the newer API client pieces: plugin review, rescoring,
 * application records, login services and the live event stream
 * (SseParser / parseRunEvent / subscribeEvents fed with fake streams).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

type ApiModule = typeof import("./api");

const DEFAULT_BASE = "http://127.0.0.1:8743";
let fetchMock: ReturnType<typeof vi.fn>;

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(body === undefined ? "" : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/** A Response whose body streams the given chunks, then closes (or stays open). */
function streamResponse(chunks: string[], keepOpen = false): Response {
  const enc = new TextEncoder();
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const c of chunks) controller.enqueue(enc.encode(c));
      if (!keepOpen) controller.close();
    },
  });
  return new Response(body, { status: 200, headers: { "Content-Type": "text/event-stream" } });
}

async function loadApi(): Promise<ApiModule> {
  vi.resetModules();
  const core = await import("@tauri-apps/api/core");
  vi.mocked(core.invoke).mockImplementation(async (cmd: string) =>
    cmd === "get_backend_info" ? { port: 8743, token: "test-token", managed: false } : undefined,
  );
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

describe("api: plugin review, rescoring and application records", () => {
  it("previewPlugin posts the file path to /plugins/preview", async () => {
    const api = await loadApi();
    fetchMock.mockResolvedValueOnce(jsonResponse({ success: true, plugin: { name: "x", sha256: "h" } }));
    const res = await api.previewPlugin("/p.yaml");
    expect(fetchMock.mock.calls[0][0]).toBe(`${DEFAULT_BASE}/plugins/preview`);
    expect(JSON.parse((fetchMock.mock.calls[0][1] as RequestInit).body as string)).toEqual({ file_path: "/p.yaml" });
    expect(res.plugin.sha256).toBe("h");
  });

  it("importPlugin sends approved_sha256 only when given", async () => {
    const api = await loadApi();
    await api.importPlugin("/p.yaml");
    await api.importPlugin("/p.yaml", "abc");
    const bodies = fetchMock.mock.calls.map((c) => JSON.parse((c[1] as RequestInit).body as string));
    expect(bodies[0]).toEqual({ file_path: "/p.yaml" });
    expect(bodies[1]).toEqual({ file_path: "/p.yaml", approved_sha256: "abc" });
  });

  it("rescoreJobs posts to /jobs/rescore", async () => {
    const api = await loadApi();
    await api.rescoreJobs();
    expect(fetchMock.mock.calls[0][0]).toBe(`${DEFAULT_BASE}/jobs/rescore`);
    expect((fetchMock.mock.calls[0][1] as RequestInit).method).toBe("POST");
  });

  it("getApplications encodes job_url", async () => {
    const api = await loadApi();
    fetchMock.mockResolvedValueOnce(jsonResponse([]));
    await api.getApplications({ jobUrl: "https://x.com/a?b=1", limit: 1 });
    expect(fetchMock.mock.calls[0][0]).toBe(
      `${DEFAULT_BASE}/applications?job_url=https%3A%2F%2Fx.com%2Fa%3Fb%3D1&limit=1`,
    );
  });

  it("launchLogin accepts any plugin service name", async () => {
    const api = await loadApi();
    await api.launchLogin("indeed");
    expect(fetchMock.mock.calls[0][0]).toBe(`${DEFAULT_BASE}/auth/login/indeed`);
  });
});

describe("api: SseParser and parseRunEvent", () => {
  it("joins chunks split mid-line and ignores comments, id, event and retry fields", async () => {
    const { SseParser } = await loadApi();
    const p = new SseParser();
    expect(p.push("retry: 3000\n\n: keep-alive\n\nid: 1\nevent: log\nda")).toEqual([]);
    expect(p.push('ta: {"a":1}\n')).toEqual([]);
    expect(p.push("\n")).toEqual(['{"a":1}']);
  });

  it("handles CRLF line endings, including a CR split from its LF", async () => {
    const { SseParser } = await loadApi();
    const p = new SseParser();
    expect(p.push('data: {"b":2}\r')).toEqual([]);
    expect(p.push("\n\r\n")).toEqual(['{"b":2}']);
  });

  it("joins multi-line data with newlines", async () => {
    const { SseParser } = await loadApi();
    expect(new SseParser().push("data: one\ndata:two\n\n")).toEqual(["one\ntwo"]);
  });

  it("normalises payloads and rejects junk", async () => {
    const { parseRunEvent } = await loadApi();
    expect(parseRunEvent("not json")).toBeNull();
    expect(parseRunEvent('{"no":"type"}')).toBeNull();
    expect(parseRunEvent('{"type":"log","kind":"collect","message":"hi"}')).toEqual({
      id: 0, run_id: "", kind: "collect", type: "log", level: "info", message: "hi", data: {},
    });
  });
});

describe("api: subscribeEvents", () => {
  it("streams /events with the bearer token and delivers parsed events", async () => {
    const api = await loadApi();
    const ev1 = { id: 1, run_id: "r1", kind: "apply", type: "job_started", level: "info", message: "Starting", data: { job_url: "u" } };
    const ev2 = { id: 2, run_id: "r1", kind: "apply", type: "cost", level: "info", message: "", data: { cost_usd: 0.12 } };
    const raw = `retry: 3000\n\nid: 1\nevent: job_started\ndata: ${JSON.stringify(ev1)}\n\n`;
    fetchMock.mockResolvedValueOnce(
      streamResponse([raw.slice(0, 25), raw.slice(25), `data: ${JSON.stringify(ev2)}\n\n`], true),
    );
    const events: unknown[] = [];
    const onOpen = vi.fn();
    const stop = api.subscribeEvents((e) => events.push(e), { onOpen });
    await vi.waitFor(() => expect(events).toHaveLength(2));
    expect(events[0]).toEqual(ev1);
    expect(events[1]).toMatchObject({ type: "cost", data: { cost_usd: 0.12 } });
    expect(onOpen).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toBe(`${DEFAULT_BASE}/events`);
    const headers = (fetchMock.mock.calls[0][1] as RequestInit).headers as Record<string, string>;
    expect(headers.Authorization).toBe("Bearer test-token");
    stop();
  });

  it("reconnects with backoff after failures and stops when unsubscribed", async () => {
    const api = await loadApi();
    fetchMock
      .mockRejectedValueOnce(new Error("down"))
      .mockResolvedValueOnce(new Response("nope", { status: 500 }))
      .mockResolvedValueOnce(streamResponse(['data: {"type":"log","kind":"collect","message":"back"}\n\n'], true));
    const events: Array<{ message: string }> = [];
    const stop = api.subscribeEvents((e) => events.push(e), { initialDelayMs: 5, maxDelayMs: 10 });
    await vi.waitFor(() => expect(events.map((e) => e.message)).toEqual(["back"]));
    expect(fetchMock).toHaveBeenCalledTimes(3);
    stop();
    const calls = fetchMock.mock.calls.length;
    await new Promise((r) => setTimeout(r, 40));
    expect(fetchMock.mock.calls.length).toBe(calls);
  });

  it("reconnects when the server closes the stream", async () => {
    const api = await loadApi();
    fetchMock
      .mockResolvedValueOnce(streamResponse(['data: {"type":"log","message":"first"}\n\n']))
      .mockResolvedValueOnce(streamResponse(['data: {"type":"log","message":"second"}\n\n'], true));
    const seen: string[] = [];
    const stop = api.subscribeEvents((e) => seen.push(e.message), { initialDelayMs: 5 });
    await vi.waitFor(() => expect(seen).toEqual(["first", "second"]));
    stop();
  });

  it("keeps going when a handler throws", async () => {
    const api = await loadApi();
    vi.spyOn(console, "warn").mockImplementation(() => {});
    fetchMock.mockResolvedValueOnce(
      streamResponse(['data: {"type":"log","message":"a"}\n\ndata: {"type":"log","message":"b"}\n\n'], true),
    );
    const seen: string[] = [];
    const stop = api.subscribeEvents((e) => {
      seen.push(e.message);
      if (e.message === "a") throw new Error("handler bug");
    });
    await vi.waitFor(() => expect(seen).toEqual(["a", "b"]));
    stop();
  });
});
