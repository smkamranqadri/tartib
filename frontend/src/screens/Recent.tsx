import { useState } from "react";
import { getRecent } from "../api";
import Card from "../components/Card";
import { ClockIcon } from "../components/Icons";
import PageHead from "../components/PageHead";
import RecentList from "../components/RecentList";
import type { Capture } from "../types";
import { useLoad } from "../useLoad";

const PAGE = 50;

export default function Recent({ version }: { version: number }) {
  const { data, error, loading } = useLoad(() => getRecent(PAGE), [version]);
  const [more, setMore] = useState<{ captures: Capture[]; next: number | null } | null>(null);
  const [busy, setBusy] = useState(false);
  const captures = [...(data?.captures ?? []), ...(more?.captures ?? [])];
  const next = more ? more.next : (data?.next_before ?? null);

  async function loadMore() {
    if (next === null || busy) return;
    setBusy(true);
    try {
      const page = await getRecent(PAGE, next);
      setMore((m) => ({ captures: [...(m?.captures ?? []), ...page.captures], next: page.next_before }));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="screen">
      <PageHead eyebrow="Recent" title="Everything you captured" subtitle="Newest first." />
      <Card icon={<ClockIcon />} label="Captures" aside={data ? `${captures.length}${next !== null ? "+" : ""}` : "…"}>
        {error && <p className="error">{error}</p>}
        {loading && !data && <p className="muted">Loading…</p>}
        {data && <RecentList captures={captures} />}
        {next !== null && (
          <p className="view-all">
            <button type="button" className="ghost" onClick={() => void loadMore()} disabled={busy}>
              {busy ? "Loading…" : "Load more"}
            </button>
          </p>
        )}
      </Card>
    </div>
  );
}
