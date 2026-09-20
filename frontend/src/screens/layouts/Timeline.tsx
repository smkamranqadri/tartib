import { useState } from "react";
import { formatLongDate } from "../../format";
import type { Item } from "../../types";
import ItemPage from "../ItemPage";
import { ItemLine, useSpaceItems } from "./shared";

/** Timeline: one stream, newest first, under day headings -- tasks and notes together, the way
 *  they arrived. A row opens in place rather than taking you somewhere else. */
export default function Timeline({ space, version, onChanged }: { space: string; version: number; onChanged: () => void }) {
  const { items, loading, error } = useSpaceItems(space, version);
  const [open, setOpen] = useState<number | null>(null);

  const days: { day: string; rows: Item[] }[] = [];
  for (const item of items) {
    const day = (item.updated_at ?? item.created_at).slice(0, 10);
    const last = days[days.length - 1];
    if (last && last.day === day) last.rows.push(item);
    else days.push({ day, rows: [item] });
  }

  return (
    <div className="timeline">
      {error && <p className="error">{error}</p>}
      {loading && <p className="muted">Loading…</p>}
      {!loading && items.length === 0 && <p className="empty muted">Nothing here yet.</p>}
      {days.map(({ day, rows }) => (
        <section key={day}>
          <h3 className="day">{formatLongDate(new Date(`${day}T00:00:00`))}</h3>
          <ul className="lines">
            {rows.map((item) => (
              <li key={item.id}>
                <button type="button" className={`line ${open === item.id ? "on" : ""}`} onClick={() => setOpen(open === item.id ? null : item.id)}>
                  <ItemLine item={item} />
                </button>
                {open === item.id && (
                  <div className="timeline-open">
                    <ItemPage version={version} itemId={item.id} onChanged={onChanged} onClosed={() => setOpen(null)} />
                  </div>
                )}
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
