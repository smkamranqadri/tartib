import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { ApiError, capture } from "./api";
import { MicIcon } from "./components/Icons";
import { enqueue, flush } from "./offline";

type Recognition = {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  onresult: ((e: { resultIndex: number; results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }> }) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
  start(): void;
  stop(): void;
};

export function speechSupported(): boolean {
  const w = window as unknown as { SpeechRecognition?: unknown; webkitSpeechRecognition?: unknown };
  return !!(w.SpeechRecognition || w.webkitSpeechRecognition);
}

function makeRecognition(): Recognition | null {
  const w = window as unknown as { SpeechRecognition?: new () => Recognition; webkitSpeechRecognition?: new () => Recognition };
  const Ctor = w.SpeechRecognition || w.webkitSpeechRecognition;
  return Ctor ? new Ctor() : null;
}

/** The capture bar in the header: one line, Enter or Add saves, mic dictates into the field. */
export default function Capture({
  onCaptured,
  onQueued,
  autoFocus,
}: {
  onCaptured: (id: number) => void;
  /** It is written down but not sent. Nothing is lost; it goes when the network comes back. */
  onQueued: () => void;
  /** Opened for this box (the ⊕ sheet), so put the cursor in it. */
  autoFocus?: boolean;
}) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [listening, setListening] = useState(false);
  const ref = useRef<HTMLTextAreaElement>(null);
  const rec = useRef<Recognition | null>(null);
  const supported = speechSupported();

  useEffect(() => {
    const focus = () => ref.current?.focus();
    if (autoFocus) focus();
    window.addEventListener("tartib:focus-capture", focus);
    return () => window.removeEventListener("tartib:focus-capture", focus);
  }, []);

  async function submit(e?: FormEvent) {
    e?.preventDefault();
    const value = text.trim();
    if (!value || busy) return;
    setBusy(true);
    setError(null);
    /* Written down before it is sent, so the box can clear at once and nothing depends on the
       send working. Rule 2: a capture never waits. */
    const queued = await enqueue(value);
    setText("");
    try {
      if (!queued) {
        // No storage to queue in. Send it straight out rather than refusing to capture at all.
        const { id } = await capture(value);
        onCaptured(id);
        return;
      }
      const result = await flush();
      if (result.rejected.length) setError(result.rejected[0]);
      else if (result.sent.length) onCaptured(result.sent[result.sent.length - 1]);
      else onQueued();
    } catch (err) {
      /* Only the unqueued path can land here; a queued one is still safely written down. */
      setError(err instanceof ApiError ? err.message : "capture failed");
      setText(value);
    } finally {
      setBusy(false);
      ref.current?.focus();
    }
  }

  function toggleMic() {
    if (listening) {
      rec.current?.stop();
      return;
    }
    const r = makeRecognition();
    if (!r) return;
    r.lang = navigator.language || "en";
    r.interimResults = true;
    r.continuous = false;
    const base = text ? text.replace(/\s+$/, "") + " " : "";
    r.onresult = (e) => {
      let transcript = "";
      for (let i = 0; i < e.results.length; i++) transcript += e.results[i][0].transcript;
      setText(base + transcript);
    };
    r.onend = () => {
      setListening(false);
      ref.current?.focus();
    };
    r.onerror = () => setListening(false);
    rec.current = r;
    setListening(true);
    r.start();
  }

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 6 * 24 + 24) + "px";
  }, [text]);

  function onKey(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void submit();
    }
  }

  return (
    <form className="capture-bar" onSubmit={submit}>
      <textarea
        ref={ref}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={onKey}
        placeholder="Capture anything… Shift+Enter for a new line"
        aria-label="Capture"
        rows={1}
      />
      {supported && (
        <button type="button" className={`icon-btn mic ${listening ? "on" : ""}`} onClick={toggleMic} aria-label={listening ? "Stop listening" : "Dictate"} title="Dictate">
          <MicIcon />
        </button>
      )}
      <button type="submit" className="primary" disabled={busy || !text.trim()}>
        Add
      </button>
      {error && <span className="error">{error}</span>}
    </form>
  );
}
