import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { approveItem, deleteItem, editItem, getCapture, getItem, getSpaces } from "../api";
import Card from "../components/Card";
import ItemEditor from "../components/ItemEditor";
import { formatDue, formatRelative, formatRemind } from "../format";
import type { Capture as CaptureRecord, Edit } from "../types";
import { useLoad } from "../useLoad";

export default function ItemPage({ version }: { version: number }) {
  const { id } = useParams();
  const itemId = Number(id);
  const navigate = useNavigate();
  const { data: item, setData, error, loading } = useLoad(() => getItem(itemId), [itemId, version]);
  const spaces = useLoad(getSpaces, [version]).data?.spaces ?? [];
  const [capture, setCapture] = useState<CaptureRecord | null>(null);
  const [text, setText] = useState("");
  const [editingText, setEditingText] = useState(false);
  const [open, setOpen] = useState<{ file: boolean; proposal: boolean } | null>(null);
  const [menu, setMenu] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    if (!item) return;
    setText(item.raw_text);
    if (open === null) setOpen({ file: item.stage === "attention", proposal: item.stage === "attention" });
    getCapture(item.capture_id).then(setCapture).catch(() => setCapture(null));
  }, [item?.id, item?.stage]); // eslint-disable-line react-hooks/exhaustive-deps

  if (error) return <p className="error">{error}</p>;
  if (loading || !item) return <p className="muted">Loading…</p>;

  const isTask = item.shape === "task";
  const waiting = item.stage === "attention";
  const originalDiffers = capture && capture.raw_text.trim() !== item.raw_text.trim();

  async function save(edit: Edit) {
    setData(await editItem(itemId, edit));
  }
  async function approve(edit: Edit) {
    setData(await approveItem(itemId, edit));
    setOpen({ file: false, proposal: false });
  }
  async function saveText() {
    const value = text.trim();
    if (!value || value === item?.raw_text) {
      setEditingText(false);
      return;
    }
    try {
      await save({ text: value });
      setEditingText(false);
      setMsg(null);
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "failed");
    }
  }
  async function remove() {
    try {
      await deleteItem(itemId);
      navigate(-1);
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "failed");
    }
  }

  return (
    <div className="screen item-page">
      <p className="crumbs">
        <Link to="/spaces">Spaces</Link>
        {item.space && (
          <>
            {" "}
            / <Link to={`/spaces?space=${item.space}`}>{item.space}</Link>
          </>
        )}{" "}
        <span className="muted">/ #{item.id}</span>
      </p>
      <Card
        label={isTask ? "Task" : "Note"}
        aside={
          <span className="item-aside">
            <span className="muted">
              {item.space ?? "no space"} · <span title={new Date(item.created_at).toLocaleString()}>{formatRelative(item.created_at)}</span>
              {waiting && <> · <span className="chip stage-attention">needs attention</span></>}
            </span>
            <span className="more">
              <button type="button" className="icon-btn" aria-label="More" onClick={() => setMenu((m) => !m)}>
                …
              </button>
              {menu && (
                <span className="menu">
                  <a href="#edit" onClick={(e) => { e.preventDefault(); setMenu(false); setEditingText(true); }}>
                    Edit text
                  </a>
                  <button type="button" onClick={() => { setMenu(false); setConfirmDelete(true); }}>
                    Delete
                  </button>
                </span>
              )}
            </span>
          </span>
        }
      >
        {isTask && item.title && !editingText && <h2 className="item-title">{item.title}</h2>}
        {editingText ? (
          <div className="text-edit">
            <textarea value={text} onChange={(e) => setText(e.target.value)} rows={Math.min(12, Math.max(3, text.split("\n").length + 1))} aria-label="Text" autoFocus />
            <div className="editor-actions">
              <button type="button" className="ghost" onClick={() => { setEditingText(false); setText(item.raw_text); }}>
                Cancel
              </button>
              <button type="button" className="primary" onClick={() => void saveText()}>
                Save
              </button>
            </div>
          </div>
        ) : (
          <p className="raw big" onDoubleClick={() => setEditingText(true)}>
            {item.raw_text}
          </p>
        )}
        {confirmDelete && (
          <p className="confirm">
            Delete this {item.shape}? The original capture stays.{" "}
            <button type="button" className="ghost danger" onClick={() => void remove()}>
              Yes, delete
            </button>{" "}
            <button type="button" className="ghost" onClick={() => setConfirmDelete(false)}>
              No
            </button>
          </p>
        )}
        {msg && <p className="error">{msg}</p>}
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
        className="accordion"
        label={
          <button type="button" className="section-toggle" onClick={() => setOpen((o) => ({ ...(o ?? { file: false, proposal: false }), file: !o?.file }))} aria-expanded={!!open?.file}>
            {waiting ? "File it" : "Edit"} {open?.file ? "▾" : "▸"}
          </button>
        }
        aside={
          !waiting && isTask && (
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
        {open?.file && (
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
        )}
      </Card>

      <Card
        className="accordion"
        label={
          <button type="button" className="section-toggle" onClick={() => setOpen((o) => ({ ...(o ?? { file: false, proposal: false }), proposal: !o?.proposal }))} aria-expanded={!!open?.proposal}>
            Proposal {open?.proposal ? "▾" : "▸"}
          </button>
        }
        aside={item.proposal && <span className="muted">{Math.round(item.proposal.confidence * 100)}% sure</span>}
      >
        {open?.proposal && (
          <>
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
            {originalDiffers && capture && (
              <div className="original">
                <p className="section-label muted">What you wrote</p>
                <p className="raw muted">{capture.raw_text}</p>
              </div>
            )}
          </>
        )}
      </Card>
    </div>
  );
}
