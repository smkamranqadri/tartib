import type { Answer, Brief, Capture, Edit, Item, Outcome, PastSession, Session, SessionState, SpaceSummary, Thought } from "./types";

/** What went wrong, in words that are true. A failed fetch reports "Failed to fetch", which is
 *  the browser's sentence and not an answer to anything the reader was asking. Shared, because
 *  since slice 25 several places other than a screen load have to say it. */
export function describe(e: unknown): string {
  if (e instanceof ApiError) return e.message;
  if (typeof navigator !== "undefined" && !navigator.onLine) return "You're offline.";
  return "Can't reach Tartib.";
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

let onUnauthorized: () => void = () => {};
export function setUnauthorizedHandler(fn: () => void) {
  onUnauthorized = fn;
}

/* Whether what a screen just loaded came from the worker's cache, and when it was stored.
 *
 * `useLoad` is handed a closure, not a path, so there is nothing to look the answer up by.
 * Instead a load opens a window and every `api()` call inside it reports what it got. Two
 * loads that overlap see each other's stamps -- accepted, because a null stamp (a live
 * response) never raises the line, so the only cross-talk is between calls that were all
 * served from cache anyway, which is the case the line is describing. */
const windows = new Set<(string | null)[]>();

export async function tracked<T>(fn: () => Promise<T>): Promise<{ data: T; cachedAt: Date | null }> {
  const seen: (string | null)[] = [];
  windows.add(seen);
  try {
    const data = await fn();
    /* The oldest of them: if a screen is drawn from several cached reads, it is only as fresh
       as the stalest one, and saying otherwise would overstate it. */
    const stamps = seen.filter((s): s is string => !!s).sort();
    return { data, cachedAt: stamps.length ? new Date(stamps[0]) : null };
  } finally {
    windows.delete(seen);
  }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init.headers ?? {}) },
    credentials: "same-origin",
  });
  if (res.status === 401) {
    onUnauthorized();
    throw new ApiError(401, "not logged in");
  }
  if (windows.size) {
    const stamp = res.headers.get("x-tartib-cached-at");
    for (const w of windows) w.push(stamp);
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* not json */
    }
    throw new ApiError(res.status, typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return (await res.json()) as T;
}

const send = <T,>(method: string, path: string, body?: unknown, init?: RequestInit) =>
  api<T>(path, { ...init, method, body: body === undefined ? undefined : JSON.stringify(body) });

export const login = (password: string) => send<{ ok: true }>("POST", "/api/login", { password });
export const logout = () => send<{ ok: true }>("POST", "/api/logout");
/** `client_id` makes the send safe to repeat: the server answers 200 with the capture it
 *  already has rather than making a second one. See `offline.ts`. */
export const capture = (text: string, client_id?: string) =>
  send<{ id: number }>("POST", "/api/capture", client_id ? { text, client_id } : { text });

export const getToday = () =>
  api<{
    date: string;
    items: Item[];
    recent: Capture[];
    active_space: string | null;
    sessions: { total: number; by_item: Record<string, number> };
  }>("/api/today");
export const getSpacesSummary = () => api<{ spaces: SpaceSummary[]; unfiled: SpaceSummary }>("/api/spaces/summary");
export const getBrief = (space: string, refresh = false) =>
  api<Brief>(`/api/spaces/${encodeURIComponent(space)}/brief${refresh ? "?refresh=true" : ""}`);
export const getCapture = (id: number) => api<Capture>(`/api/captures/${id}`);
export const getAttention = () => api<{ items: Item[]; stale: Item[]; stale_days: number }>("/api/attention");
export const getConfig = () =>
  api<{
    tz: string;
    spaces: string[];
    ai: boolean;
    autofile_confidence: number;
    house_rules: string;
    house_rules_max: number;
    corrections: number;
    vapid_public: string | null;
  }>("/api/config");

export interface AiUsage {
  calls: number;
  failed: number;
  captures: number;
  duration_ms: number;
  input_tokens: number;
  cached_input_tokens: number;
  cache_write_input_tokens: number;
  output_tokens: number;
  reasoning_output_tokens: number;
  total_tokens: number;
  cost: number;
  /** The cost arithmetic is not shown until it has been reconciled against a real call. */
  cost_verified: boolean;
  model: string | null;
  rates: { input: number; output: number; cache_read: number; cache_write: number; source: string };
  usage_limit: { count: number; last: string | null; resets_at: string | null };
  /** The last rate-limit reading the CLI gave. Null until one has been seen. */
  quota: {
    primary: QuotaWindow;
    secondary: QuotaWindow;
    at: string;
  } | null;
}

export interface QuotaWindow {
  used_percent: number | null;
  window_minutes: number | null;
  resets_at: string | null;
}

/** What the AI has done and what it cost (slice 29). */
export const getUsage = () => api<AiUsage>("/api/usage");

/** Your own filing rules, appended to the shipped classifier prompt. Empty clears them.
 *  They cannot reach the part of the prompt that defines the reply format (slice 27). */
export const setHouseRules = (text: string) =>
  send<{ house_rules: string }>("PUT", "/api/config/house-rules", { text });

