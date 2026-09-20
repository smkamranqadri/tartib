import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { getBrief } from "../../api";
import { useLoad } from "../../useLoad";
import { useWide } from "../../useWide";
import ItemPage from "../ItemPage";
import { ItemLine, matches, SpaceSessions, useSpaceItems } from "./shared";

type Filter = "all" | "task" | "note" | "done";

const KEEP: Record<Filter, (i: ReturnType<typeof useSpaceItems>["items"][number]) => boolean> = {
  all: (i) => i.shape === "note" || i.status === "open",
  task: (i) => i.shape === "task" && i.status === "open",
  note: (i) => i.shape === "note",
  done: (i) => i.status === "done",
};

/** Panes: no card frames. The brief folded into a strip, filter chips, one dense list, the item
 *  beside it. `j` and `k` walk the list, so a space can be read without the mouse. */
export default function Panes({ space, version, query, onChanged }: { space: string; version: number; query: string; onChanged: () => void }) {
  const { items, loading, error } = useSpaceItems(space, version);
  const [filter, setFilter] = useState<Filter>("all");
  const [openBrief, setOpenBrief] = useState(false);
  const brief = useLoad(() => (openBrief ? getBrief(space) : Promise.resolve(null)), [openBrief, space, version]);
  const wide = useWide();
  const [params, setParams] = useSearchParams();
  const shown = items.filter((i) => KEEP[filter](i) && matches(i, query));
  const openId = Number(params.get("item")) || shown[0]?.id || null;

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
        <div className="chips" role="group" aria-label="Filter">
          {(["all", "task", "note", "done"] as Filter[]).map((f) => (
            <button key={f} type="button" className={`chip-btn ${filter === f ? "on" : ""}`} onClick={() => setFilter(f)}>
              {f === "all" ? "All" : f === "task" ? "Tasks" : f === "note" ? "Notes" : "Done"}
              <span className="muted"> {items.filter(KEEP[f]).length}</span>
            </button>
          ))}
        </div>
        {error && <p className="error">{error}</p>}
        {loading && <p className="muted">Loading…</p>}
        {!loading && shown.length === 0 && <p className="empty muted">Nothing here.</p>}
        <ul className="lines">
          {shown.map((item) => (
            <li key={item.id}>
              <button type="button" className={`line ${item.id === openId ? "on" : ""}`} onClick={() => open(item.id)}>
                <ItemLine item={item} />
              </button>
            </li>
          ))}
        </ul>
        <p className="muted small hint">j and k move through the list.</p>
        <SpaceSessions space={space} version={version} />
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
