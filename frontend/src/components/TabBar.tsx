import { useEffect, useRef } from "react";
import { NavLink } from "react-router-dom";
import { HomeIcon, InboxIcon, LayersIcon, SettingsIcon } from "./Icons";

/** The phone's navigation, under the thumb. Hidden on wide screens, where the header's pills do
 *  the same job. The ⊕ in the middle is capture (and, from step 2, ask). */
export default function TabBar({ onAdd }: { onAdd: () => void }) {
  // Its height is published, so the ask bar and the session card stack above it exactly.
  const ref = useRef<HTMLElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const root = document.documentElement;
    const obs = new ResizeObserver(() => root.style.setProperty("--tabbar-h", `${el.offsetHeight}px`));
    obs.observe(el);
    return () => {
      obs.disconnect();
      root.style.removeProperty("--tabbar-h");
    };
  }, []);

  return (
    <nav className="tabbar" ref={ref} aria-label="Sections">
      <NavLink to="/" end>
        <HomeIcon />
        <span>Home</span>
      </NavLink>
      <NavLink to="/inbox">
        <InboxIcon />
        <span>Inbox</span>
      </NavLink>
      <button type="button" className="tab-add" onClick={onAdd} aria-label="Capture">
        <span aria-hidden="true">+</span>
      </button>
      <NavLink to="/spaces">
        <LayersIcon />
        <span>Spaces</span>
      </NavLink>
      <NavLink to="/settings">
        <SettingsIcon />
        <span>Settings</span>
      </NavLink>
    </nav>
  );
}
