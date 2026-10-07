import { useCallback, useEffect, useRef, useState } from "react";

/** Load data, optionally refreshing on an interval, and expose reload(). */
export function useData<T>(loader: () => Promise<T>, deps: unknown[], refreshMs?: number) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const loaderRef = useRef(loader);
  loaderRef.current = loader;

  const reload = useCallback(async () => {
    try {
      const result = await loaderRef.current();
      setData(result);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Terjadi kesalahan.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    reload();
    if (!refreshMs) return;
    const timer = window.setInterval(reload, refreshMs);
    return () => window.clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { data, error, loading, reload };
}

export function useStoredFlag(key: string, initial: boolean): [boolean, (v: boolean) => void] {
  const [value, setValue] = useState<boolean>(() => {
    try {
      const stored = window.localStorage.getItem(key);
      return stored === null ? initial : stored === "1";
    } catch {
      return initial;
    }
  });
  const update = (v: boolean) => {
    setValue(v);
    try {
      window.localStorage.setItem(key, v ? "1" : "0");
    } catch {
      /* storage unavailable: keep in memory */
    }
  };
  return [value, update];
}
