import { useEffect, useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { deleteSpace, getLinkedHere, getSpaces, listItems, renameSpace, setSpaceDescription, type SpacePolicy, type SpaceDescription, setSpacePolicy } from "../api";
import AddItemForm from "../components/AddItemForm";
import BackLink from "../components/BackLink";
import Card from "../components/Card";
import { LinkIcon } from "../components/Icons";
import ItemRow from "../components/ItemRow";
import Modal, { ConfirmModal } from "../components/Modal";
import NameForm from "../components/NameForm";
import PageHead from "../components/PageHead";
import { Stale } from "../components/Status";
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
  const [editingDescription, setEditingDescription] = useState(false);
  const spaces = useLoad(getSpaces, [version]);
  const policy: SpacePolicy = spaces.data?.policies[space] ?? "auto";
  // Delete is offered only for an empty space, so the page needs to know whether it is one.
  const count = useLoad(() => listItems({ space, limit: 200 }), [space, version]);
  const cachedAt = count.cachedAt;
  const itemCount = count.data?.items.length ?? null;
  // Items elsewhere that link here with `[[space:…]]` (slice 33): listed apart, never counted.
  const linked = useLoad(() => getLinkedHere(space), [space, version]);

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
          crumb={`Spaces // ${space}`}
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
          ) : (
            <>
              {/* The filing policy is the space's most consequential setting, so it is on the
                  page rather than three taps into a menu. Rename and delete sit beside it. */}
              <span className="pills policy" role="group" aria-label="Filing policy">
                {(["auto", "ask", "file"] as SpacePolicy[]).map((p) => (
                  <button
                    key={p}
                    type="button"
                    className={policy === p ? "active" : ""}
                    aria-pressed={policy === p}
                    title={p === "auto" ? "Files a proposal when the classifier is confident enough" : undefined}
                    onClick={() => void choosePolicy(p)}
                  >
                    {p[0].toUpperCase() + p.slice(1)}
                  </button>
                ))}
              </span>
              <button type="button" className="ghost" onClick={() => setRenaming(true)}>
                Rename
              </button>
              <button
                type="button"
                className="ghost danger"
                disabled={(itemCount ?? 1) > 0}
                title={itemCount ? `${itemCount} items still here` : undefined}
                onClick={() => setConfirmDelete(true)}
              >
                Delete
              </button>
            </>
          )}
          {manageError && <span className="error">{manageError}</span>}
          <ConfirmModal
            open={confirmDelete}
            question={<>Delete the space <b>{space}</b>?</>}
            detail="It is empty, so nothing else goes with it."
            confirmLabel="Delete space"
            onConfirm={() => void doDelete()}
            onCancel={() => setConfirmDelete(false)}
          />
        </div>
      </div>
      <Stale at={cachedAt} />
      <SpaceDescriptionRow
        detail={spaces.data?.descriptions[space] ?? { name: space, description: "", updated_at: "" }}
        editing={editingDescription}
        onEdit={() => setEditingDescription(true)}
        onClose={() => setEditingDescription(false)}
        onSaved={() => { spaces.reload(); setEditingDescription(false); }}
      />
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
      {(linked.data?.items.length ?? 0) > 0 && (
        <Card className="linked-here" icon={<LinkIcon />} label="Linked here" aside={<span className="muted">from other spaces</span>}>
          <ul className="rows flat">
            {linked.data!.items.map((row) => (
              <ItemRow
                key={row.id}
                item={row}
                onChange={(next) =>
                  linked.setData({ items: linked.data!.items.map((i) => (i.id === next.id ? next : i)) })
                }
              />
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}

function SpaceDescriptionRow({
  detail, editing, onEdit, onClose, onSaved,
}: {
  detail: SpaceDescription;
  editing: boolean;
  onEdit: () => void;
  onClose: () => void;
  onSaved: () => void;
}) {
  return <>
    <div className={`space-description-row ${detail.description ? "" : "space-description-empty"}`}>
      {detail.description ? <p>{detail.description}</p> : <p>No description yet.</p>}
      <button type="button" className="ghost" onClick={onEdit}>
        {detail.description ? "Edit description" : "Add a description"}
      </button>
    </div>
    <SpaceDescriptionModal key={`${detail.name}:${detail.updated_at}:${editing}`} open={editing} detail={detail} onClose={onClose} onSaved={onSaved} />
  </>;
}

function SpaceDescriptionModal({
  open, detail, onClose, onSaved,
}: { open: boolean; detail: SpaceDescription; onClose: () => void; onSaved: () => void }) {
  const [draft, setDraft] = useState(detail.description);
  const [token, setToken] = useState(detail.updated_at);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (open) { setDraft(detail.description); setToken(detail.updated_at); setError(null); }
  }, [open, detail.description, detail.updated_at]);

  async function save(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true); setError(null);
    try {
      await setSpaceDescription(detail.name, draft, token);
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save this description.");
    } finally { setBusy(false); }
  }

  async function loadLatest() {
    try {
      const latest = (await getSpaces()).descriptions[detail.name];
      if (!latest) throw new Error("Could not load the latest description.");
      setDraft(latest.description); setToken(latest.updated_at); setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load the latest description.");
    }
  }

  return <Modal open={open} title="Space description" onClose={busy ? undefined : onClose} actions={
    <>
      <button type="button" className="ghost" onClick={onClose} disabled={busy}>Cancel</button>
      <button type="submit" form="space-description-form" className="primary space-description-save" disabled={busy}>
        {busy ? <span className="spinner" aria-label="Saving" /> : "Save"}
      </button>
    </>
  }>
    <form id="space-description-form" className="space-description-editor" onSubmit={(e) => void save(e)}>
      <p>Used by agents and automatic filing.</p>
      <label><span>Description</span><textarea value={draft} onChange={(e) => setDraft(Array.from(e.target.value).slice(0, 500).join(""))} /></label>
      <div className="description-meta"><span>{Array.from(draft).length} / 500</span>{error && <span className="error" role="alert">{error}</span>}</div>
      {error?.includes("changed elsewhere") && <button type="button" className="ghost" onClick={() => void loadLatest()}>Use latest version</button>}
    </form>
  </Modal>;
}
