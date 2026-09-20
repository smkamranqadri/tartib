import { type FormEvent, useState } from "react";
import { addThought, getThoughts } from "../api";
import { formatRelative } from "../format";
import { useLoad } from "../useLoad";
import Card from "./Card";
import { NoteIcon } from "./Icons";
import Markdown from "./Markdown";
import { Empty, ErrorLine, Loading } from "./Status";

/** The item's thought log: your own thinking, kept apart from its text. Append-only -- each
 *  entry stays as written, oldest first, and the newest goes at the bottom. */
export default function Thoughts({ itemId, onAdded }: { itemId: number; onAdded?: () => void }) {
  const log = useLoad(() => getThoughts(itemId), [itemId]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
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
      onAdded?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card icon={<NoteIcon />} label="Thoughts" aside={<span className="muted">{log.data ? entries.length : "…"}</span>}>
      {log.error && <ErrorLine>{log.error}</ErrorLine>}
      {!log.data && log.loading && <Loading rows={2} />}
      {log.data && entries.length === 0 && <Empty>Nothing yet. Thinking about it goes here.</Empty>}
      {entries.length > 0 && (
        <ol className="thoughts">
          {entries.map((t) => (
            <li key={t.id}>
              <span className="muted small">{formatRelative(t.created_at)}</span>
              <Markdown text={t.body} />
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
          placeholder="Add a thought. It stays as written."
          aria-label="New thought"
        />
        <button type="submit" className="primary" disabled={busy || !text.trim()}>
          {busy ? "Adding…" : "Add"}
        </button>
      </form>
      {error && <ErrorLine>{error}</ErrorLine>}
    </Card>
  );
}
