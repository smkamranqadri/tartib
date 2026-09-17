import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { editItem } from "../api";
import { formatDueLong, formatRelative, formatRemind, todayLocal } from "../format";
import type { Edit, Item } from "../types";
import { ClockIcon, NoteIcon } from "./Icons";

interface Props {
  item: Item;
  onChange: (item: Item) => void;
}

/** One row: leading control, title, muted meta "space · 2h ago", due at the right.
 *  Hover or long-press reveals star and edit. Notes expand on tap. */
export default function ItemRow({ item, onChange }: Props) {
  const [revealed, setRevealed] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const holdTimer = useRef<number | null>(null);
  const isTask = item.shape === "task";
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
  const hasMore = !isTask && item.raw_text.trim() !== firstLine.trim();

  function startHold() {
    holdTimer.current = window.setTimeout(() => setRevealed((r) => !r), 500);
  }
  function endHold() {
    if (holdTimer.current) window.clearTimeout(holdTimer.current);
    holdTimer.current = null;
  }

  const meta = [waiting ? "needs attention" : item.space ?? "no space", formatRelative(item.updated_at ?? item.created_at)];
  if (waiting && item.proposal) meta.push(`${Math.round(item.proposal.confidence * 100)}%`);

  return (
    <li
      className={`row ${item.status === "done" ? "done" : ""} ${overdue ? "overdue" : ""} ${revealed ? "revealed" : ""} ${waiting ? "waiting" : ""}`}
      onTouchStart={startHold}
      onTouchEnd={endHold}
      onTouchMove={endHold}
    >
      <div className="row-main">
        {isTask && editable ? (
          <input
            type="checkbox"
            className="check"
            checked={item.status === "done"}
            onChange={(e) => void patch({ status: e.target.checked ? "done" : "open" })}
            aria-label="Done"
          />
        ) : (
          <span className="row-icon muted">{waiting ? <ClockIcon /> : <NoteIcon />}</span>
        )}
        <div className="row-body">
          {isTask ? (
            <Link to={`/items/${item.id}`} className="row-text">
              {headline}
            </Link>
          ) : (
            <button type="button" className={`row-text ${hasMore && !expanded ? "expandable" : ""}`} onClick={() => setExpanded((e) => !e)}>
              {expanded ? item.raw_text : headline}
            </button>
          )}
          <span className="row-meta muted">
            {meta.map((m, i) => (
              <span key={i}>
                {i > 0 && <span className="sep"> · </span>}
                {m}
              </span>
            ))}
            {expanded && !isTask && (
              <>
                <span className="sep"> · </span>
                <Link to={`/items/${item.id}`}>open</Link>
              </>
            )}
          </span>
        </div>
        {isTask && item.due && <span className={`row-due ${overdue ? "overdue" : "muted"}`}>{formatDueLong(item.due)}</span>}
        {isTask && !item.due && item.remind_at && <span className="row-due muted">⏰ {formatRemind(item.remind_at)}</span>}
        <span className="row-actions">
          {isTask && editable && (
            <button
              type="button"
              className={`star ${item.starred ? "on" : ""}`}
              onClick={() => void patch({ starred: !item.starred })}
              aria-label={item.starred ? "Unstar" : "Star"}
            >
              {item.starred ? "★" : "☆"}
            </button>
          )}
          <Link to={`/items/${item.id}`} className="icon-btn" aria-label="Edit">
            ✎
          </Link>
        </span>
      </div>
      {error && <span className="error">{error}</span>}
    </li>
  );
}
