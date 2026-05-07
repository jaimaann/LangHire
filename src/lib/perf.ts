import { trackEvent } from "./analytics";

const marks: Record<string, number> = {};

const APP_START = performance.now();

export function markStart(name: string): void {
  marks[name] = performance.now();
}

export function markEnd(name: string): number {
  const start = marks[name];
  if (start === undefined) return 0;
  const duration = Math.round(performance.now() - start);
  delete marks[name];
  return duration;
}

export function trackTiming(name: string, durationMs: number): void {
  trackEvent("performance", { metric: name, duration_ms: durationMs });
}

export function measureAndTrack(name: string): number {
  const duration = markEnd(name);
  if (duration > 0) {
    trackTiming(name, duration);
  }
  return duration;
}

export function getTimeSinceAppStart(): number {
  return Math.round(performance.now() - APP_START);
}

export function trackStartupComplete(): void {
  const total = getTimeSinceAppStart();
  trackTiming("startup_ui_render", total);
}
