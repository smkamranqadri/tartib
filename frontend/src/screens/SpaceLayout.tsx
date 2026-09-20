import { useParams } from "react-router-dom";
import BackLink from "../components/BackLink";
import PageHead from "../components/PageHead";
import Panes from "./layouts/Panes";
import { LayoutSwitch } from "./layouts/shared";
import Tree from "./layouts/Tree";

const SUBTITLE = {
  panes: "One list, the item beside it. j and k move through it.",
  tree: "Branches you open and close.",
};

/** The four layouts being tried against the classic space page (slice 21). Same data, same
 *  actions; only the shape differs, and the switcher moves between them. */
export default function SpaceLayout({ kind, version, onChanged }: { kind: keyof typeof SUBTITLE; version: number; onChanged: () => void }) {
  const { name = "" } = useParams();
  const space = name.toLowerCase();
  const Layout = { panes: Panes, tree: Tree }[kind];
  return (
    <div className="screen">
      <BackLink fallback="/spaces" />
      <div className="title-row">
        <PageHead eyebrow="Spaces" title={space} subtitle={SUBTITLE[kind]} />
        <div className="title-actions">
          <LayoutSwitch space={space} />
        </div>
      </div>
      <Layout space={space} version={version} onChanged={onChanged} />
    </div>
  );
}
