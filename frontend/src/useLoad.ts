import { useCallback, useEffect, useState } from "react";
import { describe, tracked } from "./api";

/** Load data on mount and whenever `deps` change; expose a manual reload. */
export function useLoad<T>(fn: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  /* When what is on screen was stored, or null when it came from the network just now. Every
     screen loads through here, so the one line that says how old the data is gets written once
     (slice 25). */
  const [cachedAt, setCachedAt] = useState<Date | null>(null);

  const reload = useCallback(() => {
    let cancelled = false;
    setLoading(true);
    tracked(fn)
      .then(({ data: d, cachedAt: at }) => {
        if (!cancelled) {
          setData(d);
          setCachedAt(at);
          setError(null);
        }
      })
      .catch((e) => {
        if (!cancelled) setError(describe(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(reload, [reload]);
  return { data, setData, error, loading, reload, cachedAt };
}
