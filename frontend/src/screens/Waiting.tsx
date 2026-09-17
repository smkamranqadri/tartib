import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { getAttention, getSpaces } from "../api";
import ApprovalCard from "../components/ApprovalCard";
import Card from "../components/Card";
import { AlertIcon } from "../components/Icons";
import PageHead from "../components/PageHead";
import type { Item } from "../types";
import { useLoad } from "../useLoad";

/** Every waiting item as a decision card. Enter takes the first. */
export default function Waiting({ version, onDecided }: { version: number; onDecided: () => void }) {
  const { data, setData, error, loading } = useLoad(getAttention, [version]);
  const spaces = useLoad(getSpaces, [version]).data?.spaces ?? [];
  const [deferred, setDeferred] = useState<number[]>([]);
  const items = useMemo(() => {
    const all = [...(data?.items ?? [])].sort((a, b) => b.id - a.id);
    return [...all.filter((i) => !deferred.includes(i.id)), ...all.filter((i) => deferred.includes(i.id))];
  }, [data, deferred]);

  function replace(id: number, next: Item | null) {
    if (!data) return;
    setData({ ...data, items: next ? data.items.map((i) => (i.id === id ? next : i)) : data.items.filter((i) => i.id !== id) });
    onDecided();
  }

  return (
    <div className="screen">
      <p className="crumbs">
        <Link to="/attention">← Inbox</Link>
      </p>
      <PageHead eyebrow="Inbox" title="Everything waiting" subtitle={items.length ? `${items.length} to decide` : "All caught up."} />
      <Card icon={<AlertIcon />} label="Needs attention" aside={items.length}>
        {error && <p className="error">{error}</p>}
        {loading && !data && <p className="muted">Loading…</p>}
        {data && items.length === 0 && <p className="empty muted">All caught up.</p>}
        <div className="cards">
          {items.map((item, i) => (
            <ApprovalCard key={item.id} item={item} spaces={spaces} hotkey={i === 0} onApproved={(id) => replace(id, null)} onNotNow={(id) => setDeferred((d) => [...d.filter((x) => x !== id), id])} onRejected={(next) => replace(next.id, next)} />
          ))}
        </div>
      </Card>
    </div>
  );
}
