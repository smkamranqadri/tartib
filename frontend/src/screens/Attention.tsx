import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { approveItem, getAttention, getSpaces, rejectItem } from "../api";
import Card from "../components/Card";
import { CheckSquareIcon, InboxIcon } from "../components/Icons";
import ItemRow from "../components/ItemRow";
import PageHead from "../components/PageHead";
import SpaceSelect from "../components/SpaceSelect";
import { formatDue } from "../format";
import type { Item, Shape } from "../types";
import { useLoad } from "../useLoad";

interface Draft {
  shape: Shape;
  space: string | null;
  title: string;
  due: string;
}

function draftOf(item: Item): Draft {
  const p = item.proposal && item.proposal.shape !== "question" ? item.proposal : null;
  const shape = (p?.shape ?? item.shape) as Shape;
  return {
    shape,
    space: p?.space ?? item.space,
    title: p?.title ?? item.title ?? "",
    due: p?.due ?? item.due ?? "",
  };
}

/** One card at a time. Enter approves, Not now sends it to the back of the queue. */
export default function Attention({ version, onDecided }: { version: number; onDecided: () => void }) {
  const { data, setData, error, loading } = useLoad(getAttention, [version]);
  const spaces = useLoad(getSpaces, [version]).data?.spaces ?? [];
  const [order, setOrder] = useState<number[]>([]);
  const [pass, setPass] = useState(0); // how many "Not now" in this round
  const [draft, setDraft] = useState<Draft | null>(null);
  const [editing, setEditing] = useState<"title" | "due" | null>(null);
  const [menu, setMenu] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const items = useMemo(() => data?.items ?? [], [data]);
  const stale = data?.stale ?? [];
  useEffect(() => {
    setOrder((prev) => {
      const ids = items.map((i) => i.id);
      const kept = prev.filter((id) => ids.includes(id));
      const added = ids.filter((id) => !kept.includes(id));
      return [...kept, ...added];
    });
  }, [items]);

  const current = order.length ? items.find((i) => i.id === order[0]) ?? null : null;
  useEffect(() => {
    setDraft(current ? draftOf(current) : null);
    setEditing(null);
    setMenu(false);
    setMsg(null);
  }, [current?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  function drop(id: number, next?: Item | null) {
    if (!data) return;
    setData({ ...data, items: next ? items.map((i) => (i.id === id ? next : i)) : items.filter((i) => i.id !== id) });
    if (!next) setOrder((o) => o.filter((x) => x !== id));
    onDecided();
  }

  async function approve() {
    if (!current || !draft) return;
    if (!draft.space) {
      setMsg("Pick a space first.");
      return;
    }
    try {
      await approveItem(current.id, {
        shape: draft.shape,
        space: draft.space,
        title: draft.shape === "task" ? draft.title.trim() || null : null,
        due: draft.shape === "task" && draft.due ? draft.due : null,
      });
      setPass(0);
      drop(current.id);
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "failed");
    }
  }

  function notNow() {
    if (!current) return;
    setOrder((o) => [...o.slice(1), o[0]]);
    setPass((n) => n + 1);
  }

  async function reject() {
    if (!current) return;
    setMenu(false);
    try {
      const next = await rejectItem(current.id);
      drop(current.id, next);
      setDraft(draftOf(next));
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "failed");
    }
  }

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const t = e.target as HTMLElement | null;
      const typing = t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT");
      if (e.key === "Enter" && !e.shiftKey && !e.metaKey && !e.ctrlKey) {
        if (typing && t.tagName === "TEXTAREA") return;
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

  if (error) return <p className="error">{error}</p>;
  if (loading && !data) return <p className="muted">Loading…</p>;

  const remaining = order.length;
  const position = Math.min(pass + 1, remaining);
  const total = remaining + stale.length;

  function updateStale(next: Item) {
    if (!data) return;
    setData({ ...data, stale: data.stale.filter((i) => i.id !== next.id || (i.status === "open" && next.status === "open")).map((i) => (i.id === next.id ? next : i)) });
  }

  return (
    <div className="screen">
      <PageHead eyebrow="Inbox" title="Needs attention" subtitle={total === 0 ? "All caught up." : `${total} ${total === 1 ? "thing" : "things"} to decide`} />
      <Card icon={<InboxIcon />} label="Awaiting approval" aside={remaining ? `${position} of ${remaining}` : 0}>
        {!current || !draft ? (
          <p className="empty muted">All caught up.</p>
        ) : (
          <div className="one">
            <p className="raw big">{current.raw_text}</p>
            <p className="sentence">
              <button type="button" className="word" onClick={() => setDraft({ ...draft, shape: draft.shape === "task" ? "note" : "task" })}>
                {draft.shape === "task" ? "Task" : "Note"}
              </button>
              {draft.shape === "task" && (
                <>
                  {" "}
                  {editing === "title" ? (
                    <input
                      className="word-input"
                      autoFocus
                      value={draft.title}
                      onChange={(e) => setDraft({ ...draft, title: e.target.value })}
                      onBlur={() => setEditing(null)}
                      placeholder="title"
                      aria-label="Title"
                    />
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
              {current.proposal && <span className="muted small"> · {Math.round(current.proposal.confidence * 100)}%</span>}
              {!current.proposal && current.proposal_error && <span className="muted small"> · {current.proposal_error}</span>}
            </p>
            {msg && <p className="error">{msg}</p>}
            <div className="decisions">
              <button type="button" className="primary" onClick={() => void approve()}>
                Approve <kbd>↵</kbd>
              </button>
              <button type="button" className="ghost" onClick={notNow}>
                Not now
              </button>
              <span className="more">
                <button type="button" className="icon-btn" aria-label="More" onClick={() => setMenu((m) => !m)}>
                  …
                </button>
                {menu && (
                  <span className="menu">
                    <button type="button" onClick={() => void reject()}>
                      Reject proposal
                    </button>
                    <Link to={`/items/${current.id}`}>Open</Link>
                  </span>
                )}
              </span>
            </div>
          </div>
        )}
      </Card>
      <Card icon={<CheckSquareIcon />} label="Stale tasks" aside={<span className="muted">{stale.length} · untouched {data?.stale_days ?? 14} days</span>}>
        {stale.length === 0 && <p className="empty muted">Nothing has gone quiet.</p>}
        {stale.length > 0 && (
          <ul className="rows flat">
            {stale.map((item) => (
              <ItemRow key={item.id} item={item} onChange={updateStale} />
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
