import { describe, it, expect } from "vitest";
import { applyTimelineEvent, MAX_TIMELINE_ENTRIES, type JobTimeline } from "./timeline";
import type { RunEvent } from "./types";

let id = 0;
const ev = (type: string, data: Record<string, unknown> = {}, message = ""): RunEvent => ({
  id: ++id, run_id: "r", kind: "apply", type, level: "info", message, data,
});

describe("applyTimelineEvent", () => {
  it("builds a per-job timeline from live events, even with two workers", () => {
    let m = new Map<string, JobTimeline>();
    m = applyTimelineEvent(m, ev("job_started", { job_url: "a", title: "Analyst", company: "Twilio" }));
    m = applyTimelineEvent(m, ev("job_started", { job_url: "b", title: "Engineer", company: "GitLab" }));
    m = applyTimelineEvent(m, ev("agent_step", { job_url: "a", step: 3, goal: "Fill the phone field" }));
    m = applyTimelineEvent(m, ev("field_filled", { job_url: "a" }, "⚡ Prefilled 4 standard field(s)"));
    m = applyTimelineEvent(m, ev("field_filled", { job_url: "b" }, "📎 Resume attached"));
    m = applyTimelineEvent(m, ev("job_finished", { job_url: "b", status: "test_passed" }));

    const a = m.get("a")!;
    expect(a).toMatchObject({ title: "Analyst", step: 3, goal: "Fill the phone field", finished: false });
    expect(a.entries).toEqual(["⚡ Prefilled 4 standard field(s)"]);
    expect(m.get("b")).toMatchObject({ finished: true, status: "test_passed", entries: ["📎 Resume attached"] });
  });

  it("keeps the last few milestones, ignores unknown jobs, and resets on a new run", () => {
    let m = applyTimelineEvent(new Map(), ev("job_started", { job_url: "a" }));
    for (let i = 0; i < 10; i++) m = applyTimelineEvent(m, ev("field_filled", { job_url: "a" }, `f${i}`));
    expect(m.get("a")!.entries).toHaveLength(MAX_TIMELINE_ENTRIES);
    expect(m.get("a")!.entries.at(-1)).toBe("f9");
    expect(applyTimelineEvent(m, ev("agent_step", { job_url: "zzz", step: 1 }))).toBe(m);
    expect(applyTimelineEvent(m, ev("log", {}, "hello"))).toBe(m);
    expect(applyTimelineEvent(m, ev("run_started")).size).toBe(0);
  });
});
