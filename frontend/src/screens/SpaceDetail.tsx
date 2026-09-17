import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { deleteSpace, getBrief, listItems, renameSpace } from "../api";
import ItemRow from "../components/ItemRow";
import Card from "../components/Card";
import { CheckSquareIcon, LayersIcon, NoteIcon, RefreshIcon } from "../components/Icons";
import { formatRelative } from "../format";
import type { Brief, Item } from "../types";
import { useLoad } from "../useLoad";

type Section = "tasks" | "notes";

function readOpen(space: string): Record<Section, boolean> {
  try {
    const raw = localStorage.getItem(`tartib-space-${space}`);
    if (raw) return { tasks: true, notes: true, ...JSON.parse(raw) };
  } catch {
    /* ignore */
  }
  return { tasks: true, notes: true };
}

/** Brief, tasks, and notes of one space. The search field lives in the Search page. */
export default function SpaceDetail({ space, query, version, onRenamed, onDeleted }: { space: string; query: string; version: number; onRenamed?: (name: string) => void; onDeleted?: () => void }) {
  const [menu, setMenu] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [newName, setNewName] = useState(space);
  const [manageError, setManageError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const debounced = query;
  const [showDone, setShowDone] = useState(false);
  const [open, setOpen] = useState<Record<Section, boolean>>(() => readOpen(space));
  const [brief, setBrief] = useState<Brief | null>(null);
  const [briefState, setBriefState] = useState<"loading" | "ok" | "error">("loading");
  const [briefError, setBriefError] = useState<string | null>(null);

  useEffect(() => setOpen(readOpen(space)), [space]);
  useEffect(() => {
    try {
      localStorage.setItem(`tartib-space-${space}`, JSON.stringify(open));
    } catch {
      /* ignore */
    }
  }, [open, space]);

  const briefToken = useRef(0);
  async function loadBrief(refresh = false) {
    const token = ++briefToken.current;
    setBriefState("loading");
    setBriefError(null);
    try {
      const b = await getBrief(space, refresh);
      if (token !== briefToken.current) return; // a newer load (other space) won
      setBrief(b);
      setBriefState("ok");
    } catch (err) {
      if (token !== briefToken.current) return;
      setBriefError(err instanceof Error ? err.message : "brief failed");
      setBriefState("error");
    }
  }
  useEffect(() => {
    void loadBrief();
  }, [space, version]); // eslint-disable-line react-hooks/exhaustive-deps

  const tasks = useLoad(() => listItems({ space, shape: "task", q: debounced, limit: 200 }), [space, debounced, version]);
  const notes = useLoad(() => listItems({ space, shape: "note", q: debounced, limit: 200 }), [space, debounced, version]);
  const taskRows = [...(tasks.data?.items ?? [])]
    .filter((t) => t.stage === "filed" && (showDone || t.status === "open"))
    .sort((a, b) => Number(b.starred) - Number(a.starred) || (a.due ?? "9").localeCompare(b.due ?? "9") || b.id - a.id);
  const noteRows = (notes.data?.items ?? []).filter((n) => n.stage === "filed");

  function updateTask(next: Item) {
    if (tasks.data) tasks.setData({ ...tasks.data, items: tasks.data.items.map((i) => (i.id === next.id ? next : i)) });
  }
  const toggle = (s: Section) => setOpen((o) => ({ ...o, [s]: !o[s] }));

  const itemCount = (tasks.data?.items.length ?? 0) + (notes.data?.items.length ?? 0);

  async function doRename() {
    setManageError(null);
    try {
      const r = await renameSpace(space, newName);
      setRenaming(false);
      onRenamed?.(r.name);
    } catch (err) {
      setManageError(err instanceof Error ? err.message : "failed");
    }
  }
  async function doDelete() {
    setManageError(null);
    try {
      await deleteSpace(space);
      onDeleted?.();
    } catch (err) {
      setManageError(err instanceof Error ? err.message : "failed");
      setConfirmDelete(false);
    }
  }

  return (
    <div className="space-detail">
      <div className="manage">
        {renaming ? (
          <form className="new-space-form" onSubmit={(e) => { e.preventDefault(); void doRename(); }}>
            <input autoFocus value={newName} onChange={(e) => setNewName(e.target.value)} aria-label="Rename space" maxLength={24} />
            <button type="submit" className="primary" disabled={!newName.trim() || newName.trim().toLowerCase() === space}>
              Rename
            </button>
            <button type="button" className="ghost" onClick={() => setRenaming(false)}>
              Cancel
            </button>
          </form>
        ) : confirmDelete ? (
          <span className="confirm">
            Delete <b>{space}</b>?{" "}
            <button type="button" className="ghost danger" onClick={() => void doDelete()}>
              Yes, delete
            </button>{" "}
            <button type="button" className="ghost" onClick={() => setConfirmDelete(false)}>
              No
            </button>
          </span>
        ) : (
          <span className="more">
            <button type="button" className="icon-btn" aria-label="Manage space" onClick={() => setMenu((m) => !m)}>
              …
            </button>
            {menu && (
              <span className="menu">
                <a href="#rename" onClick={(e) => { e.preventDefault(); setMenu(false); setNewName(space); setRenaming(true); }}>
                  Rename
                </a>
                <button type="button" disabled={itemCount > 0} title={itemCount > 0 ? `${itemCount} items still here` : undefined} onClick={() => { setMenu(false); setConfirmDelete(true); }}>
                  Delete{itemCount > 0 ? ` (${itemCount} items)` : ""}
                </button>
              </span>
            )}
          </span>
        )}
        {manageError && <span className="error">{manageError}</span>}
      </div>
      <Card
        icon={<LayersIcon />}
        label={`Brief · ${space}`}
        aside={
          <span className="brief-meta muted">
            {brief && briefState !== "loading" && <>Updated {formatRelative(brief.updated_at)}</>}
            {briefState === "loading" && "Writing…"}
            <button type="button" className="icon-btn" onClick={() => void loadBrief(true)} aria-label="Refresh brief" disabled={briefState === "loading"}>
              <RefreshIcon />
            </button>
          </span>
        }
      >
        {briefState === "error" && <p className="error">{briefError}</p>}
        {brief && <p className={`brief-text ${briefState === "loading" ? "dim" : ""}`}>{brief.text}</p>}
        {!brief && briefState === "loading" && <p className="brief-text dim">Reading the space…</p>}
        {brief && brief.items.length > 0 && (
          <p className="brief-cites muted small">
            {brief.items.map((i) => (
              <Link key={i.id} to={`/items/${i.id}`}>
                #{i.id}
              </Link>
            ))}
          </p>
        )}
      </Card>

      <Card
        icon={<CheckSquareIcon />}
        label={
          <button type="button" className="section-toggle" onClick={() => toggle("tasks")} aria-expanded={open.tasks}>
            Tasks {open.tasks ? "▾" : "▸"}
          </button>
        }
        aside={taskRows.length}
      >
        {open.tasks && (
          <>
            {tasks.error && <p className="error">{tasks.error}</p>}
            {tasks.data && taskRows.length === 0 && <p className="empty muted">No open tasks.</p>}
            {taskRows.length > 0 && (
              <ul className="rows flat">
                {taskRows.map((item) => (
                  <ItemRow key={item.id} item={item} onChange={updateTask} />
                ))}
              </ul>
            )}
            <label className="toggle">
              <input type="checkbox" checked={showDone} onChange={(e) => setShowDone(e.target.checked)} /> Show done
            </label>
          </>
        )}
      </Card>

      <Card
        icon={<NoteIcon />}
        label={
          <button type="button" className="section-toggle" onClick={() => toggle("notes")} aria-expanded={open.notes}>
            Notes {open.notes ? "▾" : "▸"}
          </button>
        }
        aside={noteRows.length}
      >
        {open.notes && (
          <>
            {notes.error && <p className="error">{notes.error}</p>}
            {notes.data && noteRows.length === 0 && <p className="empty muted">No notes.</p>}
            {noteRows.length > 0 && (
              <ul className="rows flat">
                {noteRows.map((item) => (
                  <ItemRow key={item.id} item={item} onChange={() => {}} />
                ))}
              </ul>
            )}
          </>
        )}
      </Card>
    </div>
  );
}
