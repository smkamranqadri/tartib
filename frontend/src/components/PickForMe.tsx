import { useState } from "react";
import { describe, pick } from "../api";
import Modal from "./Modal";

/** Pick for me (slice 32). The AI stars up to three open tasks that are not on Today yet, and
 *  takes back the stars its last pick gave; a star you set yourself is never taken. Why each was
 *  picked goes into the task's thoughts, so nothing here has to show it. */
export default function PickForMe({ onPicked }: { onPicked: () => void }) {
  const [open, setOpen] = useState(false);
  const [steer, setSteer] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  function close() {
    if (busy) return;
    setOpen(false);
    setMsg(null);
  }

  async function run() {
    setBusy(true);
    setMsg(null);
    try {
      const r = await pick(steer.trim());
      if (r.picks.length === 0) {
        setMsg(r.message ?? "Nothing to pick.");
        return;
      }
      setOpen(false);
      setSteer("");
      onPicked();
    } catch (e) {
      setMsg(describe(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <button type="button" className="ghost pick-open" onClick={() => setOpen(true)}>
        Pick for me
      </button>
      <Modal
        open={open}
        title="Pick what to work on"
        onClose={close}
        actions={
          <>
            <button type="button" className="ghost" onClick={close} disabled={busy}>
              Cancel
            </button>
            <button type="button" className="primary" onClick={() => void run()} disabled={busy}>
              {busy ? "Picking…" : "Pick"}
            </button>
          </>
        }
      >
        <p>Up to three open tasks get a star and a thought saying why. The last pick's stars go; yours stay.</p>
        <input
          className="pick-steer"
          type="text"
          value={steer}
          maxLength={300}
          onChange={(e) => setSteer(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !busy) void run();
          }}
          placeholder="Optional: 2 hours, low energy"
          aria-label="Anything to go by"
        />
        {msg && <p className="error small">{msg}</p>}
      </Modal>
    </>
  );
}
