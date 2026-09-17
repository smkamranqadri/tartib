import { Link } from "react-router-dom";
import { getToday } from "../api";
import ItemRow from "../components/ItemRow";
import { todayLocal } from "../format";
import type { Item } from "../types";
import { useLoad } from "../useLoad";

/** starred, then overdue, then due today, then reminders */
function rank(item: Item, today: string): number {
  if (item.starred) return 0;
  if (item.due && item.due < today) return 1;
  if (item.due) return 2;
  return 3;
}

export default function Today({ version }: { version: number }) {
  const { data, setData, error, loading } = useLoad(getToday, [version]);
  const today = todayLocal();
  const items = [...(data?.items ?? [])].sort(
    (a, b) => rank(a, today) - rank(b, today) || (a.due ?? "").localeCompare(b.due ?? "") || a.id - b.id,
  );

  function update(next: Item) {
    if (!data) return;
    const keep = next.status === "open";
    setData({
      ...data,
      items: keep ? data.items.map((i) => (i.id === next.id ? next : i)) : data.items.filter((i) => i.id !== next.id),
    });
  }

  return (
    <div className="screen">
      {error && <p className="error">{error}</p>}
      {loading && !data && <p className="muted">Loading…</p>}
      {data && items.length === 0 && (
        <p className="empty muted">
          Nothing due. <Link to="/">Capture something?</Link>
        </p>
      )}
      <ul className="rows">
        {items.map((item) => (
          <ItemRow key={item.id} item={item} onChange={update} />
        ))}
      </ul>
    </div>
  );
}
