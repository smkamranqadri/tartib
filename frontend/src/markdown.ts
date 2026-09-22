/** Markdown is presentation only: the stored bytes are never rewritten (rule 1). This module
 *  holds the pieces that are not React -- decoding entities for a text node, flattening a first
 *  line for a row, and finding a checklist box in the source so a tap can tick it. A tick is the
 *  one write here, and it is yours: the same edit as typing the `x`. */

import { marked } from "marked";

/** The one way item text is lexed. The renderer and `toggleTask` must count boxes the same way,
 *  so they share this rather than each passing their own options. `breaks: true` is explained
 *  where the renderer uses it. */
export function lex(text: string) {
  return marked.lexer(text, { gfm: true, breaks: true });
}

type Tok = { type: string; raw?: string; task?: boolean; tokens?: Tok[]; items?: Tok[] };

/** Every task item, in the order the renderer draws them: depth first, a parent before the list
 *  nested in it. A box inside a code block is not a token, so it is not counted. */
export function eachTask(tokens: Tok[] | undefined, visit: (item: Tok) => void): void {
  for (const t of tokens ?? []) {
    if (t.type === "list") {
      for (const item of t.items ?? []) {
        if (item.task) visit(item);
        eachTask(item.tokens, visit);
      }
    } else eachTask(t.tokens, visit);
  }
}

/** The text with its `n`th box flipped, or null if it cannot be found for certain.
 *
 *  Top-level tokens' `raw`s concatenate back to the source exactly, which gives each block its
 *  offset. Inside a block an item is found by its first line, searched forward from the one
 *  before -- the first line because a quoted item's `raw` has lost its `> `. Anything that
 *  does not line up returns null: a tick that lands on the wrong box is worse than none. */
export function toggleTask(text: string, n: number): string | null {
  const blocks = lex(text) as unknown as Tok[];
  let offset = 0;
  let seen = 0;
  let at: number | null = null;
  for (const block of blocks) {
    let cursor = offset;
    eachTask([block], (item) => {
      if (at !== null || cursor < 0) return;
      const first = (item.raw ?? "").split("\n")[0];
      const pos = text.indexOf(first, cursor);
      const box = /\[[ xX]\]/.exec(first);
      if (pos < 0 || !box) {
        cursor = -1;
        return;
      }
      if (seen++ === n) at = pos + box.index + 1;
      cursor = pos + first.length;
    });
    if (at !== null || cursor < 0) break;
    offset += (block.raw ?? "").length;
  }
  if (at === null) return null;
  return text.slice(0, at) + (text[at] === " " ? "x" : " ") + text.slice(at + 1);
}

const NAMED: Record<string, string> = {
  amp: "&",
  lt: "<",
  gt: ">",
  quot: '"',
  apos: "'",
  nbsp: " ",
  hellip: "…",
  mdash: "—",
  ndash: "–",
};

/** marked hands back the source text with its entities intact, and React renders a string
 *  literally -- so `&amp;` would reach the page as five characters. Decoding is safe here
 *  because nothing downstream builds HTML: every character goes into a React text node, which
 *  escapes on output. */
export function decodeEntities(text: string): string {
  if (!text.includes("&")) return text;
  return text.replace(/&(#[0-9]+|#[xX][0-9a-fA-F]+|[a-zA-Z]+);/g, (whole, body: string) => {
    if (body[0] === "#") {
      const hex = body[1] === "x" || body[1] === "X";
      const code = parseInt(hex ? body.slice(2) : body.slice(1), hex ? 16 : 10);
      if (!Number.isFinite(code) || code <= 0 || code > 0x10ffff) return whole;
      try {
        return String.fromCodePoint(code);
      } catch {
        return whole;
      }
    }
    return NAMED[body.toLowerCase()] ?? whole;
  });
}

/** The first line of a note with its markdown syntax taken off, for a row. A row is one dense
 *  line and the punctuation is noise there. This is not a renderer: it never calls marked, and
 *  it only ever looks at one line. */
export function flattenFirstLine(text: string): string {
  const line = text.split("\n").find((l) => l.trim().length > 0) ?? "";
  return decodeEntities(stripInline(stripLeaders(line))).trim();
}

