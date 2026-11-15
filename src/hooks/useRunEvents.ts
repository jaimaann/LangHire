import { useEffect, useRef } from "react";
import { subscribeEvents } from "../lib/api";
import type { RunEvent, RunKind } from "../lib/types";

/**
 * Listen to live run events of one kind ("collect" or "apply") from the
 * backend's SSE stream while the component is mounted. The handler may change
 * between renders without re-subscribing.
 */
export function useRunEvents(kind: RunKind, onEvent: (event: RunEvent) => void, enabled = true) {
  const handlerRef = useRef(onEvent);
  useEffect(() => {
    handlerRef.current = onEvent;
  });

  useEffect(() => {
    if (!enabled) return;
    return subscribeEvents((event) => {
      if (event.kind === kind) handlerRef.current(event);
    });
  }, [kind, enabled]);
}

/** Running LLM cost carried by a `cost` event, if any. */
export function costFromEvent(event: RunEvent): number | null {
  if (event.type !== "cost") return null;
  const v = Number(event.data.cost_usd);
  return Number.isFinite(v) ? v : null;
}

/** Fallback poll interval while a live event stream is also open. */
export const FALLBACK_POLL_MS = 10_000;

/** Lines of live log kept in memory (matches the status endpoints). */
export const MAX_LIVE_LOG_LINES = 100;

export function appendLogLine(log: string[], message: string): string[] {
  if (!message) return log;
  const next = [...log, message];
  return next.length > MAX_LIVE_LOG_LINES ? next.slice(next.length - MAX_LIVE_LOG_LINES) : next;
}
