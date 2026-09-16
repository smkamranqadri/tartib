import { useState, type FormEvent } from "react";
import { fromLocalInput, toLocalInput } from "../format";
import type { Edit, Item, Shape } from "../types";

interface Props {
  item: Item;
  /** Start from the proposal instead of the item's own fields (Needs Attention). */
  fromProposal?: boolean;
  spaces: string[];
  submitLabel: string;
  onSubmit: (edit: Edit) => Promise<void>;
  onCancel: () => void;
}

export default function ItemEditor({ item, fromProposal, spaces, submitLabel, onSubmit, onCancel }: Props) {
  const base = fromProposal && item.proposal ? item.proposal : item;
  const [shape, setShape] = useState<Shape>(base.shape);
  const [space, setSpace] = useState(base.space);
  const [title, setTitle] = useState(base.title ?? "");
  const [due, setDue] = useState(base.due ?? "");
  const [remind, setRemind] = useState(toLocalInput(base.remind_at));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const edit: Edit = { shape, space: space.trim() || "inbox" };
    if (shape === "task") {
      edit.title = title.trim() || null;
      edit.due = due || null;
      edit.remind_at = fromLocalInput(remind);
    }
    try {
      await onSubmit(edit);
    } catch (err) {
      setError(err instanceof Error ? err.message : "failed");
      setBusy(false);
    }
  }

  return (
    <form className="editor" onSubmit={submit}>
      <div className="editor-row">
        <label>
          <span>Shape</span>
          <select value={shape} onChange={(e) => setShape(e.target.value as Shape)}>
            <option value="task">Task</option>
            <option value="note">Note</option>
          </select>
        </label>
        <label>
          <span>Space</span>
          <input list="spaces" value={space} onChange={(e) => setSpace(e.target.value)} placeholder="inbox" />
          <datalist id="spaces">
            {spaces.map((s) => (
              <option key={s} value={s} />
            ))}
          </datalist>
        </label>
      </div>
      {shape === "task" && (
        <>
          <label>
            <span>Title</span>
            <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Short imperative title" />
          </label>
          <div className="editor-row">
            <label>
              <span>Due</span>
              <input type="date" value={due} onChange={(e) => setDue(e.target.value)} />
            </label>
            <label>
              <span>Remind at</span>
              <input type="datetime-local" value={remind} onChange={(e) => setRemind(e.target.value)} />
            </label>
          </div>
        </>
      )}
      <div className="editor-actions">
        {error && <span className="error">{error}</span>}
        <button type="button" className="ghost" onClick={onCancel} disabled={busy}>
          Cancel
        </button>
        <button type="submit" disabled={busy}>
          {submitLabel}
        </button>
      </div>
    </form>
  );
}
