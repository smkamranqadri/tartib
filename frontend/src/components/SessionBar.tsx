import { formatRemaining, useSession } from "../session";
import { ClockIcon } from "./Icons";

/** The running session, or the question that follows it. It sits under the capture bar on
 *  every screen, so a session is never something you have to go and look for.
 *
 *  The outcome is asked inline rather than in a modal: this product has no dialogs, and a
 *  sheet that blocks the app to ask about 25 minutes that already happened would be the
 *  nagging rule 4 exists to prevent. */
export default function SessionBar() {
  const { current, remaining, busy, stop, answer } = useSession();
  if (!current || current.state === null) return null;

  const what = current.item?.title || current.item?.raw_text.split("\n")[0] || "No task";

  if (current.state === "running") {
    return (
      <div className="session-bar" role="status">
        <span className="session-icon muted">
          <ClockIcon />
        </span>
        <span className="session-time">{formatRemaining(remaining)}</span>
        <span className="session-what muted">{what}</span>
        <button type="button" className="ghost" disabled={busy} onClick={() => void stop()}>
          Stop
        </button>
      </div>
    );
  }

  return (
    <div className="session-bar done">
      <span className="session-time">Session done</span>
      <span className="session-what muted">{what}</span>
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
    </div>
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
