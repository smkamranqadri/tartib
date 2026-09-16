import { useState } from "react";
import { editItem } from "../api";
import { formatCreated, formatDue, formatRemind } from "../format";
import type { Edit, Item } from "../types";
import ItemEditor from "./ItemEditor";

interface Props {
  item: Item;
  spaces: string[];
  onChange: (item: Item) => void;
  showStage?: boolean;
}

export default function ItemRow({ item, spaces, onChange, showStage }: Props) {
  const [open, setOpen] = useState(false);
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
  const showRaw = isTask && item.title !== null && item.title !== item.raw_text;

  return (
    <li className={`item ${item.status === "done" ? "done" : ""}`}>
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
        <button type="button" className="item-text" onClick={() => setOpen((o) => !o)}>
          {headline}
        </button>
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
      </div>
      <div className="item-meta">
        {showStage && item.stage !== "filed" && <span className={`chip stage-${item.stage}`}>{item.stage}</span>}
        <span className="chip">{item.space}</span>
        {item.due && <span className={`chip ${item.due < today() ? "overdue" : ""}`}>{formatDue(item.due)}</span>}
        {item.remind_at && <span className="chip">⏰ {formatRemind(item.remind_at)}</span>}
        <span className="chip muted">{formatCreated(item.created_at)}</span>
      </div>
      {open && !editing && (
        <div className="item-detail">
          {showRaw && <p className="raw">{item.raw_text}</p>}
          {editable && (
            <button type="button" className="ghost" onClick={() => setEditing(true)}>
              Edit
            </button>
          )}
          {error && <span className="error">{error}</span>}
        </div>
      )}
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

function today(): string {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}
