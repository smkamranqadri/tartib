import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { deleteSpace, renameSpace } from "../api";
import PageHead from "../components/PageHead";
import SearchAsk from "../components/SearchAsk";
import SpaceDetail, { type ShapeFilter } from "./SpaceDetail";

/** One space on its own page: back, title row with filter and manage, scoped search, detail. */
export default function Space({ version, onChanged }: { version: number; onChanged: () => void }) {
  const { name = "" } = useParams();
  const space = name.toLowerCase();
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [debounced, setDebounced] = useState("");
  const [filter, setFilter] = useState<ShapeFilter>("all");
  const [menu, setMenu] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [newName, setNewName] = useState(space);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [manageError, setManageError] = useState<string | null>(null);
  const [itemCount, setItemCount] = useState<number | null>(null);

  useEffect(() => {
    const t = setTimeout(() => setDebounced(q.trim()), 200);
    return () => clearTimeout(t);
  }, [q]);
  useEffect(() => {
    setQ("");
    setFilter("all");
    setMenu(false);
    setRenaming(false);
    setConfirmDelete(false);
    setManageError(null);
  }, [space]);

  async function doRename() {
    setManageError(null);
    try {
      const r = await renameSpace(space, newName);
      setRenaming(false);
      onChanged();
      navigate(`/spaces/${encodeURIComponent(r.name)}`, { replace: true });
    } catch (err) {
      setManageError(err instanceof Error ? err.message : "failed");
    }
  }
  async function doDelete() {
    setManageError(null);
    try {
      await deleteSpace(space);
      onChanged();
      navigate("/spaces", { replace: true });
    } catch (err) {
      setManageError(err instanceof Error ? err.message : "failed");
      setConfirmDelete(false);
    }
  }

  return (
    <div className="screen">
      <p className="crumbs">
        <Link to="/spaces">← Spaces</Link>
      </p>
      <div className="title-row">
        <PageHead eyebrow="Space" title={space} />
        <div className="title-actions">
          <div className="seg" role="group" aria-label="Shape">
            {(["all", "task", "note"] as ShapeFilter[]).map((f) => (
              <button key={f} type="button" className={filter === f ? "on" : ""} onClick={() => setFilter(f)}>
                {f === "all" ? "All" : f === "task" ? "Tasks" : "Notes"}
              </button>
            ))}
          </div>
          {renaming ? (
            <form className="new-space-form" onSubmit={(e) => { e.preventDefault(); void doRename(); }}>
              <input autoFocus value={newName} onChange={(e) => setNewName(e.target.value)} aria-label="Rename space" maxLength={24} />
              <button type="submit" className="primary" disabled={!newName.trim() || newName.trim().toLowerCase() === space}>
                Rename
              </button>
              <button type="button" className="ghost" onClick={() => setRenaming(false)}>
                Cancel
              </button>
            </form>
          ) : confirmDelete ? (
            <span className="confirm">
              Delete <b>{space}</b>?{" "}
              <button type="button" className="ghost danger" onClick={() => void doDelete()}>
                Yes, delete
              </button>{" "}
              <button type="button" className="ghost" onClick={() => setConfirmDelete(false)}>
                No
              </button>
            </span>
          ) : (
            <span className="more">
              <button type="button" className="icon-btn" aria-label="Manage space" onClick={() => setMenu((m) => !m)}>
                …
              </button>
              {menu && (
                <span className="menu">
                  <a href="#rename" onClick={(e) => { e.preventDefault(); setMenu(false); setNewName(space); setRenaming(true); }}>
                    Rename
                  </a>
                  <button type="button" disabled={(itemCount ?? 1) > 0} title={itemCount ? `${itemCount} items still here` : undefined} onClick={() => { setMenu(false); setConfirmDelete(true); }}>
                    Delete{itemCount ? ` (${itemCount} items)` : ""}
                  </button>
                </span>
              )}
            </span>
          )}
          {manageError && <span className="error">{manageError}</span>}
        </div>
      </div>
      <SearchAsk value={q} onChange={setQ} space={space} placeholder={`Search ${space}, or ask`} />
      <SpaceDetail space={space} query={debounced} version={version} filter={filter} onCount={setItemCount} />
    </div>
  );
}
