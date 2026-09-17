import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getSpacesSummary, listItems } from "../api";
import ItemRow from "../components/ItemRow";
import SearchAsk from "../components/SearchAsk";
import { formatRelative } from "../format";
import type { Item, SpaceSummary } from "../types";
import { useLoad } from "../useLoad";

export default function Spaces({ version }: { version: number }) {
  const [q, setQ] = useState("");
  const [debounced, setDebounced] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setDebounced(q.trim()), 200);
    return () => clearTimeout(t);
  }, [q]);

  const summary = useLoad(getSpacesSummary, [version]);
  const results = useLoad(() => (debounced ? listItems({ q: debounced, limit: 100 }) : Promise.resolve(null)), [debounced, version]);

  function update(next: Item) {
    if (results.data) results.setData({ ...results.data, items: results.data.items.map((i) => (i.id === next.id ? next : i)) });
  }

  const groups = groupBySpace(results.data?.items ?? []);

  return (
    <div className="screen">
      <SearchAsk value={q} onChange={setQ} placeholder="Search all spaces, or ask" />
      {debounced ? (
        <>
          {results.error && <p className="error">{results.error}</p>}
          {results.data && groups.length === 0 && <p className="empty muted">No items match.</p>}
          {groups.map(([space, items]) => (
            <section key={space ?? "unfiled"} className="group">
              <p className="section-label muted">
                {space ? <Link to={`/spaces/${space}`}>{space}</Link> : "Unfiled"}
              </p>
              <ul className="rows">
                {items.map((item) => (
                  <ItemRow key={item.id} item={item} onChange={update} />
                ))}
              </ul>
            </section>
          ))}
        </>
      ) : (
        <>
          {summary.error && <p className="error">{summary.error}</p>}
          {summary.loading && !summary.data && <p className="muted">Loading…</p>}
          {summary.data && (
            <div className="space-grid">
              {summary.data.spaces.map((s) => (
                <SpaceCard key={s.name} s={s} />
              ))}
              <SpaceCard s={summary.data.unfiled} />
            </div>
          )}
        </>
      )}
    </div>
  );
}

function SpaceCard({ s }: { s: SpaceSummary }) {
  const to = s.unfiled ? "/attention" : `/spaces/${s.name}`;
  return (
    <Link to={to} className={`space-card ${s.unfiled ? "unfiled" : ""}`}>
      <span className="space-name">
        {s.unfiled ? "Unfiled" : s.name}
        {s.overdue > 0 && <span className="overdue-dot" title={`${s.overdue} overdue`} aria-label={`${s.overdue} overdue`} />}
      </span>
      <span className="space-counts muted">
        {s.unfiled ? `${s.total} waiting` : `${s.open} open · ${s.notes} ${s.notes === 1 ? "note" : "notes"}`}
      </span>
      <span className="space-when muted">{s.last_activity ? formatRelative(s.last_activity) : "—"}</span>
    </Link>
  );
}

function groupBySpace(items: Item[]): [string | null, Item[]][] {
  const map = new Map<string | null, Item[]>();
  for (const it of items) {
    const key = it.space;
    map.set(key, [...(map.get(key) ?? []), it]);
  }
  const entries = [...map.entries()];
  entries.sort((a, b) => (a[0] === null ? 1 : b[0] === null ? -1 : a[0].localeCompare(b[0])));
  return entries;
}
