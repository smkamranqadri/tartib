import { useRef, useState, type ReactNode } from "react";

/** The one list row. Every list in the app renders through this, so a row looks and
 *  behaves the same wherever it appears. Hover, focus, or a long press reveals `actions`. */
export default function Row({
  leading,
  title,
  meta,
  right,
  trailing,
  actions,
  className = "",
  children,
}: {
  /** Checkbox or glyph at the start of the row. */
  leading?: ReactNode;
  title: ReactNode;
  meta?: ReactNode;
  /** Right-aligned value, such as a due date. */
  right?: ReactNode;
  /** Always-visible control, such as the star. */
  trailing?: ReactNode;
  /** Revealed on hover, focus, or long press. */
  actions?: ReactNode;
  className?: string;
  children?: ReactNode;
}) {
  const [revealed, setRevealed] = useState(false);
  const holdTimer = useRef<number | null>(null);

  function startHold() {
    holdTimer.current = window.setTimeout(() => setRevealed((r) => !r), 500);
  }
  function endHold() {
    if (holdTimer.current) window.clearTimeout(holdTimer.current);
    holdTimer.current = null;
  }

  return (
    <li
      className={`row ${revealed ? "revealed" : ""} ${className}`}
      onTouchStart={startHold}
      onTouchEnd={endHold}
      onTouchMove={endHold}
    >
      <div className="row-main">
        {leading}
        <div className="row-body">
          {title}
          {meta && <span className="row-meta muted">{meta}</span>}
        </div>
        {right}
        {trailing}
        {actions && <span className="row-actions">{actions}</span>}
      </div>
      {children}
    </li>
  );
}
