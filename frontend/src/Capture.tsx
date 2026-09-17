import { useEffect, useRef, useState, type FormEvent } from "react";
import { capture } from "./api";
import { MicIcon } from "./components/Icons";

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
export default function Capture({ onCaptured }: { onCaptured: (id: number) => void }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [listening, setListening] = useState(false);
  const ref = useRef<HTMLInputElement>(null);
  const rec = useRef<Recognition | null>(null);
  const supported = speechSupported();

  useEffect(() => {
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

  return (
    <form className="capture-bar" onSubmit={submit}>
      <input
        ref={ref}
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Capture anything…"
        aria-label="Capture"
        autoComplete="off"
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
