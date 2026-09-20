import { useEffect, useState } from "react";
import { Navigate, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { deleteSpace, getSpaces, listItems, renameSpace, type SpacePolicy, setSpacePolicy } from "../api";
import AddItemForm from "../components/AddItemForm";
import BackLink from "../components/BackLink";
import Confirm from "../components/Confirm";
import Menu from "../components/Menu";
import NameForm from "../components/NameForm";
import PageHead from "../components/PageHead";
import SearchAsk from "../components/SearchAsk";
import { useLoad } from "../useLoad";
import { useWide } from "../useWide";
import ItemPage from "./ItemPage";
import { LayoutSwitch, spaceView } from "./layouts/shared";
import SpaceDetail, { type ShapeFilter } from "./SpaceDetail";

const POLICY: Record<SpacePolicy, { menu: string; note: string }> = {
  auto: { menu: "Files when sure", note: "" },
  ask: { menu: "Always ask me", note: "Nothing files here without you." },
  file: { menu: "Always file here", note: "Anything proposed for here files itself." },
};

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
  // The view this device prefers. Classic is "", so landing here confirms it.
  const preferred = spaceView();
  // Wide screens keep the open item beside the list, in the URL so Back and links still work.
  const wide = useWide();
  const [params, setParams] = useSearchParams();
  const openId = Number(params.get("item")) || null;
  // Opening a space on a wide screen lands on its newest item, so the pane is never an empty
  // panel waiting to be clicked. Replaces the history entry: Back still leaves the space.
  const newest = useLoad(() => (wide ? listItems({ space, limit: 1 }) : Promise.resolve(null)), [wide, space, version]);
  const firstId = newest.data?.items[0]?.id;
  useEffect(() => {
    if (wide && !openId && firstId) setParams({ item: String(firstId) }, { replace: true });
  }, [wide, openId, firstId]); // eslint-disable-line react-hooks/exhaustive-deps

  const rowTo = wide
    ? (item: { id: number }) => `/spaces/${encodeURIComponent(space)}?item=${item.id}${debounced ? `&q=${encodeURIComponent(debounced)}` : ""}`
    : undefined;
  const spaces = useLoad(getSpaces, [version]);
  const policy: SpacePolicy = spaces.data?.policies[space] ?? "auto";

  async function choosePolicy(next: SpacePolicy) {
    setManageError(null);
    try {
      await setSpacePolicy(space, next);
      spaces.reload();
    } catch (err) {
      setManageError(err instanceof Error ? err.message : "failed");
    }
  }

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

  if (preferred) return <Navigate to={`/spaces/${encodeURIComponent(space)}/${preferred}`} replace />;

  return (
    <div className="screen">
      <BackLink fallback="/spaces" />
      <div className="title-row">
        <PageHead eyebrow="Spaces" title={space} subtitle={`Brief, tasks, and notes in this space.${POLICY[policy].note ? ` ${POLICY[policy].note}` : ""}`} />
        <div className="title-actions">
          <div className="seg" role="group" aria-label="Shape">
            {(["all", "task", "note"] as ShapeFilter[]).map((f) => (
              <button key={f} type="button" className={filter === f ? "on" : ""} onClick={() => setFilter(f)}>
                {f === "all" ? "All" : f === "task" ? "Tasks" : "Notes"}
              </button>
            ))}
          </div>
          <LayoutSwitch space={space} current="" />
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
                ...(["auto", "ask", "file"] as SpacePolicy[]).map((p) => ({
                  label: `${policy === p ? "✓ " : ""}${POLICY[p].menu}`,
                  title: p === "auto" ? "Files a proposal when the classifier is confident enough" : undefined,
                  onSelect: () => void choosePolicy(p),
                })),
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
      <div className={wide ? "split" : undefined}>
        <div className="split-list">
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
          <SpaceDetail space={space} query={debounced} version={version} filter={filter} onCount={setItemCount} rowTo={rowTo} />
        </div>
        {wide && (
          <aside className="split-item">
            {openId ? (
              <ItemPage
                key={openId}
                version={version}
                itemId={openId}
                onChanged={onChanged}
                onClosed={() => setParams((p) => {
                  p.delete("item");
                  return p;
                })}
              />
            ) : (
              <p className="split-empty muted">Pick an item to read it here.</p>
            )}
          </aside>
        )}
      </div>
    </div>
  );
}
