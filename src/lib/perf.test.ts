/**
 * Tests for src/lib/perf.ts — lightweight performance instrumentation.
 *
 * perf.ts imports `trackEvent` from ./analytics, so we mock that module to
 * avoid touching real analytics/network and to assert the calls made to it.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock the analytics module BEFORE importing perf so the mocked trackEvent is
// wired into perf's module-scope import.
vi.mock("./analytics", () => ({
  trackEvent: vi.fn(),
}));

import { trackEvent } from "./analytics";
import {
  markStart,
  markEnd,
  trackTiming,
  measureAndTrack,
  getTimeSinceAppStart,
  trackStartupComplete,
} from "./perf";

const mockedTrackEvent = vi.mocked(trackEvent);

describe("perf", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("markStart / markEnd", () => {
    it("returns 0 for an unknown mark", () => {
      expect(markEnd("never-started")).toBe(0);
    });

    it("returns a non-negative integer duration for a valid mark", () => {
      markStart("op");
      const duration = markEnd("op");
      expect(duration).toBeGreaterThanOrEqual(0);
      expect(Number.isInteger(duration)).toBe(true);
    });

    it("returns a rounded duration reflecting elapsed time", () => {
      // Drive performance.now() deterministically: start at 1000, end at 1042.7.
      const nowSpy = vi
        .spyOn(performance, "now")
        .mockReturnValueOnce(1000) // markStart
        .mockReturnValueOnce(1042.7); // markEnd
      markStart("timed");
      const duration = markEnd("timed");
      expect(duration).toBe(43); // Math.round(42.7)
      nowSpy.mockRestore();
    });

    it("consumes the mark so a second markEnd returns 0", () => {
      markStart("once");
      expect(markEnd("once")).toBeGreaterThanOrEqual(0);
      // Second call: the mark has been deleted, so it is now unknown.
      expect(markEnd("once")).toBe(0);
    });

    it("supports multiple independent marks", () => {
      markStart("a");
      markStart("b");
      const a = markEnd("a");
      const b = markEnd("b");
      expect(a).toBeGreaterThanOrEqual(0);
      expect(b).toBeGreaterThanOrEqual(0);
      // Both should now be consumed.
      expect(markEnd("a")).toBe(0);
      expect(markEnd("b")).toBe(0);
    });
  });

  describe("trackTiming", () => {
    it("forwards a 'performance' event to analytics with metric + duration", () => {
      trackTiming("load_jobs", 123);
      expect(mockedTrackEvent).toHaveBeenCalledTimes(1);
      expect(mockedTrackEvent).toHaveBeenCalledWith("performance", {
        metric: "load_jobs",
        duration_ms: 123,
      });
    });

    it("forwards a zero duration as-is (no filtering at this layer)", () => {
      trackTiming("instant", 0);
      expect(mockedTrackEvent).toHaveBeenCalledWith("performance", {
        metric: "instant",
        duration_ms: 0,
      });
    });
  });

  describe("measureAndTrack", () => {
    it("tracks timing when the measured duration is > 0", () => {
      const nowSpy = vi
        .spyOn(performance, "now")
        .mockReturnValueOnce(500) // markStart
        .mockReturnValueOnce(560); // markEnd
      markStart("render");
      const duration = measureAndTrack("render");
      expect(duration).toBe(60);
      expect(mockedTrackEvent).toHaveBeenCalledWith("performance", {
        metric: "render",
        duration_ms: 60,
      });
      nowSpy.mockRestore();
    });

    it("does NOT track timing when the mark is unknown (duration 0)", () => {
      const duration = measureAndTrack("nonexistent");
      expect(duration).toBe(0);
      expect(mockedTrackEvent).not.toHaveBeenCalled();
    });

    it("does NOT track timing when the measured duration is exactly 0", () => {
      const nowSpy = vi
        .spyOn(performance, "now")
        .mockReturnValueOnce(1000) // markStart
        .mockReturnValueOnce(1000); // markEnd -> 0ms
      markStart("zero");
      const duration = measureAndTrack("zero");
      expect(duration).toBe(0);
      expect(mockedTrackEvent).not.toHaveBeenCalled();
      nowSpy.mockRestore();
    });
  });

  describe("getTimeSinceAppStart", () => {
    it("returns a non-negative rounded integer", () => {
      const value = getTimeSinceAppStart();
      expect(value).toBeGreaterThanOrEqual(0);
      expect(Number.isInteger(value)).toBe(true);
    });

    it("increases (or stays equal) as time advances", () => {
      const first = getTimeSinceAppStart();
      // Advance the clock far past module-load time.
      const nowSpy = vi
        .spyOn(performance, "now")
        .mockReturnValue(first + 1_000_000);
      const second = getTimeSinceAppStart();
      expect(second).toBeGreaterThan(first);
      nowSpy.mockRestore();
    });
  });

  describe("trackStartupComplete", () => {
    it("tracks a 'startup_ui_render' performance metric", () => {
      trackStartupComplete();
      expect(mockedTrackEvent).toHaveBeenCalledTimes(1);
      const [eventName, params] = mockedTrackEvent.mock.calls[0];
      expect(eventName).toBe("performance");
      expect(params).toMatchObject({ metric: "startup_ui_render" });
      expect(typeof (params as { duration_ms: number }).duration_ms).toBe(
        "number"
      );
      expect(
        (params as { duration_ms: number }).duration_ms
      ).toBeGreaterThanOrEqual(0);
    });
  });
});
