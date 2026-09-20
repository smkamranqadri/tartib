import { type FormEvent, useEffect, useRef, useState } from "react";
import { ask, describe } from "../api";
import type { Answer } from "../types";
import AnswerView from "./AnswerView";

/** Ask this question wherever the form is: the bar on a wide screen, the sheet on a phone. */
export function askInBar(question: string, space?: string): void {
  window.dispatchEvent(new CustomEvent("tartib:ask", { detail: { question, space: space ?? "" } }));
}

/** The question, the space it is asked in, and the answer. One of these is mounted at a time. */
export default function AskForm({
  spaces,
  autoFocus,
  initial,
}: {
  spaces: string[];
  autoFocus?: boolean;
  /** A question handed over before this form existed -- the phone's sheet opens holding one. */
  initial?: { question: string; space: string };
}) {
  const [question, setQuestion] = useState(initial?.question ?? "");
  const [space, setSpace] = useState(initial?.space ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Answer | null>(null);
  /** The turn just before this one, sent so a follow-up has something to refer to. Cleared when
   *  the answer is dismissed: the next question is then a fresh one, not a follow-up. */
  const prior = useRef<{ question: string; item_ids: number[] } | null>(null);

  async function run(value: string, inSpace: string) {
    if (!value || busy) return;
    setSpace(inSpace);
    setBusy(true);
    setError(null);
    try {
      const answer = await ask(value, inSpace, prior.current ?? undefined);
      prior.current = { question: value, item_ids: answer.item_ids };
      setResult(answer);
    } catch (err) {
      /* Ask needs the classifier, so it cannot be queued -- it says so rather than failing blank. */
      setError(describe(err));
    } finally {
      setBusy(false);
    }
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    void run(question.trim(), space);
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (initial?.question) void run(initial.question, initial.space);
  }, []); // once, for the question this form opened with

  // A question handed over from a space's search box: fill the form in, and answer it here.
  useEffect(() => {
    const onAsk = (e: Event) => {
      const { question: q, space: s } = (e as CustomEvent<{ question: string; space: string }>).detail;
      setQuestion(q);
      void run(q, s);
    };
    window.addEventListener("tartib:ask", onAsk);
    return () => window.removeEventListener("tartib:ask", onAsk);
  }); // re-bound every render so `run` sees the latest state

  return (
    <>
      {result && (
        <AnswerView
          result={result}
          onClose={() => {
            prior.current = null;
            setResult(null);
          }}
        />
      )}
      {error && <p className="error">{error}</p>}
      <form className="ask" onSubmit={submit}>
        <input
          // biome-ignore lint/a11y/noAutofocus: the sheet opens for this field
          autoFocus={autoFocus}
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
    </>
  );
}
