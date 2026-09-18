/** The running pomodoro, shared by the bar that shows it and the rows that start it.
 *
 * The server owns the truth: this only renders a countdown against the session's `ends_at`
 * and asks again when the app comes back. Closing the tab loses nothing.
 */
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { answerSession, getCurrentSession, startSession, stopSession } from "./api";
import type { Outcome, SessionState } from "./types";

interface SessionContextValue {
  current: SessionState | null;
  /** Seconds left, or 0 once the time is up. */
  remaining: number;
  busy: boolean;
  start: (itemId: number | null) => Promise<void>;
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

  const reload = useCallback(async () => {
    try {
      const next = await getCurrentSession();
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
      if (left === 0) void reload();
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
      try {
        await fn();
        await reload();
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
    reload,
    start: (itemId) => act(() => startSession(itemId)),
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
