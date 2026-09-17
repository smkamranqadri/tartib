import { Link } from "react-router-dom";
import { getAttention, getToday } from "../api";
import AnswerView from "../components/AnswerView";
import ItemRow from "../components/ItemRow";
import Capture from "../Capture";
import { formatRelative, todayLocal } from "../format";
import type { Answer, Capture as CaptureRecord, Item } from "../types";
import { useLoad } from "../useLoad";

/** starred, then overdue, then due today, then reminders */
function rank(item: Item, today: string): number {
  if (item.starred) return 0;
  if (item.due && item.due < today) return 1;
  if (item.due) return 2;
  return 3;
}

/** One page: capture at the top, today's list underneath. */
export default function Home({
  version,
  answer,
  onCaptured,
  onCloseAnswer,
}: {
  version: number;
  answer: Answer | null;
  onCaptured: (id: number) => void;
  onCloseAnswer: () => void;
}) {
  const attention = useLoad(getAttention, [version]).data?.items.length;
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
    <div className="home">
      <Capture onCaptured={onCaptured} />
      {answer && <AnswerView result={answer} onClose={onCloseAnswer} />}
      <p className="home-line muted">
        <Link to="/attention">{attention ?? "…"} need attention</Link>
      </p>
      <section className="today">
        {error && <p className="error">{error}</p>}
        {loading && !data && <p className="muted">Loading…</p>}
        {data && items.length === 0 && <p className="empty muted">Nothing due today.</p>}
        {items.length > 0 && (
          <ul className="rows">
            {items.map((item) => (
              <ItemRow key={item.id} item={item} onChange={update} />
            ))}
          </ul>
        )}
      </section>
      {data && data.recent.length > 0 && (
        <section className="today recent">
          <p className="section-label muted">Recent</p>
          <ul className="rows">
            {data.recent.map((cap) => (
              <RecentRow key={cap.id} cap={cap} />
            ))}
          </ul>
          <p className="view-all">
            <Link to="/all">View all →</Link>
          </p>
        </section>
      )}
    </div>
  );
}

/** One capture: its first line, linking to the item it became (or the first of them). */
function RecentRow({ cap }: { cap: CaptureRecord }) {
  const first = cap.items[0];
  const line = cap.raw_text.split("\n")[0];
  const state = cap.status === "pending" ? "filing…" : cap.answer && cap.items.length === 0 ? "answered" : first?.stage === "attention" ? "needs attention" : null;
  return (
    <li className="row">
      <div className="row-main">
        <span className={`dot ${first?.shape ?? "note"}`} aria-hidden />
        {first ? (
          <Link to={`/items/${first.id}`} className="row-text">
            {line}
          </Link>
        ) : (
          <span className="row-text">{line}</span>
        )}
        {state && <span className={`chip ${state === "needs attention" ? "stage-attention" : ""}`}>{state}</span>}
        <span className="row-actions">
          <span className="when muted" title={new Date(cap.created_at).toLocaleString()}>
            {formatRelative(cap.created_at)}
          </span>
        </span>
      </div>
    </li>
  );
}
