import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { createSpace, getSpacesSummary, listItems } from "../api";
import Card from "../components/Card";
import { SearchIcon } from "../components/Icons";
import ItemRow from "../components/ItemRow";
import PageHead from "../components/PageHead";
import SearchAsk from "../components/SearchAsk";
import { formatRelative } from "../format";
import type { Item, SpaceSummary } from "../types";
import { useLoad } from "../useLoad";
import SpaceDetail from "./SpaceDetail";

type Shape = "" | "task" | "note";

/** Spaces: search-or-ask across everything, space and shape chips, the cards, or one space's detail. */
export default function Spaces({ version, onChanged }: { version: number; onChanged: () => void }) {
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [createError, setCreateError] = useState<string | null>(null);
  const [params, setParams] = useSearchParams();
  const space = params.get("space") ?? "";
  const shape = (params.get("shape") ?? "") as Shape;
  const [q, setQ] = useState(params.get("q") ?? "");
  const [debounced, setDebounced] = useState(q.trim());
  useEffect(() => {
    const t = setTimeout(() => setDebounced(q.trim()), 200);
    return () => clearTimeout(t);
  }, [q]);

  function setParam(key: string, value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
  }

  const summary = useLoad(getSpacesSummary, [version]);
  const spaces = summary.data?.spaces.map((s) => s.name) ?? [];
  const results = useLoad(
    () => (debounced ? listItems({ q: debounced, space: space || undefined, shape: shape || undefined, limit: 100 }) : Promise.resolve(null)),
    [debounced, space, shape, version],
  );

  function update(next: Item) {
    if (results.data) results.setData({ ...results.data, items: results.data.items.map((i) => (i.id === next.id ? next : i)) });
  }

  const groups = groupBySpace(results.data?.items ?? []);
  const count = results.data?.items.length ?? 0;

  return (
    <div className="screen">
      <PageHead eyebrow="Spaces" title={space || "Spaces"} subtitle={space ? undefined : "Where things live. Search across all of them, or end with ? to ask."} />
      <SearchAsk value={q} onChange={setQ} space={space || undefined} placeholder={space ? `Search ${space}, or ask` : "Search everything"} large />
      <div className="chip-rows">
        <div className="chips" role="group" aria-label="Space">
          <button type="button" className={`chip-btn ${space === "" ? "on" : ""}`} onClick={() => setParam("space", "")}>
            All spaces
          </button>
          {spaces.map((s) => (
            <button key={s} type="button" className={`chip-btn ${space === s ? "on" : ""}`} onClick={() => setParam("space", s)}>
              {s}
            </button>
          ))}
        </div>
        {!creating ? (
          <button type="button" className="ghost new-space" onClick={() => setCreating(true)}>
            + New space
          </button>
        ) : (
          <form
            className="new-space-form"
            onSubmit={async (e) => {
              e.preventDefault();
              setCreateError(null);
              try {
                const r = await createSpace(newName);
                setNewName("");
                setCreating(false);
                onChanged();
                setParam("space", r.name);
              } catch (err) {
                setCreateError(err instanceof Error ? err.message : "failed");
              }
            }}
          >
            <input autoFocus value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="name, e.g. gym" aria-label="New space name" maxLength={24} />
            <button type="submit" className="primary" disabled={!newName.trim()}>
              Create
            </button>
            <button type="button" className="ghost" onClick={() => { setCreating(false); setCreateError(null); }}>
              Cancel
            </button>
            {createError && <span className="error">{createError}</span>}
          </form>
        )}
        <div className="chips" role="group" aria-label="Shape">
          {(["", "task", "note"] as Shape[]).map((s) => (
            <button key={s || "any"} type="button" className={`chip-btn ${shape === s ? "on" : ""}`} onClick={() => setParam("shape", s)}>
              {s === "" ? "Any shape" : s === "task" ? "Tasks" : "Notes"}
            </button>
          ))}
        </div>
      </div>

      {debounced ? (
        <Card icon={<SearchIcon />} label="Results" aside={<span className="muted">{count} {count === 1 ? "item" : "items"}</span>}>
          {results.error && <p className="error">{results.error}</p>}
          {results.data && groups.length === 0 && <p className="empty muted">No items match.</p>}
          {groups.map(([g, items]) => (
            <div key={g ?? "unfiled"} className="result-group">
              {!space && (
                <p className="section-label muted">{g ? <button type="button" className="link-btn" onClick={() => setParam("space", g)}>{g}</button> : "Unfiled"}</p>
              )}
              <ul className="rows flat">
                {items.map((item) => (
                  <ItemRow key={item.id} item={item} onChange={update} />
                ))}
              </ul>
            </div>
          ))}
        </Card>
      ) : space ? (
        <SpaceDetail space={space} query="" version={version} onRenamed={(name) => { onChanged(); setParam("space", name); }} onDeleted={() => { onChanged(); setParam("space", ""); }} />
      ) : (
        <>
          {summary.error && <p className="error">{summary.error}</p>}
          {summary.loading && !summary.data && <p className="muted">Loading…</p>}
          {summary.data && (
            <div className="space-grid">
              {summary.data.spaces.map((s) => (
                <SpaceCard key={s.name} s={s} onOpen={() => setParam("space", s.name)} />
              ))}
              <SpaceCard s={summary.data.unfiled} />
            </div>
          )}
        </>
      )}
    </div>
  );
}

function SpaceCard({ s, onOpen }: { s: SpaceSummary; onOpen?: () => void }) {
  const inner = (
    <>
      <span className="space-name">
        {s.unfiled ? "Unfiled" : s.name}
        {s.overdue > 0 && <span className="overdue-dot" title={`${s.overdue} overdue`} aria-label={`${s.overdue} overdue`} />}
      </span>
      <span className="space-counts muted">{s.unfiled ? `${s.total} waiting` : `${s.open} open · ${s.notes} ${s.notes === 1 ? "note" : "notes"}`}</span>
      <span className="space-when muted">{s.last_activity ? formatRelative(s.last_activity) : "—"}</span>
    </>
  );
  if (s.unfiled)
    return (
      <Link to="/attention" className="space-card unfiled">
        {inner}
      </Link>
    );
  return (
    <button type="button" className="space-card" onClick={onOpen}>
      {inner}
    </button>
  );
}

function groupBySpace(items: Item[]): [string | null, Item[]][] {
  const map = new Map<string | null, Item[]>();
  for (const it of items) map.set(it.space, [...(map.get(it.space) ?? []), it]);
  const entries = [...map.entries()];
  entries.sort((a, b) => (a[0] === null ? 1 : b[0] === null ? -1 : a[0].localeCompare(b[0])));
  return entries;
}
