import { useState } from "react";
import { Link } from "react-router-dom";
import { editItem } from "../api";
import { formatCreated, formatDue, formatRemind, todayLocal } from "../format";
import type { Edit, Item } from "../types";
import ItemEditor from "./ItemEditor";

interface Props {
  item: Item;
  spaces: string[];
  onChange: (item: Item) => void;
  showStage?: boolean;
}

/** One list row. Notes show their raw text; tasks show the title with done and star controls. */
export default function ItemRow({ item, spaces, onChange, showStage }: Props) {
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const isTask = item.shape === "task";
  const editable = item.stage === "filed";

  async function patch(edit: Edit) {
    setError(null);
    try {
      onChange(await editItem(item.id, edit));
    } catch (err) {
      setError(err instanceof Error ? err.message : "failed");
      throw err;
    }
  }

  const headline = isTask && item.title ? item.title : item.raw_text;

  return (
    <li className={`item ${item.status === "done" ? "done" : ""} ${isTask ? "task" : "note"}`}>
      <div className="item-main">
        {isTask && editable ? (
          <input
            type="checkbox"
            className="check"
            checked={item.status === "done"}
            onChange={(e) => void patch({ status: e.target.checked ? "done" : "open" }).catch(() => {})}
            aria-label="Done"
          />
        ) : (
          <span className={`dot ${item.shape}`} aria-hidden />
        )}
        <Link to={`/items/${item.id}`} className="item-text">
          {headline}
        </Link>
        {isTask && editable && (
          <button
            type="button"
            className={`star ${item.starred ? "on" : ""}`}
            onClick={() => void patch({ starred: !item.starred }).catch(() => {})}
            aria-label={item.starred ? "Unstar" : "Star"}
          >
            {item.starred ? "★" : "☆"}
          </button>
        )}
        {editable && (
          <button type="button" className="icon-btn" onClick={() => setEditing((e) => !e)} aria-label="Edit">
            ✎
          </button>
        )}
      </div>
      <div className="item-meta">
        {showStage && item.stage !== "filed" && <span className={`chip stage-${item.stage}`}>{item.stage}</span>}
        {item.space ? <span className="chip">{item.space}</span> : <span className="chip none">no space</span>}
        {item.due && <span className={`chip ${item.due < todayLocal() ? "overdue" : ""}`}>{formatDue(item.due)}</span>}
        {item.remind_at && <span className="chip">⏰ {formatRemind(item.remind_at)}</span>}
        <span className="chip muted">{formatCreated(item.created_at)}</span>
      </div>
      {error && <span className="error">{error}</span>}
      {editing && (
        <ItemEditor
          item={item}
          spaces={spaces}
          submitLabel="Save"
          onSubmit={async (edit) => {
            await patch(edit);
            setEditing(false);
          }}
          onCancel={() => setEditing(false)}
        />
      )}
    </li>
  );
}
