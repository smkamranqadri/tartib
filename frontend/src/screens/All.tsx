import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { ask, getSpaces, listItems } from "../api";
import AnswerView from "../components/AnswerView";
import ItemRow from "../components/ItemRow";
import type { Answer, Item } from "../types";
import { useLoad } from "../useLoad";

export default function All({ version }: { version: number }) {
  const [q, setQ] = useState("");
  const [debounced, setDebounced] = useState("");
  const [space, setSpace] = useState("");
  const [showDone, setShowDone] = useState(false);
  const [more, setMore] = useState<Item[]>([]);
  const [loadingMore, setLoadingMore] = useState(false);
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [asking, setAsking] = useState(false);
  const [askError, setAskError] = useState<string | null>(null);
  const searchRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const t = setTimeout(() => setDebounced(q.trim()), 200);
    return () => clearTimeout(t);
  }, [q]);

  useEffect(() => {
    const focus = () => searchRef.current?.focus();
    window.addEventListener("tartib:focus-search", focus);
    return () => window.removeEventListener("tartib:focus-search", focus);
  }, []);

  const { data, setData, error, loading } = useLoad(
    () => listItems({ q: debounced, space }),
    [debounced, space, version],
  );
  useEffect(() => setMore([]), [data]);
  const spaces = useLoad(getSpaces, [version]).data?.spaces ?? [];

  const all = [...(data?.items ?? []), ...more];
  const items = showDone ? all : all.filter((i) => !(i.shape === "task" && i.status === "done"));
  const last = all[all.length - 1];
  const nextBefore = more.length ? (last ? last.id : null) : (data?.next_before ?? null);
  const canLoadMore = !debounced && nextBefore !== null && (more.length === 0 || more.length % 50 === 0);

  async function loadMore() {
    if (nextBefore === null) return;
    setLoadingMore(true);
    try {
      const page = await listItems({ space, before: nextBefore });
      setMore((m) => [...m, ...page.items]);
    } finally {
      setLoadingMore(false);
    }
  }

  function update(next: Item) {
    if (data) setData({ ...data, items: data.items.map((i) => (i.id === next.id ? next : i)) });
    setMore((m) => m.map((i) => (i.id === next.id ? next : i)));
  }

  async function runAsk() {
    const question = q.trim();
    if (!question || asking) return;
    setAsking(true);
    setAskError(null);
    try {
      setAnswer(await ask(question, space));
    } catch (err) {
      setAskError(err instanceof Error ? err.message : "ask failed");
    } finally {
      setAsking(false);
    }
  }

  function onKey(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey || q.trim().endsWith("?"))) {
      e.preventDefault();
      void runAsk();
    }
  }

  function onChange(value: string) {
    setQ(value);
    if (answer || askError) {
      setAnswer(null);
      setAskError(null);
    }
  }

  return (
    <div className="screen">
      <div className="filters">
        <input
          ref={searchRef}
          type="search"
          value={q}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={onKey}
          placeholder="Search or ask your notes"
          aria-label="Search"
        />
        {q.trim() && (
          <button type="button" className="ask-btn" onClick={() => void runAsk()} disabled={asking} aria-label="Ask">
            {asking ? "Thinking…" : "Ask"}
          </button>
        )}
        <select value={space} onChange={(e) => setSpace(e.target.value)} aria-label="Space">
          <option value="">Any space</option>
          {spaces.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <label className="toggle">
          <input type="checkbox" checked={showDone} onChange={(e) => setShowDone(e.target.checked)} /> Show done
        </label>
      </div>
      {askError && <p className="error">{askError}</p>}
      {answer && <AnswerView result={answer} onClose={() => setAnswer(null)} />}
      {error && <p className="error">{error}</p>}
      {loading && !data && <p className="muted">Loading…</p>}
      {data && items.length === 0 && <p className="empty muted">No items match.</p>}
      <ul className="rows">
        {items.map((item) => (
          <ItemRow key={item.id} item={item} onChange={update} />
        ))}
      </ul>
      {canLoadMore && (
        <button type="button" className="ghost" onClick={() => void loadMore()} disabled={loadingMore}>
          {loadingMore ? "Loading…" : "Load more"}
        </button>
      )}
    </div>
  );
}
