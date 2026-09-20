import { useNavigate } from "react-router-dom";
import { getRecentSessions, listItems } from "../../api";
import { describe } from "../../components/SessionPast";
import { formatDue, formatRelative, todayLocal } from "../../format";
import type { Item } from "../../types";
import { useLoad } from "../../useLoad";

/** The five ways to read a space. Classic is the one the app has always had; the other four are
 *  here to be tried against it (slice 21). */
export const LAYOUTS = [
  { slug: "panes", label: "Panes" },
  { slug: "tree", label: "Tree" },
  { slug: "classic", label: "Classic" },
];

const KEY = "tartib-space-view";

export function viewPath(space: string, slug: string): string {
  const base = `/spaces/${encodeURIComponent(space)}`;
  return slug === "classic" ? base : `${base}/${slug}`;
}

/** The view a space opens in, per device. Panes until a device says otherwise; "classic" is
 *  stored as itself, so choosing it is a choice and not an empty setting. */
export function spaceView(): string {
  try {
    const v = localStorage.getItem(KEY);
    if (v && LAYOUTS.some((l) => l.slug === v)) return v;
  } catch {
    /* private mode */
  }
  return "panes";
}

export function setSpaceView(slug: string): void {
  try {
    localStorage.setItem(KEY, slug);
  } catch {
    /* private mode: the choice lasts as long as the page */
  }
}

/** Pick how to read this space. Remembered, so it is a preference and not a per-visit detour. */
export function LayoutSwitch({ space, current }: { space: string; current: string }) {
  const navigate = useNavigate();
  return (
    <label className="view-pick muted small">
      View
      <select
        value={current}
        aria-label="View"
        onChange={(e) => {
          setSpaceView(e.target.value);
          navigate(viewPath(space, e.target.value), { replace: true });
        }}
      >
        {LAYOUTS.map((l) => (
          <option key={l.slug} value={l.slug}>
            {l.label}
          </option>
        ))}
      </select>
    </label>
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


/** Does this item answer the search box? Text, title and space, the way a reader would expect. */
export function matches(item: Item, q: string): boolean {
  const needle = q.trim().toLowerCase();
  if (!needle) return true;
  const hay = `${item.title ?? ""} ${item.raw_text} ${item.space ?? ""}`.toLowerCase();
  return needle.split(/\s+/).every((word) => hay.includes(word));
}

/** This space's own sessions as plain lines: a tab in Panes, a branch in Tree. */
export function useSessions(space: string, version: number) {
  const { data } = useLoad(() => getRecentSessions(20, space), [space, version]);
  return data?.sessions ?? [];
}

export function SessionLines({ rows }: { rows: ReturnType<typeof useSessions> }) {
  if (rows.length === 0) return <p className="empty muted">No sessions in this space yet.</p>;
  return (
    <ul className="lines">
      {rows.map((p) => {
        const d = describe(p);
        return (
          <li key={p.id} className="line static">
            <span className="line-title">{d.what}</span>
            <span className="line-meta muted">{d.meta}</span>
          </li>
        );
      })}
    </ul>
  );
}
