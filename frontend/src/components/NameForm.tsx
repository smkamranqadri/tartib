import { useState, type FormEvent } from "react";

/** One short name in, submit or cancel. Used to create and to rename a space. */
export default function NameForm({
  initial = "",
  label,
  placeholder,
  submitLabel,
  onSubmit,
  onCancel,
}: {
  initial?: string;
  /** The accessible name of the field. */
  label: string;
  placeholder?: string;
  submitLabel: string;
  onSubmit: (value: string) => Promise<void>;
  onCancel: () => void;
}) {
  const [value, setValue] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const clean = value.trim();
  const unchanged = clean.toLowerCase() === initial.trim().toLowerCase();

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!clean || busy) return;
    setBusy(true);
    setError(null);
    try {
      await onSubmit(clean);
    } catch (err) {
      setError(err instanceof Error ? err.message : "failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="name-form" onSubmit={submit}>
      <input autoFocus value={value} onChange={(e) => setValue(e.target.value)} placeholder={placeholder} aria-label={label} maxLength={24} />
      <button type="submit" className="primary" disabled={busy || !clean || (!!initial && unchanged)}>
        {submitLabel}
      </button>
      <button type="button" className="ghost" onClick={onCancel} disabled={busy}>
        Cancel
      </button>
      {error && <span className="error">{error}</span>}
    </form>
  );
}
