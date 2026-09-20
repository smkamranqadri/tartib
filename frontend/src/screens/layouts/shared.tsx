import { NavLink } from "react-router-dom";
import { listItems } from "../../api";
import { formatDue, formatRelative, todayLocal } from "../../format";
import type { Item } from "../../types";
import { useLoad } from "../../useLoad";

/** The five ways to read a space. Classic is the one the app has always had; the other four are
 *  here to be tried against it (slice 21). */
export const LAYOUTS = [
  { slug: "", label: "Classic" },
  { slug: "panes", label: "Panes" },
  { slug: "board", label: "Board" },
  { slug: "timeline", label: "Timeline" },
  { slug: "tree", label: "Tree" },
];

export function LayoutSwitch({ space }: { space: string }) {
  const base = `/spaces/${encodeURIComponent(space)}`;
  return (
    <nav className="pills tabs" aria-label="Layout">
      {LAYOUTS.map((l) => (
        <NavLink key={l.slug} to={l.slug ? `${base}/${l.slug}` : base} end>
          {l.label}
        </NavLink>
      ))}
    </nav>
  );
}

/** Every filed item in the space, newest first: what all four layouts read. */
export function useSpaceItems(space: string, version: number) {
  const load = useLoad(() => listItems({ space, limit: 200 }), [space, version]);
  const items = (load.data?.items ?? []).filter((i) => i.stage === "filed");
  return { items, loading: load.loading && !load.data, error: load.error, reload: load.reload };
}

export const isOverdue = (i: Item) => i.shape === "task" && i.status === "open" && !!i.due && i.due < todayLocal();
export const isToday = (i: Item) => i.shape === "task" && i.status === "open" && !!i.due && i.due <= todayLocal();

/** One line: the title, then what matters about it. No card frame anywhere in these layouts. */
export function ItemLine({ item, meta = true }: { item: Item; meta?: boolean }) {
  const title = item.shape === "task" ? item.title || item.raw_text.split("\n")[0] : item.raw_text.split("\n")[0];
  return (
    <>
      <span className={`line-title ${item.status === "done" ? "done" : ""}`}>{title}</span>
      {meta && (
        <span className="line-meta muted">
          {item.due && <span className={isOverdue(item) ? "error" : ""}>{formatDue(item.due)}</span>}
          {item.starred && <span>★</span>}
          {item.thought_count > 0 && <span>{item.thought_count}💭</span>}
          <span>{formatRelative(item.updated_at ?? item.created_at)}</span>
        </span>
      )}
    </>
  );
}
