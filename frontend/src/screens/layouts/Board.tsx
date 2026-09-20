import { useSearchParams } from "react-router-dom";
import { Link } from "react-router-dom";
import type { Item } from "../../types";
import { useWide } from "../../useWide";
import ItemPage from "../ItemPage";
import { ItemLine, isToday, useSpaceItems } from "./shared";

const COLUMNS: { key: string; label: string; keep: (i: Item) => boolean }[] = [
  { key: "today", label: "Today", keep: (i) => isToday(i) },
  { key: "open", label: "Open", keep: (i) => i.shape === "task" && i.status === "open" && !isToday(i) },
  { key: "notes", label: "Notes", keep: (i) => i.shape === "note" },
  { key: "done", label: "Done", keep: (i) => i.status === "done" },
];

/** Board: the space by state, four columns to scan. A click opens the item beside the board on a
 *  wide screen; on a phone the columns stack and a row opens the item's own page. */
export default function Board({ space, version, onChanged }: { space: string; version: number; onChanged: () => void }) {
  const { items, loading, error } = useSpaceItems(space, version);
  const wide = useWide();
  const [params, setParams] = useSearchParams();
  const openId = Number(params.get("item")) || null;

  return (
    <div className={wide ? "split board-split" : undefined}>
      <div>
        {error && <p className="error">{error}</p>}
        {loading && <p className="muted">Loading…</p>}
        <div className="board">
          {COLUMNS.map((col) => {
            const rows = items.filter(col.keep);
            return (
              <section key={col.key} className="board-col">
                <h3>
                  {col.label} <span className="muted">{rows.length}</span>
                </h3>
                {rows.length === 0 && <p className="empty muted small">—</p>}
                <ul className="lines">
                  {rows.map((item) =>
                    wide ? (
                      <li key={item.id}>
                        <button type="button" className={`line ${item.id === openId ? "on" : ""}`} onClick={() => setParams({ item: String(item.id) }, { replace: true })}>
                          <ItemLine item={item} />
                        </button>
                      </li>
                    ) : (
                      <li key={item.id}>
                        <Link className="line" to={`/items/${item.id}`}>
                          <ItemLine item={item} />
                        </Link>
                      </li>
                    ),
                  )}
                </ul>
              </section>
            );
          })}
        </div>
      </div>
      {wide && (
        <aside className="split-item">
          {openId ? (
            <ItemPage key={openId} version={version} itemId={openId} onChanged={onChanged} onClosed={() => setParams({}, { replace: true })} />
          ) : (
            <p className="split-empty muted">Pick something from the board.</p>
          )}
        </aside>
      )}
    </div>
  );
}
