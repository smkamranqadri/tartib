import { useCallback } from "react";
import CodeMirror, { EditorView, type ReactCodeMirrorRef } from "@uiw/react-codemirror";
import { markdown } from "@codemirror/lang-markdown";
import { HighlightStyle, syntaxHighlighting } from "@codemirror/language";
import { tags } from "@lezer/highlight";
import { findSpot, type Spot } from "../markdown";

/** Everything CodeMirror is in this module and nothing else imports it, so it is its own chunk.
 *  `TextEditor` pulls it in on the first tap into the text; a note you only read never fetches
 *  it. Keep it that way: a static import of this file from anywhere puts the editor back on the
 *  cold page. */

/** The reason the editor is CodeMirror and not a textarea: a heading is drawn at heading size
 *  while you are typing it, and the caret still lands where the character is. A transparent
 *  textarea over a styled mirror cannot do this -- the caret comes from the textarea's own
 *  uniform metrics -- which is what was costed and rejected when this was planned. */
const highlight = HighlightStyle.define([
  { tag: tags.heading1, fontSize: "1.3em", fontWeight: "600", lineHeight: "1.4" },
  { tag: tags.heading2, fontSize: "1.15em", fontWeight: "600", lineHeight: "1.4" },
  { tag: tags.heading3, fontSize: "1.05em", fontWeight: "600" },
  { tag: tags.heading4, fontWeight: "600", color: "var(--muted)" },
  { tag: tags.heading5, fontWeight: "600", color: "var(--muted)" },
  { tag: tags.heading6, fontWeight: "600", color: "var(--muted)" },
  { tag: tags.strong, fontWeight: "600" },
  { tag: tags.emphasis, fontStyle: "italic" },
  { tag: tags.strikethrough, textDecoration: "line-through", color: "var(--muted)" },
  { tag: tags.link, color: "var(--accent)" },
  { tag: tags.url, color: "var(--accent)" },
  { tag: tags.monospace, color: "var(--accent-2)" },
  { tag: tags.quote, color: "var(--muted)" },
  { tag: tags.list, color: "var(--muted)" },
  // The syntax itself -- the #, the *, the backticks -- recedes rather than disappearing.
  { tag: tags.processingInstruction, color: "var(--muted)", opacity: "0.6" },
  { tag: tags.contentSeparator, color: "var(--muted)" },
]);

/** Bronze, from the app's own tokens rather than a second palette. */
const theme = EditorView.theme(
  {
    "&": { color: "var(--fg)", backgroundColor: "transparent", fontSize: "18px" },
    "&.cm-focused": { outline: "none" },
    ".cm-content": { fontFamily: "var(--font-mono)", padding: "0", lineHeight: "1.55", caretColor: "var(--accent)" },
    ".cm-line": { padding: "0" },
    ".cm-cursor, .cm-dropCursor": { borderLeftColor: "var(--accent)", borderLeftWidth: "2px" },
    "&.cm-focused .cm-selectionBackground, .cm-selectionBackground, ::selection": {
      backgroundColor: "color-mix(in srgb, var(--accent) 28%, transparent)",
    },
    ".cm-gutters": { display: "none" },
    ".cm-activeLine": { backgroundColor: "transparent" },
    ".cm-scroller": { fontFamily: "var(--font-mono)", lineHeight: "1.55" },
  },
  { dark: true },
);

export default function MarkdownEditor({
  value,
  onChange,
  onBlur,
  /** The word the tap landed on, which is how a point in the rendered text is carried across
   *  to the source. Null means the end of the document. */
  spot,
}: {
  value: string;
  onChange: (next: string) => void;
  onBlur: () => void;
  spot: Spot | null;
}) {
  const onCreate = useCallback(
    (view: EditorView) => {
      // The tapped word, found again in the source. This needs no layout and no measurement,
      // so it is right on the first frame -- unlike mapping the tap's coordinates, which asks
      // the editor about a point that belonged to a different layout.
      const doc = view.state.doc.toString();
      const pos = spot ? findSpot(doc, spot) : null;
      const anchor = Math.min(pos ?? doc.length, doc.length);
      view.dispatch({ selection: { anchor }, scrollIntoView: true });
      view.focus();
    },
    [spot],
  );

  return (
    <CodeMirror
      value={value}
      onChange={onChange}
      onBlur={onBlur}
      theme={theme}
      extensions={[markdown(), syntaxHighlighting(highlight), EditorView.lineWrapping]}
      basicSetup={{
        lineNumbers: false,
        foldGutter: false,
        highlightActiveLine: false,
        highlightActiveLineGutter: false,
        dropCursor: false,
        allowMultipleSelections: false,
        indentOnInput: false,
        bracketMatching: false,
        closeBrackets: false,
        autocompletion: false,
        searchKeymap: false,
      }}
      onCreateEditor={onCreate as unknown as (view: EditorView, state: ReactCodeMirrorRef["state"]) => void}
    />
  );
}
