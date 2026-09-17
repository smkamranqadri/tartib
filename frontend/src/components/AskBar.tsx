import { useState, type FormEvent } from "react";
import { ask } from "../api";
import type { Answer } from "../types";
import AnswerView from "./AnswerView";

/** Chat-style bar pinned to the bottom of every screen, as wide as the app column. */
export default function AskBar({ spaces }: { spaces: string[] }) {
  const [question, setQuestion] = useState("");
  const [space, setSpace] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Answer | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    const value = question.trim();
    if (!value || busy) return;
    setBusy(true);
    setError(null);
    try {
      setResult(await ask(value, space));
    } catch (err) {
      setError(err instanceof Error ? err.message : "ask failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="askbar">
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
