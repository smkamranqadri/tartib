import type { ReactNode } from "react";
import { Link } from "react-router-dom";

/** The state of the day in four numbers, before any list. Each tile is a link to the screen that
 *  explains it -- a number you cannot act on is decoration. A tile shows "…" until its data
 *  lands rather than a 0 that is about to change. */
export default function Tiles({ tiles }: { tiles: { label: string; value: ReactNode; to?: string; tone?: string }[] }) {
  return (
    <div className="tiles">
      {tiles.map((t) => {
        const body = (
          <>
            <span className={`tile-value ${t.tone ?? ""}`}>{t.value}</span>
            <span className="tile-label">{t.label}</span>
          </>
        );
        return t.to ? (
          <Link key={t.label} to={t.to} className="tile">
            {body}
          </Link>
        ) : (
          <div key={t.label} className="tile">
            {body}
          </div>
        );
      })}
    </div>
  );
}
