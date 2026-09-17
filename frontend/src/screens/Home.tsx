import { Link } from "react-router-dom";
import { getAttention, getToday } from "../api";
import AnswerView from "../components/AnswerView";
import Card from "../components/Card";
import { AlertIcon, ClockIcon, StarIcon } from "../components/Icons";
import ItemRow from "../components/ItemRow";
import PageHead from "../components/PageHead";
import RecentList from "../components/RecentList";
import { formatLongDate, formatRelative, todayLocal } from "../format";
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
export default function Home({ version, answer, onCloseAnswer }: { version: number; answer: Answer | null; onCloseAnswer: () => void }) {
  const { data, setData, error, loading } = useLoad(getToday, [version]);
  const attention = useLoad(getAttention, [version]).data;
  const today = todayLocal();
  const items = [...(data?.items ?? [])].sort((a, b) => rank(a, today) - rank(b, today) || (a.due ?? "").localeCompare(b.due ?? "") || a.id - b.id);

  function update(next: Item) {
    if (!data) return;
    const keep = next.status === "open";
    setData({ ...data, items: keep ? data.items.map((i) => (i.id === next.id ? next : i)) : data.items.filter((i) => i.id !== next.id) });
  }

  const waiting = attention ? attention.items.length + attention.stale.length : null;

  return (
    <div className="screen">
      <PageHead eyebrow="Dashboard" title={formatLongDate()} />
      {answer && <AnswerView result={answer} onClose={onCloseAnswer} />}
      <div className="dash">
        <Card className="area-today" icon={<StarIcon />} label="Today" aside={data ? items.length : "…"}>
          {error && <p className="error">{error}</p>}
          {loading && !data && <p className="muted">Loading…</p>}
          {data && items.length === 0 && <p className="empty muted">Nothing due today.</p>}
          {items.length > 0 && (
            <ul className="rows flat">
              {items.map((item) => (
                <ItemRow key={item.id} item={item} onChange={update} />
              ))}
            </ul>
          )}
        </Card>
        <Card className="area-attention" icon={<AlertIcon />} label="Needs attention" aside={waiting ?? "…"}>
          {attention && waiting === 0 && <p className="empty muted">All caught up.</p>}
          <ul className="rows flat">
            {attention?.items.slice(0, 3).map((item) => (
              <li key={item.id} className="row">
                <div className="row-main">
                  <span className="row-icon muted">
                    <AlertIcon />
                  </span>
                  <div className="row-body">
                    <Link to="/attention" className="row-text">
                      {item.shape === "task" && item.title ? item.title : item.raw_text.split("\n")[0]}
                    </Link>
                    <span className="row-meta muted">
                      {item.proposal ? item.proposal.shape : item.shape}
                      {item.proposal?.space ? <> · {item.proposal.space}</> : <> · no space fits</>}
                      {item.proposal && <> · {Math.round(item.proposal.confidence * 100)}%</>}
                    </span>
                  </div>
                </div>
              </li>
            ))}
            {attention?.stale.slice(0, Math.max(0, 3 - (attention?.items.length ?? 0))).map((item) => (
              <li key={item.id} className="row">
                <div className="row-main">
                  <span className="row-icon muted">
                    <ClockIcon />
                  </span>
                  <div className="row-body">
                    <Link to={`/items/${item.id}`} className="row-text">
                      {item.title ?? item.raw_text.split("\n")[0]}
                    </Link>
                    <span className="row-meta muted">untouched {formatRelative(item.updated_at ?? item.created_at)} · {item.space}</span>
                  </div>
                </div>
              </li>
            ))}
          </ul>
          {waiting !== null && waiting > 3 && (
            <p className="view-all">
              <Link to="/attention">View all →</Link>
            </p>
          )}
          {data?.active_space && (
            <p className="side-note muted">
              <Link to={`/spaces/${data.active_space}`}>{data.active_space}</Link> is the most recently touched space.
            </p>
          )}
        </Card>
        <Card className="area-recent" icon={<ClockIcon />} label="Recent" aside={<span className="muted">last 3</span>}>
          {data && <RecentList captures={data.recent} />}
          <p className="view-all">
            <Link to="/recent">View all →</Link>
          </p>
        </Card>
      </div>
    </div>
  );
}
