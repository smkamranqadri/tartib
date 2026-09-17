import { useEffect, useRef, useState } from "react";
import { NavLink, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { getCapture, getSpaces, setUnauthorizedHandler } from "./api";
import Capture from "./Capture";
import AskBar from "./components/AskBar";
import { HomeIcon, InboxIcon, LayersIcon, SettingsIcon } from "./components/Icons";
import Toast, { type ToastState } from "./components/Toast";
import Home from "./screens/Home";
import Inbox from "./screens/Inbox";
import ItemPage from "./screens/ItemPage";
import Login from "./screens/Login";
import Recent from "./screens/Recent";
import Space from "./screens/Space";
import Spaces from "./screens/Spaces";
import Waiting from "./screens/Waiting";
import Settings from "./screens/Settings";
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
  const pollRef = useRef(0);
  const toastTimer = useRef<number | null>(null);
  const navigate = useNavigate();
  const location = useLocation();
  const bump = () => setVersion((v) => v + 1);
  const spaces = useLoad(getSpaces, [authed]).data?.spaces ?? [];
  const onSearchPage = location.pathname.startsWith("/spaces") || location.pathname.startsWith("/search");
  const showChat = location.pathname === "/" || location.pathname === "/inbox";

  useEffect(() => {
    setUnauthorizedHandler(() => setAuthed(false));
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
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
        <Capture onCaptured={onCaptured} />
        <main>
          <Routes>
            <Route path="/" element={<Home version={version} answer={answer} onCloseAnswer={() => setAnswer(null)} />} />
            <Route path="/today" element={<Navigate to="/" replace />} />
            <Route path="/inbox" element={<Inbox version={version} onDecided={bump} />} />
            <Route path="/inbox/attention" element={<Waiting version={version} onDecided={bump} />} />
            <Route path="/inbox/recent" element={<Recent version={version} />} />
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
    </ThemeContext.Provider>
  );
}
