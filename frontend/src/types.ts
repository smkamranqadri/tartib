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
  /** Entries in the item's thought log. */
  thought_count: number;
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
  text?: string;
  /** The `updated_at` the editor loaded; the server refuses the write with 409 if it moved. */
  expected_updated_at?: string;
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

export type Outcome = "done" | "unfinished" | "abandoned";

export interface Session {
  id: number;
  item_id: number | null;
  started_at: string;
  ends_at: string;
  ended_at: string | null;
  outcome: Outcome | null;
  created_at: string;
}

/** A finished session with what it was about, for the card and a space's list. */
export interface PastSession extends Session {
  item_title: string | null;
  item_text: string | null;
  item_space: string | null;
}

/** What the app shows on load: a countdown, an outcome sheet, or neither. */
export interface SessionState {
  state: "running" | "awaiting" | null;
  session: Session | null;
  item: Item | null;
}

/** One entry in an item's thought log. Append-only: never edited, never removed on its own. */
export interface Thought {
  id: number;
  item_id: number;
  body: string;
  created_at: string;
}
