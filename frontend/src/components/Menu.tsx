import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

export interface MenuItem {
  label: string;
  /** Renders a link instead of a button. */
  to?: string;
  onSelect?: () => void;
  danger?: boolean;
  disabled?: boolean;
  title?: string;
}

/** The "…" dropdown. Closes on selection, on Escape, and when you click outside it. */
export default function Menu({ items, label = "More" }: { items: MenuItem[]; label?: string }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (!open) return;
    function onDown(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    window.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      window.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <span className="more" ref={ref}>
      <button type="button" className="icon-btn" aria-label={label} aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        …
      </button>
      {open && (
        <span className="menu">
          {items.map((item) =>
            item.to ? (
              <Link key={item.label} to={item.to} onClick={() => setOpen(false)}>
                {item.label}
              </Link>
            ) : (
              <button
                key={item.label}
                type="button"
                className={item.danger ? "danger" : ""}
                disabled={item.disabled}
                title={item.title}
                onClick={() => {
                  setOpen(false);
                  item.onSelect?.();
                }}
              >
                {item.label}
              </button>
            ),
          )}
        </span>
      )}
    </span>
  );
}
