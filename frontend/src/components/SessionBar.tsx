import { type ReactElement, useEffect, useRef, useState } from "react";
import { getRecentSessions } from "../api";
import { flattenFirstLine } from "../markdown";
import { formatRemaining, useSession } from "../session";
import { useLoad } from "../useLoad";
import Card from "./Card";
import { ClockIcon } from "./Icons";
import Modal from "./Modal";
import { describe } from "./SessionPast";

/** The session: running, waiting for its outcome, or none with the recent ones to run again.
 *
 *  `card` is Home's: an ordinary dashboard card, in every state. `float` is every other page's:
 *  pinned above the ask bar, and only while a session is live -- running, or ended and waiting
 *  for its outcome -- so a session is never something you have to go and look for.
 *
 *  The outcome is asked in a modal (slice 31, the owner's call: every question in the app asks
 *  in one). It opens once when a session ends, and "Later" closes it for good for that session
 *  -- the bar keeps an Answer button -- because a question that reopens on every page would be
 *  the nagging rule 4 exists to prevent. Only one SessionBar is ever mounted (the card on Home,
 *  the float elsewhere), so there is only ever one modal. The sessions put off are kept for the
 *  tab in sessionStorage, so reopening the app does not ask again either; a new session does. */
const LATER_KEY = "tartib-session-later";
function putOff(id: number) {
  try {
    sessionStorage.setItem(LATER_KEY, String(id));
  } catch {
    /* storage refused: the modal just asks again next time the bar mounts */
  }
}
function isPutOff(id: number): boolean {
  try {
    return sessionStorage.getItem(LATER_KEY) === String(id);
  } catch {
    return false;
  }
}
export default function SessionBar({ placement }: { placement: "card" | "float" }) {
  const { current, remaining, busy, stop, answer, start, error } = useSession();
  const state = current?.state ?? null;
  const endedId = state === "awaiting" ? current?.session?.id ?? null : null;
  const [asking, setAsking] = useState(false);
  useEffect(() => {
    setAsking(endedId !== null && !isPutOff(endedId));
  }, [endedId]);
  const later = () => {
    if (endedId !== null) putOff(endedId);
    setAsking(false);
  };
  // The last few, on Home's card only: floating above the ask bar it would be a list in the
  // way of the page. Under the question once a session stops, on their own when none runs.
  const past = useLoad(
    () =>
      placement === "card" && current && state !== "running"
        ? getRecentSessions(4)
        : Promise.resolve(null),
    [placement, !!current, state, current?.session?.id],
  );
  // A floating card is fixed above the ask bar; it publishes its height (plus the gap) so the
  // page leaves room for it and the toast clears it. Gone, it takes the room back.
  const floatRef = useRef<HTMLDivElement>(null);
  const floating = placement === "float" && !!current && state !== null;
  useEffect(() => {
    const el = floatRef.current;
    const root = document.documentElement;
    if (!floating || !el) return;
    const obs = new ResizeObserver(() => root.style.setProperty("--session-h", `${el.offsetHeight + 10}px`));
    obs.observe(el);
    return () => {
      obs.disconnect();
      root.style.removeProperty("--session-h");
    };
  }, [floating, state]);

  if (!current) return null; // not loaded yet
  if (placement === "float" && state === null) return null; // quiet pages show only a live one
  const wrap = (body: ReactElement) =>
    placement === "card" ? (
      <Card className="area-session" icon={<ClockIcon />} label="Session">
        {body}
      </Card>
    ) : (
      body
    );

  if (state === null) {
    const recent = (past.data?.sessions ?? []).slice(0, 3);
    return wrap(
      <div ref={floatRef} className={`session-bar idle${placement === "float" ? " floating" : ""}`}>
        <Ring fraction={0} />
        <div className="session-main">
          <span className="session-time">No session running</span>
          <span className="session-what muted">
            {error ?? (recent.length ? "Run one again, or start fresh." : "Start one when you are ready.")}
          </span>
        </div>
        <button type="button" className="ghost" disabled={busy} onClick={() => void start(null)}>
          Start
        </button>
        {recent.length > 0 && (
          <ul className="session-past" aria-label="Recent sessions">
            {recent.map((p) => {
              const d = describe(p);
              return (
                <li key={p.id}>
                  <span className="what">{d.what}</span>
                  <span className="session-again">
                    <span className="muted">{d.meta}</span>
                    <button
                      type="button"
                      className="icon-btn"
                      disabled={busy}
                      onClick={() => void start(p.item_id)}
                      aria-label={`Start again: ${d.what}`}
                      title="Start again"
                    >
                      ▶
                    </button>
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    );
  }

  const what = current.item?.title || flattenFirstLine(current.item?.raw_text ?? "") || "No task";

  if (state === "running") {
    const s = current.session;
    const total = s ? Math.max(1, (new Date(s.ends_at).getTime() - new Date(s.started_at).getTime()) / 1000) : 1;
    return wrap(
      <div ref={floatRef} className={`session-bar running${placement === "float" ? " floating" : ""}`} role="status">
        <Ring fraction={remaining / total} />
        <div className="session-main">
          <span className="session-time">{formatRemaining(remaining)}</span>
          <span className="session-what muted">{what}</span>
        </div>
        <button type="button" className="ghost" disabled={busy} onClick={() => void stop()}>
          Stop
        </button>
      </div>
    );
  }

  // The one being asked about is itself the newest finished session; the list is the ones before.
  const earlier = (past.data?.sessions ?? []).filter((p) => p.id !== current.session?.id).slice(0, 3);
  return wrap(
    <div ref={floatRef} className={`session-bar done${placement === "float" ? " floating" : ""}`}>
      <Ring fraction={0} />
      <div className="session-main">
        <span className="session-time">Session done</span>
        <span className="session-what muted">{what}</span>
      </div>
      <button type="button" className="primary" disabled={busy} onClick={() => setAsking(true)}>
        Answer
      </button>
      <Modal
        open={asking}
        title="How did the session go?"
        onClose={later}
        actions={
          <>
            <button type="button" className="ghost" disabled={busy} onClick={later}>
              Later
            </button>
            <button type="button" className="ghost" disabled={busy} onClick={() => void answer("abandoned")}>
              Abandoned
            </button>
            <button type="button" className="ghost" disabled={busy} onClick={() => void answer("unfinished")}>
              Not finished
            </button>
            <button type="button" className="primary" disabled={busy} onClick={() => void answer("done")}>
              Done
            </button>
          </>
        }
      >
        {what}
      </Modal>
      {earlier.length > 0 && (
        <ul className="session-past" aria-label="Earlier sessions">
          {earlier.map((p) => {
            const d = describe(p);
            return (
              <li key={p.id}>
                <span className="what">{d.what}</span>
                <span className="muted">{d.meta}</span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

/** Time left as a ring that empties clockwise from the top. */
function Ring({ fraction }: { fraction: number }) {
  const r = 20;
  const c = 2 * Math.PI * r;
  const f = Math.min(1, Math.max(0, fraction));
  return (
    <svg className="session-ring" viewBox="0 0 48 48" aria-hidden="true">
      <circle className="track" cx="24" cy="24" r={r} fill="none" strokeWidth="4" />
      <circle className="left" cx="24" cy="24" r={r} fill="none" strokeWidth="4" strokeLinecap="round" strokeDasharray={c} strokeDashoffset={c * (1 - f)} transform="rotate(-90 24 24)" />
    </svg>
  );
}

/** Start a session on this task, or on nothing. Hidden while one is already running: one at
 *  a time, so the control is never offered where it would only earn a 409. */
export function StartSession({
  itemId,
  className = "icon-btn",
  label,
}: {
  itemId: number | null;
  className?: string;
  /** Given, the button reads as words. Without it, it is the row's play glyph. */
  label?: string;
}) {
  const { current, busy, start, error } = useSession();
  if (current?.state === "running") return null;
  return (
    <>
      <button
        type="button"
        className={className}
        disabled={busy}
        onClick={() => void start(itemId)}
        aria-label={label ?? "Start session"}
        title="Start a session"
      >
        {label ?? "▶"}
      </button>
      {/* Offline the session bar does not render at all -- `getCurrentSession` fails and it
          stays away by design -- so without this the button is the only thing on screen and
          pressing it would do nothing visible. A session is not queued (slice 25), so the
          honest answer belongs next to the button that cannot do it. */}
      {error && <span className="error small">{error}</span>}
    </>
  );
}
