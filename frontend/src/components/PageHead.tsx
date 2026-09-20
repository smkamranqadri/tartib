import type { ReactNode } from "react";

/** Every page opens the same way: a breadcrumb saying where you are, the title, and one line
 *  saying what the page is for. The breadcrumb is `TARTIB // SPACES` -- it carries the app's
 *  name so a screenshot of any screen says what it is, and it never repeats the title. */
export default function PageHead({
  crumb,
  title,
  subtitle,
}: {
  crumb?: string;
  title: ReactNode;
  subtitle?: ReactNode;
}) {
  return (
    <header className="page-head">
      {crumb && (
        <p className="eyebrow">
          Tartib<span className="sep">//</span>
          {crumb}
        </p>
      )}
      <h1>{title}</h1>
      {subtitle && <p className="subtitle muted">{subtitle}</p>}
    </header>
  );
}