export const subscribePush = (endpoint: string, keys: { p256dh: string; auth: string }) =>
  send<{ id: number }>("POST", "/api/subscriptions", { endpoint, keys });
export const unsubscribePush = (endpoint: string) =>
  send<{ ok: true; removed: number }>("DELETE", "/api/subscriptions", { endpoint });
export type SpacePolicy = "auto" | "ask" | "file";
export const getSpaces = () => api<{ spaces: string[]; policies: Record<string, SpacePolicy> }>("/api/spaces");
export const setSpacePolicy = (space: string, policy: SpacePolicy) =>
  send<{ name: string; policy: SpacePolicy }>("PUT", `/api/spaces/${encodeURIComponent(space)}/policy`, { policy });

export const getCurrentSession = () => api<SessionState>("/api/sessions/current");
export const getRecentSessions = (limit: number, space?: string) =>
  api<{ sessions: PastSession[] }>(`/api/sessions/recent?limit=${limit}${space ? `&space=${encodeURIComponent(space)}` : ""}`);
export const startSession = (item_id: number | null) => send<Session>("POST", "/api/sessions", { item_id });
export const stopSession = (id: number) => send<Session>("POST", `/api/sessions/${id}/stop`);
export const answerSession = (id: number, outcome: Outcome) =>
  send<Session>("POST", `/api/sessions/${id}/outcome`, { outcome });

export interface ListParams {
  q?: string;
  space?: string;
  shape?: string;
  status?: string;
  before?: number;
  limit?: number;
}
export function listItems(params: ListParams) {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== "" && v !== null) qs.set(k, String(v));
  }
  const suffix = qs.toString();
  return api<{ items: Item[]; next_before: number | null }>(`/api/items${suffix ? `?${suffix}` : ""}`);
}

export const getItem = (id: number) => api<Item>(`/api/items/${id}`);
/** `prior` is the turn just before this one. The server has no conversation of its own, so a
 *  follow-up like "what about the second one?" only resolves if the client sends what it is a
 *  follow-up to (slice 26). One turn, not a history. */
export const ask = (question: string, space?: string, prior?: { question: string; item_ids: number[] }) =>
  send<Answer>("POST", "/api/ask", {
    question,
    space: space || undefined,
    prior_question: prior?.item_ids.length ? prior.question : undefined,
    prior_item_ids: prior?.item_ids.length ? prior.item_ids : undefined,
  });

/** Pick for me (slice 32): the AI stars up to three open tasks off Today, each with a reason. */
export const pick = (steer?: string) =>
  send<{ picks: { item: Item; reason: string }[]; message?: string }>("POST", "/api/pick", { steer: steer || undefined });

/** The `[[` picker (slice 33): items whose first line contains `q`. */
export const suggestLinks = (q: string, exclude?: number) =>
  api<{ items: { id: number; title: string; space: string | null; shape: "task" | "note" }[] }>(
    `/api/links/suggest?q=${encodeURIComponent(q)}${exclude ? `&exclude=${exclude}` : ""}`,
  );
export const resolveLink = (title: string) => api<{ id: number }>(`/api/links/resolve?title=${encodeURIComponent(title)}`);

export const addItem = (item: { shape: "task" | "note"; space: string; text: string; due?: string }) =>
  send<Item>("POST", "/api/items", item);
/** `keepalive` lets an edit outlive the page that sent it: the autosave flushed when a tab
 *  closes or a phone backgrounds would otherwise be cancelled mid-flight (slice 24). */
export const editItem = (id: number, edit: Edit, keepalive = false) =>
  send<Item>("PATCH", `/api/items/${id}`, edit, keepalive ? { keepalive: true } : undefined);
export const approveItem = (id: number, edit?: Edit) =>
  send<Item>("POST", `/api/items/${id}/approve`, edit);
export const getThoughts = (id: number) => api<{ thoughts: Thought[] }>(`/api/items/${id}/thoughts`);
export const addThought = (id: number, body: string) =>
  send<{ thought: Thought; thought_count: number }>("POST", `/api/items/${id}/thoughts`, { body });
/** Keep as one (slice 30): a split capture's pieces become one waiting note with its whole text. */
export const keepWhole = (captureId: number) => send<Item>("POST", `/api/captures/${captureId}/whole`);
export const redoItem = (id: number, reason: string) => send<Item>("POST", `/api/items/${id}/redo`, { reason });
export const deleteItem = (id: number) => send<{ ok: true; id: number }>("DELETE", `/api/items/${id}`);
export const getRecent = (limit = 50, before?: number) =>
  api<{ captures: Capture[]; next_before: number | null }>(`/api/recent?limit=${limit}${before ? `&before=${before}` : ""}`);
export const createSpace = (name: string) => send<{ spaces: string[]; name: string }>("POST", "/api/spaces", { name });
export const renameSpace = (old: string, name: string) =>
  send<{ spaces: string[]; name: string }>("PATCH", `/api/spaces/${encodeURIComponent(old)}`, { name });
export const deleteSpace = (name: string) => send<{ spaces: string[] }>("DELETE", `/api/spaces/${encodeURIComponent(name)}`);
