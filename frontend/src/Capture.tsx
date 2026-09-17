import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { capture } from "./api";

/** The one capture box. Lives on Home only. */
export default function Capture({ onCaptured }: { onCaptured: (id: number) => void }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    ref.current?.focus();
    const focus = () => ref.current?.focus();
    window.addEventListener("tartib:focus-capture", focus);
    return () => window.removeEventListener("tartib:focus-capture", focus);
  }, []);

  async function submit(e?: FormEvent) {
    e?.preventDefault();
    const value = text.trim();
    if (!value || busy) return;
    setBusy(true);
    setError(null);
    try {
      const { id } = await capture(value);
      setText("");
      onCaptured(id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "capture failed");
    } finally {
      setBusy(false);
      ref.current?.focus();
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
        ref={ref}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={onKey}
        placeholder="What's on your mind?"
        rows={3}
        aria-label="Capture"
      />
      {error && <p className="error">{error}</p>}
    </form>
  );
}
