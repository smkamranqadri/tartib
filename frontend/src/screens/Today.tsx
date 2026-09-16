import { Link } from "react-router-dom";
import { getSpaces, getToday } from "../api";
import Card from "../components/Card";
import ItemRow from "../components/ItemRow";
import { formatCreated } from "../format";
import type { Capture, Item } from "../types";
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
    <div className="screen">
      <Card label="Today" aside={data && <span className="muted">{data.date}</span>}>
        {error && <p className="error">{error}</p>}
        {loading && !data && <p className="muted">Loading…</p>}
        {data && data.items.length === 0 && <p className="muted">Nothing due, starred, or waiting on a reminder.</p>}
        <ul className="items">
          {data?.items.map((item) => (
            <ItemRow key={item.id} item={item} spaces={spaces} onChange={update} />
          ))}
        </ul>
      </Card>
      <Card label="Recent" aside={<span className="muted">what you captured</span>}>
        {data && data.recent.length === 0 && <p className="muted">Nothing captured yet.</p>}
        <ul className="recent">{data?.recent.map((cap) => <RecentRow key={cap.id} cap={cap} />)}</ul>
      </Card>
    </div>
  );
}

function RecentRow({ cap }: { cap: Capture }) {
  const first = cap.items[0];
  const text = cap.raw_text;
  return (
    <li className="recent-row">
      <div className="recent-main">
        {first ? (
          <Link to={`/items/${first.id}`} className="item-text">
            {text}
          </Link>
        ) : (
          <span className="item-text">{text}</span>
        )}
      </div>
      <div className="item-meta">
        {cap.status === "pending" && <span className="chip stage-attention">filing…</span>}
        {cap.answer && <span className="chip">answered</span>}
        {cap.items.map((item) => (
          <Link key={item.id} to={`/items/${item.id}`} className={`chip link ${item.stage === "attention" ? "stage-attention" : ""}`}>
            {item.shape === "task" && item.title ? item.title : item.shape}
            {" · "}
            {item.space ?? (item.stage === "attention" ? "needs attention" : "no space")}
          </Link>
        ))}
        <span className="chip muted">{formatCreated(cap.created_at)}</span>
      </div>
      {cap.answer && <p className="recent-answer">{cap.answer.answer}</p>}
    </li>
  );
}
