import { useState } from "react";
import { ApiError, editItem, getRecentSessions, listItems } from "../../api";
import { enqueueEdit } from "../../offline";
import { applyTo, isPending } from "../../pending";
import { usePending } from "../../usePending";
import { ClockIcon, NoteIcon } from "../../components/Icons";
import { describe } from "../../components/SessionPast";
import { formatDue, formatRelative, todayLocal } from "../../format";
import { flattenFirstLine } from "../../markdown";
import type { Item } from "../../types";
import { useLoad } from "../../useLoad";

/** The five ways to read a space. Classic is the one the app has always had; the other four are
 *  here to be tried against it (slice 21). */
/** Every filed item in the space, newest first: what all four layouts read. */
export function useSpaceItems(space: string, version: number) {
  const load = useLoad(() => listItems({ space, limit: 200 }), [space, version]);
  const items = (load.data?.items ?? []).filter((i) => i.stage === "filed");
  return { items, loading: load.loading && !load.data, error: load.error, reload: load.reload };
}

export const isOverdue = (i: Item) => i.shape === "task" && i.status === "open" && !!i.due && i.due < todayLocal();
export const isToday = (i: Item) => i.shape === "task" && i.status === "open" && !!i.due && i.due <= todayLocal();

/** What a line leads with: a task's checkbox, which ticks it off where it stands, or a note's
 *  glyph. The checkbox is its own control beside the line, never inside the button that opens
 *  the item -- a tick is not "read this". */
export function ItemLead({ item: serverItem, onChanged }: { item: Item; onChanged: () => void }) {
  const [busy, setBusy] = useState(false);
  const pending = usePending();
  const item = applyTo(serverItem, pending);
  if (item.shape !== "task") return <span className="line-lead muted"><NoteIcon /></span>;
  return (
    <label className="tap-box">
      <input
      type="checkbox"
      className="line-lead"
      checked={item.status === "done"}
      disabled={busy}
      aria-label={item.status === "done" ? "Mark open" : "Mark done"}
      onChange={async () => {
        setBusy(true);
        const edit = { status: item.status === "done" ? ("open" as const) : ("done" as const) };
        try {
          await editItem(item.id, edit);
          onChanged();
        } catch (err) {
          /* The network, not the server: write it down and the row keeps the tick (slice 25). */
          if (err instanceof ApiError) throw err;
          await enqueueEdit(item.id, edit, null);
        } finally {
          setBusy(false);
        }
      }}
      />
    </label>
  );
}

/** One line: the title, then what matters about it. No card frame anywhere in these layouts. */
export function ItemLine({ item: serverItem, meta = true }: { item: Item; meta?: boolean }) {
  const pending = usePending();
  const item = applyTo(serverItem, pending);
  // The first line is the title (slice 31), so a row reads it straight from the text -- which is
  // also what a queued offline edit changes.
  const title = flattenFirstLine(item.raw_text);
  return (
    <>
      <span className={`line-title ${item.status === "done" ? "done" : ""}`}>{title}</span>
      {meta && (
        <span className="line-meta muted">
          {item.due && <span className={isOverdue(item) ? "error" : ""}>{formatDue(item.due)}</span>}
          {item.starred && <span>★</span>}
          {item.thought_count > 0 && <span>{item.thought_count}💭</span>}
          {isPending(item.id, pending) && <span className="pending-mark">waiting to send</span>}
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
            <span className="line-lead muted"><ClockIcon /></span>
            <span className="line-title">{d.what}</span>
            <span className="line-meta muted">{d.meta}</span>
          </li>
        );
      })}
    </ul>
  );
}
