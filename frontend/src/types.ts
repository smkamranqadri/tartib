export type Shape = "task" | "note";
export type Stage = "inbox" | "attention" | "filed";
export type Status = "open" | "done";

export interface Proposal {
  shape: Shape;
  space: string;
  title: string | null;
  due: string | null;
  remind_at: string | null;
  confidence: number;
}

export interface Item {
  id: number;
  raw_text: string;
  space: string;
  shape: Shape;
  stage: Stage;
  created_at: string;
  title: string | null;
  due: string | null;
  remind_at: string | null;
  starred: boolean;
  status: Status;
  proposal: Proposal | null;
  proposal_error: string | null;
  classified_at: string | null;
}

/** Fields the user may change. Only keys present are sent. */
export interface Edit {
  shape?: Shape;
  space?: string;
  title?: string | null;
  due?: string | null;
  remind_at?: string | null;
  starred?: boolean;
  status?: Status;
}
