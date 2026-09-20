import { useState } from "react";
import type { Item } from "../../types";
import ItemPage from "../ItemPage";
import { ItemLine, isOverdue, useSpaceItems } from "./shared";

type Branch = { key: string; label: string; keep: (i: Item) => boolean; children?: Branch[] };

const TREE: Branch[] = [
  {
    key: "tasks",
    label: "Tasks",
    keep: (i) => i.shape === "task",
    children: [
      { key: "overdue", label: "Overdue", keep: (i) => isOverdue(i) },
      { key: "open", label: "Open", keep: (i) => i.shape === "task" && i.status === "open" && !isOverdue(i) },
      { key: "done", label: "Done", keep: (i) => i.shape === "task" && i.status === "done" },
    ],
  },
  { key: "notes", label: "Notes", keep: (i) => i.shape === "note" },
];

/** Tree: the space as branches you open and close -- Tasks (Overdue, Open, Done) and Notes, each
 *  counted. A leaf opens the item underneath it, indented, so where you are stays visible. */
export default function Tree({ space, version, onChanged }: { space: string; version: number; onChanged: () => void }) {
  const { items, loading, error } = useSpaceItems(space, version);
  const [shut, setShut] = useState<string[]>([]);
  const [open, setOpen] = useState<number | null>(null);
  const toggle = (key: string) => setShut((s) => (s.includes(key) ? s.filter((k) => k !== key) : [...s, key]));

  function Node({ branch, depth }: { branch: Branch; depth: number }) {
    const rows = items.filter(branch.keep);
    const closed = shut.includes(branch.key);
    return (
      <li className={`node depth-${depth}`}>
        <button type="button" className="branch" onClick={() => toggle(branch.key)} aria-expanded={!closed}>
          <span className="twist">{closed ? "▸" : "▾"}</span> {branch.label} <span className="muted">{rows.length}</span>
        </button>
        {!closed && (
          <ul className="lines">
            {branch.children
              ? branch.children.map((child) => <Node key={child.key} branch={child} depth={depth + 1} />)
              : rows.map((item) => (
                  <li key={item.id} className={`node depth-${depth + 1}`}>
                    <button type="button" className={`line ${open === item.id ? "on" : ""}`} onClick={() => setOpen(open === item.id ? null : item.id)}>
                      <ItemLine item={item} />
                    </button>
                    {open === item.id && (
                      <div className="tree-open">
                        <ItemPage version={version} itemId={item.id} onChanged={onChanged} onClosed={() => setOpen(null)} />
                      </div>
                    )}
                  </li>
                ))}
          </ul>
        )}
      </li>
    );
  }

  return (
    <div className="tree">
      {error && <p className="error">{error}</p>}
      {loading && <p className="muted">Loading…</p>}
      <ul className="lines">
        {TREE.map((branch) => (
          <Node key={branch.key} branch={branch} depth={0} />
        ))}
      </ul>
    </div>
  );
}
