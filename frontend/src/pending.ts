/** Queued changes, seen through (slice 25).
 *
 *  The queue is not just a list of requests waiting to go out: it is a layer the reads look
 *  through. Tick a task off with no network and the row has to stay ticked, or the app reads as
 *  broken while it is in fact working exactly as designed.
 *
 *  What it changes and what it does not: a queued edit is applied to **item fields**, wherever
 *  that item appears. It is not applied to counts, tiles or a space's brief, which the server
 *  computes -- doing that would mean reimplementing the backend's aggregation here and keeping a
 *  second source of truth for it. So aggregates lag until the queue drains, and the offline line
 *  on each screen is what explains the discrepancy. That was put to the owner and accepted.
 */
import type { PendingEdit } from "./offline";
import type { Item } from "./types";

/** The queued change for one item, or undefined. */
export function editFor(id: number, pending: PendingEdit[]): PendingEdit | undefined {
  return pending.find((p) => p.kind === "edit" && p.item_id === id);
}

/** How many thoughts are queued for an item, so its count can say so. */
export function thoughtsFor(id: number, pending: PendingEdit[]): PendingEdit[] {
  return pending.filter((p) => p.kind === "thought" && p.item_id === id);
}

/** Is anything waiting to be sent for this item? */
export function isPending(id: number, pending: PendingEdit[]): boolean {
  return pending.some((p) => p.item_id === id);
}

/** Is this item's queued edit one the server refused? */
export function hasConflict(id: number, pending: PendingEdit[]): boolean {
  return pending.some((p) => p.item_id === id && p.conflict);
}

/** One item with whatever is queued for it laid over the top. */
export function applyTo(item: Item, pending: PendingEdit[]): Item {
  const queued = editFor(item.id, pending);
  const thoughts = thoughtsFor(item.id, pending).length;
  if (!queued && !thoughts) return item;
  const e = queued?.edit ?? {};
  return {
    ...item,
    // `text` on the wire is `raw_text` on the item: the one field whose name differs.
    raw_text: e.text ?? item.raw_text,
    space: e.space !== undefined ? e.space : item.space,
    shape: e.shape ?? item.shape,
    title: e.title !== undefined ? e.title : item.title,
    due: e.due !== undefined ? e.due : item.due,
    remind_at: e.remind_at !== undefined ? e.remind_at : item.remind_at,
    starred: e.starred ?? item.starred,
    status: e.status ?? item.status,
    thought_count: item.thought_count + thoughts,
  };
}

/** A list of items, each with its queued change laid over it. Order is untouched: a queued edit
 *  changes what a row says, never where it sits, because a list reordering under a tap is its
 *  own kind of wrong. */
export function applyAll<T extends Item>(items: T[], pending: PendingEdit[]): T[] {
  if (pending.length === 0) return items;
  return items.map((i) => applyTo(i, pending) as T);
}
