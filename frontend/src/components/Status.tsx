import type { ReactNode } from "react";

export function Loading({ children = "Loading…" }: { children?: ReactNode }) {
  return <p className="muted">{children}</p>;
}

export function ErrorLine({ children }: { children: ReactNode }) {
  return <p className="error">{children}</p>;
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="empty muted">{children}</p>;
}
