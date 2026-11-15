import type { RunEvent } from "./types";

/** What one job's application has done so far, built from live run events. */
export interface JobTimeline {
  url: string;
  title: string;
  company: string;
  /** The agent's current goal ("Fill the phone field"), from the latest step. */
  goal: string;
  step: number;
  /** Milestones: prefilled fields, resume upload, answers, reported outcome. */
  entries: string[];
  finished: boolean;
  status?: string;
}

export const MAX_TIMELINE_ENTRIES = 6;

/** Fold one event into the per-job timelines. Returns a new map when something changed. */
export function applyTimelineEvent(
  timelines: Map<string, JobTimeline>,
  event: RunEvent,
): Map<string, JobTimeline> {
  if (event.type === "run_started") return new Map();
  const url = typeof event.data?.job_url === "string" ? event.data.job_url : "";
  if (!url) return timelines;
  const prev = timelines.get(url);
  let next: JobTimeline | undefined;
  switch (event.type) {
    case "job_started":
      next = {
        url,
        title: String(event.data.title || ""),
        company: String(event.data.company || ""),
        goal: "",
        step: 0,
        entries: [],
        finished: false,
      };
      break;
    case "agent_step":
      if (!prev) return timelines;
      next = { ...prev, step: Number(event.data.step) || prev.step, goal: String(event.data.goal || prev.goal) };
      break;
    case "field_filled":
    case "job_result":
      if (!prev || !event.message) return timelines;
      next = { ...prev, entries: [...prev.entries, event.message].slice(-MAX_TIMELINE_ENTRIES) };
      break;
    case "job_finished":
      if (!prev) return timelines;
      next = { ...prev, finished: true, goal: "", status: String(event.data.status || "") };
      break;
    default:
      return timelines;
  }
  const out = new Map(timelines);
  out.set(url, next);
  return out;
}
