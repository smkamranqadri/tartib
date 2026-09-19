import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { deleteSpace, renameSpace } from "../api";
import AddItemForm from "../components/AddItemForm";
import BackLink from "../components/BackLink";
import Confirm from "../components/Confirm";
import Menu from "../components/Menu";
import NameForm from "../components/NameForm";
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
  const [renaming, setRenaming] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [manageError, setManageError] = useState<string | null>(null);
  const [itemCount, setItemCount] = useState<number | null>(null);
  const [adding, setAdding] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setDebounced(q.trim()), 200);
    return () => clearTimeout(t);
  }, [q]);
  useEffect(() => {
    setQ("");
    setFilter("all");
    setRenaming(false);
    setConfirmDelete(false);
    setManageError(null);
    setAdding(false);
  }, [space]);

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
      <BackLink fallback="/spaces" />
      <div className="title-row">
        <PageHead eyebrow="Spaces" title={space} subtitle="Brief, tasks, and notes in this space." />
        <div className="title-actions">
          <div className="seg" role="group" aria-label="Shape">
            {(["all", "task", "note"] as ShapeFilter[]).map((f) => (
              <button key={f} type="button" className={filter === f ? "on" : ""} onClick={() => setFilter(f)}>
                {f === "all" ? "All" : f === "task" ? "Tasks" : "Notes"}
              </button>
            ))}
          </div>
          {!adding && (
            <button type="button" className="ghost" onClick={() => setAdding(true)}>
              + Add
            </button>
          )}
          {renaming ? (
            <NameForm
              initial={space}
              label="Rename space"
              submitLabel="Rename"
              onSubmit={async (value) => {
                const r = await renameSpace(space, value);
                setRenaming(false);
                onChanged();
                navigate(`/spaces/${encodeURIComponent(r.name)}`, { replace: true });
              }}
              onCancel={() => setRenaming(false)}
            />
          ) : confirmDelete ? (
            <Confirm question={<>Delete <b>{space}</b>?</>} onConfirm={() => void doDelete()} onCancel={() => setConfirmDelete(false)} />
          ) : (
            <Menu
              label="Manage space"
              items={[
                { label: "Rename", onSelect: () => setRenaming(true) },
                {
                  label: itemCount ? `Delete (${itemCount} items)` : "Delete",
                  danger: true,
                  disabled: (itemCount ?? 1) > 0,
                  title: itemCount ? `${itemCount} items still here` : undefined,
                  onSelect: () => setConfirmDelete(true),
                },
              ]}
            />
          )}
          {manageError && <span className="error">{manageError}</span>}
        </div>
      </div>
      {adding && (
        <AddItemForm
          space={space}
          onAdded={() => {
            setAdding(false);
            onChanged();
          }}
          onCancel={() => setAdding(false)}
        />
      )}
      <SearchAsk value={q} onChange={setQ} space={space} placeholder={`Search ${space}, or ask`} />
      <SpaceDetail space={space} query={debounced} version={version} filter={filter} onCount={setItemCount} />
    </div>
  );
}
