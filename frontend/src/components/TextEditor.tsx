import { Suspense, lazy, useCallback, useEffect, useRef, useState, type MouseEvent } from "react";
import { spotFromPoint, toggleTask, type Spot } from "../markdown";
import Markdown from "./Markdown";

/** The editor is a chunk of its own and `sw.js` does not precache it -- it only caches what
 *  `index.html` names, and a lazy chunk is not in there. So offline, this import rejects. Left
 *  alone that would throw inside `lazy` and take the whole page down; instead the text stays
 *  readable and the page says why it cannot be edited. */
const MarkdownEditor = lazy(() =>
  import("./MarkdownEditor").catch(() => ({ default: EditorUnavailable })),
);

function EditorUnavailable({ value }: { value: string }) {
  return (
    <>
      <div className="raw big">
        <Markdown text={value} query={null} titled />
      </div>
      <p className="save-state bad">
        <span className="tone warn">The editor could not load{navigator.onLine ? "" : " -- you are offline"}. Your text is unchanged.</span>
      </p>
    </>
  );
}

/** `queued` is slice 25: the network would not take it, so it was written down instead. That is
 *  not a failure and must not read as one -- the words are safe, they are just not there yet. */
export type SaveResult = "ok" | "conflict" | "failed" | "queued";

export type Save = (text: string, keepalive?: boolean) => Promise<SaveResult>;

type Status = "clean" | "pending" | "saving" | "saved" | "failed" | "empty" | "queued";

const DEBOUNCE = 2000;

/** The draft, kept next to the text it was started from.
 *
 *  A save flushed while the page is being torn down -- a closed tab, a killed app -- is sent
 *  with `keepalive`, and that is still the right thing to do, but it is not a guarantee: the
 *  browser drops it often enough to have been measured doing so. So the words are also written
 *  here as they are typed, and read back on the way in. That is what makes "nothing is lost"
 *  true: the text comes back and saves itself on the next keystroke or blur.
 *
 *  This is crash safety, not the offline edit queue in the backlog -- no queue, no replay, no
 *  conflict logic of its own. A restored draft saves through the ordinary path and gets the
 *  ordinary 409 strip if the item moved on meanwhile. */
interface Draft {
  base: string;
  draft: string;
}

const key = (id: string) => `tartib-draft-${id}`;

function readDraft(id: string): Draft | null {
  try {
    const raw = localStorage.getItem(key(id));
    return raw ? (JSON.parse(raw) as Draft) : null;
  } catch {
    return null;
  }
}

function writeDraft(id: string, d: Draft | null) {
  try {
    if (d) localStorage.setItem(key(id), JSON.stringify(d));
    else localStorage.removeItem(key(id));
  } catch {
    /* private mode, or full: the autosave is still the main path */
  }
}

/** The item's text: rendered markdown until you tap it, the editor after.
 *
 *  There is no mode to enter and no button to enter it -- tapping the words is the whole
 *  gesture. CodeMirror is fetched on that first tap, so a note you only read never pays for it.
 *
 *  Saving is debounced rather than a button, which is what the owner chose. Three things make
 *  that safe, and they are the reason this component exists rather than a `useEffect` on the
 *  page: the debounce is flushed on blur and on leaving the page, so a pause before you navigate
 *  cannot lose the last sentence; only one save is ever in flight, so a fast typist cannot send
 *  an edit against a version the previous save has already moved past; and a refused save stops
 *  the loop instead of retrying into the same 409 every two seconds. The state is always on
 *  screen, because an autosave that fails silently is worse than no autosave. */
/** Pull the editor's chunk down quietly once the page is idle.
 *
 *  Two reasons, and the second is why it is here rather than nice-to-have. It hides the beat
 *  between the first tap and the caret. And it is what makes editing text offline possible at
 *  all: `sw.js` caches assets it has fetched before, so a chunk nobody has ever needed is a
 *  chunk that is not there when the network goes. Slice 24 kept the editor out of the install
 *  precache on purpose -- the shell should not carry 600kB for a note you only read -- and this
 *  gets it cached after one unhurried moment online instead, which costs the install nothing. */
