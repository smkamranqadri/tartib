import { useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { ApiError, approveItem, deleteItem, editItem, getCapture, getItem } from "../api";
import BackLink from "../components/BackLink";
import Card from "../components/Card";
import Confirm from "../components/Confirm";
import Highlight from "../components/Highlight";
import Thoughts from "../components/Thoughts";
import ItemEditor from "../components/ItemEditor";
import { ErrorLine, Loading } from "../components/Status";
import { formatDue, formatRelative, formatRemind } from "../format";
import { useSession } from "../session";
import type { Capture as CaptureRecord, Edit, Item } from "../types";
import { useLoad } from "../useLoad";
import { useSpaces } from "../useSpaces";

/** One item. Its own route on a phone; on a wide space page it is embedded beside the list
 *  (`itemId` given), where it has no Back, and tells the list when it changed. */
export default function ItemPage({
  version,
  itemId: embeddedId,
  onChanged,
  onClosed,
}: {
  version: number;
  itemId?: number;
  onChanged?: () => void;
  onClosed?: () => void;
}) {
  const session = useSession();
  const { id } = useParams();
  const [params] = useSearchParams();
  const query = params.get("q");
  const embedded = embeddedId !== undefined;
  const itemId = embedded ? embeddedId : Number(id);
  const navigate = useNavigate();
  const { data: item, setData, error, loading } = useLoad(() => getItem(itemId), [itemId, version]);
  const spaces = useSpaces(version);
  const [capture, setCapture] = useState<CaptureRecord | null>(null);
  const [text, setText] = useState("");
  const [editingText, setEditingText] = useState(false);
  const [open, setOpen] = useState<{ file: boolean; proposal: boolean } | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  // An edit the server refused because the item moved on elsewhere, kept so it can be sent anyway.
  const [conflict, setConflict] = useState<Edit | null>(null);

  useEffect(() => {
    if (!item) return;
    setText(item.raw_text);
    if (open === null) setOpen({ file: item.stage === "attention", proposal: item.stage === "attention" });
    getCapture(item.capture_id).then(setCapture).catch(() => setCapture(null));
  }, [item?.id, item?.stage]); // eslint-disable-line react-hooks/exhaustive-deps

  // Opened from a search: land on the first match rather than the top of a long note.
  useEffect(() => {
    if (!query || !item) return;
    document.querySelector("mark.hit")?.scrollIntoView({ block: "center" });
  }, [item?.id, query]); // eslint-disable-line react-hooks/exhaustive-deps

  if (error) return <ErrorLine>{error}</ErrorLine>;
  if (loading || !item)
    return (
      <div className="screen item-page">
        <div className="card">
          <Loading rows={4} />
        </div>
      </div>
    );

  const isTask = item.shape === "task";
  const waiting = item.stage === "attention";
  const originalDiffers = capture && capture.raw_text.trim() !== item.raw_text.trim();

  /** A write the server took: show it, and let an embedding list know. */
  function land(next: Item) {
    setData(next);
    onChanged?.();
  }
  /** Toggles: sent as they are, never refused. */
  async function save(edit: Edit) {
    land(await editItem(itemId, edit));
  }
  /** Real edits carry the version this page loaded. False when refused as stale: the edit is
   *  held in `conflict` for the person to reload over or send anyway. */
  async function saveChecked(edit: Edit): Promise<boolean> {
    try {
      land(await editItem(itemId, { ...edit, expected_updated_at: item?.updated_at ?? undefined }));
      setConflict(null);
      return true;
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setConflict(edit);
        return false;
      }
      throw err;
    }
  }
  async function reloadItem() {
    const fresh = await getItem(itemId);
    setData(fresh);
    setText(fresh.raw_text);
    setEditingText(false);
    setConflict(null);
  }
  async function overwrite() {
    if (!conflict) return;
    land(await editItem(itemId, conflict));
    setEditingText(false);
    setConflict(null);
  }
  async function approve(edit: Edit) {
    land(await approveItem(itemId, edit));
    setOpen({ file: false, proposal: false });
  }
  async function saveText() {
    const value = text.trim();
    if (!value || value === item?.raw_text) {
      setEditingText(false);
      return;
    }
    try {
      if (await saveChecked({ text: value })) setEditingText(false);
      setMsg(null);
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "failed");
    }
  }
  async function remove() {
    try {
      await deleteItem(itemId);
      if (embedded) {
        onChanged?.();
        onClosed?.();
      } else navigate(-1);
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "failed");
    }
  }

  return (
    <div className="screen item-page">
      {!embedded && <BackLink fallback={item.space ? `/spaces/${item.space}` : "/inbox"} />}
      <Card
        label={isTask ? "Task" : "Note"}
        aside={
          <span className="item-aside">
            <span className="muted">
              {item.space ? <Link to={`/spaces/${item.space}`}>{item.space}</Link> : "no space"} ·{" "}
              <span title={new Date(item.created_at).toLocaleString()}>{formatRelative(item.created_at)}</span>
              {waiting && (
                <>
                  {" "}
                  · <span className="chip stage-attention">needs attention</span>
                </>
              )}
            </span>
            {/* Three actions, three buttons. They were behind a "…" that hid what the page could
                do; there was never enough in there to be worth a menu. */}
            <span className="item-actions">
              {isTask && item.stage === "filed" && item.status === "open" && (
                <button type="button" className="ghost" onClick={() => void session.start(item.id)}>
                  Start session
                </button>
              )}
              <button type="button" className="ghost" onClick={() => setEditingText(true)}>
                Edit
              </button>
              <button type="button" className="ghost danger" onClick={() => setConfirmDelete(true)}>
                Delete
              </button>
            </span>
          </span>
        }
      >
        {isTask && item.title && !editingText && item.title.trim() !== item.raw_text.trim() && <h2 className="item-title">{item.title}</h2>}
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
            <Highlight text={item.raw_text} query={query} />
          </p>
        )}
        {confirmDelete && (
          <Confirm question={<>Delete this {item.shape}? The original capture stays.</>} onConfirm={() => void remove()} onCancel={() => setConfirmDelete(false)} />
        )}
        {msg && <ErrorLine>{msg}</ErrorLine>}
        {conflict && (
          <div className="load-failed">
            <ErrorLine>This changed on another device or tab since you opened it.</ErrorLine>
            <span className="toggles">
              <button type="button" className="ghost" onClick={() => void reloadItem()}>
                Reload
              </button>
              <button type="button" className="ghost" onClick={() => void overwrite()}>
                Overwrite
              </button>
            </span>
          </div>
        )}
        {isTask && (
          <div className="item-meta">
            <span className="chip">{item.status}</span>
            {item.starred && <span className="chip">★ starred</span>}
            {item.due && <span className="chip">due {formatDue(item.due)}</span>}
            {item.remind_at && <span className="chip">⏰ {formatRemind(item.remind_at)}</span>}
          </div>
        )}
      </Card>

      <Thoughts itemId={item.id} onAdded={onChanged} />

      <Card
        className="accordion"
        label={waiting ? "File it" : "Edit"}
        collapsible
        open={!!open?.file}
        onToggle={() => setOpen((o) => ({ ...(o ?? { file: false, proposal: false }), file: !o?.file }))}
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
          key={`${item.id}-${item.stage}-${item.classified_at}-${item.updated_at}`}
          item={item}
          fromProposal={waiting}
          spaces={spaces}
          submitLabel={waiting ? "Approve" : "Save"}
          requireSpace
          onSubmit={waiting ? approve : async (edit) => void (await saveChecked(edit))}
          onCancel={() => {}}
          hideCancel
          inline
        />
      </Card>

      <Card
        className="accordion"
        label="Proposal"
        collapsible
        open={!!open?.proposal}
        onToggle={() => setOpen((o) => ({ ...(o ?? { file: false, proposal: false }), proposal: !o?.proposal }))}
        aside={item.proposal && <span className="muted">{Math.round(item.proposal.confidence * 100)}% sure</span>}
      >
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
      </Card>
    </div>
  );
}
