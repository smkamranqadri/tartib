import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getBrief, listItems } from "../api";
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
export default function SpaceDetail({ space, query, version }: { space: string; query: string; version: number }) {
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

  async function loadBrief(refresh = false) {
    setBriefState("loading");
    setBriefError(null);
    try {
      setBrief(await getBrief(space, refresh));
      setBriefState("ok");
    } catch (err) {
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

  return (
    <div className="space-detail">
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
