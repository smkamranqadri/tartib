import type { ReactNode } from "react";
import { formatRelative } from "../format";

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

/** What you are looking at, and how old it is (slice 25). Shown only when the worker answered
 *  from its cache, which network-first means only happens when the network did not -- so its
 *  presence is the honest signal that this is not live, and its absence means it is. Copy is
 *  calm and corrective, never guilt (rule 9): it says what is on screen, not what you failed
 *  to do. */
export function Stale({ at }: { at: Date | null }) {
  if (!at) return null;
  return (
    <p className="stale-line muted">
      <span className="stale-dot" aria-hidden /> Offline · showing what was here {formatRelative(at.toISOString())}.
    </p>
  );
}
