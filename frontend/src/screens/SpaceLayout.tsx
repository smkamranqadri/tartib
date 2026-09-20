import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import AddItemForm from "../components/AddItemForm";
import BackLink from "../components/BackLink";
import PageHead from "../components/PageHead";
import SearchAsk from "../components/SearchAsk";
import Panes from "./layouts/Panes";
import { LayoutSwitch, setSpaceView } from "./layouts/shared";
import Tree from "./layouts/Tree";

const SUBTITLE = {
  panes: "One list, the item beside it. j and k move through it.",
  tree: "Branches you open and close.",
};

/** The shell both new views share: back, title, the view picker, "+ Add", and the scoped search
 *  box. Only what is under it differs (slice 21). */
export default function SpaceLayout({ kind, version, onChanged }: { kind: keyof typeof SUBTITLE; version: number; onChanged: () => void }) {
  const { name = "" } = useParams();
  const space = name.toLowerCase();
  const Layout = { panes: Panes, tree: Tree }[kind];
  const [q, setQ] = useState("");
  const [adding, setAdding] = useState(false);

  // Landing here by link or bookmark is a choice too: remember it for the next space.
  useEffect(() => setSpaceView(kind), [kind]);
  useEffect(() => {
    setQ("");
    setAdding(false);
  }, [space]);

  return (
    <div className="screen">
      <BackLink fallback="/spaces" />
      <div className="title-row">
        <PageHead eyebrow="Spaces" title={space} subtitle={SUBTITLE[kind]} />
        <div className="title-actions">
          <LayoutSwitch space={space} current={kind} />
          {!adding && (
            <button type="button" className="ghost" onClick={() => setAdding(true)}>
              + Add
            </button>
          )}
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
      <Layout space={space} version={version} query={q} onChanged={onChanged} />
    </div>
  );
}
