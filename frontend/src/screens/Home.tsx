import { Link } from "react-router-dom";
import { getAttention, getToday } from "../api";
import AnswerView from "../components/AnswerView";
import Card from "../components/Card";
import { AlertIcon, ClockIcon, StarIcon } from "../components/Icons";
import ItemRow from "../components/ItemRow";
import SessionBar from "../components/SessionBar";
import Tiles from "../components/Tiles";
import PageHead from "../components/PageHead";
import RecentList from "../components/RecentList";
import type { Pending } from "../offline";
import { Empty, ErrorLine, Loading, Stale } from "../components/Status";
import { formatLongDate, todayLocal } from "../format";
import type { Answer, Item } from "../types";
import { useLoad } from "../useLoad";

function rank(item: Item, today: string): number {
  if (item.starred) return 0;
  if (item.due && item.due < today) return 1;
  if (item.due) return 2;
  return 3;
}

/** Dashboard. DOM order is Today, Needs attention, Recent, which is the phone order;
 *  the desktop grid places Needs attention in the right column. */
export default function Home({ version, answer, pending, onCloseAnswer }: { version: number; answer: Answer | null; pending: Pending[]; onCloseAnswer: () => void }) {
  const { data, setData, error, loading, cachedAt } = useLoad(getToday, [version]);
  const sessions = data?.sessions.total ?? 0;
  const attention = useLoad(getAttention, [version]);
  const today = todayLocal();
  const items = [...(data?.items ?? [])].sort((a, b) => rank(a, today) - rank(b, today) || (a.due ?? "").localeCompare(b.due ?? "") || a.id - b.id);

  function update(next: Item) {
    if (!data) return;
    const keep = next.status === "open";
    setData({ ...data, items: keep ? data.items.map((i) => (i.id === next.id ? next : i)) : data.items.filter((i) => i.id !== next.id) });
  }

  function updateAttention(next: Item) {
    const a = attention.data;
    if (!a) return;
    attention.setData({
      ...a,
      items: a.items.map((i) => (i.id === next.id ? next : i)),
      stale: a.stale.filter((i) => i.id !== next.id || next.status === "open").map((i) => (i.id === next.id ? next : i)),
    });
  }

  const queue = attention.data?.items ?? [];
  const stale = attention.data?.stale ?? [];
  const waiting = attention.data ? queue.length + stale.length : null;
  const needing = [...queue.slice(0, 3), ...stale.slice(0, Math.max(0, 3 - queue.length))];

  return (
    <div className="screen">
      <PageHead crumb="Today" title={formatLongDate()} subtitle="Today, what needs you, and what you captured." />
      <Stale at={cachedAt} />
      {answer && <AnswerView result={answer} onClose={onCloseAnswer} />}
      <Tiles
        tiles={[
          { label: "Due today", value: data ? items.length : "…", to: "/" },
          { label: "Needs you", value: waiting ?? "…", to: "/inbox", tone: waiting ? "warn" : "" },
          { label: "Sessions", value: data ? sessions : "…" },
          { label: "Captured", value: data ? (data.recent?.length ?? 0) : "…", to: "/inbox/recent" },
        ]}
      />
      <div className="dash">
        {/* Two columns that stack on their own, so a long one never leaves a gap in the
            other. On a phone the columns dissolve and the cards take their own order. */}
        <div className="dash-col">
          <Card className="area-today" icon={<StarIcon />} label="Today" aside={data ? items.length : "…"}>
            {error && <ErrorLine>{error}</ErrorLine>}
            {loading && !data && <Loading />}
            {data && items.length === 0 && <Empty>Nothing due today.</Empty>}
            {items.length > 0 && (
              <ul className="rows flat">
                {items.map((item) => (
                  <ItemRow
                    key={item.id}
                    item={item}
                    onChange={update}
                    sessions={data?.sessions.by_item[String(item.id)] ?? 0}
                  />
                ))}
              </ul>
            )}
            {data && sessions > 0 && (
              <p className="session-total">
                <span className="muted">{sessions === 1 ? "1 session today" : `${sessions} sessions today`}</span>
              </p>
            )}
          </Card>
          <Card className="area-recent" icon={<ClockIcon />} label="Recent" aside={<span className="muted">last 3</span>}>
            {/* Also when there is no `data`: offline the server call fails, and a capture waiting
                to send is exactly what you want to see then. Hiding it behind the load was how
                the queue became invisible in the one situation it exists for. */}
            {(data || pending.length > 0) && (
              <RecentList captures={data?.recent ?? []} pending={pending} />
            )}
            {!data && pending.length === 0 && loading && <Loading />}
            <p className="view-all">
              <Link to="/inbox/recent">View all →</Link>
            </p>
          </Card>
        </div>
        <div className="dash-col">
          <Card className="area-attention" icon={<AlertIcon />} label="Needs attention" aside={waiting ?? "…"}>
            {!attention.data && !attention.error && <Loading />}
            {attention.data && waiting === 0 && <Empty>All caught up.</Empty>}
            {needing.length > 0 && (
              <ul className="rows flat">
                {needing.map((item) => (
                  <ItemRow key={item.id} item={item} onChange={updateAttention} />
                ))}
              </ul>
            )}
            {waiting !== null && waiting > 3 && (
              <p className="view-all">
                <Link to="/inbox">View all →</Link>
              </p>
            )}
            {data?.active_space && (
              <p className="side-note muted">
                <Link to={`/spaces/${data.active_space}`}>{data.active_space}</Link> is the most recently touched space.
              </p>
            )}
          </Card>
          <SessionBar placement="card" />
        </div>
      </div>
    </div>
  );
}
