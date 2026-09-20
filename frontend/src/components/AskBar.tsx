import { type FormEvent, useEffect, useRef, useState } from "react";
import { ask } from "../api";
import type { Answer } from "../types";
import AnswerView from "./AnswerView";

/** Ask this question in the bar, from anywhere: the space search box hands its questions over
 *  rather than answering where they were typed. */
export function askInBar(question: string, space?: string): void {
  window.dispatchEvent(new CustomEvent("tartib:ask", { detail: { question, space: space ?? "" } }));
}

/** Chat-style bar pinned to the bottom of every screen, as wide as the app column. */
export default function AskBar({ spaces }: { spaces: string[] }) {
  const [question, setQuestion] = useState("");
  const [space, setSpace] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Answer | null>(null);

  async function run(value: string, inSpace: string) {
    if (!value || busy) return;
    setSpace(inSpace);
    setBusy(true);
    setError(null);
    try {
      setResult(await ask(value, inSpace));
    } catch (err) {
      setError(err instanceof Error ? err.message : "ask failed");
    } finally {
      setBusy(false);
    }
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    void run(question.trim(), space);
  }

  // A question handed over from a space's search box: fill the bar in, and answer it there.
  useEffect(() => {
    const onAsk = (e: Event) => {
      const { question: q, space: s } = (e as CustomEvent<{ question: string; space: string }>).detail;
      setQuestion(q);
      void run(q, s);
    };
    window.addEventListener("tartib:ask", onAsk);
    return () => window.removeEventListener("tartib:ask", onAsk);
  }); // re-bound every render so `run` sees the latest state

  // Publish the bar's height, so what sits above it (the session card) clears it exactly -- it
  // grows with an answer, and wraps to two rows on a phone.
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const root = document.documentElement;
    const obs = new ResizeObserver(() => root.style.setProperty("--askbar-h", `${el.offsetHeight}px`));
    obs.observe(el);
    return () => {
      obs.disconnect();
      root.style.removeProperty("--askbar-h");
    };
  }, []);

  return (
    <div className="askbar" ref={ref}>
      {result && <AnswerView result={result} onClose={() => setResult(null)} />}
      {error && <p className="error">{error}</p>}
      <form className="ask" onSubmit={submit}>
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask your notes: what did I decide about…"
          aria-label="Question"
        />
        <select value={space} onChange={(e) => setSpace(e.target.value)} aria-label="Ask in space">
          <option value="">All spaces</option>
          {spaces.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <button type="submit" disabled={busy || !question.trim()}>
          {busy ? "Thinking…" : "Ask"}
        </button>
      </form>
    </div>
  );
}
