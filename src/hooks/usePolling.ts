import { useState, useEffect, useRef, useCallback } from "react";

interface UsePollingOptions {
  interval: number;
  enabled?: boolean;
  pauseOnHidden?: boolean;
}

interface UsePollingResult<T> {
  data: T | null;
  loading: boolean;
  error: Error | null;
  refresh: () => void;
}

export function usePolling<T>(
  fetcher: () => Promise<T>,
  options: UsePollingOptions,
): UsePollingResult<T> {
  const { interval, enabled = true, pauseOnHidden = true } = options;
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const activeRef = useRef(true);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const doFetch = useCallback(async () => {
    try {
      const result = await fetcherRef.current();
      if (activeRef.current) {
        setData(result);
        setError(null);
        setLoading(false);
      }
    } catch (e) {
      if (activeRef.current) {
        setError(e instanceof Error ? e : new Error(String(e)));
        setLoading(false);
      }
    }
  }, []);

  const refresh = useCallback(() => {
    doFetch();
  }, [doFetch]);

  useEffect(() => {
    if (!enabled) return;
    activeRef.current = true;
    let timer: ReturnType<typeof setTimeout> | null = null;
    let visible = true;

    const schedule = () => {
      timer = setTimeout(async () => {
        if (activeRef.current && visible) {
          await doFetch();
        }
        if (activeRef.current) schedule();
      }, interval);
    };

    doFetch().then(() => {
      if (activeRef.current) schedule();
    });

    const onVisibility = () => {
      visible = !document.hidden;
      if (visible && activeRef.current) doFetch();
    };

    if (pauseOnHidden) {
      document.addEventListener("visibilitychange", onVisibility);
    }

    return () => {
      activeRef.current = false;
      if (timer) clearTimeout(timer);
      if (pauseOnHidden) {
        document.removeEventListener("visibilitychange", onVisibility);
      }
    };
  }, [interval, enabled, pauseOnHidden, doFetch]);

  return { data, loading, error, refresh };
}
