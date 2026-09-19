import { formatRelative } from "../format";
import type { PastSession } from "../types";

const OUTCOME: Record<string, string> = { done: "done", unfinished: "not finished", abandoned: "abandoned" };

export function minutes(s: PastSession): number {
  const end = s.ended_at ?? s.ends_at;
  return Math.max(1, Math.round((new Date(end).getTime() - new Date(s.started_at).getTime()) / 60000));
}

/** "Fix gate · 25 min · done · 2h ago" -- one line per session, no totals, no chart (rule 4). */
export function describe(s: PastSession): { what: string; meta: string } {
  const what = s.item_title || s.item_text?.split("\n")[0] || "No task";
  const meta = [`${minutes(s)} min`, s.outcome ? OUTCOME[s.outcome] : "no outcome", formatRelative(s.ended_at ?? s.started_at)].join(" · ");
  return { what, meta };
}
