import { useState } from "react";
import { Link } from "react-router-dom";
import { approveItem, getAttention, getSpaces, rejectItem } from "../api";
import Card from "../components/Card";
import ItemEditor from "../components/ItemEditor";
import { formatCreated, formatDue, formatRemind } from "../format";
import type { Edit, Item } from "../types";
import { useLoad } from "../useLoad";

export default function Attention({ version, onDecided }: { version: number; onDecided: () => void }) {
  const { data, setData, error, loading } = useLoad(getAttention, [version]);
  const spaces = useLoad(getSpaces, [version]).data?.spaces ?? [];
  const [editing, setEditing] = useState<number | null>(null);
  const [rowError, setRowError] = useState<{ id: number; message: string } | null>(null);

  function remove(id: number) {
    if (data) setData({ items: data.items.filter((i) => i.id !== id) });
    setEditing(null);
    onDecided();
  }

  async function decide(id: number, action: () => Promise<Item>) {
    setRowError(null);
    try {
      await action();
      remove(id);
    } catch (err) {
      setRowError({ id, message: err instanceof Error ? err.message : "failed" });
      throw err;
    }
  }

  return (
    <div className="screen">
      <Card label="Needs Attention" aside={data && <span className="muted">{data.items.length} waiting</span>}>
      {error && <p className="error">{error}</p>}
      {loading && !data && <p className="muted">Loading…</p>}
      {data && data.items.length === 0 && <p className="muted">Inbox zero. Everything is filed.</p>}
      <ul className="items">
        {data?.items.map((item) => (
          <li key={item.id} className="item attention">
            <Link to={`/items/${item.id}`} className="raw link">{item.raw_text}</Link>
            <div className="item-meta">
              <span className="chip muted">{formatCreated(item.created_at)}</span>
            </div>
            {item.proposal ? (
              <p className="proposal">
                <strong>{item.proposal.shape}</strong> in <strong>{item.proposal.space}</strong>
                {item.proposal.title && <> · {item.proposal.title}</>}
                {item.proposal.due && <> · due {formatDue(item.proposal.due)}</>}
                {item.proposal.remind_at && <> · remind {formatRemind(item.proposal.remind_at)}</>}
                <span className="muted"> · {Math.round(item.proposal.confidence * 100)}% sure</span>
              </p>
            ) : (
              <p className="proposal muted">No proposal{item.proposal_error ? `: ${item.proposal_error}` : ""}</p>
            )}
            {editing === item.id ? (
              <ItemEditor
                item={item}
                fromProposal
                spaces={spaces}
                submitLabel="Approve"
                onSubmit={(edit: Edit) => decide(item.id, () => approveItem(item.id, edit))}
                onCancel={() => setEditing(null)}
              />
            ) : (
              <div className="decisions">
                <button type="button" onClick={() => void decide(item.id, () => approveItem(item.id)).catch(() => {})}>
                  {item.proposal ? "Approve" : "Keep as note"}
                </button>
                <button type="button" className="ghost" onClick={() => setEditing(item.id)}>
                  Edit
                </button>
                <button type="button" className="ghost danger" onClick={() => void decide(item.id, () => rejectItem(item.id)).catch(() => {})}>
                  Reject
                </button>
                {rowError?.id === item.id && <span className="error">{rowError.message}</span>}
              </div>
            )}
          </li>
        ))}
      </ul>
      </Card>
    </div>
  );
}
