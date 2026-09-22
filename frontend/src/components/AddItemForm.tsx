import { type FormEvent, useState } from "react";
import { addItem } from "../api";
import type { Item } from "../types";
import { ErrorLine } from "./Status";

/** File a task or note straight into a space: no classifier, the shape and space are known. */
export default function AddItemForm({ space, onAdded, onCancel }: { space: string; onAdded: (item: Item) => void; onCancel: () => void }) {
  const [shape, setShape] = useState<"task" | "note">("task");
  const [text, setText] = useState("");
  const [due, setDue] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!text.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      onAdded(await addItem({ shape, space, text: text.trim(), due: shape === "task" && due ? due : undefined }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="card add-item" onSubmit={submit}>
      <div className="add-item-top">
        <div className="pills" role="group" aria-label="Shape">
          {(["task", "note"] as const).map((s) => (
            <button key={s} type="button" className={shape === s ? "active" : ""} aria-pressed={shape === s} onClick={() => setShape(s)}>
              {s === "task" ? "Task" : "Note"}
            </button>
          ))}
        </div>
        <span className="muted small">into {space}</span>
      </div>
      <textarea
        autoFocus
        rows={3}
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={shape === "task" ? "What needs doing" : "What to keep"}
        aria-label="Text"
        onKeyDown={(e) => {
          if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) void submit(e);
          if (e.key === "Escape") onCancel();
        }}
      />
      <div className="add-item-bottom">
        {shape === "task" ? (
          <label className="muted small">
            Due <input type="date" value={due} onChange={(e) => setDue(e.target.value)} aria-label="Due" />
          </label>
        ) : (
          <span />
        )}
        <span className="toggles">
          <button type="button" className="ghost" onClick={onCancel} disabled={busy}>
            Cancel
          </button>
          <button type="submit" className="primary" disabled={busy || !text.trim()}>
            {busy ? "Adding…" : "Add"}
          </button>
        </span>
      </div>
      {error && <ErrorLine>{error}</ErrorLine>}
    </form>
  );
}
