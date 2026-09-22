import type { Item } from "./types";

const DAY = 86_400_000;

export function todayLocal(): string {
  return localDateString(new Date());
}

function localDateString(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

/** "today", "tomorrow", "yesterday", "3d overdue", or a short date. Compares calendar days in the browser zone. */
export function formatDue(due: string): string {
  const [y, m, d] = due.split("-").map(Number);
  const target = new Date(y, m - 1, d);
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const diff = Math.round((target.getTime() - today.getTime()) / DAY);
  if (diff === 0) return "today";
  if (diff === 1) return "tomorrow";
  if (diff === -1) return "yesterday";
  if (diff < 0) return `${-diff}d overdue`;
  if (diff < 7) return target.toLocaleDateString(undefined, { weekday: "short" });
  return target.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function formatRemind(iso: string): string {
  const d = new Date(iso);
  const sameDay = localDateString(d) === localDateString(new Date());
  return d.toLocaleString(undefined, {
    ...(sameDay ? {} : { month: "short", day: "numeric" }),
    hour: "numeric",
    minute: "2-digit",
  });
}

/** ISO UTC -> value for <input type="datetime-local"> in the browser zone. */
export function toLocalInput(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** datetime-local value -> ISO UTC, or null when empty. */
export function fromLocalInput(value: string): string | null {
  return value ? new Date(value).toISOString() : null;
}

/** "just now", "5m ago", "2h ago", "3d ago", or a short date. */
export function formatRelative(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.round(diff / 60_000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.round(h / 24);
  if (d < 7) return `${d}d ago`;
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

/** Short weekday or date for a due value: "Fri", "Sep 24", "today", "yesterday". */
export function formatDueShort(due: string): string {
  return formatDue(due);
}

/** "due today", "due yesterday", "3d overdue", "due Fri, Sep 18". */
export function formatDueLong(due: string): string {
  const [y, m, d] = due.split("-").map(Number);
  const target = new Date(y, m - 1, d);
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const diff = Math.round((target.getTime() - today.getTime()) / DAY);
  if (diff === 0) return "due today";
  if (diff === -1) return "due yesterday";
  if (diff < 0) return `${-diff}d overdue`;
  if (diff === 1) return "due tomorrow";
  return "due " + target.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
}

export function formatLongDate(d: Date = new Date()): string {
  return d.toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" });
}

/** Why an item is waiting for you, from what it already carries. No threshold needed: an item
 *  that kept a space and a proposal is only waiting because the classifier was unsure. `short`
 *  is the row's meta-line form: lowercase, and without the error's detail. */
export function waitingReason(item: Item, short = false): string {
  const pct = item.proposal ? Math.round(item.proposal.confidence * 100) : 0;
  if (item.proposal_error) return short ? "AI failed" : `AI failed: ${item.proposal_error}`;
  if (!item.proposal) return short ? "proposal rejected" : "Proposal rejected";
  /* One capture read as several things files none of them: the owner says whether it was. */
  if (item.wait_reason === "split") {
    const n = item.split?.of;
    return short ? "split from one capture" : `Split from one capture${n ? ` into ${n}` : ""}`;
  }
  if (item.wait_reason === "whole") return short ? "kept as one" : "Kept as one: choose where it goes";
  if (item.wait_reason === "duplicate") return short ? "looks like a duplicate" : "Looks like something already here";
  /* The classifier asked rather than guessed. Checked before confidence, because an item
     carrying a question is waiting on an answer -- at 0.9 it used to read "Unsure (90%)". */
  if (item.wait_reason === "asked" || item.proposal?.clarify)
    return short ? "has a question for you" : "Has a question for you";
  if (!item.space) return short ? "no space matched" : "No space matched";
  return short ? `unsure, ${pct}%` : `Unsure (${pct}%)`;
}
