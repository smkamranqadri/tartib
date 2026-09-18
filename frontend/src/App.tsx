import { useEffect, useRef, useState } from "react";
import { NavLink, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { getCapture, getSpaces, setUnauthorizedHandler } from "./api";
import { type Pending, onPending, watchForReconnect } from "./offline";
import { takePendingNav } from "./push";
import Capture from "./Capture";
import AskBar from "./components/AskBar";
import { HomeIcon, InboxIcon, LayersIcon, SettingsIcon } from "./components/Icons";
import SessionBar from "./components/SessionBar";
import Toast, { type ToastState } from "./components/Toast";
import UpdateBar from "./components/UpdateBar";
import Home from "./screens/Home";
import Inbox from "./screens/Inbox";
import ItemPage from "./screens/ItemPage";
import Login from "./screens/Login";
import Recent from "./screens/Recent";
import Space from "./screens/Space";
import Spaces from "./screens/Spaces";
import Waiting from "./screens/Waiting";
import Settings from "./screens/Settings";
import { SessionProvider } from "./session";
import { ThemeContext, type Theme } from "./theme";
import type { Answer, Capture as CaptureRecord } from "./types";
import { useLoad } from "./useLoad";

function readTheme(): Theme {
  try {
    const t = localStorage.getItem("tartib-theme");
    if (t === "light" || t === "dark") return t;
  } catch {
    /* storage unavailable */
  }
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

/** "Filed as task in namazee", "Needs your look", "Filed 2 tasks · 1 needs your look", "Answered". */
function outcome(cap: CaptureRecord): string {
  if (cap.answer && cap.items.length === 0) return "Answered";
  const filed = cap.items.filter((i) => i.stage === "filed");
  const waiting = cap.items.length - filed.length;
  if (cap.items.length === 1) {
    const [it] = cap.items;
    return it.stage === "filed" ? `Filed as ${it.shape} in ${it.space}` : "Needs your look";
  }
  const parts: string[] = [];
  if (filed.length) parts.push(`Filed ${filed.length} ${filed.every((i) => i.shape === "task") ? "tasks" : "items"}`);
  if (waiting) parts.push(`${waiting} need${waiting === 1 ? "s" : ""} your look`);
  if (cap.answer) parts.push("answered");
  return parts.join(" · ") || "Saved";
}

export default function App() {
  const [authed, setAuthed] = useState(true);
  const [version, setVersion] = useState(0);
  const [theme, setTheme] = useState<Theme>(readTheme);
  const [toast, setToast] = useState<ToastState | null>(null);
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [pending, setPending] = useState<Pending[]>([]);
  const pollRef = useRef(0);
  const toastTimer = useRef<number | null>(null);
  const navigate = useNavigate();

  /* A tapped reminder routes here instead of reloading the page, so whatever is half-typed
     in the capture bar survives. A running page hears the message; one that was asleep when
     the tap happened -- every iOS home-screen app is -- finds the note when it wakes.

     `useNavigate` returns a new function on every route change, so it is held in a ref: as a
     dependency it would tear this down and restart the retries each time you moved around. */
  const navigateRef = useRef(navigate);
  navigateRef.current = navigate;
  useEffect(() => {
    let consuming = false;
    const timers = new Set<number>();
    const check = async () => {
      // Only one reader at a time: taking the note is a read then a delete, and two readers
      // can both see it and both navigate, leaving a Back press that appears to do nothing.
      if (consuming || document.visibilityState !== "visible") return;
      consuming = true;
      try {
        const url = await takePendingNav();
        if (url) navigateRef.current(url);
      } finally {
        consuming = false;
      }
    };
    /* iOS does not reliably fire any resume event a home-screen app can hear, so waking looks
       for the note a few times rather than trusting one event. Bounded, and only on a resume:
       a timer that outlives that would cost battery for something that may never come. */
    const wake = () => {
      let left = 6;
      const id = window.setInterval(() => {
        void check();
        if ((left -= 1) <= 0) {
          window.clearInterval(id);
          timers.delete(id);
        }
      }, 500);
      timers.add(id);
    };
    /* The worker writes the note before it messages anyone, so this only has to look. Acting
       on the message directly would race the same note and navigate twice. */
    const onMessage = (event: MessageEvent) => {
      if (event.data?.type === "tartib:navigate") void check();
    };

    if ("serviceWorker" in navigator) navigator.serviceWorker.addEventListener("message", onMessage);
    document.addEventListener("visibilitychange", wake);
    window.addEventListener("focus", wake);
    window.addEventListener("pageshow", wake);
    void check();
    return () => {
      if ("serviceWorker" in navigator) navigator.serviceWorker.removeEventListener("message", onMessage);
      document.removeEventListener("visibilitychange", wake);
      window.removeEventListener("focus", wake);
      window.removeEventListener("pageshow", wake);
      for (const id of timers) window.clearInterval(id);
    };
  }, []);
  const location = useLocation();
  const bump = () => setVersion((v) => v + 1);

  /* The queue, and sending it when the network or the app comes back. A capture that landed
     this way was typed minutes ago, so it gets a quiet line rather than the full outcome
     toast: the answer to "did my capture survive" is that it is on the list now. */
  useEffect(() => onPending(setPending), []);
  useEffect(
    () =>
      watchForReconnect((result) => {
        bump();
        if (result.rejected.length) showToast({ text: result.rejected[0], phase: "final" });
        else if (result.sent.length)
          showToast({
            text: `Sent ${result.sent.length} capture${result.sent.length === 1 ? "" : "s"}`,
            phase: "final",
          });
      }),
    [],
  );
  const spaces = useLoad(getSpaces, [authed]).data?.spaces ?? [];
  const onSearchPage = location.pathname.startsWith("/spaces") || location.pathname.startsWith("/search");
  const showChat = location.pathname === "/" || location.pathname === "/inbox";

  useEffect(() => {
    setUnauthorizedHandler(() => setAuthed(false));
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    /* The status bar should agree with the theme you picked. index.html carries one of these
       per colour scheme so the first paint is right; this corrects it when the chosen theme
       is not the system's. Both are updated, or the media queries would fight this back. */
    const bar = theme === "dark" ? "#0f1412" : "#f2f5f3";
    for (const meta of document.querySelectorAll('meta[name="theme-color"]')) {
      meta.setAttribute("content", bar);
    }
    try {
      localStorage.setItem("tartib-theme", theme);
    } catch {
      /* ignore */
    }
  }, [theme]);

  // keyboard: c -> capture bar, / -> search field on Search
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const t = e.target as HTMLElement | null;
      if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT" || t.isContentEditable)) return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.key === "c") {
        e.preventDefault();
        window.dispatchEvent(new Event("tartib:focus-capture"));
      } else if (e.key === "/" && onSearchPage) {
        e.preventDefault();
        window.dispatchEvent(new Event("tartib:focus-search"));
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onSearchPage, navigate]);

  function showToast(next: ToastState) {
    if (toastTimer.current) window.clearTimeout(toastTimer.current);
    setToast(next);
    if (next.phase === "final") toastTimer.current = window.setTimeout(() => setToast(null), 4000);
  }

  /** Follow a capture until the runner is done; toast the outcome, show an answer if any. */
  function onCaptured(id: number) {
    bump();
    setAnswer(null);
    showToast({ text: "Saved", phase: "busy" });
    const token = ++pollRef.current;
    const started = Date.now();
    const tick = async () => {
      if (pollRef.current !== token) return;
      try {
        const cap = await getCapture(id);
        if (cap.status !== "pending") {
          bump();
          if (cap.answer) {
            setAnswer(cap.answer);
            if (location.pathname !== "/") navigate("/");
          }
          showToast({ text: cap.status === "error" ? "Needs your look" : outcome(cap), phase: "final" });
          return;
        }
      } catch {
        /* keep polling */
      }
      if (Date.now() - started < 120_000) setTimeout(tick, 1000);
      else showToast({ text: "Still filing…", phase: "final" });
    };
    setTimeout(tick, 1000);
  }

  if (!authed) return <Login onLoggedIn={() => setAuthed(true)} />;

  return (
    <ThemeContext.Provider value={{ theme, setTheme }}>
      <SessionProvider onFinish={bump}>
      <div className={`app ${showChat ? "has-askbar" : ""}`}>
        <header className="top">
          <NavLink to="/" className="brand" end>
            <img className="brand-mark" src="/icon-192.png" alt="" width={28} height={28} />
            <span className="brand-name">Tartib</span>
            <span className="brand-ar" lang="ur">ترتیب</span>
          </NavLink>
          <nav className="pills">
            <NavLink to="/" end>
              <HomeIcon /> Home
            </NavLink>
            <NavLink to="/inbox">
              <InboxIcon /> Inbox
            </NavLink>
            <NavLink to="/spaces" className={onSearchPage ? "active" : undefined}>
              <LayersIcon /> Spaces
            </NavLink>
            <NavLink to="/settings">
              <SettingsIcon /> Settings
            </NavLink>
          </nav>
          <div className="top-actions" />
        </header>
        <UpdateBar />
        <Capture
          onCaptured={onCaptured}
          onQueued={() => showToast({ text: "Saved offline", phase: "final" })}
        />
        <SessionBar />
        <main>
          <Routes>
            <Route path="/" element={<Home version={version} answer={answer} pending={pending} onCloseAnswer={() => setAnswer(null)} />} />
            <Route path="/today" element={<Navigate to="/" replace />} />
            <Route path="/inbox" element={<Inbox version={version} onDecided={bump} />} />
            <Route path="/inbox/attention" element={<Waiting version={version} onDecided={bump} />} />
            <Route path="/inbox/recent" element={<Recent version={version} pending={pending} />} />
            <Route path="/attention" element={<Navigate to="/inbox" replace />} />
            <Route path="/attention/all" element={<Navigate to="/inbox/attention" replace />} />
            <Route path="/recent" element={<Navigate to="/inbox/recent" replace />} />
            <Route path="/spaces" element={<Spaces version={version} onChanged={bump} />} />
            <Route path="/spaces/:name" element={<Space version={version} onChanged={bump} />} />
            <Route path="/search" element={<Navigate to="/spaces" replace />} />
            <Route path="/all" element={<Navigate to="/spaces" replace />} />
            <Route path="/settings" element={<Settings onSignedOut={() => setAuthed(false)} />} />
            <Route path="/items/:id" element={<ItemPage version={version} />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
        {showChat && <AskBar spaces={spaces} />}
        <Toast toast={toast} />
      </div>
      </SessionProvider>
    </ThemeContext.Provider>
  );
}
