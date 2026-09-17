export type Shape = "task" | "note";
export type Stage = "attention" | "filed";
export type Status = "open" | "done";

export interface Proposal {
  shape: Shape | "question";
  space: string | null;
  title: string | null;
  due: string | null;
  remind_at: string | null;
  confidence: number;
}

export interface Item {
  id: number;
  capture_id: number;
  raw_text: string;
  space: string | null;
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
  updated_at: string | null;
}

export interface Answer {
  answer: string;
  item_ids: number[];
  items: Item[];
  matched?: boolean;
}

export interface Capture {
  id: number;
  raw_text: string;
  source: "web" | "api" | "migrated";
  created_at: string;
  status: "pending" | "done" | "error";
  error: string | null;
  classified_at: string | null;
  items: Item[];
  answer: Answer | null;
}

/** Fields the user may change. Only keys present are sent. */
export interface Edit {
  shape?: Shape;
  space?: string | null;
  title?: string | null;
  due?: string | null;
  remind_at?: string | null;
  starred?: boolean;
  status?: Status;
}

export interface SpaceSummary {
  name: string;
  unfiled: boolean;
  open: number;
  notes: number;
  overdue: number;
  total: number;
  last_activity: string | null;
}

export interface Brief {
  space: string;
  text: string;
  item_ids: number[];
  items: Item[];
  updated_at: string;
  fresh: boolean;
}
