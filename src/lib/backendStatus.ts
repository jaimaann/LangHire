/**
 * Tracks the backend sidecar lifecycle reported by the Tauri host via the
 * `backend-status` event (starting | running | crashed | failed).
 *
 * The host supervises the sidecar and restarts it with backoff; the UI uses
 * this store to show a non-blocking "Backend restarting…" banner.
 */
import { useSyncExternalStore } from "react";
import { listen } from "@tauri-apps/api/event";

export type BackendStatus = "starting" | "running" | "crashed" | "failed";

export interface BackendStatusState {
  status: BackendStatus;
  /** Restarts within the host's current restart window. */
  restarts: number;
}

interface BackendStatusPayload {
  status: BackendStatus;
  restarts?: number;
}

export const BACKEND_STATUS_EVENT = "backend-status";

let state: BackendStatusState = { status: "starting", restarts: 0 };
const subscribers = new Set<() => void>();
let listening: Promise<void> | null = null;

function setState(next: BackendStatusState) {
  if (next.status === state.status && next.restarts === state.restarts) return;
  state = next;
  subscribers.forEach((fn) => fn());
}

/** Apply a status payload (exported for tests and non-Tauri callers). */
export function applyBackendStatus(payload: BackendStatusPayload) {
  setState({ status: payload.status, restarts: payload.restarts ?? 0 });
}

function ensureListening() {
  if (listening) return;
  listening = listen<BackendStatusPayload>(BACKEND_STATUS_EVENT, (event) => {
    if (event?.payload?.status) applyBackendStatus(event.payload);
  })
    .then(() => undefined)
    .catch(() => {
      // Not running inside Tauri (plain browser / tests): nothing to listen to.
    });
}

export function getBackendStatus(): BackendStatusState {
  return state;
}

/** Subscribe to status changes. Returns an unsubscribe function. */
export function onBackendStatus(cb: (s: BackendStatusState) => void): () => void {
  ensureListening();
  const fn = () => cb(state);
  subscribers.add(fn);
  return () => {
    subscribers.delete(fn);
  };
}

/** React hook returning the current backend status. */
export function useBackendStatus(): BackendStatusState {
  return useSyncExternalStore(
    (notify) => onBackendStatus(notify),
    getBackendStatus,
    getBackendStatus,
  );
}
