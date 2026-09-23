import { useEffect, useMemo, useRef, useState } from "react";
import { NavLink } from "react-router-dom";
import { getAttention } from "../api";
import ApprovalCard from "../components/ApprovalCard";
import Card from "../components/Card";
import { AlertIcon, CheckSquareIcon } from "../components/Icons";
import ItemRow from "../components/ItemRow";
import PageHead from "../components/PageHead";
import { Empty, ErrorLine, Loading, Stale } from "../components/Status";
import type { Pending } from "../offline";
import type { Item } from "../types";
import { useLoad } from "../useLoad";
import { useSpaces } from "../useSpaces";
import RecentTab from "./Recent";

export type InboxTab = "attention" | "stale" | "recent";

const SUBTITLE: Record<InboxTab, string> = {
  attention: "Approve what the classifier proposed, or file it yourself.",
  stale: "Open tasks nobody has touched in a while.",
  recent: "Everything you captured, newest first.",
};

/** Inbox: one tab at a time, each its own route so Back moves between them. The same component
 *  renders all three, so switching tabs keeps what is loaded instead of fetching it again. */
export default function Inbox({
  tab,
  version,
  onDecided,
  pending,
}: {
  tab: InboxTab;
  version: number;
  onDecided: () => void;
  pending: Pending[];
}) {
  const { data, setData, error, loading, cachedAt } = useLoad(getAttention, [version]);
  const spaces = useSpaces(version);
  // "Later" sends a card to the end; newest first otherwise.
  const [deferred, setDeferred] = useState<number[]>([]);
  /* What Later just did, said once (slice 36): it moves a card and sends nothing, and the owner
     took it for a rejection when the card simply left the screen. */
  const [moved, setMoved] = useState<string | null>(null);
  /* Half a second after a card leaves, clicks on the list are ignored (slice 36). The cards below
     move up at once, and a quick next click used to land on the next card's space picker or text
     where the button had been. */
  const [settling, setSettling] = useState(false);
  const settle = useRef<number | undefined>(undefined);
  function settleList() {
    setSettling(true);
    window.clearTimeout(settle.current);
    settle.current = window.setTimeout(() => setSettling(false), 500);
  }
  useEffect(() => () => window.clearTimeout(settle.current), []);
  const items = useMemo(() => {
    const all = [...(data?.items ?? [])].sort((a, b) => b.id - a.id);
    return [...all.filter((i) => !deferred.includes(i.id)), ...all.filter((i) => deferred.includes(i.id))];
  }, [data, deferred]);
  const stale = data?.stale ?? [];

  function replace(id: number, next: Item | null) {
    if (!data) return;
    /* A piece of a split that was decided on means the rest can no longer be kept as one. */
    const gone = data.items.find((i) => i.id === id);
    if (!next) settleList();
    const items = next ? data.items.map((i) => (i.id === id ? next : i)) : data.items.filter((i) => i.id !== id);
    setData({
      ...data,
      items: items.map((i) =>
        i.split && gone && i.capture_id === gone.capture_id ? { ...i, split: { ...i.split, whole: false } } : i,
      ),
    });
    onDecided();
  }

  /* Keep as one: the capture's pieces go, and the one note that replaces them takes their place. */
  function kept(captureId: number, note: Item) {
    if (!data) return;
    setData({ ...data, items: [...data.items.filter((i) => i.capture_id !== captureId), note] });
    onDecided();
  }

  function updateStale(next: Item) {
    if (!data) return;
    setData({ ...data, stale: data.stale.filter((i) => i.id !== next.id || next.status === "open").map((i) => (i.id === next.id ? next : i)) });
  }

  const count = (n: number) => (data ? <span className="count">{n}</span> : null);

  return (
    <div className="screen">
      <div className="title-row">
        <PageHead crumb="Inbox" title="Inbox" subtitle={SUBTITLE[tab]} />
        <Stale at={cachedAt} />
        <div className="title-actions">
          <nav className="pills tabs" aria-label="Inbox">
            <NavLink to="/inbox" end>
              Needs attention {count(items.length)}
            </NavLink>
            <NavLink to="/inbox/stale">Stale {count(stale.length)}</NavLink>
            <NavLink to="/inbox/recent">Recent</NavLink>
          </nav>
        </div>
      </div>
      {tab === "recent" ? (
        <RecentTab version={version} pending={pending} />
      ) : error ? (
        <ErrorLine>{error}</ErrorLine>
      ) : loading && !data ? (
        <Loading />
      ) : tab === "attention" ? (
        <Card icon={<AlertIcon />} label="Needs attention" aside={items.length === 0 ? "All caught up" : `${items.length} ${items.length === 1 ? "thing" : "things"} to decide`}>
          {items.length === 0 && <Empty>All caught up.</Empty>}
          {moved && <p className="moved muted small" role="status">{moved}</p>}
          <div className={`cards ${settling ? "settling" : ""}`}>
            {items.map((item, i) => (
              <ApprovalCard
                key={item.id}
                item={item}
                spaces={spaces}
                hotkey={i === 0}
                onApproved={(id) => replace(id, null)}
                onNotNow={(id) => {
                  setDeferred((d) => [...d.filter((x) => x !== id), id]);
                  const first = (item.raw_text.split("\n").find((l) => l.trim()) ?? "").trim();
                  setMoved(`Moved “${first.length > 40 ? first.slice(0, 40) + "…" : first}” to the end.`);
                  settleList();
                }}
                onRetried={(next) => replace(next.id, next)}
                onKept={kept}
              />
            ))}
          </div>
        </Card>
      ) : (
        <Card icon={<CheckSquareIcon />} label="Stale tasks" aside={<span className="muted">untouched {data?.stale_days ?? 14} days</span>}>
          {stale.length === 0 && <Empty>Nothing has gone quiet.</Empty>}
          {stale.length > 0 && (
            <ul className="rows flat">
              {stale.map((item) => (
                <ItemRow key={item.id} item={item} onChange={updateStale} />
              ))}
            </ul>
          )}
        </Card>
      )}
    </div>
  );
}
