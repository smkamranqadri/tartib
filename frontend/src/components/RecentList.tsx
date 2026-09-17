import { useState } from "react";
import { formatRelative } from "../format";
import type { Capture, Item } from "../types";
import ItemRow from "./ItemRow";
import Row from "./Row";
import { Empty } from "./Status";

/** Captures, newest first, as the same rows used everywhere: one per item the capture
 *  became. A capture with no items yet (still filing, or answered) gets a plain row. */
export default function RecentList({ captures }: { captures: Capture[] }) {
  // edits made from a row (done, star) show at once without re-fetching the captures
  const [edited, setEdited] = useState<Record<number, Item>>({});
  const onChange = (item: Item) => setEdited((e) => ({ ...e, [item.id]: item }));
  if (captures.length === 0) return <Empty>Nothing captured yet.</Empty>;
  return (
    <ul className="rows flat">
      {captures.map((cap) =>
        cap.items.length > 0 ? (
          cap.items.map((item) => <ItemRow key={item.id} item={edited[item.id] ?? item} onChange={onChange} />)
        ) : (
          <Row
            key={`c${cap.id}`}
            className="waiting"
            leading={<span className="row-icon muted"><span className="dot" /></span>}
            title={<span className="row-text">{cap.raw_text.split("\n")[0]}</span>}
            meta={
              <>
                {cap.status === "pending" ? "filing…" : cap.answer ? "answered" : "no items"}
                <span className="sep"> · </span>
                {formatRelative(cap.created_at)}
              </>
            }
          />
        ),
      )}
    </ul>
  );
}
