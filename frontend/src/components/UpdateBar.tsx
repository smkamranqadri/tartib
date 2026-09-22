import { useEffect, useState } from "react";
import { applyUpdate, onUpdateReady } from "../update";

/** One line offering the version that is already downloaded and waiting. It is an offer, not a
 *  question, so it is not a modal (slice 31 put every *question* in one) and it does not
 *  interrupt: a reload you did not ask for in the middle of typing a capture would be the
 *  rudest thing it does. */
export default function UpdateBar() {
  const [ready, setReady] = useState(false);
  useEffect(() => onUpdateReady(setReady), []);
  if (!ready) return null;
  return (
    <div className="update-bar" role="status">
      <span>A new version is ready.</span>
      <button type="button" className="ghost" onClick={applyUpdate}>
        Reload
      </button>
    </div>
  );
}
