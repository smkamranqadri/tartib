import { Fragment, useMemo, type ReactNode } from "react";
import { marked } from "marked";
import { decodeEntities, safeHref } from "../markdown";
import Highlight from "./Highlight";

/** Markdown rendered from marked's token stream straight into React elements.
 *
 *  Deliberately not `marked.parse()` into `dangerouslySetInnerHTML`, for two reasons that turn
 *  out to be one decision. Raw HTML in the source can then never become an element -- it renders
 *  as the characters it is -- which matters because the space brief and Ask answers are written
 *  by the model, and marked has had no `sanitize` option since v5. And because every text node
 *  is emitted here, marking the search terms (slice 20) is a branch in this file rather than a
 *  walk over output someone else built.
 *
 *  An unknown token renders its own raw text. It never falls back to HTML. */

type Loose = {
  type: string;
  raw?: string;
  text?: string;
  tokens?: Loose[];
  depth?: number;
  ordered?: boolean;
  start?: number | "";
  items?: Loose[];
  task?: boolean;
  checked?: boolean;
  href?: string;
  title?: string | null;
  header?: { tokens?: Loose[] }[];
  rows?: { tokens?: Loose[] }[][];
  align?: ("center" | "left" | "right" | null)[];
};

export default function Markdown({
  text,
  query = null,
  className,
}: {
  text: string;
  /** The search that brought you here, so the match is marked where it sits. */
  query?: string | null;
  className?: string;
}) {
  const tokens = useMemo(() => {
    try {
      // `breaks: true` deliberately. Notes here are typed, not authored: people end a line and
      // start another, and every note written before this slice looked that way because the old
      // `.raw` was `white-space: pre-wrap`. With marked's default a single newline is a space,
      // so every existing note would quietly reflow into one block on the day this shipped.
      return marked.lexer(text, { gfm: true, breaks: true }) as unknown as Loose[];
    } catch {
      return null;
    }
  }, [text]);

  // A lexer failure shows the bytes rather than nothing: the text is the user's, and it is the
  // one thing that must never disappear because of how we chose to draw it.
  if (!tokens) {
    return (
      <div className={`md ${className ?? ""}`}>
        <p className="md-plain">
          <Highlight text={text} query={query} />
        </p>
      </div>
    );
  }

  return <div className={`md ${className ?? ""}`}>{blocks(tokens, query)}</div>;
}

function blocks(tokens: Loose[] | undefined, query: string | null): ReactNode {
  if (!tokens) return null;
  return tokens.map((t, i) => <Fragment key={i}>{block(t, query)}</Fragment>);
}

function block(token: Loose, query: string | null): ReactNode {
  switch (token.type) {
    case "space":
      return null;
    case "hr":
      return <hr />;
    case "heading": {
      const depth = Math.min(6, Math.max(1, token.depth ?? 1));
      const Tag = `h${depth}` as "h1" | "h2" | "h3" | "h4" | "h5" | "h6";
      return <Tag>{inlines(token.tokens, query)}</Tag>;
    }
    case "paragraph":
      return <p>{inlines(token.tokens, query)}</p>;
    case "text":
      return <p>{token.tokens ? inlines(token.tokens, query) : plain(token.text ?? "", query)}</p>;
    case "blockquote":
      return <blockquote>{blocks(token.tokens, query)}</blockquote>;
    case "code":
      return (
        <pre>
          <code>{plain(token.text ?? "", query)}</code>
        </pre>
      );
    case "list": {
      const items = (token.items ?? []).map((item, i) => (
        <li key={i} className={item.task ? "md-task" : undefined}>
          {item.task && <input type="checkbox" checked={!!item.checked} readOnly disabled tabIndex={-1} />}
          {itemContent(item.tokens, query)}
        </li>
      ));
      return token.ordered ? (
        <ol start={typeof token.start === "number" ? token.start : undefined}>{items}</ol>
      ) : (
        <ul>{items}</ul>
      );
    }
    case "table": {
      const align = token.align ?? [];
      return (
        <div className="md-table">
          <table>
            <thead>
              <tr>
                {(token.header ?? []).map((cell, i) => (
                  <th key={i} style={align[i] ? { textAlign: align[i] as "left" } : undefined}>
                    {inlines(cell.tokens, query)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(token.rows ?? []).map((row, i) => (
                <tr key={i}>
                  {row.map((cell, j) => (
                    <td key={j} style={align[j] ? { textAlign: align[j] as "left" } : undefined}>
                      {inlines(cell.tokens, query)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    }
    // Raw HTML in the source is content, not markup. It renders as the characters it is.
    case "html":
      return <p className="md-plain">{plain(token.raw ?? "", query)}</p>;
    default:
      return <p className="md-plain">{plain(token.raw ?? token.text ?? "", query)}</p>;
  }
}

/** A tight list item holds `text` tokens that must not become paragraphs, or every list grows a
 *  blank line between its lines. A loose one holds real blocks and keeps them. */
function itemContent(tokens: Loose[] | undefined, query: string | null): ReactNode {
  if (!tokens) return null;
  return tokens
    // marked puts a `checkbox` token first in a task item and its raw text is the literal
    // "[ ] ". The box is drawn from the item's own `task`/`checked`, so the token is dropped.
    .filter((t) => t.type !== "checkbox")
    .map((t, i) => (
      <Fragment key={i}>
        {t.type === "text" ? (t.tokens ? inlines(t.tokens, query) : plain(t.text ?? "", query)) : block(t, query)}
      </Fragment>
    ));
}

function inlines(tokens: Loose[] | undefined, query: string | null): ReactNode {
  if (!tokens) return null;
  return tokens.map((t, i) => <Fragment key={i}>{inline(t, query)}</Fragment>);
}

function inline(token: Loose, query: string | null): ReactNode {
  switch (token.type) {
    case "text":
    case "escape":
      return token.tokens ? inlines(token.tokens, query) : plain(token.text ?? "", query);
    case "strong":
      return <strong>{inlines(token.tokens, query)}</strong>;
    case "em":
      return <em>{inlines(token.tokens, query)}</em>;
    case "del":
      return <del>{inlines(token.tokens, query)}</del>;
    case "codespan":
      return <code>{plain(token.text ?? "", query)}</code>;
    case "br":
      return <br />;
    case "link": {
      const href = safeHref(token.href ?? "");
      if (!href) return inlines(token.tokens, query);
      const external = /^https?:/i.test(href);
      return (
        <a href={href} {...(external ? { target: "_blank", rel: "noopener noreferrer" } : {})}>
          {inlines(token.tokens, query)}
        </a>
      );
    }
    case "image": {
      const src = safeHref(token.href ?? "");
      const alt = decodeEntities(token.text ?? "");
      if (!src) return <>{alt}</>;
      return <img src={src} alt={alt} loading="lazy" />;
    }
    // Same rule as a block: the characters, never an element.
    case "html":
      return plain(token.raw ?? "", query);
    default:
      return plain(token.raw ?? token.text ?? "", query);
  }
}

function plain(raw: string, query: string | null): ReactNode {
  return <Highlight text={decodeEntities(raw)} query={query} />;
}
