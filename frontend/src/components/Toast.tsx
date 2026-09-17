export interface ToastState {
  text: string;
  /** "busy" keeps it on screen; "final" fades after a few seconds. */
  phase: "busy" | "final";
}

export default function Toast({ toast }: { toast: ToastState | null }) {
  if (!toast) return null;
  return (
    <div className={`toast ${toast.phase}`} role="status" aria-live="polite">
      {toast.text}
    </div>
  );
}
