/** The running pomodoro, shared by the bar that shows it and the rows that start it.
 *
 * The server owns the truth: this only renders a countdown against the session's `ends_at`
 * and asks again when the app comes back. Closing the tab loses nothing.
 */
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { answerSession, describe, getCurrentSession, startSession, stopSession } from "./api";
import { playChime, unlockChime } from "./chime";
import { currentSubscription } from "./push";
import type { Outcome, SessionState } from "./types";

/** The session this tab is counting, and the one it has already rung for. Kept in
 *  sessionStorage so a reload (or a wake from frozen) still knows what it was watching: an
 *  in-memory ref is lost exactly when the catch-up below needs it. */
const TRACK_KEY = "tartib-session-tracking";
const RUNG_KEY = "tartib-session-rung";
function readStored(key: string): number | null {
  try {
    const v = sessionStorage.getItem(key);
    return v === null ? null : Number(v);
  } catch {
    return null;
  }
}
function writeStored(key: string, id: number | null): void {
  try {
    if (id === null) sessionStorage.removeItem(key);
    else sessionStorage.setItem(key, String(id));
  } catch {
    /* private mode: the ring still works for a tab that never reloads */
  }
}

interface SessionContextValue {
  current: SessionState | null;
  /** Seconds left, or 0 once the time is up. */
  remaining: number;
  busy: boolean;
  start: (itemId: number | null) => Promise<void>;
  /** Why the last start or stop did not happen, if it did not. */
  error: string | null;
  stop: () => Promise<void>;
  answer: (outcome: Outcome) => Promise<void>;
  reload: () => Promise<void>;
}

const SessionContext = createContext<SessionContextValue | null>(null);

export function useSession(): SessionContextValue {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession outside SessionProvider");
  return ctx;
}

function secondsLeft(endsAt: string | undefined): number {
  if (!endsAt) return 0;
  return Math.max(0, Math.round((new Date(endsAt).getTime() - Date.now()) / 1000));
}

export function SessionProvider({ children, onFinish }: { children: ReactNode; onFinish?: () => void }) {
  const [current, setCurrent] = useState<SessionState | null>(null);
  const [remaining, setRemaining] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // The session this tab has already rung for: the countdown can read zero on more than one tick
  // before the server confirms the end.
  const rung = useRef<number | null>(readStored(RUNG_KEY));
  // The session this tab is counting, so an end it did not watch can still be rung for.
  const tracking = useRef<number | null>(readStored(TRACK_KEY));

  const reload = useCallback(async () => {
    try {
      const next = await getCurrentSession();
      // A session this tab was counting that ended while it was not watching -- the tab left
      // open in the background, where the 1s countdown is throttled or frozen, or the machine
      // asleep -- never reached the zero tick, so nothing ever rang. Ring now instead, once:
      // on the next wake the end is still here to be heard even though the moment was missed.
      // Not when this device has push: the notification is the announcer for that case, and a
      // chime on top of it is the nagging rule 4 exists to prevent (owner, 2026-10-07).
      const ended = next.state === "awaiting" ? next.session : null;
      if (
        ended &&
        ended.id === tracking.current &&
        ended.id !== rung.current &&
        ended.ended_at !== null &&
        // Exactly equal is the only ran-out: the server stamps ended_at = ends_at when the
        // clock runs down (close_finished) and when the outcome is set (set_outcome), while a
        // hand-stop stamps now, which is strictly past ends_at whenever Stop is tapped after
        // the time was up. Equality keeps the ran-out; everything later is a hand-stop.
        ended.ended_at === ended.ends_at &&
        // A push check that fails is read as no push: a missed announcement is worse than a
        // late one, and it must never cost the state update below.
        (await currentSubscription().catch(() => null)) === null &&
        // Re-asserted after that await: coming back to the tab fires visibilitychange and
        // focus together, so a second reload() can be in flight and pass the tests above
        // while this one is suspended at the await. Whichever caller resumes last sees
        // rung.current already set, and only the other rings -- one end, one ring.
        ended.id !== rung.current
      ) {
        rung.current = ended.id;
        writeStored(RUNG_KEY, ended.id);
        void playChime();
      }
      if (next.state === "running" && next.session) {
        tracking.current = next.session.id;
        writeStored(TRACK_KEY, next.session.id);
      } else if (next.state === null) {
        tracking.current = null;
        writeStored(TRACK_KEY, null);
      }
      setCurrent(next);
      setRemaining(secondsLeft(next.session?.ends_at));
    } catch {
      /* not signed in yet, or offline; the bar simply does not appear */
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  // The countdown is the browser's clock against the server's end time. They drift by
  // seconds; the server is the truth, which is why the end is confirmed by asking again.
  useEffect(() => {
    if (current?.state !== "running") return;
    const tick = () => {
      const left = secondsLeft(current.session?.ends_at);
      setRemaining(left);
      if (left === 0) {
        // A countdown watched to zero rings here. A session stopped by hand never gets here;
        // one that ended while this tab was not watching is caught by `reload` instead.
        const id = current.session?.id ?? null;
        if (id !== null && rung.current !== id) {
          rung.current = id;
          writeStored(RUNG_KEY, id);
          void playChime();
        }
        void reload();
      }
    };
    tick();
    const id = window.setInterval(tick, 1000);
    return () => window.clearInterval(id);
  }, [current, reload]);

  // Coming back to the app is when to re-ask: a session may have ended while it was away.
  useEffect(() => {
    const check = () => document.visibilityState === "visible" && void reload();
    document.addEventListener("visibilitychange", check);
    window.addEventListener("focus", check);
    return () => {
      document.removeEventListener("visibilitychange", check);
      window.removeEventListener("focus", check);
    };
  }, [reload]);

  const act = useCallback(
    async (fn: () => Promise<unknown>) => {
      setBusy(true);
      setError(null);
      try {
        await fn();
        await reload();
      } catch (err) {
        /* A session is not queued: a timer you start with no network is a fiction, and the
           server is what holds the clock. So it says what is wrong instead (slice 25). */
        setError(describe(err));
      } finally {
        setBusy(false);
      }
    },
    [reload],
  );

  const value: SessionContextValue = {
    current,
    remaining,
    busy,
    error,
    reload,
    start: (itemId) => {
      unlockChime(); // inside the tap, or iOS will not play the chime at the end
      return act(() => startSession(itemId));
    },
    stop: () => act(() => (current?.session ? stopSession(current.session.id) : Promise.resolve())),
    answer: (outcome) =>
      act(async () => {
        if (current?.session) await answerSession(current.session.id, outcome);
        onFinish?.();
      }),
  };
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function formatRemaining(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}
