import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ApiError, editItem } from "../api";
import { enqueueEdit } from "../offline";
import { applyTo, isPending } from "../pending";
import { usePending } from "../usePending";
import { formatDueLong, formatRelative, formatRemind, todayLocal, waitingReason } from "../format";
import type { Edit, Item } from "../types";
import { flattenFirstLine } from "../markdown";
import { useWide } from "../useWide";
import { AlertIcon, NoteIcon } from "./Icons";
import Row from "./Row";
import { StartSession } from "./SessionBar";

/** An item as a row. Leading glyph: checkbox for a filed task, alert for something
 *  awaiting a decision, note for a note. */
export default function ItemRow({
  item: serverItem,
  onChange,
  sessions = 0,
  query,
  to,
}: {
  item: Item;
  onChange: (item: Item) => void;
  /** The search that listed this row: the item page opens on the match. */
  query?: string;
  /** Where the row opens, when not the item's own page: the space page's side pane. */
  to?: string;
  /** Today's pomodoro count for this item, shown in the meta line when there is one. */
  sessions?: number;
}) {
  const [error, setError] = useState<string | null>(null);
  const pending = usePending();
  /* What is queued for this item, laid over what the server last said. The row shows your
     change, not the version that has not heard about it yet (slice 25). */
  const item = applyTo(serverItem, pending);
  const waitingToSend = isPending(item.id, pending);
  // On a phone the item opens in a sheet over this list; `?item=` carries it, so Back closes it.
  const wide = useWide(641);
  const [, setParams] = useSearchParams();
  const isTask = item.shape === "task";
  const href = to ?? (query ? `/items/${item.id}?q=${encodeURIComponent(query)}` : `/items/${item.id}`);
  const editable = item.stage === "filed";
  const waiting = item.stage === "attention";
  const overdue = isTask && item.status === "open" && !!item.due && item.due < todayLocal();

  async function patch(edit: Edit) {
    setError(null);
    try {
      onChange(await editItem(item.id, edit));
    } catch (err) {
      /* An ApiError means the server answered and would answer the same way again, so queueing
         it would only defer the same refusal. Anything else is the network, and that is what
         the queue is for. A tick or a star queues with no base version, so it replays exactly
         as an online one would. */
      if (!(err instanceof ApiError) && (await enqueueEdit(item.id, edit, null))) return;
      setError(err instanceof Error ? err.message : "failed");
    }
  }

  const firstLine = flattenFirstLine(item.raw_text);
  const headline = isTask ? item.title || firstLine : firstLine;

  /* The space is a chip, not another word in a grey run-on line: it is the one piece of metadata
     you scan a list by. Everything else stays plain text after it. */
  const meta: string[] = [formatRelative(item.updated_at ?? item.created_at)];
  if (sessions) meta.push(sessions === 1 ? "1 session" : `${sessions} sessions`);
  if (item.thought_count) meta.push(item.thought_count === 1 ? "1 thought" : `${item.thought_count} thoughts`);
  const lead = waiting ? (
    <span className="chip warn">{waitingReason(item, true)}</span>
  ) : item.space ? (
    <span className="chip space">{item.space}</span>
  ) : (
    <span className="chip neutral">no space</span>
  );

  return (
    <Row
      className={`${item.status === "done" ? "done" : ""} ${overdue ? "overdue" : ""} ${waiting ? "waiting" : ""}`}
      leading={
        isTask && editable ? (
          <label className="tap-box">
            <input
              type="checkbox"
              className="check"
              checked={item.status === "done"}
              onChange={(e) => void patch({ status: e.target.checked ? "done" : "open" })}
              aria-label="Done"
            />
          </label>
        ) : (
          <span className="row-icon muted">{waiting ? <AlertIcon /> : <NoteIcon />}</span>
        )
      }
      title={
        !wide && !to ? (
          <button
            type="button"
            className="row-text"
            onClick={() =>
              setParams((p) => {
                p.set("item", String(item.id));
                return p;
              })
            }
          >
            {headline}
          </button>
        ) : (
          <Link to={href} className="row-text">
            {headline}
          </Link>
        )
      }
      meta={
        <>
          {lead}
          {waitingToSend && (
            <span>
              <span className="sep"> · </span>
              <span className="pending-mark">waiting to send</span>
            </span>
          )}
          {meta.map((m, i) => (
            <span key={i}>
              <span className="sep"> · </span>
              {m}
            </span>
          ))}
        </>
      }
      right={
        isTask && item.due ? (
          <span className={`row-due ${overdue ? "overdue" : "muted"}`}>{formatDueLong(item.due)}</span>
        ) : isTask && item.remind_at ? (
          <span className="row-due muted">⏰ {formatRemind(item.remind_at)}</span>
        ) : undefined
      }
      trailing={
        isTask && editable ? (
          <button
            type="button"
            className={`star always ${item.starred ? "on" : ""}`}
            onClick={() => void patch({ starred: !item.starred })}
            aria-label={item.starred ? "Unstar" : "Star"}
          >
            {item.starred ? "★" : "☆"}
          </button>
        ) : undefined
      }
      actions={
        <>
          {isTask && editable && item.status === "open" && <StartSession itemId={item.id} />}
          <Link to={href} className="icon-btn" aria-label="Edit">
            ✎
          </Link>
        </>
      }
    >
      {error && <span className="error">{error}</span>}
    </Row>
  );
}
