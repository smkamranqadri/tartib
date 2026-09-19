import { useEffect } from "react";
import { getSpaces } from "./api";
import { useLoad } from "./useLoad";

/** The space names every picker offers. Reloaded when `version` moves, and whenever the app
 *  comes back to the foreground: a space made on another device would otherwise stay missing
 *  from a screen left open here until something else happened to reload it. Only the names are
 *  refreshed on return, never the screen's own data, so nothing being edited is disturbed. */
export function useSpaces(version: unknown): string[] {
  const { data, reload } = useLoad(getSpaces, [version]);
  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState === "visible") reload();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, [reload]);
  return data?.spaces ?? [];
}
