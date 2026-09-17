import type { ReactNode } from "react";

/** Section card: icon and uppercase label in the header, optional right-side slot, body
 *  below. With `collapsible`, the label becomes the toggle and the body follows `open`. */
export default function Card({
  icon,
  label,
  aside,
  children,
  className = "",
  collapsible,
  open = true,
  onToggle,
}: {
  icon?: ReactNode;
  label: ReactNode;
  aside?: ReactNode;
  children: ReactNode;
  className?: string;
  collapsible?: boolean;
  open?: boolean;
  onToggle?: () => void;
}) {
  const heading = collapsible ? (
    <button type="button" className="section-toggle" onClick={onToggle} aria-expanded={open}>
      {label} {open ? "▾" : "▸"}
    </button>
  ) : (
    label
  );
  return (
    <section className={`card ${className}`}>
      <header className="card-head">
        <span className="card-label">
          {icon && <span className="card-icon">{icon}</span>}
          {heading}
        </span>
        {aside !== undefined && aside !== null && aside !== false && <span className="card-aside">{aside}</span>}
      </header>
      {(!collapsible || open) && <div className="card-body">{children}</div>}
    </section>
  );
}
