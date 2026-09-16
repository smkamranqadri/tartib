import { useEffect, useState } from "react";
import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { logout, setUnauthorizedHandler } from "./api";
import Capture from "./Capture";
import All from "./screens/All";
import Attention from "./screens/Attention";
import Login from "./screens/Login";
import Today from "./screens/Today";

export default function App() {
  const [authed, setAuthed] = useState(true);
  const [version, setVersion] = useState(0);
  const bump = () => setVersion((v) => v + 1);

  useEffect(() => {
    setUnauthorizedHandler(() => setAuthed(false));
  }, []);

  // Classification finishes shortly after a capture; refresh once so the result shows up.
  function onCaptured() {
    bump();
    setTimeout(bump, 4000);
  }

  if (!authed) return <Login onLoggedIn={() => setAuthed(true)} />;

  return (
    <div className="app">
      <header>
        <nav>
          <NavLink to="/today">Today</NavLink>
          <NavLink to="/attention">Needs Attention</NavLink>
          <NavLink to="/all">All</NavLink>
        </nav>
        <button className="link" onClick={() => logout().then(() => setAuthed(false))} type="button">
          Log out
        </button>
      </header>
      <Capture onCaptured={onCaptured} />
      <Routes>
        <Route path="/" element={<Navigate to="/today" replace />} />
        <Route path="/today" element={<Today version={version} />} />
        <Route path="/attention" element={<Attention version={version} onDecided={bump} />} />
        <Route path="/all" element={<All version={version} />} />
      </Routes>
    </div>
  );
}
