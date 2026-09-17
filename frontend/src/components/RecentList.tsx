import { useState } from "react";
import { formatRelative } from "../format";
import type { Capture, Item } from "../types";
import ItemRow from "./ItemRow";

/** Captures, newest first, rendered with the same row as everywhere else: one ItemRow per
 *  item the capture became. A capture with no items (still filing, or answered) gets a plain row. */
export default function RecentList({ captures }: { captures: Capture[] }) {
  // edits made from a row (done, star) show at once without re-fetching the captures
  const [edited, setEdited] = useState<Record<number, Item>>({});
  const onChange = (item: Item) => setEdited((e) => ({ ...e, [item.id]: item }));
  if (captures.length === 0) return <p className="empty muted">Nothing captured yet.</p>;
  return (
    <ul className="rows flat">
      {captures.map((cap) =>
        cap.items.length > 0 ? (
          cap.items.map((item) => <ItemRow key={item.id} item={edited[item.id] ?? item} onChange={onChange} />)
        ) : (
          <li key={`c${cap.id}`} className="row waiting">
            <div className="row-main">
              <span className="row-icon muted">
                <span className="dot" />
              </span>
              <div className="row-body">
                <span className="row-text">{cap.raw_text.split("\n")[0]}</span>
                <span className="row-meta muted">
                  {cap.status === "pending" ? "filing…" : cap.answer ? "answered" : "no items"}
                  <span className="sep"> · </span>
                  {formatRelative(cap.created_at)}
                </span>
              </div>
            </div>
          </li>
        ),
      )}
    </ul>
  );
}
