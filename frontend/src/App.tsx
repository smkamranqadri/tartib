import { useEffect, useRef, useState } from "react";
import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { getCapture, logout, setUnauthorizedHandler } from "./api";
import Capture from "./Capture";
import AnswerView from "./components/AnswerView";
import All from "./screens/All";
import Attention from "./screens/Attention";
import ItemPage from "./screens/ItemPage";
import Login from "./screens/Login";
import Today from "./screens/Today";
import type { Answer } from "./types";

type Theme = "light" | "dark";

function readTheme(): Theme {
  try {
    const t = localStorage.getItem("tartib-theme");
    if (t === "light" || t === "dark") return t;
  } catch {
    /* storage unavailable */
  }
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export default function App() {
  const [authed, setAuthed] = useState(true);
  const [version, setVersion] = useState(0);
  const [theme, setTheme] = useState<Theme>(readTheme);
  const [filing, setFiling] = useState<string | null>(null);
  const [answer, setAnswer] = useState<Answer | null>(null);
  const pollRef = useRef(0);
  const bump = () => setVersion((v) => v + 1);

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

  /** Follow a capture until the runner is done; show an answer if it was a question. */
  function onCaptured(id: number) {
    bump();
    setAnswer(null);
    setFiling("Filing…");
    const token = ++pollRef.current;
    const started = Date.now();
    const tick = async () => {
      if (pollRef.current !== token) return;
      try {
        const cap = await getCapture(id);
        if (cap.status !== "pending") {
          setFiling(null);
          bump();
          if (cap.answer) setAnswer(cap.answer);
          return;
        }
      } catch {
        /* keep polling */
      }
      if (Date.now() - started < 120_000) setTimeout(tick, 1000);
      else setFiling(null);
    };
    setTimeout(tick, 1000);
  }

  if (!authed) return <Login onLoggedIn={() => setAuthed(true)} />;

  return (
    <div className="app">
      <header className="top">
        <div className="brand">
          <img className="brand-mark" src="/icon-192.png" alt="" width={28} height={28} />
          <span className="brand-name">Tartib</span>
        </div>
        <nav className="pills">
          <NavLink to="/today">
            <span aria-hidden>◷</span> Today
          </NavLink>
          <NavLink to="/attention">
            <span aria-hidden>◔</span> Needs Attention
          </NavLink>
          <NavLink to="/all">
            <span aria-hidden>≡</span> All
          </NavLink>
        </nav>
        <div className="top-actions">
          <button
            className="icon-btn"
            type="button"
            onClick={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
            aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
            title="Theme"
          >
            {theme === "dark" ? "☀" : "☾"}
          </button>
          <button className="link" onClick={() => logout().then(() => setAuthed(false))} type="button">
            Log out
          </button>
        </div>
      </header>
      <main>
        <Capture onCaptured={onCaptured} />
        {filing && <p className="filing muted">{filing}</p>}
        {answer && <AnswerView result={answer} onClose={() => setAnswer(null)} />}
        <Routes>
          <Route path="/" element={<Navigate to="/today" replace />} />
          <Route path="/today" element={<Today version={version} />} />
          <Route path="/attention" element={<Attention version={version} onDecided={bump} />} />
          <Route path="/all" element={<All version={version} />} />
          <Route path="/items/:id" element={<ItemPage version={version} />} />
          <Route path="*" element={<Navigate to="/today" replace />} />
        </Routes>
      </main>
    </div>
  );
}
