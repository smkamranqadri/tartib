import type { ReactNode } from "react";

export default function PageHead({ eyebrow, title, subtitle }: { eyebrow?: string; title: ReactNode; subtitle?: ReactNode }) {
  return (
    <header className="page-head">
      {eyebrow && <p className="eyebrow">{eyebrow}</p>}
      <h1>{title}</h1>
      {subtitle && <p className="subtitle muted">{subtitle}</p>}
    </header>
  );
}
