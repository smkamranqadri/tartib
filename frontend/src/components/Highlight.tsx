/** Text with every occurrence of the search terms marked. Case-insensitive and by prefix, the way
 *  the server's search matches, so what found the item is what gets marked. */
export default function Highlight({ text, query }: { text: string; query: string | null }) {
  const terms = (query ?? "")
    .split(/\s+/)
    .map((t) => t.replace(/[^\p{L}\p{N}]/gu, ""))
    .filter((t) => t.length > 0);
  if (terms.length === 0) return <>{text}</>;
  const pattern = new RegExp(`(${terms.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})`, "giu");
  const parts = text.split(pattern);
  return (
    <>
      {parts.map((part, i) =>
        i % 2 === 1 ? (
          <mark key={i} className="hit">
            {part}
          </mark>
        ) : (
          part
        ),
      )}
    </>
  );
}
