import { useCallback, useEffect, useState } from "react";
import { ApiError } from "./api";

/** What went wrong, in words that are true. A failed fetch reports "Failed to fetch", which is
 *  the browser's sentence and not an answer to anything the reader was asking. The shell opens
 *  offline since slice 15, so this line is now the first thing you see there and it should say
 *  what is actually the matter. */
function describe(e: unknown): string {
  if (e instanceof ApiError) return e.message;
  if (typeof navigator !== "undefined" && !navigator.onLine) return "You're offline.";
  return "Can't reach Tartib.";
}

/** Load data on mount and whenever `deps` change; expose a manual reload. */
export function useLoad<T>(fn: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(() => {
    let cancelled = false;
    setLoading(true);
    fn()
      .then((d) => {
        if (!cancelled) {
          setData(d);
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
  return { data, setData, error, loading, reload };
}
