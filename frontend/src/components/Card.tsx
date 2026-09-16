import type { ReactNode } from "react";

/** Section card: uppercase label in the header, optional right-side slot, body below. */
export default function Card({
  label,
  aside,
  children,
  className = "",
}: {
  label: ReactNode;
  aside?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`card ${className}`}>
      <header className="card-head">
        <span className="card-label">{label}</span>
        {aside && <span className="card-aside">{aside}</span>}
      </header>
      <div className="card-body">{children}</div>
    </section>
  );
}
