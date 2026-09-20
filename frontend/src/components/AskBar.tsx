import { useEffect, useRef } from "react";
import AskForm from "./AskForm";

/** Chat-style bar pinned to the bottom of a wide screen. A phone asks in the ⊕ sheet instead. */
export default function AskBar({ spaces }: { spaces: string[] }) {
  // Publish the bar's height, so what sits above it (the session card) clears it exactly -- it
  // grows with an answer, and wraps to two rows on a narrow window.
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const root = document.documentElement;
    const obs = new ResizeObserver(() => root.style.setProperty("--askbar-h", `${el.offsetHeight}px`));
    obs.observe(el);
    return () => {
      obs.disconnect();
      root.style.removeProperty("--askbar-h");
    };
  }, []);

  return (
    <div className="askbar" ref={ref}>
      <AskForm spaces={spaces} />
    </div>
  );
}
