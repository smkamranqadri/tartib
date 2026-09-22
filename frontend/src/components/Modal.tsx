import { useEffect, useRef, type ReactNode } from "react";

/** The one modal (slice 31). Every question the app asks -- delete this, sign out, clear the
 *  rules, how did the session go, whose words win -- asks here, over the page, rather than in
 *  place. Until 2026-09-22 the app had no modal at all; the owner chose one for every question.
 *
 *  A native `<dialog>` opened with `showModal()`: the browser traps focus inside it, makes the
 *  page behind it inert, and gives Escape. Escape and a tap on the backdrop call `onClose` --
 *  unless there is none, which is how a question that must be answered says so. Focus goes back
 *  to whatever had it before, so a keyboard user lands on the button that asked. */
export default function Modal({
  open,
  title,
  children,
  actions,
  onClose,
}: {
  open: boolean;
  title: ReactNode;
  children?: ReactNode;
  /** The answers. The first is the one Enter would expect; a primary button goes last. */
  actions: ReactNode;
  /** Without it the modal cannot be dismissed, only answered. */
  onClose?: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const before = useRef<Element | null>(null);

  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) {
      before.current = document.activeElement;
      d.showModal();
      d.querySelector<HTMLElement>(".modal-panel")?.focus();
    } else if (!open && d.open) {
      d.close();
      if (before.current instanceof HTMLElement) before.current.focus();
    }
  }, [open]);

  // Unmounted while open -- the page it belonged to navigated away -- still gives focus back.
  useEffect(
    () => () => {
      if (ref.current?.open && before.current instanceof HTMLElement) before.current.focus();
    },
    [],
  );

  return (
    <dialog
      ref={ref}
      className="modal"
      aria-labelledby="modal-title"
      onCancel={(e) => {
        e.preventDefault(); // the parent decides; the dialog must not close itself out of sync
        onClose?.();
      }}
      onClick={(e) => {
        if (e.target === ref.current) onClose?.(); // the backdrop, not the panel
      }}
    >
      {open && (
        // Focus lands on the panel, not the first button: on a phone a ring round "Later" or
        // "Cancel" reads as the answer being suggested. Tab still walks the buttons.
        <div className="modal-panel" tabIndex={-1}>
          <h2 id="modal-title" className="modal-title">
            {title}
          </h2>
          {children && <div className="modal-body">{children}</div>}
          <div className="modal-actions">{actions}</div>
        </div>
      )}
    </dialog>
  );
}

/** Are you sure: a question, a cancel, and one button that does the thing. */
export function ConfirmModal({
  open,
  question,
  detail,
  confirmLabel,
  danger = true,
  busy = false,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  question: ReactNode;
  detail?: ReactNode;
  confirmLabel: string;
  danger?: boolean;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <Modal
      open={open}
      title={question}
      onClose={onCancel}
      actions={
        <>
          <button type="button" className="ghost" onClick={onCancel} disabled={busy}>
            Cancel
          </button>
          <button type="button" className={danger ? "ghost danger" : "primary"} onClick={onConfirm} disabled={busy}>
            {confirmLabel}
          </button>
        </>
      }
    >
      {detail}
    </Modal>
  );
}
