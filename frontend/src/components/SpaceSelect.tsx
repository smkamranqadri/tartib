/** The one way to pick a space: every configured space, plus "no space" while an item waits. */
export default function SpaceSelect({
  value,
  spaces,
  onChange,
  allowNone = true,
  id,
}: {
  value: string | null;
  spaces: string[];
  onChange: (space: string | null) => void;
  allowNone?: boolean;
  id?: string;
}) {
  return (
    <select id={id} value={value ?? ""} onChange={(e) => onChange(e.target.value || null)} aria-label="Space">
      {allowNone && <option value="">No space</option>}
      {spaces.map((s) => (
        <option key={s} value={s}>
          {s}
        </option>
      ))}
    </select>
  );
}
