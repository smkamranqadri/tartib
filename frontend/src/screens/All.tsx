import { useEffect, useState, type FormEvent } from "react";
import { ask, getSpaces, listItems } from "../api";
import AnswerView from "../components/AnswerView";
import Card from "../components/Card";
import ItemRow from "../components/ItemRow";
import type { Answer, Item } from "../types";
import { useLoad } from "../useLoad";

export default function All({ version }: { version: number }) {
  const [q, setQ] = useState("");
  const [debounced, setDebounced] = useState("");
  const [space, setSpace] = useState("");
  const [shape, setShape] = useState("");
  const [status, setStatus] = useState("");
  const [more, setMore] = useState<Item[]>([]);
  const [loadingMore, setLoadingMore] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setDebounced(q.trim()), 200);
    return () => clearTimeout(t);
  }, [q]);

  const { data, setData, error, loading } = useLoad(
    () => listItems({ q: debounced, space, shape, status }),
    [debounced, space, shape, status, version],
  );
  useEffect(() => setMore([]), [data]);
  const spaces = useLoad(getSpaces, [version]).data?.spaces ?? [];

  const items = [...(data?.items ?? []), ...more];
  const last = items[items.length - 1];
  const nextBefore = more.length ? (last ? last.id : null) : (data?.next_before ?? null);
  const canLoadMore = !debounced && nextBefore !== null && (more.length === 0 || more.length % 50 === 0);

  async function loadMore() {
    if (nextBefore === null) return;
    setLoadingMore(true);
    try {
      const page = await listItems({ space, shape, status, before: nextBefore });
      setMore((m) => [...m, ...page.items]);
    } finally {
      setLoadingMore(false);
    }
  }

  function update(next: Item) {
    if (data) setData({ ...data, items: data.items.map((i) => (i.id === next.id ? next : i)) });
    setMore((m) => m.map((i) => (i.id === next.id ? next : i)));
  }

  const count = data ? `${items.length}${data.next_before ? "+" : ""}` : "";

  return (
    <div className="screen has-askbar">
      <Card label="Search" aside={count && <span className="muted">{count} items</span>}>
        <div className="filters">
          <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search notes and tasks" aria-label="Search" />
          <select value={space} onChange={(e) => setSpace(e.target.value)} aria-label="Space">
            <option value="">Any space</option>
            {spaces.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <select value={shape} onChange={(e) => setShape(e.target.value)} aria-label="Shape">
            <option value="">Any shape</option>
            <option value="task">Tasks</option>
            <option value="note">Notes</option>
          </select>
          <select value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Status">
            <option value="">Any status</option>
            <option value="open">Open</option>
            <option value="done">Done</option>
          </select>
        </div>
        {error && <p className="error">{error}</p>}
        {loading && !data && <p className="muted">Loading…</p>}
        {data && items.length === 0 && <p className="muted">No items match.</p>}
        <ul className="items">
          {items.map((item) => (
            <ItemRow key={item.id} item={item} spaces={spaces} onChange={update} showStage />
          ))}
        </ul>
        {canLoadMore && (
          <button type="button" className="ghost" onClick={() => void loadMore()} disabled={loadingMore}>
            {loadingMore ? "Loading…" : "Load more"}
          </button>
        )}
      </Card>
      <AskBar spaces={spaces} />
    </div>
  );
}

/** Chat-style bar pinned to the bottom of the viewport. The answer opens above it. */
function AskBar({ spaces }: { spaces: string[] }) {
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
      <div className="askbar-inner">
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
    </div>
  );
}
