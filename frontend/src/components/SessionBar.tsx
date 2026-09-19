import { getRecentSessions } from "../api";
import { formatRemaining, useSession } from "../session";
import { useLoad } from "../useLoad";
import { describe } from "./SessionPast";

/** The running session, or the question that follows it. It sits under the capture bar on
 *  every screen, so a session is never something you have to go and look for.
 *
 *  The outcome is asked inline rather than in a modal: this product has no dialogs, and a
 *  sheet that blocks the app to ask about 25 minutes that already happened would be the
 *  nagging rule 4 exists to prevent. */
export default function SessionBar() {
  const { current, remaining, busy, stop, answer } = useSession();
  const state = current?.state ?? null;
  // The last few, shown once a session has stopped. Fetched when the card turns to its question.
  const past = useLoad(() => (state === "awaiting" ? getRecentSessions(4) : Promise.resolve(null)), [state, current?.session?.id]);
  if (!current || state === null) return null;

  const what = current.item?.title || current.item?.raw_text.split("\n")[0] || "No task";

  if (state === "running") {
    const s = current.session;
    const total = s ? Math.max(1, (new Date(s.ends_at).getTime() - new Date(s.started_at).getTime()) / 1000) : 1;
    return (
      <div className="session-bar running" role="status">
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
  return (
    <div className="session-bar done">
      <Ring fraction={0} />
      <div className="session-main">
        <span className="session-time">Session done</span>
        <span className="session-what muted">{what}</span>
      </div>
      <div className="session-outcomes">
        <button type="button" className="primary" disabled={busy} onClick={() => void answer("done")}>
          Done
        </button>
        <button type="button" className="ghost" disabled={busy} onClick={() => void answer("unfinished")}>
          Not finished
        </button>
        <button type="button" className="ghost" disabled={busy} onClick={() => void answer("abandoned")}>
          Abandoned
        </button>
      </div>
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
  const { current, busy, start } = useSession();
  if (current?.state === "running") return null;
  return (
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
  );
}
