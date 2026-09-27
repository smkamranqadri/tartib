import { type FormEvent, useState } from "react";
import { addThought, ApiError, deleteThought, editThought, getThoughts } from "../api";
import { enqueueThought } from "../offline";
import { thoughtsFor } from "../pending";
import { usePending } from "../usePending";
import { formatRelative } from "../format";
import { useLoad } from "../useLoad";
import type { Thought } from "../types";
import Card from "./Card";
import { NoteIcon } from "./Icons";
import Markdown from "./Markdown";
import { ConfirmModal } from "./Modal";
import { Empty, ErrorLine, Loading } from "./Status";

/** The item's thought log: your own thinking, kept apart from its text, oldest first, the newest
 *  at the bottom. An entry can be edited, which marks it, or deleted (slice 37); both need the
 *  network, where adding one queues offline. */
export default function Thoughts({ itemId, onChanged }: { itemId: number; onChanged?: () => void }) {
  const log = useLoad(() => getThoughts(itemId), [itemId]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<{ id: number; body: string } | null>(null);
  const [removing, setRemoving] = useState<Thought | null>(null);
  const pending = usePending();
  /* Queued thoughts sit at the end of the log, where they will be once they land. The log is
     oldest-first and a new entry always lands last, so a waiting one belongs in exactly one place
     (slice 25). */
  const queued = thoughtsFor(itemId, pending);
  const entries = log.data?.thoughts ?? [];

  async function submit(e: FormEvent) {
    e.preventDefault();
    const body = text.trim();
    if (!body || busy) return;
    setBusy(true);
    setError(null);
    try {
      const r = await addThought(itemId, body);
      log.setData({ thoughts: [...entries, r.thought] });
      setText("");
      onChanged?.();
    } catch (err) {
      if (!(err instanceof ApiError) && (await enqueueThought(itemId, body))) {
        setText("");
      } else {
        setError(err instanceof Error ? err.message : "failed");
      }
    } finally {
      setBusy(false);
    }
  }

  function failed(err: unknown) {
    setError(err instanceof ApiError ? err.message : "Needs a connection. Try again when you are online.");
  }

  async function saveEdit(e: FormEvent) {
    e.preventDefault();
    if (!editing || busy) return;
    const body = editing.body.trim();
    if (!body) return;
    setBusy(true);
    setError(null);
    try {
      const r = await editThought(itemId, editing.id, body);
      log.setData({ thoughts: entries.map((t) => (t.id === r.thought.id ? r.thought : t)) });
      setEditing(null);
    } catch (err) {
      failed(err);
    } finally {
      setBusy(false);
    }
  }

  async function confirmRemove() {
    if (!removing || busy) return;
    setBusy(true);
    setError(null);
    try {
      await deleteThought(itemId, removing.id);
      log.setData({ thoughts: entries.filter((t) => t.id !== removing.id) });
      setRemoving(null);
      onChanged?.();
    } catch (err) {
      setRemoving(null);
      failed(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card icon={<NoteIcon />} label="Thoughts" aside={<span className="muted">{log.data ? entries.length + queued.length : "…"}</span>}>
      {log.error && <ErrorLine>{log.error}</ErrorLine>}
      {!log.data && log.loading && <Loading rows={2} />}
      {log.data && entries.length === 0 && queued.length === 0 && <Empty>Nothing yet. Thinking about it goes here.</Empty>}
      {entries.length > 0 && (
        <ol className="thoughts">
          {entries.map((t) => (
            <li key={t.id}>
              <div className="thought-head">
                <span className="muted small">
                  {formatRelative(t.created_at)}
                  {t.edited_at && <> · edited</>}
                </span>
                {editing?.id !== t.id && (
                  <span className="thought-actions small">
                    <button type="button" className="link-btn" onClick={() => setEditing({ id: t.id, body: t.body })}>
                      Edit
                    </button>
                    <button type="button" className="link-btn" onClick={() => setRemoving(t)}>
                      Delete
                    </button>
                  </span>
                )}
              </div>
              {editing?.id === t.id ? (
                <form className="thought-edit" onSubmit={saveEdit}>
                  <textarea
                    rows={3}
                    value={editing.body}
                    autoFocus
                    onChange={(e) => setEditing({ id: t.id, body: e.target.value })}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) void saveEdit(e);
                      if (e.key === "Escape") setEditing(null);
                    }}
                    aria-label="Edit thought"
                  />
                  <div className="thought-edit-actions">
                    <button type="button" className="ghost" onClick={() => setEditing(null)}>
                      Cancel
                    </button>
                    <button type="submit" className="primary" disabled={busy || !editing.body.trim()}>
                      {busy ? "Saving…" : "Save"}
                    </button>
                  </div>
                </form>
              ) : (
                <Markdown text={t.body} />
              )}
            </li>
          ))}
        </ol>
      )}
      {queued.length > 0 && (
        <ol className="thoughts">
          {queued.map((q) => (
            <li key={q.id}>
              <span className="muted small">
                {formatRelative(q.created_at)} · <span className="pending-mark">waiting to send</span>
              </span>
              <Markdown text={q.body ?? ""} />
            </li>
          ))}
        </ol>
      )}
      <form className="thought-add" onSubmit={submit}>
        <textarea
          rows={2}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) void submit(e);
          }}
          placeholder="Add a thought."
          aria-label="New thought"
        />
        <button type="submit" className="primary" disabled={busy || !text.trim()}>
          {busy ? "Adding…" : "Add"}
        </button>
      </form>
      {error && <ErrorLine>{error}</ErrorLine>}
      <ConfirmModal
        open={!!removing}
        question="Delete this thought?"
        detail="It cannot be brought back."
        confirmLabel="Delete"
        busy={busy}
        onConfirm={() => void confirmRemove()}
        onCancel={() => setRemoving(null)}
      />
    </Card>
  );
}
