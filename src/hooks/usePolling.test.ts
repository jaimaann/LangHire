import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { usePolling } from "./usePolling";

describe("usePolling", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  // Helper: flush the initial doFetch() promise chain so schedule() runs.
  async function flushMicrotasks() {
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
  }

  it("fetches immediately on mount and exposes the resolved data", async () => {
    const fetcher = vi.fn().mockResolvedValue("hello");
    const { result } = renderHook(() => usePolling(fetcher, { interval: 1000 }));

    expect(result.current.loading).toBe(true);

    await flushMicrotasks();

    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(result.current.data).toBe("hello");
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it("fires the callback again after the interval elapses", async () => {
    const fetcher = vi.fn().mockResolvedValue("tick");
    renderHook(() => usePolling(fetcher, { interval: 5000 }));

    await flushMicrotasks();
    expect(fetcher).toHaveBeenCalledTimes(1);

    // Advance to the next scheduled poll.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    expect(fetcher).toHaveBeenCalledTimes(2);

    // And the one after that.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    expect(fetcher).toHaveBeenCalledTimes(3);
  });

  it("respects the configured interval (no fire before it elapses)", async () => {
    const fetcher = vi.fn().mockResolvedValue("x");
    renderHook(() => usePolling(fetcher, { interval: 10000 }));

    await flushMicrotasks();
    expect(fetcher).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(9999);
    });
    // Still only the initial fetch — interval not yet reached.
    expect(fetcher).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("does not fetch when disabled", async () => {
    const fetcher = vi.fn().mockResolvedValue("x");
    renderHook(() => usePolling(fetcher, { interval: 1000, enabled: false }));

    await flushMicrotasks();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });

    expect(fetcher).not.toHaveBeenCalled();
  });

  it("stops polling after unmount", async () => {
    const fetcher = vi.fn().mockResolvedValue("x");
    const { unmount } = renderHook(() => usePolling(fetcher, { interval: 1000 }));

    await flushMicrotasks();
    expect(fetcher).toHaveBeenCalledTimes(1);

    unmount();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(10000);
    });
    // No additional calls after unmount.
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("captures errors thrown by the fetcher", async () => {
    const boom = new Error("network down");
    const fetcher = vi.fn().mockRejectedValue(boom);
    const { result } = renderHook(() => usePolling(fetcher, { interval: 1000 }));

    await flushMicrotasks();

    expect(result.current.error).toBe(boom);
    expect(result.current.loading).toBe(false);
    expect(result.current.data).toBeNull();
  });

  it("wraps non-Error rejections into an Error", async () => {
    const fetcher = vi.fn().mockRejectedValue("string failure");
    const { result } = renderHook(() => usePolling(fetcher, { interval: 1000 }));

    await flushMicrotasks();

    expect(result.current.error).toBeInstanceOf(Error);
    expect(result.current.error?.message).toBe("string failure");
  });

  it("refresh() triggers an out-of-band fetch", async () => {
    const fetcher = vi.fn().mockResolvedValue("data");
    const { result } = renderHook(() => usePolling(fetcher, { interval: 100000 }));

    await flushMicrotasks();
    expect(fetcher).toHaveBeenCalledTimes(1);

    await act(async () => {
      result.current.refresh();
      await Promise.resolve();
    });

    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("re-fetches when becoming visible again (pauseOnHidden)", async () => {
    const fetcher = vi.fn().mockResolvedValue("v");
    renderHook(() => usePolling(fetcher, { interval: 1000, pauseOnHidden: true }));

    await flushMicrotasks();
    expect(fetcher).toHaveBeenCalledTimes(1);

    await act(async () => {
      Object.defineProperty(document, "hidden", { value: false, configurable: true });
      document.dispatchEvent(new Event("visibilitychange"));
      await Promise.resolve();
    });

    expect(fetcher).toHaveBeenCalledTimes(2);
  });
});
