import { useEffect, useState } from "react";

/** True from `min` pixels wide: where there is room for a list and an item side by side. */
export function useWide(min = 1100): boolean {
  const query = `(min-width: ${min}px)`;
  const [wide, setWide] = useState(() => window.matchMedia(query).matches);
  useEffect(() => {
    const mq = window.matchMedia(query);
    const on = () => setWide(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, [query]);
  return wide;
}
