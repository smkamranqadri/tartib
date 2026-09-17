import type { ReactNode } from "react";

/** Section card: icon + uppercase label in the header, optional right-side slot, body below. */
export default function Card({
  icon,
  label,
  aside,
  children,
  className = "",
}: {
  icon?: ReactNode;
  label: ReactNode;
  aside?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`card ${className}`}>
      <header className="card-head">
        <span className="card-label">
          {icon && <span className="card-icon">{icon}</span>}
          {label}
        </span>
        {aside !== undefined && aside !== null && aside !== false && <span className="card-aside">{aside}</span>}
      </header>
      <div className="card-body">{children}</div>
    </section>
  );
}
