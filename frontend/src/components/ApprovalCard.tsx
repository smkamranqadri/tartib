import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { approveItem, rejectItem } from "../api";
import { formatDue } from "../format";
import type { Item, Shape } from "../types";
import SpaceSelect from "./SpaceSelect";

interface Draft {
  shape: Shape;
  space: string | null;
  title: string;
  due: string;
}

function draftOf(item: Item): Draft {
  const p = item.proposal && item.proposal.shape !== "question" ? item.proposal : null;
  const shape = (p?.shape ?? item.shape) as Shape;
  return { shape, space: p?.space ?? item.space, title: p?.title ?? item.title ?? "", due: p?.due ?? item.due ?? "" };
}

/** One waiting item as a decision: text, the proposal as a sentence with tappable words,
 *  Approve / Not now / "…". When `hotkey` is set, Enter approves it. */
export default function ApprovalCard({
  item,
  spaces,
  hotkey,
  onApproved,
  onNotNow,
  onRejected,
}: {
  item: Item;
  spaces: string[];
  hotkey?: boolean;
  onApproved: (id: number) => void;
  onNotNow?: (id: number) => void;
  onRejected: (next: Item) => void;
}) {
  const [draft, setDraft] = useState<Draft>(() => draftOf(item));
  const [editing, setEditing] = useState<"title" | "due" | null>(null);
  const [menu, setMenu] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    setDraft(draftOf(item));
    setEditing(null);
    setMenu(false);
    setMsg(null);
  }, [item.id, item.proposal, item.space]);

  async function approve() {
    if (!draft.space) {
      setMsg("Pick a space first.");
      return;
    }
    try {
      await approveItem(item.id, {
        shape: draft.shape,
        space: draft.space,
        title: draft.shape === "task" ? draft.title.trim() || null : null,
        due: draft.shape === "task" && draft.due ? draft.due : null,
      });
      onApproved(item.id);
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "failed");
    }
  }

  async function reject() {
    setMenu(false);
    try {
      onRejected(await rejectItem(item.id));
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "failed");
    }
  }

  useEffect(() => {
    if (!hotkey) return;
    function onKey(e: KeyboardEvent) {
      const t = e.target as HTMLElement | null;
      const typing = t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT");
      if (e.key === "Enter" && !e.shiftKey && !e.metaKey && !e.ctrlKey) {
        if (typing && t.tagName === "TEXTAREA") return;
        if (typing && t.tagName === "INPUT" && (t as HTMLInputElement).type === "search") return;
        e.preventDefault();
        void approve();
      } else if (e.key === "Escape") {
        setEditing(null);
        setMenu(false);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }); // re-bound every render so approve sees the latest draft

  return (
    <div className={`one ${hotkey ? "hot" : ""}`}>
      <p className="raw big">{item.raw_text}</p>
      <p className="sentence">
        <button type="button" className="word" onClick={() => setDraft({ ...draft, shape: draft.shape === "task" ? "note" : "task" })}>
          {draft.shape === "task" ? "Task" : "Note"}
        </button>
        {draft.shape === "task" && (
          <>
            {" "}
            {editing === "title" ? (
              <input className="word-input" autoFocus value={draft.title} onChange={(e) => setDraft({ ...draft, title: e.target.value })} onBlur={() => setEditing(null)} placeholder="title" aria-label="Title" />
            ) : (
              <button type="button" className="word quoted" onClick={() => setEditing("title")}>
                {draft.title || "untitled"}
              </button>
            )}
          </>
        )}{" "}
        in{" "}
        <span className={`word select ${draft.space ? "" : "missing"}`}>
          <SpaceSelect value={draft.space} spaces={spaces} onChange={(space) => setDraft({ ...draft, space })} />
          <b>{draft.space ?? "no space"}</b>
        </span>
        {draft.shape === "task" && (
          <>
            , due{" "}
            {editing === "due" ? (
              <input type="date" className="word-input" autoFocus value={draft.due} onChange={(e) => setDraft({ ...draft, due: e.target.value })} onBlur={() => setEditing(null)} aria-label="Due" />
            ) : (
              <button type="button" className="word" onClick={() => setEditing("due")}>
                {draft.due ? formatDue(draft.due) : "never"}
              </button>
            )}
          </>
        )}
        {item.proposal && <span className="muted small"> · {Math.round(item.proposal.confidence * 100)}%</span>}
        {!item.proposal && item.proposal_error && <span className="muted small"> · {item.proposal_error}</span>}
      </p>
      {msg && <p className="error">{msg}</p>}
      <div className="decisions">
        <button type="button" className="primary" onClick={() => void approve()}>
          Approve {hotkey && <kbd>↵</kbd>}
        </button>
        {onNotNow && (
          <button type="button" className="ghost" onClick={() => onNotNow(item.id)}>
            Not now
          </button>
        )}
        <span className="more">
          <button type="button" className="icon-btn" aria-label="More" onClick={() => setMenu((m) => !m)}>
            …
          </button>
          {menu && (
            <span className="menu">
              <button type="button" onClick={() => void reject()}>
                Reject proposal
              </button>
              <Link to={`/items/${item.id}`}>Open</Link>
            </span>
          )}
        </span>
      </div>
    </div>
  );
}
