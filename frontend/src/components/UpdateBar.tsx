import { useEffect, useState } from "react";
import { applyUpdate, onUpdateReady } from "../update";

/** One line offering the version that is already downloaded and waiting. It is not a dialog
 *  and it does not interrupt: this product has no modals, and a reload you did not ask for in
 *  the middle of typing a capture would be the rudest thing it does. */
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
