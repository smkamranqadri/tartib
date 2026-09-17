import { Link } from "react-router-dom";
import { formatDueLong, formatRelative } from "../format";
import type { Capture } from "../types";

/** Rows for captures: first line, what it became, when. */
export default function RecentList({ captures }: { captures: Capture[] }) {
  if (captures.length === 0) return <p className="empty muted">Nothing captured yet.</p>;
  return (
    <ul className="rows flat">
      {captures.map((cap) => {
        const first = cap.items[0];
        const line = cap.raw_text.split("\n")[0];
        const state = cap.status === "pending" ? "filing…" : cap.answer && cap.items.length === 0 ? "answered" : first?.stage === "attention" ? "needs attention" : first?.space ?? "no items";
        return (
          <li key={cap.id} className="row">
            <div className="row-main">
              <span className="row-icon muted">{first?.shape === "task" ? <span className="dot task" /> : <span className="dot" />}</span>
              <div className="row-body">
                {first ? (
                  <Link to={`/items/${first.id}`} className="row-text">
                    {line}
                  </Link>
                ) : (
                  <span className="row-text">{line}</span>
                )}
                <span className="row-meta muted">
                  {state}
                  {cap.items.length > 1 && <> · {cap.items.length} items</>}
                  <span className="sep"> · </span>
                  {formatRelative(cap.created_at)}
                </span>
              </div>
              {first?.due && first.status === "open" && <span className="row-due muted">{formatDueLong(first.due)}</span>}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
