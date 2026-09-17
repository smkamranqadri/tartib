import { useNavigate } from "react-router-dom";

/** "← Back" to wherever the visitor came from; to `fallback` when the page was opened directly. */
export default function BackLink({ fallback = "/", label = "Back" }: { fallback?: string; label?: string }) {
  const navigate = useNavigate();
  const canGoBack = typeof window !== "undefined" && window.history.state && window.history.state.idx > 0;
  return (
    <p className="crumbs">
      <a
        href={fallback}
        onClick={(e) => {
          e.preventDefault();
          if (canGoBack) navigate(-1);
          else navigate(fallback);
        }}
      >
        ← {label}
      </a>
    </p>
  );
}
