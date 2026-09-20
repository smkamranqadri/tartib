import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { getBrief } from "../../api";
import { useLoad } from "../../useLoad";
import { useWide } from "../../useWide";
import ItemPage from "../ItemPage";
import SearchAsk from "../../components/SearchAsk";
import { ItemLead, ItemLine, matches, SessionLines, useSessions, useSpaceItems } from "./shared";

type Filter = "all" | "task" | "note" | "done" | "sessions";

const LABEL: Record<Filter, string> = { all: "All", task: "Tasks", note: "Notes", done: "Done", sessions: "Sessions" };

const KEEP: Record<Filter, (i: ReturnType<typeof useSpaceItems>["items"][number]) => boolean> = {
  all: (i) => i.shape === "note" || i.status === "open",
  task: (i) => i.shape === "task" && i.status === "open",
  note: (i) => i.shape === "note",
  done: (i) => i.status === "done",
  sessions: () => false, // its own tab: sessions are not items
};

/** Panes: no card frames. The brief folded into a strip, filter chips, one dense list, the item
 *  beside it. `j` and `k` walk the list, so a space can be read without the mouse. */
export default function Panes({ space, version, query, onQuery, onChanged }: { space: string; version: number; query: string; onQuery: (q: string) => void; onChanged: () => void }) {
  const { items, loading, error, reload } = useSpaceItems(space, version);
  const [filter, setFilter] = useState<Filter>("all");
  const [openBrief, setOpenBrief] = useState(false);
  const brief = useLoad(() => (openBrief ? getBrief(space) : Promise.resolve(null)), [openBrief, space, version]);
  const sessions = useSessions(space, version);
  const count = (f: Filter) => (f === "sessions" ? sessions.length : items.filter(KEEP[f]).length);
  const wide = useWide();
  const [params, setParams] = useSearchParams();
  const shown = items.filter((i) => KEEP[filter](i) && matches(i, query));
  const openId = Number(params.get("item")) || (wide ? shown[0]?.id : null) || null;

  const open = (id: number) => setParams({ item: String(id) }, { replace: true });
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const t = e.target as HTMLElement | null;
      if (t && ["INPUT", "TEXTAREA", "SELECT"].includes(t.tagName)) return;
      if (e.key !== "j" && e.key !== "k") return;
      const at = shown.findIndex((i) => i.id === openId);
      const next = shown[Math.min(shown.length - 1, Math.max(0, at + (e.key === "j" ? 1 : -1)))];
      if (next) open(next.id);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  return (
    <div className={`panes ${wide ? "split" : ""}`}>
      <div className="panes-list">
        <button type="button" className="brief-strip" onClick={() => setOpenBrief((b) => !b)} aria-expanded={openBrief}>
          <span>{openBrief ? "▾" : "▸"} Brief</span>
          <span className="muted small">{openBrief ? "" : "what is going on here"}</span>
        </button>
        {openBrief && <p className="brief-text">{brief.data?.text ?? (brief.error ?? "Reading the space…")}</p>}
        <SearchAsk value={query} onChange={onQuery} space={space} placeholder={`Search ${space}, or ask`} />
        <div className="filter-row">
          <div className="pills tabs" role="group" aria-label="Show">
            {(["all", "task", "note"] as Filter[]).map((f) => (
              <button key={f} type="button" className={filter === f ? "active" : ""} onClick={() => setFilter(f)}>
                {LABEL[f]} <span className="count">{count(f)}</span>
              </button>
            ))}
          </div>
          <div className="pills tabs" role="group" aria-label="Also">
            {(["done", "sessions"] as Filter[]).map((f) => (
              <button key={f} type="button" className={filter === f ? "active" : ""} onClick={() => setFilter(f)}>
                {LABEL[f]} <span className="count">{count(f)}</span>
              </button>
            ))}
          </div>
        </div>
        {error && <p className="error">{error}</p>}
        {loading && <p className="muted">Loading…</p>}
        {filter === "sessions" ? (
          <SessionLines rows={sessions} />
        ) : (
          <>
            {!loading && shown.length === 0 && <p className="empty muted">Nothing here.</p>}
            <ul className="lines">
              {shown.map((item) => (
                <li key={item.id} className="line-row">
                  <ItemLead item={item} onChanged={reload} />
                  <button type="button" className={`line ${item.id === openId ? "on" : ""}`} onClick={() => open(item.id)}>
                    <ItemLine item={item} />
                  </button>
                </li>
              ))}
            </ul>
          </>
        )}
        {filter !== "sessions" && <p className="muted small hint">j and k move through the list.</p>}
      </div>
      {wide && (
        <aside className="split-item">
          {openId ? (
            <ItemPage key={openId} version={version} itemId={openId} onChanged={onChanged} onClosed={() => setParams({}, { replace: true })} />
          ) : (
            <p className="split-empty muted">Nothing to read yet.</p>
          )}
        </aside>
      )}
    </div>
  );
}
