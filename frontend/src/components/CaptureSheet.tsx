import { useEffect } from "react";
import Capture from "../Capture";
import AskForm from "./AskForm";

export type SheetMode = "capture" | "ask";

/** The ⊕ sheet: capture, or ask, on a phone. Everything the capture bar and the ask bar do on a
 *  wide screen happens here instead, which is what gives a phone its screen back. */
export default function CaptureSheet({
  mode,
  spaces,
  onMode,
  onClose,
  onCaptured,
  onQueued,
  question,
}: {
  mode: SheetMode;
  spaces: string[];
  onMode: (m: SheetMode) => void;
  onClose: () => void;
  onCaptured: (id: number) => void;
  onQueued: () => void;
  /** Handed over from a space's search box while the sheet was closed. */
  question?: { question: string; space: string };
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="sheet-scrim" onPointerDown={onClose}>
      {/* biome-ignore lint/a11y/noStaticElementInteractions: the scrim closes, the panel must not */}
      <section className="sheet" onPointerDown={(e) => e.stopPropagation()} aria-label={mode === "capture" ? "Capture" : "Ask"}>
        <div className="sheet-head">
          <div className="pills tabs">
            {(["capture", "ask"] as SheetMode[]).map((m) => (
              <button key={m} type="button" className={mode === m ? "active" : ""} onClick={() => onMode(m)}>
                {m === "capture" ? "Capture" : "Ask"}
              </button>
            ))}
          </div>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>
        {mode === "capture" ? (
          <Capture
            autoFocus
            onCaptured={(id) => {
              onCaptured(id);
              onClose();
            }}
            onQueued={() => {
              onQueued();
              onClose();
            }}
          />
        ) : (
          <AskForm spaces={spaces} autoFocus={!question} initial={question} />
        )}
      </section>
    </div>
  );
}
