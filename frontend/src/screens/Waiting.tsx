import { useMemo, useState } from "react";
import { getAttention, getSpaces } from "../api";
import ApprovalCard from "../components/ApprovalCard";
import BackLink from "../components/BackLink";
import Card from "../components/Card";
import { AlertIcon } from "../components/Icons";
import PageHead from "../components/PageHead";
import { Empty, ErrorLine, Loading } from "../components/Status";
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
      <BackLink fallback="/inbox" />
      <PageHead eyebrow="Inbox" title="Everything waiting" subtitle="Every item that needs a decision." />
      <Card icon={<AlertIcon />} label="Needs attention" aside={items.length === 0 ? "All caught up" : `${items.length} ${items.length === 1 ? "thing" : "things"} to decide`}>
        {error && <ErrorLine>{error}</ErrorLine>}
        {loading && !data && <Loading />}
        {data && items.length === 0 && <Empty>All caught up.</Empty>}
        <div className="cards">
          {items.map((item, i) => (
            <ApprovalCard key={item.id} item={item} spaces={spaces} hotkey={i === 0} onApproved={(id) => replace(id, null)} onNotNow={(id) => setDeferred((d) => [...d.filter((x) => x !== id), id])} onRejected={(next) => replace(next.id, next)} />
          ))}
        </div>
      </Card>
    </div>
  );
}
