import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { deleteSpace, getSpaces, listItems, renameSpace, type SpacePolicy, setSpacePolicy } from "../api";
import AddItemForm from "../components/AddItemForm";
import BackLink from "../components/BackLink";
import Confirm from "../components/Confirm";
import Menu from "../components/Menu";
import NameForm from "../components/NameForm";
import PageHead from "../components/PageHead";
import { useLoad } from "../useLoad";
import Panes from "./layouts/Panes";

const POLICY: Record<SpacePolicy, { menu: string; note: string }> = {
  auto: { menu: "Files when sure", note: "" },
  ask: { menu: "Always ask me", note: "Nothing files here without you." },
  file: { menu: "Always file here", note: "Anything proposed for here files itself." },
};

/** One space: back, title row with "+ Add" and manage, then the list with the item beside it.
 *  This is the Panes layout from slice 21, kept over the card column and the tree. */
export default function Space({ version, onChanged }: { version: number; onChanged: () => void }) {
  const { name = "" } = useParams();
  const space = name.toLowerCase();
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [renaming, setRenaming] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [manageError, setManageError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const spaces = useLoad(getSpaces, [version]);
  const policy: SpacePolicy = spaces.data?.policies[space] ?? "auto";
  // Delete is offered only for an empty space, so the page needs to know whether it is one.
  const count = useLoad(() => listItems({ space, limit: 200 }), [space, version]);
  const itemCount = count.data?.items.length ?? null;

  useEffect(() => {
    setQ("");
    setAdding(false);
    setRenaming(false);
    setConfirmDelete(false);
    setManageError(null);
  }, [space]);

  async function choosePolicy(next: SpacePolicy) {
    setManageError(null);
    try {
      await setSpacePolicy(space, next);
      spaces.reload();
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
      <BackLink fallback="/spaces" />
      <div className="title-row">
        <PageHead
          eyebrow="Spaces"
          title={space}
          subtitle={`Tasks, notes and sessions in this space.${POLICY[policy].note ? ` ${POLICY[policy].note}` : ""}`}
        />
        <div className="title-actions">
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
      <Panes space={space} version={version} query={q} onQuery={setQ} onChanged={onChanged} />
    </div>
  );
}
