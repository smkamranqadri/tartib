import { useEffect, useRef, type KeyboardEvent } from "react";
import { askInBar } from "./AskBar";

/** One field that searches as you type and hands a question to the ask bar on demand (button,
 *  trailing "?", Cmd/Ctrl+Enter). The answer belongs in one place, at the foot of the app, not
 *  wherever the question happened to be typed. */
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
  const ref = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const focus = () => ref.current?.focus();
    window.addEventListener("tartib:focus-search", focus);
    return () => window.removeEventListener("tartib:focus-search", focus);
  }, []);

  function handOff() {
    const question = value.trim();
    if (!question) return;
    askInBar(question, space);
    onChange(""); // the question is the bar's now; the list comes back
  }

  function onKey(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey || value.trim().endsWith("?"))) {
      e.preventDefault();
      handOff();
    }
  }

  return (
    <>
      <div className={`search-row ${large ? "large" : ""}`}>
        <input
          ref={ref}
          type="search"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={onKey}
          placeholder={placeholder}
          aria-label="Search"
        />
        {value.trim() && (
          <button type="button" className="primary" onClick={handOff} aria-label="Ask">
            Ask
          </button>
        )}
      </div>
    </>
  );
}
