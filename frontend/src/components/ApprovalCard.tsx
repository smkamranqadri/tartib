import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { approveItem, redoItem } from "../api";
import { formatDue, waitingReason } from "../format";
import type { Item, Shape } from "../types";
import { useWide } from "../useWide";
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
  onRetried,
}: {
  item: Item;
  spaces: string[];
  hotkey?: boolean;
  onApproved: (id: number) => void;
  onNotNow?: (id: number) => void;
  /** The classifier tried again and the item is still waiting, with a new proposal. */
  onRetried: (next: Item) => void;
}) {
  const [draft, setDraft] = useState<Draft>(() => draftOf(item));
  const [editing, setEditing] = useState<"title" | "due" | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  // Tell it why: the reason being written, and whether the classifier is on it.
  const [why, setWhy] = useState<string | null>(null);
  const [asking, setAsking] = useState(false);
  const wide = useWide(641);
  const [, setParams] = useSearchParams();

  useEffect(() => {
    setDraft(draftOf(item));
    setEditing(null);
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

  async function tryAgain() {
    const reason = (why ?? "").trim();
    if (!reason || asking) return;
    setAsking(true);
    setMsg(null);
    try {
      const next = await redoItem(item.id, reason);
      setWhy(null);
      // A confident second answer files itself, like any capture; then this card is done.
      if (next.stage === "filed") onApproved(item.id);
      else onRetried(next);
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "failed");
    } finally {
      setAsking(false);
    }
  }

  useEffect(() => {
    if (!hotkey) return;
    function onKey(e: KeyboardEvent) {
      const t = e.target as HTMLElement | null;
      if (t?.closest(".why")) return; // Enter there sends the reason, not an approval
      const typing = t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT");
      if (e.key === "Enter" && !e.shiftKey && !e.metaKey && !e.ctrlKey) {
        if (typing && t.tagName === "TEXTAREA") return;
        if (typing && t.tagName === "INPUT" && (t as HTMLInputElement).type === "search") return;
        e.preventDefault();
        void approve();
      } else if (e.key === "Escape") {
        setEditing(null);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }); // re-bound every render so approve sees the latest draft

  return (
    <div className={`one ${hotkey ? "hot" : ""}`}>
      {/* The card is two halves on a wide screen: what you are deciding about on the left, the
          decision itself on the right. Stacked, it left everything in the first third of a
          1200px card and wasted the rest. */}
      <div className="one-main">
      {wide ? (
        <Link className="raw big" to={`/items/${item.id}`}>
          {item.raw_text}
        </Link>
      ) : (
        <button
          type="button"
          className="raw big"
          onClick={() =>
            setParams((p) => {
              p.set("item", String(item.id));
              return p;
            })
          }
        >
          {item.raw_text}
        </button>
      )}
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
      </p>
      <p className="reason muted small">{waitingReason(item)}</p>
      {msg && <p className="error">{msg}</p>}
      {why !== null && (
        <form
          className="why"
          onSubmit={(e) => {
            e.preventDefault();
            void tryAgain();
          }}
        >
          <input
            autoFocus
            value={why}
            onChange={(e) => setWhy(e.target.value)}
            onKeyDown={(e) => e.key === "Escape" && setWhy(null)}
            placeholder="What's wrong with it? e.g. this is a home task"
            aria-label="Why"
            maxLength={500}
            disabled={asking}
          />
          <button type="submit" className="primary" disabled={asking || !why.trim()}>
            {asking ? "Asking…" : "Try again"}
          </button>
          <button type="button" className="ghost" onClick={() => setWhy(null)} disabled={asking}>
            Cancel
          </button>
        </form>
      )}
      </div>
      {/* While a reason is being written, that is the decision on the table. */}
      <div className="decisions" hidden={why !== null}>
        <button type="button" className="primary" onClick={() => void approve()}>
          Approve {hotkey && <kbd>↵</kbd>}
        </button>
        {onNotNow && (
          <button type="button" className="ghost" onClick={() => onNotNow(item.id)}>
            Not now
          </button>
        )}
        <button type="button" className="ghost" onClick={() => setWhy("")}>
          Tell it why…
        </button>
      </div>
    </div>
  );
}
