import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import type { Item } from "../../types";
import { useWide } from "../../useWide";
import ItemPage from "../ItemPage";
import { ItemLine, isOverdue, matches, SpaceSessions, useSpaceItems } from "./shared";

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
 *  counted. The item opens beside the tree, so the branch you are in stays where it was. */
export default function Tree({ space, version, query, onChanged }: { space: string; version: number; query: string; onChanged: () => void }) {
  const { items: all, loading, error } = useSpaceItems(space, version);
  const items = all.filter((i) => matches(i, query));
  const [shut, setShut] = useState<string[]>([]);
  const wide = useWide();
  const [params, setParams] = useSearchParams();
  const openId = Number(params.get("item")) || null;
  const toggle = (key: string) => setShut((s) => (s.includes(key) ? s.filter((k) => k !== key) : [...s, key]));

  function Leaf({ item, depth }: { item: Item; depth: number }) {
    const inner = <ItemLine item={item} />;
    return (
      <li className={`node depth-${depth}`}>
        {wide ? (
          <button type="button" className={`line ${item.id === openId ? "on" : ""}`} onClick={() => setParams({ item: String(item.id) }, { replace: true })}>
            {inner}
          </button>
        ) : (
          <Link className="line" to={`/items/${item.id}`}>
            {inner}
          </Link>
        )}
      </li>
    );
  }

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
              : rows.map((item) => <Leaf key={item.id} item={item} depth={depth + 1} />)}
          </ul>
        )}
      </li>
    );
  }

  return (
    <div className={wide ? "split" : undefined}>
      <div className="tree">
        {error && <p className="error">{error}</p>}
        {loading && <p className="muted">Loading…</p>}
        <ul className="lines">
          {TREE.map((branch) => (
            <Node key={branch.key} branch={branch} depth={0} />
          ))}
        </ul>
        <SpaceSessions space={space} version={version} />
      </div>
      {wide && (
        <aside className="split-item">
          {openId ? (
            <ItemPage key={openId} version={version} itemId={openId} onChanged={onChanged} onClosed={() => setParams({}, { replace: true })} />
          ) : (
            <p className="split-empty muted">Pick something from the tree.</p>
          )}
        </aside>
      )}
    </div>
  );
}
