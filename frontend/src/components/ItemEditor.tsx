import { useState, type FormEvent } from "react";
import { fromLocalInput, toLocalInput } from "../format";
import type { Edit, Item, Shape } from "../types";
import SpaceSelect from "./SpaceSelect";

interface Props {
  item: Item;
  /** Start from the proposal instead of the item's own fields (Needs Attention). */
  fromProposal?: boolean;
  spaces: string[];
  submitLabel: string;
  /** Filing needs a space; the submit button stays disabled until one is picked. */
  requireSpace?: boolean;
  onSubmit: (edit: Edit) => Promise<void>;
  onCancel: () => void;
  hideCancel?: boolean;
  inline?: boolean;
}

export default function ItemEditor({
  item,
  fromProposal,
  spaces,
  submitLabel,
  requireSpace,
  onSubmit,
  onCancel,
  hideCancel,
  inline,
}: Props) {
  const base = fromProposal && item.proposal && item.proposal.shape !== "question" ? item.proposal : item;
  const [shape, setShape] = useState<Shape>(base.shape === "question" ? "note" : base.shape);
  const [space, setSpace] = useState<string | null>(base.space ?? item.space);
  const [title, setTitle] = useState(base.title ?? "");
  const [due, setDue] = useState(base.due ?? "");
  const [remind, setRemind] = useState(toLocalInput(base.remind_at));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const missingSpace = !!requireSpace && !space;

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (missingSpace) return;
    setBusy(true);
    setError(null);
    setSaved(false);
    const edit: Edit = { shape, space };
    if (shape === "task") {
      edit.title = title.trim() || null;
      edit.due = due || null;
      edit.remind_at = fromLocalInput(remind);
    }
    try {
      await onSubmit(edit);
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className={`editor ${inline ? "inline" : ""}`} onSubmit={submit}>
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
          <SpaceSelect value={space} spaces={spaces} onChange={setSpace} />
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
        {saved && !error && <span className="muted">Saved</span>}
        {missingSpace && !error && <span className="muted">Pick a space to file</span>}
        {!hideCancel && (
          <button type="button" className="ghost" onClick={onCancel} disabled={busy}>
            Cancel
          </button>
        )}
        <button type="submit" disabled={busy || missingSpace}>
          {submitLabel}
        </button>
      </div>
    </form>
  );
}
