import type { ReactNode } from "react";

/** Grey rows in the shape of the list about to arrive, so the card holds its size instead of
 *  jumping when data lands. Widths vary so it reads as rows of text, not a grid. */
export function Loading({ rows = 3 }: { rows?: number }) {
  return (
    <ul className="rows flat skeleton" aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }, (_, i) => (
        <li key={i} className="skeleton-row">
          <span className="bar" style={{ width: `${[72, 55, 64, 48][i % 4]}%` }} />
          <span className="bar short" style={{ width: `${[28, 22, 34, 25][i % 4]}%` }} />
        </li>
      ))}
    </ul>
  );
}

export function ErrorLine({ children }: { children: ReactNode }) {
  return <p className="error">{children}</p>;
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="empty muted">{children}</p>;
}