function warm() {
  const idle = (window as unknown as { requestIdleCallback?: (cb: () => void) => void }).requestIdleCallback;
  const run = () => void import("./MarkdownEditor").catch(() => {});
  if (idle) idle(run);
  else setTimeout(run, 2000);
}

export default function TextEditor({
  value,
  query,
  onSave,
  blocked,
  draftId,
  queued = false,
}: {
  value: string;
  query: string | null;
  onSave: (text: string, keepalive?: boolean) => Promise<SaveResult>;
  /** A conflict is on screen and unresolved: stop autosaving until it is answered. */
  blocked: boolean;
  /** Identifies the draft held for this item. */
  draftId: string;
  /** An edit for this item is already written down and waiting to go (slice 25). */
  queued?: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [spot, setSpot] = useState<Spot | null>(null);
  const rendered = useRef<HTMLDivElement | null>(null);
  // A draft left by a page that went away before its last save landed.
  const held = readDraft(draftId);
  const restored = held && held.draft !== value ? held.draft : null;
  const [draft, setDraft] = useState(restored ?? value);
  const [status, setStatus] = useState<Status>(restored ? "pending" : queued ? "queued" : "clean");
  const [offline, setOffline] = useState(false);

  const draftRef = useRef(draft);
  const savedRef = useRef(value);
  const inflight = useRef(false);
  const alive = useRef(true);
  draftRef.current = draft;

  const flush = useCallback(async (keepalive = false) => {
    const text = draftRef.current;
    if (text === savedRef.current) return;
    if (!text.trim()) {
      if (alive.current) setStatus("empty");
      return;
    }
    if (inflight.current) return;
    inflight.current = true;
    // The request goes out before anything touches React state. On the way out of a page that
    // order matters: a state update first can defer the fetch past the point where the renderer
    // is gone, and the edit dies with it.
    const sending = onSave(text, keepalive).catch((): SaveResult => "failed");
    if (alive.current) setStatus("saving");
    const result = await sending;
    inflight.current = false;
    if (result === "ok" || result === "queued") {
      savedRef.current = text;
      /* On the server, or written down in the queue which survives the tab closing either way.
         Both mean the localStorage draft -- which only ever covered the seconds between
         keystrokes and a save -- has nothing left to protect. */
      if (draftRef.current === text) writeDraft(draftId, null);
    }
    if (!alive.current) return;
    if (result === "ok" || result === "queued") {
      // Something was typed while that request was out: it is still unsaved, so say so.
      const settled = result === "queued" ? "queued" : "saved";
      setStatus(draftRef.current === text ? settled : "pending");
    } else {
      setOffline(!navigator.onLine);
      // A refusal leaves the text unsaved, and it keeps saying so. The strip above explains what
      // happened; this says what is true of the words. `pending` is safe here because the
      // debounce is paused while `blocked`, so it waits for the answer rather than retrying.
      setStatus(result === "conflict" ? "pending" : "failed");
    }
  }, [onSave, draftId]);

  const flushRef = useRef(flush);
  flushRef.current = flush;
  // While a conflict is unresolved the parent owns the text: Reload and Overwrite both remount
  // this component, and a flush on the way out would send the held draft a second time -- which
  // 409s again and puts the strip straight back up, undoing the choice that was just made.
  const blockedRef = useRef(blocked);
  blockedRef.current = blocked;

  // The debounce. A conflict pauses it rather than letting it retry into the same refusal.
  useEffect(() => {
    if (status !== "pending" || blocked) return;
    const t = setTimeout(() => void flushRef.current(), DEBOUNCE);
    return () => clearTimeout(t);
  }, [draft, status, blocked]);

  // "Saved" is an acknowledgement, not a permanent label.
  useEffect(() => {
    // "Queued" is not an acknowledgement that fades: it is a state the item is in until the
    // network comes back, and the row says the same thing.
    if (status !== "saved") return;
    const t = setTimeout(() => setStatus((s) => (s === "saved" ? "clean" : s)), 2500);
    return () => clearTimeout(t);
  }, [status]);

  useEffect(warm, []);

  /* A save flushed as the page was torn down lands, but the page is gone before it can clear
     the draft it was protecting. Nothing is lost by that -- the restore only fires when the
     draft differs from the server -- but the key would sit there for good, so it goes as soon
     as the server is seen holding the same words. */
  useEffect(() => {
    const held = readDraft(draftId);
    if (held && held.draft === value) writeDraft(draftId, null);
  }, [draftId, value]);

  /* The queue is read from IndexedDB, so `queued` is false on the first render and true a tick
     later. Without this the status is fixed at mount and an item reopened with an edit still
     waiting says nothing at all until you type into it. */
  useEffect(() => {
    if (queued) setStatus((s) => (s === "clean" ? "queued" : s));
    else setStatus((s) => (s === "queued" ? "clean" : s));
  }, [queued]);

  // Leaving the page, and closing the tab. Without this a two-second pause before tapping Back
  // loses whatever came after the last save.
  useEffect(() => {
    alive.current = true;
    // A tab closing or a phone backgrounding tears the page down mid-request, so this one is
    // sent with `keepalive` -- an ordinary fetch is cancelled and the last sentence is lost.
    const onHide = () => {
      if (!blockedRef.current) void flushRef.current(true);
    };
    window.addEventListener("pagehide", onHide);
    document.addEventListener("visibilitychange", onHide);
    return () => {
      window.removeEventListener("pagehide", onHide);
      document.removeEventListener("visibilitychange", onHide);
      alive.current = false;
      if (!blockedRef.current) void flushRef.current(true);
    };
  }, []);

  function enter(e: MouseEvent) {
    if (editing) return;
    // A click that was really a selection drag should not become an edit.
    if (window.getSelection()?.toString()) return;
    const target = e.target as HTMLElement;
    if (target.closest("a")) return; // following a link is not editing
    if (target.closest("input")) return; // nor is ticking a box
    setSpot(rendered.current ? spotFromPoint(rendered.current, e.clientX, e.clientY) : null);
    setEditing(true);
  }

  /** A tick is an edit like any other, and it saves at once: there is no more typing to wait
   *  for. While a conflict is open it only joins the draft, as a keystroke would. */
  function tick(box: number) {
    const next = toggleTask(draftRef.current, box);
    if (next === null) return;
    change(next);
    draftRef.current = next;
    if (!blocked) void flush();
  }

  function change(next: string) {
    setDraft(next);
    setStatus(next === savedRef.current ? "clean" : "pending");
    // Written as it is typed, so a teardown cannot take it.
    writeDraft(draftId, next === savedRef.current ? null : { base: savedRef.current, draft: next });
  }

  return (
    <div className="text-body">
      {editing ? (
        <Suspense fallback={<div className="raw big md-loading">{draft}</div>}>
          <div className="raw big cm-host">
            <MarkdownEditor value={draft} onChange={change} onBlur={() => void flush()} spot={spot} />
          </div>
        </Suspense>
      ) : (
        <div className="raw big" ref={rendered} onClick={enter} role="presentation" title="Click to edit">
          <Markdown text={draft} query={query} onTick={tick} titled />
        </div>
      )}
      <SaveState status={status} offline={offline} onRetry={() => void flush()} />
    </div>
  );
}

function SaveState({ status, offline, onRetry }: { status: Status; offline: boolean; onRetry: () => void }) {
  if (status === "clean") return null;
  if (status === "failed" || status === "empty") {
    return (
      <p className="save-state bad">
        <span className="tone danger">
          {status === "empty" ? "Not saved · the text is empty" : offline ? "Not saved · offline" : "Not saved"}
        </span>
        {status === "failed" && (
          <button type="button" className="link-btn" onClick={onRetry}>
            Retry
          </button>
        )}
      </p>
    );
  }
  if (status === "queued") {
    return (
      <p className="save-state">
        <span className="pending-mark">waiting to send</span>
      </p>
    );
  }
  const label = status === "saving" ? "Saving…" : status === "saved" ? "Saved" : "Unsaved";
  return <p className={`save-state ${status}`}>{label}</p>;
}
