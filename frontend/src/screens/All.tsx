import { useEffect, useState } from "react";
import { getSpaces, listItems } from "../api";
import ItemRow from "../components/ItemRow";
import type { Item } from "../types";
import { useLoad } from "../useLoad";

export default function All({ version }: { version: number }) {
  const [q, setQ] = useState("");
  const [debounced, setDebounced] = useState("");
  const [space, setSpace] = useState("");
  const [shape, setShape] = useState("");
  const [more, setMore] = useState<Item[]>([]);
  const [loadingMore, setLoadingMore] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setDebounced(q.trim()), 200);
    return () => clearTimeout(t);
  }, [q]);

  const { data, setData, error, loading } = useLoad(
    () => listItems({ q: debounced, space, shape }),
    [debounced, space, shape, version],
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
      const page = await listItems({ space, shape, before: nextBefore });
      setMore((m) => [...m, ...page.items]);
    } finally {
      setLoadingMore(false);
    }
  }

  function update(next: Item) {
    if (data) setData({ ...data, items: data.items.map((i) => (i.id === next.id ? next : i)) });
    setMore((m) => m.map((i) => (i.id === next.id ? next : i)));
  }

  return (
    <section className="screen">
      <h2>All</h2>
      <div className="filters">
        <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search" aria-label="Search" />
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
    </section>
  );
}
