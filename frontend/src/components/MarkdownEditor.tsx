import { useCallback } from "react";
import CodeMirror, { Decoration, EditorView, type ReactCodeMirrorRef } from "@uiw/react-codemirror";
import { autocompletion, type CompletionContext, type CompletionResult } from "@codemirror/autocomplete";
import { markdown } from "@codemirror/lang-markdown";
import { HighlightStyle, syntaxHighlighting } from "@codemirror/language";
import { tags } from "@lezer/highlight";
import { suggestLinks } from "../api";
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

/** Line one is the item's title (slice 31), drawn as `Markdown` draws it -- unless it is a
 *  heading, a list item, a quote or a fence, which the renderer does not title either. */
const NOT_A_TITLE = /^\s*(#|>|```|~~~|[-*+]\s|\d+[.)]\s)/;
const titleLine = EditorView.decorations.compute(["doc"], (state) => {
  const line = state.doc.line(1);
  if (!line.text.trim() || NOT_A_TITLE.test(line.text)) return Decoration.none;
  return Decoration.set([Decoration.line({ class: "cm-title-line" }).range(line.from)]);
});

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
    // The `[[` picker (slice 33), as a panel of this app rather than CodeMirror's default list:
    // rows reach the 44px tap floor, the choice is marked in the accent, the space stays muted.
    ".cm-tooltip.cm-tooltip-autocomplete": {
      backgroundColor: "var(--panel)",
      border: "1px solid var(--line)",
      borderRadius: "10px",
      overflow: "hidden",
      boxShadow: "0 8px 24px rgba(0,0,0,.35)",
    },
    ".cm-tooltip.cm-tooltip-autocomplete > ul": {
      fontFamily: "var(--font-mono)",
      fontSize: "15px",
      maxHeight: "min(50vh, 320px)",
      maxWidth: "min(calc(100vw - 32px), 420px)",
    },
    ".cm-tooltip.cm-tooltip-autocomplete > ul > li": {
      display: "flex",
      alignItems: "center",
      gap: "10px",
      minHeight: "44px",
      padding: "0 12px",
      color: "var(--fg)",
    },
    ".cm-tooltip.cm-tooltip-autocomplete > ul > li[aria-selected]": {
      backgroundColor: "color-mix(in srgb, var(--accent) 22%, transparent)",
      color: "var(--fg)",
    },
    ".cm-completionLabel": { overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" },
    ".cm-completionDetail": { marginLeft: "auto", fontStyle: "normal", color: "var(--muted)", fontSize: "13px" },
  },
  { dark: true },
);

/** The `[[` picker (slice 33). Completion is otherwise off in this editor; this is its one
 *  source, so nothing else is ever offered while typing. It answers only after `[[`, and picking
 *  an item writes `[[Its first line]]`, closing the brackets if they were not already. */
function linkSource(exclude?: number) {
  return async (ctx: CompletionContext): Promise<CompletionResult | null> => {
    const open = ctx.matchBefore(/\[\[[^[\]\n]*$/);
    if (!open) return null;
    const q = open.text.slice(2);
    let items;
    try {
      items = (await suggestLinks(q, exclude)).items;
    } catch {
      return null; // offline: typing a link by hand still works
    }
    if (ctx.aborted || !items.length) return null;
    const closed = ctx.state.sliceDoc(ctx.pos, ctx.pos + 2) === "]]";
    return {
      from: open.from + 2,
      to: closed ? ctx.pos + 2 : ctx.pos,
      filter: false,
      options: items.map((i) => ({
        label: i.title,
        detail: i.space ?? "no space",
        type: i.shape === "task" ? "task" : "note",
        apply: `${i.title}]]`,
      })),
    };
  };
}

export default function MarkdownEditor({
  value,
  onChange,
  onBlur,
  /** The word the tap landed on, which is how a point in the rendered text is carried across
   *  to the source. Null means the end of the document. */
  spot,
  exclude,
}: {
  value: string;
  onChange: (next: string) => void;
  onBlur: () => void;
  spot: Spot | null;
  /** The item being edited, never offered as a link to itself. */
  exclude?: number;
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
      extensions={[
        markdown(),
        syntaxHighlighting(highlight),
        EditorView.lineWrapping,
        titleLine,
        autocompletion({ override: [linkSource(exclude)], icons: false, activateOnTyping: true }),
      ]}
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
