import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ApiError, describe, resolveLink } from "../api";
import { ErrorLine, Loading } from "../components/Status";

/** `/link?title=…`: where a `[[…]]` goes when the page that drew it did not know its target -- a
 *  brief, an Ask answer, a link typed since the page loaded (slice 33). Found by first line, the
 *  most recently touched winning, and replaced in history so Back skips this stop. */
export default function LinkTo() {
  const [params] = useSearchParams();
  const title = params.get("title") ?? "";
  const navigate = useNavigate();
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    resolveLink(title)
      .then(({ id }) => live && navigate(`/items/${id}`, { replace: true }))
      .catch((e) => {
        if (!live) return;
        setMsg(e instanceof ApiError && e.status === 404 ? `No item has "${title}" as its first line.` : describe(e));
      });
    return () => {
      live = false;
    };
  }, [title, navigate]);

  return (
    <div className="screen">
      {msg ? (
        <>
          <ErrorLine>{msg}</ErrorLine>
          <p className="view-all">
            <Link to="/spaces">Search your spaces →</Link>
          </p>
        </>
      ) : (
        <Loading />
      )}
    </div>
  );
}
