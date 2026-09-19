import { useEffect, useState } from "react";
import { Link, Navigate, useSearchParams } from "react-router-dom";
import { createSpace, getSpacesSummary, listItems } from "../api";
import Card from "../components/Card";
import { SearchIcon } from "../components/Icons";
import ItemRow from "../components/ItemRow";
import NameForm from "../components/NameForm";
import PageHead from "../components/PageHead";
import SearchAsk from "../components/SearchAsk";
import { Empty, ErrorLine, Loading } from "../components/Status";
import { formatRelative } from "../format";
import type { Item, SpaceSummary } from "../types";
import { useLoad } from "../useLoad";

/** All spaces as cards, search across everything. Each card opens its own page. */
export default function Spaces({ version, onChanged }: { version: number; onChanged: () => void }) {
  const [params] = useSearchParams();
  const [q, setQ] = useState("");
  const [debounced, setDebounced] = useState("");
  const [creating, setCreating] = useState(false);
  const [created, setCreated] = useState<string | null>(null);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(q.trim()), 200);
    return () => clearTimeout(t);
  }, [q]);

  const summary = useLoad(getSpacesSummary, [version]);
  const results = useLoad(() => (debounced ? listItems({ q: debounced, limit: 100 }) : Promise.resolve(null)), [debounced, version]);

  const legacy = params.get("space");
  if (legacy) return <Navigate to={`/spaces/${encodeURIComponent(legacy)}`} replace />;
  if (created) return <Navigate to={`/spaces/${encodeURIComponent(created)}`} replace />;

  function update(next: Item) {
    if (results.data) results.setData({ ...results.data, items: results.data.items.map((i) => (i.id === next.id ? next : i)) });
  }
  const groups = groupBySpace(results.data?.items ?? []);
  const count = results.data?.items.length ?? 0;

  return (
    <div className="screen">
      <div className="title-row">
        <PageHead title="Spaces" subtitle="Where things live. Search across all of them, or end with ? to ask." />
        <div className="title-actions">
          {creating ? (
            <NameForm
              label="New space name"
              placeholder="name, e.g. gym"
              submitLabel="Create"
              onSubmit={async (name) => {
                const r = await createSpace(name);
                onChanged();
                setCreated(r.name);
              }}
              onCancel={() => setCreating(false)}
            />
          ) : (
            <button type="button" className="ghost" onClick={() => setCreating(true)}>
              + New space
            </button>
          )}
        </div>
      </div>
      <SearchAsk value={q} onChange={setQ} placeholder="Search everything, or end with ? to ask" large />
      {debounced ? (
        <Card icon={<SearchIcon />} label="Results" aside={<span className="muted">{count} {count === 1 ? "item" : "items"}</span>}>
          {results.error && <ErrorLine>{results.error}</ErrorLine>}
          {results.data && groups.length === 0 && <Empty>No items match.</Empty>}
          {groups.map(([g, items]) => (
            <div key={g ?? "unfiled"} className="result-group">
              <p className="section-label muted">{g ? <Link to={`/spaces/${g}`}>{g}</Link> : "Unfiled"}</p>
              <ul className="rows flat">
                {items.map((item) => (
                  <ItemRow key={item.id} item={item} onChange={update} query={debounced} />
                ))}
              </ul>
            </div>
          ))}
        </Card>
      ) : (
        <>
          {summary.error && <ErrorLine>{summary.error}</ErrorLine>}
          {summary.loading && !summary.data && <Loading />}
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
  return (
    <Link to={s.unfiled ? "/inbox" : `/spaces/${s.name}`} className={`space-card ${s.unfiled ? "unfiled" : ""}`}>
      <span className="space-name">
        {s.unfiled ? "Unfiled" : s.name}
        {s.overdue > 0 && <span className="overdue-dot" title={`${s.overdue} overdue`} aria-label={`${s.overdue} overdue`} />}
      </span>
      <span className="space-counts muted">{s.unfiled ? `${s.total} waiting` : `${s.open} open · ${s.notes} ${s.notes === 1 ? "note" : "notes"}`}</span>
      <span className="space-when muted">{s.last_activity ? formatRelative(s.last_activity) : "—"}</span>
    </Link>
  );
}

function groupBySpace(items: Item[]): [string | null, Item[]][] {
  const map = new Map<string | null, Item[]>();
  for (const it of items) map.set(it.space, [...(map.get(it.space) ?? []), it]);
  const entries = [...map.entries()];
  entries.sort((a, b) => (a[0] === null ? 1 : b[0] === null ? -1 : a[0].localeCompare(b[0])));
  return entries;
}
