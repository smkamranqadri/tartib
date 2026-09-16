import { useEffect, useState } from "react";
import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { logout, setUnauthorizedHandler } from "./api";
import Capture from "./Capture";
import Login from "./screens/Login";

function Placeholder({ name }: { name: string }) {
  return <section className="screen"><h2>{name}</h2><p className="muted">Coming in the next phase.</p></section>;
}

export default function App() {
  const [authed, setAuthed] = useState(true);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    setUnauthorizedHandler(() => setAuthed(false));
  }, []);

  if (!authed) return <Login onLoggedIn={() => setAuthed(true)} />;

  return (
    <div className="app">
      <header>
        <nav>
          <NavLink to="/today">Today</NavLink>
          <NavLink to="/attention">Needs Attention</NavLink>
          <NavLink to="/all">All</NavLink>
        </nav>
        <button
          className="link"
          onClick={() => logout().then(() => setAuthed(false))}
          type="button"
        >
          Log out
        </button>
      </header>
      <Capture onCaptured={() => setTick((t) => t + 1)} />
      <Routes>
        <Route path="/" element={<Navigate to="/today" replace />} />
        <Route path="/today" element={<Placeholder key={tick} name="Today" />} />
        <Route path="/attention" element={<Placeholder key={tick} name="Needs Attention" />} />
        <Route path="/all" element={<Placeholder key={tick} name="All" />} />
      </Routes>
    </div>
  );
}
