import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { getAttention, getToday } from "../api";
import ApprovalCard from "../components/ApprovalCard";
import Card from "../components/Card";
import { AlertIcon, CheckSquareIcon, ClockIcon } from "../components/Icons";
import ItemRow from "../components/ItemRow";
import PageHead from "../components/PageHead";
import RecentList from "../components/RecentList";
import { Empty, ErrorLine, Loading } from "../components/Status";
import type { Item } from "../types";
import { useLoad } from "../useLoad";
import { useSpaces } from "../useSpaces";

const SHOW = 3;

/** Inbox: the newest waiting items as decision cards (Enter takes the first), stale tasks, recent. */
export default function Inbox({ version, onDecided }: { version: number; onDecided: () => void }) {
  const { data, setData, error, loading } = useLoad(getAttention, [version]);
  const spaces = useSpaces(version);
  const today = useLoad(getToday, [version]).data;
  // Needs Attention is right above, so Recent leaves out what is already waiting there. Today's
  // list is shared with Home, which has no Needs Attention, so the filter lives here.
  const recent = useMemo(
    () =>
      (today?.recent ?? []).flatMap((cap) => {
        const items = cap.items.filter((i) => i.stage !== "attention");
        return cap.items.length > 0 && items.length === 0 ? [] : [{ ...cap, items }];
      }),
    [today],
  );
  const [order, setOrder] = useState<number[]>([]);

  const items = useMemo(() => data?.items ?? [], [data]);
  const stale = data?.stale ?? [];
  useEffect(() => {
    setOrder((prev) => {
      const ids = [...items].sort((a, b) => b.id - a.id).map((i) => i.id); // newest first
      const kept = prev.filter((id) => ids.includes(id));
      return [...kept, ...ids.filter((id) => !kept.includes(id))];
    });
  }, [items]);

  function replace(id: number, next: Item | null) {
    if (!data) return;
    setData({ ...data, items: next ? items.map((i) => (i.id === id ? next : i)) : items.filter((i) => i.id !== id) });
    if (!next) setOrder((o) => o.filter((x) => x !== id));
    onDecided();
  }
  const notNow = (id: number) => setOrder((o) => [...o.filter((x) => x !== id), id]);

  function updateStale(next: Item) {
    if (!data) return;
    setData({ ...data, stale: data.stale.filter((i) => i.id !== next.id || next.status === "open").map((i) => (i.id === next.id ? next : i)) });
  }

  if (error) return <ErrorLine>{error}</ErrorLine>;
  if (loading && !data) return <Loading />;

  const shown = order.slice(0, SHOW).map((id) => items.find((i) => i.id === id)).filter((i): i is Item => !!i);

  return (
    <div className="screen">
      <PageHead title="Inbox" subtitle="Approve what the classifier proposed, or file it yourself." />
      <Card icon={<AlertIcon />} label="Needs attention" aside={items.length === 0 ? "All caught up" : `${items.length} ${items.length === 1 ? "thing" : "things"} to decide`}>
        {items.length === 0 && <Empty>All caught up.</Empty>}
        <div className="cards">
          {shown.map((item, i) => (
            <ApprovalCard key={item.id} item={item} spaces={spaces} hotkey={i === 0} onApproved={(id) => replace(id, null)} onNotNow={notNow} onRejected={(next) => replace(next.id, next)} />
          ))}
        </div>
        {items.length > SHOW && (
          <p className="view-all">
            <Link to="/inbox/attention">View all {items.length} →</Link>
          </p>
        )}
      </Card>
      <Card icon={<CheckSquareIcon />} label="Stale tasks" aside={<span className="muted">{stale.length} · untouched {data?.stale_days ?? 14} days</span>}>
        {stale.length === 0 && <Empty>Nothing has gone quiet.</Empty>}
        {stale.length > 0 && (
          <ul className="rows flat">
            {stale.map((item) => (
              <ItemRow key={item.id} item={item} onChange={updateStale} />
            ))}
          </ul>
        )}
      </Card>
      <Card icon={<ClockIcon />} label="Recent" aside={<span className="muted">last 3</span>}>
        <RecentList captures={recent} />
        <p className="view-all">
          <Link to="/inbox/recent">View all →</Link>
        </p>
      </Card>
    </div>
  );
}
