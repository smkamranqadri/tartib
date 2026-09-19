import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { getBrief, getRecentSessions, listItems } from "../api";
import Card from "../components/Card";
import { CheckSquareIcon, ClockIcon, LayersIcon, NoteIcon, RefreshIcon } from "../components/Icons";
import ItemRow from "../components/ItemRow";
import { describe } from "../components/SessionPast";
import { Empty, ErrorLine, Loading } from "../components/Status";
import { formatRelative } from "../format";
import type { Brief, Item } from "../types";
import { useLoad } from "../useLoad";

export type ShapeFilter = "all" | "task" | "note";
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

/** Brief, tasks, and notes of one space. The search field lives on the page around it. */
export default function SpaceDetail({
  space,
  query,
  version,
  filter = "all",
  onCount,
  rowTo,
}: {
  space: string;
  query: string;
  version: number;
  filter?: ShapeFilter;
  onCount?: (n: number) => void;
  /** Where a row opens, when the page keeps the item beside the list. */
  rowTo?: (item: Item) => string;
}) {
  const debounced = query;
  const [showDone, setShowDone] = useState(false);
  const [open, setOpen] = useState<Record<Section, boolean>>(() => readOpen(space));
  const [brief, setBrief] = useState<Brief | null>(null);
  const [briefState, setBriefState] = useState<"loading" | "ok" | "error">("loading");
  const [briefError, setBriefError] = useState<string | null>(null);

  useEffect(() => {
    setOpen(readOpen(space));
    setBrief(null); // never show another space's brief while this one loads
    setBriefState("loading");
  }, [space]);
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
  // This space's own sessions: a plain list, newest first. No totals or charts (rule 4).
  const sessions = useLoad(() => getRecentSessions(20, space), [space, version]);
  const past = sessions.data?.sessions ?? [];
  const taskRows = [...(tasks.data?.items ?? [])]
    .filter((t) => t.stage === "filed" && (showDone || t.status === "open"))
    .sort((a, b) => Number(b.starred) - Number(a.starred) || (a.due ?? "9").localeCompare(b.due ?? "9") || b.id - a.id);
  const noteRows = (notes.data?.items ?? []).filter((n) => n.stage === "filed");

  function updateTask(next: Item) {
    if (tasks.data) tasks.setData({ ...tasks.data, items: tasks.data.items.map((i) => (i.id === next.id ? next : i)) });
  }
  const toggle = (s: Section) => setOpen((o) => ({ ...o, [s]: !o[s] }));

  const itemCount = (tasks.data?.items.length ?? 0) + (notes.data?.items.length ?? 0);
  useEffect(() => {
    if (tasks.data && notes.data) onCount?.(itemCount);
  }, [itemCount, tasks.data, notes.data]); // eslint-disable-line react-hooks/exhaustive-deps

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
        {briefState === "error" && <ErrorLine>{briefError}</ErrorLine>}
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

      {filter !== "note" && (
        <Card icon={<CheckSquareIcon />} label="Tasks" aside={taskRows.length} collapsible open={open.tasks} onToggle={() => toggle("tasks")}>
          {tasks.error && <ErrorLine>{tasks.error}</ErrorLine>}
          {!tasks.data && tasks.loading && <Loading />}
          {tasks.data && taskRows.length === 0 && <Empty>No open tasks.</Empty>}
          {taskRows.length > 0 && (
            <ul className="rows flat">
              {taskRows.map((item) => (
                <ItemRow key={item.id} item={item} onChange={updateTask} query={debounced || undefined} to={rowTo?.(item)} />
              ))}
            </ul>
          )}
          <label className="toggle">
            <input type="checkbox" checked={showDone} onChange={(e) => setShowDone(e.target.checked)} /> Show done
          </label>
        </Card>
      )}

      {filter !== "task" && (
        <Card icon={<NoteIcon />} label="Notes" aside={noteRows.length} collapsible open={open.notes} onToggle={() => toggle("notes")}>
          {notes.error && <ErrorLine>{notes.error}</ErrorLine>}
          {!notes.data && notes.loading && <Loading />}
          {notes.data && noteRows.length === 0 && <Empty>No notes.</Empty>}
          {noteRows.length > 0 && (
            <ul className="rows flat">
              {noteRows.map((item) => (
                <ItemRow key={item.id} item={item} onChange={() => {}} query={debounced || undefined} to={rowTo?.(item)} />
              ))}
            </ul>
          )}
        </Card>
      )}

      {past.length > 0 && !debounced && (
        <Card icon={<ClockIcon />} label="Sessions" aside={<span className="muted">last {past.length}</span>}>
          <ul className="rows flat">
            {past.map((p) => {
              const d = describe(p);
              return (
                <li key={p.id} className="row session-row">
                  <span className="row-text">{d.what}</span>
                  <span className="muted small">{d.meta}</span>
                </li>
              );
            })}
          </ul>
        </Card>
      )}
    </div>
  );
}
