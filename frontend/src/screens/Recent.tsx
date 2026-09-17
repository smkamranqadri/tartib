import { getRecent } from "../api";
import Card from "../components/Card";
import { ClockIcon } from "../components/Icons";
import PageHead from "../components/PageHead";
import RecentList from "../components/RecentList";
import { useLoad } from "../useLoad";

export default function Recent({ version }: { version: number }) {
  const { data, error, loading } = useLoad(() => getRecent(50), [version]);
  return (
    <div className="screen">
      <PageHead eyebrow="Recent" title="Everything you captured" subtitle="Newest first, last 50." />
      <Card icon={<ClockIcon />} label="Captures" aside={data ? data.captures.length : "…"}>
        {error && <p className="error">{error}</p>}
        {loading && !data && <p className="muted">Loading…</p>}
        {data && <RecentList captures={data.captures} />}
      </Card>
    </div>
  );
}
