import { useEffect, useState } from "react";
import { onPendingEdits, type PendingEdit } from "./offline";

/** What is written down and not yet sent, for the screens that draw it (slice 25). */
export function usePending(): PendingEdit[] {
  const [pending, setPending] = useState<PendingEdit[]>([]);
  useEffect(() => onPendingEdits(setPending), []);
  return pending;
}
