import { Link } from "react-router-dom";
import type { Answer } from "../types";

/** An answer with its cited items as links. Used after a question capture and by the Ask bar. */
export default function AnswerView({ result, onClose }: { result: Answer; onClose?: () => void }) {
  return (
    <div className="answer">
      <div className="answer-head">
        <span className="card-label">Answer</span>
        {onClose && (
          <button type="button" className="icon-btn" onClick={onClose} aria-label="Close answer">
            ×
          </button>
        )}
      </div>
      <p>{result.answer}</p>
      {result.items.length > 0 ? (
        <ul className="cited">
          {result.items.map((item) => (
            <li key={item.id}>
              <Link to={`/items/${item.id}`}>
                <span className="muted">#{item.id}</span> {item.shape === "task" && item.title ? item.title : item.raw_text}
              </Link>
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted small">No items cited.</p>
      )}
    </div>
  );
}
