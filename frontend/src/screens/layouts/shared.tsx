import { useNavigate } from "react-router-dom";
import { getRecentSessions, listItems } from "../../api";
import Card from "../../components/Card";
import { ClockIcon } from "../../components/Icons";
import { describe } from "../../components/SessionPast";
import { formatDue, formatRelative, todayLocal } from "../../format";
import type { Item } from "../../types";
import { useLoad } from "../../useLoad";

/** The five ways to read a space. Classic is the one the app has always had; the other four are
 *  here to be tried against it (slice 21). */
export const LAYOUTS = [
  { slug: "", label: "Classic" },
  { slug: "panes", label: "Panes" },
  { slug: "tree", label: "Tree" },
];

const KEY = "tartib-space-view";

/** The view a space opens in, per device. A space page sets it whenever one is picked, so the
 *  next space opens the same way. */
export function spaceView(): string {
  try {
    const v = localStorage.getItem(KEY);
    if (v && LAYOUTS.some((l) => l.slug === v)) return v;
  } catch {
    /* private mode */
  }
  return "panes"; // the default until a device says otherwise
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
  const base = `/spaces/${encodeURIComponent(space)}`;
  return (
    <label className="view-pick muted small">
      View
      <select
        value={current}
        aria-label="View"
        onChange={(e) => {
          setSpaceView(e.target.value);
          navigate(e.target.value ? `${base}/${e.target.value}` : base, { replace: true });
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

/** This space's own sessions, the same list the classic page shows, in these layouts' shape. */
export function SpaceSessions({ space, version }: { space: string; version: number }) {
  const { data } = useLoad(() => getRecentSessions(20, space), [space, version]);
  const past = data?.sessions ?? [];
  if (past.length === 0) return null;
  return (
    <Card icon={<ClockIcon />} label="Sessions" aside={<span className="muted">last {past.length}</span>}>
      <ul className="lines">
        {past.map((p) => {
          const d = describe(p);
          return (
            <li key={p.id} className="line static">
              <span className="line-title">{d.what}</span>
              <span className="line-meta muted">{d.meta}</span>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