/** Block markers, in the order they can stack: `> - # thing` is all three. */
function stripLeaders(line: string): string {
  return line
    .trim()
    .replace(/^(?:>\s*)+/, "")
    .replace(/^(?:[-*+]|\d+[.)])\s+/, "")
    .replace(/^#{1,6}\s+/, "")
    .replace(/^\[[ xX]\]\s+/, "")
    .replace(/\s+#+\s*$/, "");
}

/** Emphasis, code and links. Underscores are only taken at a word boundary, or `snake_case_name`
 *  would lose its underscores; no lookbehind, because this runs on phones. */
function stripInline(text: string): string {
  return text
    .replace(/!?\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/!?\[([^\]]*)\]\[[^\]]*\]/g, "$1")
    .replace(/`+([^`]+)`+/g, "$1")
    .replace(/\*\*\*(\S(?:[\s\S]*?\S)?)\*\*\*/g, "$1")
    .replace(/\*\*(\S(?:[\s\S]*?\S)?)\*\*/g, "$1")
    .replace(/\*(\S(?:[\s\S]*?\S)?)\*/g, "$1")
    .replace(/~~(\S(?:[\s\S]*?\S)?)~~/g, "$1")
    .replace(/(^|[^A-Za-z0-9_])___(\S(?:[\s\S]*?\S)?)___(?![A-Za-z0-9_])/g, "$1$2")
    .replace(/(^|[^A-Za-z0-9_])__(\S(?:[\s\S]*?\S)?)__(?![A-Za-z0-9_])/g, "$1$2")
    .replace(/(^|[^A-Za-z0-9_])_(\S(?:[\s\S]*?\S)?)_(?![A-Za-z0-9_])/g, "$1$2")
    .replace(/\s+/g, " ");
}

/** Anything that is not plainly a web link renders as text instead. A `javascript:` href is the
 *  one way a link token could still run something, so unknown schemes are refused and only the
 *  words are kept. */
export function safeHref(href: string): string | null {
  const h = href.trim();
  if (!h) return null;
  if (/^(?:https?:|mailto:)/i.test(h)) return h;
  if (/^[/#]/.test(h)) return h;
  if (/^[a-zA-Z][a-zA-Z0-9+.-]*:/.test(h)) return null;
  return h;
}

/** Where a tap landed, expressed so it survives the difference between rendered markdown and its
 *  source. Coordinates do not survive it: a rendered heading is shorter than `# heading`, so the
 *  same point is a different character in each. A word does survive -- markdown syntax sits
 *  around words, not inside them -- so the tap is recorded as "the Nth occurrence of this word",
 *  which the editor can find again in the source. */
export interface Spot {
  word: string;
  /** Which occurrence of that word it was, counting from the start of the rendered text. */
  nth: number;
  /** How far into the word the caret sat. */
  into: number;
}

const WORD = /[\p{L}\p{N}_]+/gu;

/** Read the tapped spot out of a click on rendered markdown. Null when the tap was not on a word
 *  (whitespace, a margin), which the caller turns into "the end of the document". */
export function spotFromPoint(root: HTMLElement, x: number, y: number): Spot | null {
  const range = caretRangeAt(x, y);
  if (!range || !root.contains(range.startContainer)) return null;

  // The offset of the tap within the block's whole text, walking the same text nodes the
  // renderer emitted.
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let before = "";
  let hit = -1;
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    if (n === range.startContainer) {
      hit = before.length + range.startOffset;
      before += n.textContent ?? "";
      break;
    }
    before += n.textContent ?? "";
  }
  if (hit < 0) return null;
  const text = before + restOf(walker);
  return spotAt(text, hit);
}

function restOf(walker: TreeWalker): string {
  let rest = "";
  for (let n = walker.nextNode(); n; n = walker.nextNode()) rest += n.textContent ?? "";
  return rest;
}

/** The word covering `at` in `text`, and which occurrence of it that is. */
export function spotAt(text: string, at: number): Spot | null {
  WORD.lastIndex = 0;
  let nth = 0;
  const seen = new Map<string, number>();
  for (let m = WORD.exec(text); m; m = WORD.exec(text)) {
    const start = m.index;
    const end = start + m[0].length;
    nth = (seen.get(m[0]) ?? 0) + 1;
    seen.set(m[0], nth);
    if (at >= start && at <= end) return { word: m[0], nth, into: at - start };
  }
  return null;
}

/** The same word, found again in the source. Falls back to the last occurrence when the source
 *  holds fewer of them than the rendered text did, and to null when it holds none. */
export function findSpot(source: string, spot: Spot): number | null {
  const re = new RegExp(`(?<![\\p{L}\\p{N}_])${spot.word.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}(?![\\p{L}\\p{N}_])`, "gu");
  const at: number[] = [];
  for (let m = re.exec(source); m; m = re.exec(source)) at.push(m.index);
  if (at.length === 0) return null;
  const start = at[Math.min(spot.nth, at.length) - 1];
  return start + Math.min(spot.into, spot.word.length);
}

/** `caretRangeFromPoint` is WebKit and Blink; `caretPositionFromPoint` is the standard one
 *  Firefox has. Neither is everywhere, so both are tried. */
function caretRangeAt(x: number, y: number): { startContainer: Node; startOffset: number } | null {
  const d = document as Document & {
    caretRangeFromPoint?: (x: number, y: number) => Range | null;
    caretPositionFromPoint?: (x: number, y: number) => { offsetNode: Node; offset: number } | null;
  };
  const r = d.caretRangeFromPoint?.(x, y);
  if (r) return { startContainer: r.startContainer, startOffset: r.startOffset };
  const pos = d.caretPositionFromPoint?.(x, y);
  return pos ? { startContainer: pos.offsetNode, startOffset: pos.offset } : null;
}
