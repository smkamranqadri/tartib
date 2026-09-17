import type { ReactNode } from "react";

/** Inline confirmation: a question and two answers, in place, with no dialog. */
export default function Confirm({
  question,
  confirmLabel = "Yes, delete",
  onConfirm,
  onCancel,
}: {
  question: ReactNode;
  confirmLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <span className="confirm">
      {question}{" "}
      <button type="button" className="ghost danger" onClick={onConfirm}>
        {confirmLabel}
      </button>{" "}
      <button type="button" className="ghost" onClick={onCancel}>
        No
      </button>
    </span>
  );
}
