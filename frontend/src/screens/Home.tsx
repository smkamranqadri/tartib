import { Link } from "react-router-dom";
import { getAttention, getToday } from "../api";
import AnswerView from "../components/AnswerView";
import Capture from "../Capture";
import type { Answer } from "../types";
import { useLoad } from "../useLoad";

export default function Home({
  version,
  answer,
  onCaptured,
  onCloseAnswer,
}: {
  version: number;
  answer: Answer | null;
  onCaptured: (id: number) => void;
  onCloseAnswer: () => void;
}) {
  const attention = useLoad(getAttention, [version]).data?.items.length;
  const due = useLoad(getToday, [version]).data?.items.filter((i) => i.due && i.status === "open").length;

  return (
    <div className="home">
      <Capture onCaptured={onCaptured} />
      {answer && <AnswerView result={answer} onClose={onCloseAnswer} />}
      <p className="home-line muted">
        <Link to="/attention">{attention ?? "…"} need attention</Link>
        <span className="sep"> · </span>
        <Link to="/today">{due ?? "…"} due today</Link>
      </p>
    </div>
  );
}
