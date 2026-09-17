import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { editItem } from "../api";
import { formatDue, formatRelative, formatRemind, todayLocal } from "../format";
import type { Edit, Item } from "../types";

interface Props {
  item: Item;
  onChange: (item: Item) => void;
}

/** One minimal row: checkbox (tasks), title or first line, at most one chip.
 *  Hover or long-press reveals star, edit, and the relative time. Notes expand on tap. */
export default function ItemRow({ item, onChange }: Props) {
  const [revealed, setRevealed] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const holdTimer = useRef<number | null>(null);
  const isTask = item.shape === "task";
  const editable = item.stage === "filed";
  const overdue = isTask && item.status === "open" && !!item.due && item.due < todayLocal();

  async function patch(edit: Edit) {
    setError(null);
    try {
      onChange(await editItem(item.id, edit));
    } catch (err) {
      setError(err instanceof Error ? err.message : "failed");
    }
  }

  const chip = overdue
    ? { text: formatDue(item.due!), cls: "overdue" }
    : item.remind_at
      ? { text: formatRemind(item.remind_at), cls: "" }
      : null;

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

  return (
    <li
      className={`row ${item.status === "done" ? "done" : ""} ${overdue ? "overdue" : ""} ${revealed ? "revealed" : ""} ${item.stage !== "filed" ? "waiting" : ""}`}
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
          <span className={`dot ${item.shape}`} aria-hidden />
        )}
        {isTask ? (
          <Link to={`/items/${item.id}`} className="row-text">
            {headline}
          </Link>
        ) : (
          <button type="button" className={`row-text ${hasMore ? "expandable" : ""}`} onClick={() => setExpanded((e) => !e)}>
            {expanded ? item.raw_text : headline}
          </button>
        )}
        {chip && <span className={`chip ${chip.cls}`}>{chip.text}</span>}
        <span className="row-actions">
          <span className="when muted" title={new Date(item.created_at).toLocaleString()}>
            {formatRelative(item.created_at)}
          </span>
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
      {expanded && !isTask && (
        <div className="row-more">
          <Link to={`/items/${item.id}`} className="muted small">
            open
          </Link>
        </div>
      )}
      {error && <span className="error">{error}</span>}
    </li>
  );
}
