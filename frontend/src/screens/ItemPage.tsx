import { useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { ApiError, approveItem, deleteItem, editItem, getCapture, getItem } from "../api";
import { enqueueEdit, resolveEdit } from "../offline";
import { applyTo, editFor } from "../pending";
import { usePending } from "../usePending";
import BackLink from "../components/BackLink";
import Card from "../components/Card";
import Confirm from "../components/Confirm";
import TextEditor, { type SaveResult } from "../components/TextEditor";
import Thoughts from "../components/Thoughts";
import ItemEditor from "../components/ItemEditor";
import { ErrorLine, Loading, Stale } from "../components/Status";
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
  const { data: item, setData, error, loading, cachedAt } = useLoad(() => getItem(itemId), [itemId, version]);
  const spaces = useSpaces(version);
  const [capture, setCapture] = useState<CaptureRecord | null>(null);
  // Bumped on Reload and on Overwrite: the editor remounts clean against the settled text.
  const [editorKey, setEditorKey] = useState(0);
  const [open, setOpen] = useState<{ file: boolean; proposal: boolean } | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const pending = usePending();
  const [msg, setMsg] = useState<string | null>(null);
  // An edit the server refused because the item moved on elsewhere, kept so it can be sent anyway.
  const [conflict, setConflict] = useState<Edit | null>(null);

  useEffect(() => {
    if (!item) return;
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

  /* What is queued for this item, over what the server last said (slice 25). */
  const shown = applyTo(item, pending);
  const queued = editFor(item.id, pending);
  /* Two ways to arrive at the same question: a live save refused while you were typing, or a
     queued one refused when the network came back. Both get the same strip and the same two
     answers -- the second is just discovered later. */
  const stale = conflict ?? (queued?.conflict ? queued.edit ?? null : null);
  const isTask = shown.shape === "task";
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
  async function saveChecked(edit: Edit, keepalive = false): Promise<boolean> {
    try {
      land(await editItem(itemId, { ...edit, expected_updated_at: item?.updated_at ?? undefined }, keepalive));
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
    setConflict(null);
    await resolveEdit(itemId); // the queued version loses; the server's copy is what you asked for
    setEditorKey((k) => k + 1);
  }
  async function overwrite() {
    if (!stale) return;
    land(await editItem(itemId, stale));
    setConflict(null);
    await resolveEdit(itemId);
    setEditorKey((k) => k + 1);
  }
  async function approve(edit: Edit) {
    land(await approveItem(itemId, edit));
    setOpen({ file: false, proposal: false });
  }
  /** What `TextEditor` autosaves through. It never throws: the editor shows the outcome, and a
   *  refusal must pause the loop rather than surface as an unhandled rejection every 2s. */
  async function saveText(next: string, keepalive = false): Promise<SaveResult> {
    try {
      const ok = await saveChecked({ text: next }, keepalive);
      setMsg(null);
      return ok ? "ok" : "conflict";
    } catch (err) {
      /* The network rather than the server: the text becomes a queued edit, which is what lets
         the editor stop saying "not saved" and start saying "waiting to send" (slice 25). */
      if (!(err instanceof ApiError) && (await enqueueEdit(itemId, { text: next }, item?.updated_at ?? null))) {
        setMsg(null);
        return "queued";
      }
      setMsg(err instanceof Error ? err.message : "failed");
      return "failed";
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
      <Stale at={cachedAt} />
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
              {isTask && shown.stage === "filed" && shown.status === "open" && (
                <button type="button" className="ghost" onClick={() => void session.start(item.id)}>
                  Start session
                </button>
              )}
              {/* A session needs the server's clock, so it is never queued. Offline the session
                  bar does not render at all, so the reason belongs here (slice 25). */}
              {session.error && <span className="error small">{session.error}</span>}
              <button type="button" className="ghost danger" onClick={() => setConfirmDelete(true)}>
                Delete
              </button>
            </span>
          </span>
        }
      >
        {isTask && item.title && item.title.trim() !== item.raw_text.trim() && <h2 className="item-title">{item.title}</h2>}
        {stale && (
          <div className="conflict-strip">
            <span className="tone warn">Changed elsewhere since you opened it. Your text is kept.</span>
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
        <TextEditor
          key={editorKey}
          draftId={String(itemId)}
          value={shown.raw_text}
          query={query}
          onSave={saveText}
          blocked={!!stale}
          queued={!!queued && !queued.conflict}
        />
        {confirmDelete && (
          <Confirm question={<>Delete this {item.shape}? The original capture stays.</>} onConfirm={() => void remove()} onCancel={() => setConfirmDelete(false)} />
        )}
        {msg && <ErrorLine>{msg}</ErrorLine>}
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
