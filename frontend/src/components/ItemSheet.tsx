import { useEffect } from "react";
import ItemPage from "../screens/ItemPage";

/** An item read on a phone: the same page, in a sheet over what you were looking at, so the list
 *  behind it keeps its place. The open item is in the URL, so Back closes it. */
export default function ItemSheet({
  itemId,
  version,
  onChanged,
  onClose,
}: {
  itemId: number;
  version: number;
  onChanged: () => void;
  onClose: () => void;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="sheet-scrim" onPointerDown={onClose}>
      {/* biome-ignore lint/a11y/noStaticElementInteractions: the scrim closes, the panel must not */}
      <section className="sheet item-sheet" onPointerDown={(e) => e.stopPropagation()} aria-label="Item">
        <div className="sheet-head">
          <span className="sheet-grip" aria-hidden="true" />
          <button type="button" className="icon-btn" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>
        <ItemPage key={itemId} version={version} itemId={itemId} onChanged={onChanged} onClosed={onClose} />
      </section>
    </div>
  );
}
