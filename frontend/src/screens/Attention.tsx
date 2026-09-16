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

  function replace(next: Item | null, id: number) {
    if (!data) return;
    setData({ items: next ? data.items.map((i) => (i.id === id ? next : i)) : data.items.filter((i) => i.id !== id) });
    setEditing(null);
    onDecided();
  }

  async function approve(item: Item, edit?: Edit) {
    setRowError(null);
    try {
      await approveItem(item.id, edit);
      replace(null, item.id);
    } catch (err) {
      setRowError({ id: item.id, message: err instanceof Error ? err.message : "failed" });
      throw err;
    }
  }

  async function reject(item: Item) {
    setRowError(null);
    try {
      replace(await rejectItem(item.id), item.id);
    } catch (err) {
      setRowError({ id: item.id, message: err instanceof Error ? err.message : "failed" });
    }
  }

  return (
    <div className="screen">
      <Card label="Needs Attention" aside={data && <span className="muted">{data.items.length} waiting</span>}>
        {error && <p className="error">{error}</p>}
        {loading && !data && <p className="muted">Loading…</p>}
        {data && data.items.length === 0 && <p className="muted">Inbox zero. Everything is filed.</p>}
        <ul className="items">
          {data?.items.map((item) => {
            const p = item.proposal;
            const canApprove = !!(p?.space ?? item.space);
            return (
              <li key={item.id} className="item attention">
                <Link to={`/items/${item.id}`} className="raw link">
                  {item.raw_text}
                </Link>
                <div className="item-meta">
                  <span className="chip muted">{formatCreated(item.created_at)}</span>
                </div>
                {p ? (
                  <p className="proposal">
                    <strong>{p.shape}</strong>
                    {p.space ? (
                      <>
                        {" "}
                        in <strong>{p.space}</strong>
                      </>
                    ) : (
                      <span className="muted"> · no space fits</span>
                    )}
                    {p.title && <> · {p.title}</>}
                    {p.due && <> · due {formatDue(p.due)}</>}
                    {p.remind_at && <> · remind {formatRemind(p.remind_at)}</>}
                    <span className="muted"> · {Math.round(p.confidence * 100)}% sure</span>
                  </p>
                ) : (
                  <p className="proposal muted">No proposal{item.proposal_error ? `: ${item.proposal_error}` : ". Pick a space to file it."}</p>
                )}
                {editing === item.id ? (
                  <ItemEditor
                    item={item}
                    fromProposal
                    spaces={spaces}
                    submitLabel="Approve"
                    requireSpace
                    onSubmit={(edit: Edit) => approve(item, edit)}
                    onCancel={() => setEditing(null)}
                  />
                ) : (
                  <div className="decisions">
                    {canApprove ? (
                      <button type="button" onClick={() => void approve(item).catch(() => {})}>
                        Approve
                      </button>
                    ) : (
                      <button type="button" onClick={() => setEditing(item.id)}>
                        File…
                      </button>
                    )}
                    <button type="button" className="ghost" onClick={() => setEditing(item.id)}>
                      Edit
                    </button>
                    {p && (
                      <button type="button" className="ghost danger" onClick={() => void reject(item)} title="Discard the proposal; the item stays here">
                        Reject
                      </button>
                    )}
                    {rowError?.id === item.id && <span className="error">{rowError.message}</span>}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      </Card>
    </div>
  );
}
