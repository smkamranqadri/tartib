import { useState } from "react";
import { Link } from "react-router-dom";
import { editItem } from "../api";
import { formatDueLong, formatRelative, formatRemind, todayLocal, waitingReason } from "../format";
import type { Edit, Item } from "../types";
import { AlertIcon, NoteIcon } from "./Icons";
import Row from "./Row";
import { StartSession } from "./SessionBar";

/** An item as a row. Leading glyph: checkbox for a filed task, alert for something
 *  awaiting a decision, note for a note. */
export default function ItemRow({
  item,
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
      setError(err instanceof Error ? err.message : "failed");
    }
  }

  const firstLine = item.raw_text.split("\n")[0];
  const headline = isTask ? item.title || firstLine : firstLine;

  const meta: string[] = [waiting ? waitingReason(item, true) : (item.space ?? "no space"), formatRelative(item.updated_at ?? item.created_at)];
  if (sessions) meta.push(sessions === 1 ? "1 session" : `${sessions} sessions`);

  return (
    <Row
      className={`${item.status === "done" ? "done" : ""} ${overdue ? "overdue" : ""} ${waiting ? "waiting" : ""}`}
      leading={
        isTask && editable ? (
          <input
            type="checkbox"
            className="check"
            checked={item.status === "done"}
            onChange={(e) => void patch({ status: e.target.checked ? "done" : "open" })}
            aria-label="Done"
          />
        ) : (
          <span className="row-icon muted">{waiting ? <AlertIcon /> : <NoteIcon />}</span>
        )
      }
      title={
        <Link to={href} className="row-text">
          {headline}
        </Link>
      }
      meta={meta.map((m, i) => (
        <span key={i}>
          {i > 0 && <span className="sep"> · </span>}
          {m}
        </span>
      ))}
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
