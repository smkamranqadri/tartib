import { getSpaces, getToday } from "../api";
import ItemRow from "../components/ItemRow";
import type { Item } from "../types";
import { useLoad } from "../useLoad";

export default function Today({ version }: { version: number }) {
  const { data, setData, error, loading } = useLoad(getToday, [version]);
  const spaces = useLoad(getSpaces, [version]).data?.spaces ?? [];

  function update(next: Item) {
    if (!data) return;
    const keep = next.status === "open";
    setData({
      ...data,
      items: keep ? data.items.map((i) => (i.id === next.id ? next : i)) : data.items.filter((i) => i.id !== next.id),
    });
  }

  return (
    <section className="screen">
      <h2>Today</h2>
      {error && <p className="error">{error}</p>}
      {loading && !data && <p className="muted">Loading…</p>}
      {data && data.items.length === 0 && <p className="muted">Nothing due, starred, or waiting on a reminder.</p>}
      <ul className="items">
        {data?.items.map((item) => (
          <ItemRow key={item.id} item={item} spaces={spaces} onChange={update} />
        ))}
      </ul>
    </section>
  );
}
