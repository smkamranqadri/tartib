import { Link, useParams } from "react-router-dom";
import { approveItem, editItem, getItem, getSpaces } from "../api";
import Card from "../components/Card";
import ItemEditor from "../components/ItemEditor";
import { formatDue, formatRelative, formatRemind } from "../format";
import type { Edit } from "../types";
import { useLoad } from "../useLoad";

export default function ItemPage({ version }: { version: number }) {
  const { id } = useParams();
  const itemId = Number(id);
  const { data: item, setData, error, loading } = useLoad(() => getItem(itemId), [itemId, version]);
  const spaces = useLoad(getSpaces, [version]).data?.spaces ?? [];

  if (error) return <p className="error">{error}</p>;
  if (loading || !item) return <p className="muted">Loading…</p>;

  const isTask = item.shape === "task";
  const waiting = item.stage === "attention";

  async function save(edit: Edit) {
    setData(await editItem(itemId, edit));
  }
  async function approve(edit: Edit) {
    setData(await approveItem(itemId, edit));
  }

  return (
    <div className="screen item-page">
      <p className="crumbs">
        <Link to="/all">All</Link> <span className="muted">/ #{item.id}</span>
      </p>
      <Card
        label={isTask ? "Task" : "Note"}
        aside={
          <span className="muted">
            {item.space ?? "no space"} · <span className="when" title={new Date(item.created_at).toLocaleString()}>{formatRelative(item.created_at)}</span>
            {waiting && <> · <span className="chip stage-attention">needs attention</span></>}
          </span>
        }
      >
        {isTask && item.title && <h2 className="item-title">{item.title}</h2>}
        <p className="raw big">{item.raw_text}</p>
        {isTask && (
          <div className="item-meta">
            <span className="chip">{item.status}</span>
            {item.starred && <span className="chip">★ starred</span>}
            {item.due && <span className="chip">due {formatDue(item.due)}</span>}
            {item.remind_at && <span className="chip">⏰ {formatRemind(item.remind_at)}</span>}
          </div>
        )}
      </Card>

      <Card
        label={waiting ? "File it" : "Edit"}
        aside={
          !waiting &&
          isTask && (
            <span className="toggles">
              <button type="button" className="ghost" onClick={() => void save({ starred: !item.starred })}>
                {item.starred ? "★ Starred" : "☆ Star"}
              </button>
              <button type="button" className="ghost" onClick={() => void save({ status: item.status === "done" ? "open" : "done" })}>
                {item.status === "done" ? "Reopen" : "Mark done"}
              </button>
            </span>
          )
        }
      >
        <ItemEditor
          key={`${item.id}-${item.stage}-${item.classified_at}`}
          item={item}
          fromProposal={waiting}
          spaces={spaces}
          submitLabel={waiting ? "Approve" : "Save"}
          requireSpace
          onSubmit={waiting ? approve : save}
          onCancel={() => {}}
          hideCancel
          inline
        />
      </Card>

      <Card label="Proposal" aside={item.proposal && <span className="muted">{Math.round(item.proposal.confidence * 100)}% sure</span>}>
        {item.proposal ? (
          <dl className="kv">
            <dt>shape</dt>
            <dd>{item.proposal.shape}</dd>
            <dt>space</dt>
            <dd>{item.proposal.space ?? <span className="muted">none fits</span>}</dd>
            {item.proposal.title && (
              <>
                <dt>title</dt>
                <dd>{item.proposal.title}</dd>
              </>
            )}
            <dt>due</dt>
            <dd>{item.proposal.due ?? "—"}</dd>
            {item.proposal.remind_at && (
              <>
                <dt>remind</dt>
                <dd>{formatRemind(item.proposal.remind_at)}</dd>
              </>
            )}
          </dl>
        ) : (
          <p className="muted">No proposal{item.proposal_error ? `: ${item.proposal_error}` : "."}</p>
        )}
      </Card>
    </div>
  );
}
