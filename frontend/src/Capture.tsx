import { useState, type FormEvent, type KeyboardEvent } from "react";
import { capture } from "./api";

export default function Capture({ onCaptured }: { onCaptured?: () => void }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e?: FormEvent) {
    e?.preventDefault();
    const value = text.trim();
    if (!value || busy) return;
    setBusy(true);
    setError(null);
    try {
      await capture(value);
      setText("");
      onCaptured?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "capture failed");
    } finally {
      setBusy(false);
    }
  }

  function onKey(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void submit();
    }
  }

  return (
    <form className="capture" onSubmit={submit}>
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={onKey}
        placeholder="Capture anything. Enter to save, Shift+Enter for a new line."
        rows={2}
        autoFocus
        aria-label="Capture"
      />
      <div className="capture-row">
        {error ? <span className="error">{error}</span> : <span />}
        <button type="submit" disabled={busy || !text.trim()}>
          {busy ? "Saving…" : "Save"}
        </button>
      </div>
    </form>
  );
}
