import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { ask } from "../api";
import type { Answer } from "../types";
import AnswerView from "./AnswerView";

/** One field that searches as you type and asks on demand (button, trailing "?", Cmd/Ctrl+Enter). */
export default function SearchAsk({
  value,
  onChange,
  space,
  placeholder,
  large,
}: {
  value: string;
  onChange: (q: string) => void;
  space?: string;
  placeholder: string;
  large?: boolean;
}) {
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [asking, setAsking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const ref = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const focus = () => ref.current?.focus();
    window.addEventListener("tartib:focus-search", focus);
    return () => window.removeEventListener("tartib:focus-search", focus);
  }, []);

  async function runAsk() {
    const question = value.trim();
    if (!question || asking) return;
    setAsking(true);
    setError(null);
    try {
      setAnswer(await ask(question, space));
    } catch (err) {
      setError(err instanceof Error ? err.message : "ask failed");
    } finally {
      setAsking(false);
    }
  }

  function onKey(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey || value.trim().endsWith("?"))) {
      e.preventDefault();
      void runAsk();
    }
  }

  function change(q: string) {
    onChange(q);
    if (answer || error) {
      setAnswer(null);
      setError(null);
    }
  }

  return (
    <>
      <div className={`search-row ${large ? "large" : ""}`}>
        <input
          ref={ref}
          type="search"
          value={value}
          onChange={(e) => change(e.target.value)}
          onKeyDown={onKey}
          placeholder={placeholder}
          aria-label="Search"
        />
        {value.trim() && (
          <button type="button" className="primary" onClick={() => void runAsk()} disabled={asking} aria-label="Ask">
            {asking ? "Thinking…" : "Ask"}
          </button>
        )}
      </div>
      {error && <p className="error">{error}</p>}
      {answer && <AnswerView result={answer} onClose={() => setAnswer(null)} />}
    </>
  );
}
