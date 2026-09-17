import type { Answer, Brief, Capture, Edit, Item, SpaceSummary } from "./types";

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

const send = <T,>(method: string, path: string, body?: unknown) =>
  api<T>(path, { method, body: body === undefined ? undefined : JSON.stringify(body) });

export const login = (password: string) => send<{ ok: true }>("POST", "/api/login", { password });
export const logout = () => send<{ ok: true }>("POST", "/api/logout");
export const capture = (text: string) => send<{ id: number }>("POST", "/api/capture", { text });

export const getToday = () =>
  api<{ date: string; items: Item[]; recent: Capture[]; active_space: string | null }>("/api/today");
export const getSpacesSummary = () => api<{ spaces: SpaceSummary[]; unfiled: SpaceSummary }>("/api/spaces/summary");
export const getBrief = (space: string, refresh = false) =>
  api<Brief>(`/api/spaces/${encodeURIComponent(space)}/brief${refresh ? "?refresh=true" : ""}`);
export const getCapture = (id: number) => api<Capture>(`/api/captures/${id}`);
export const getAttention = () => api<{ items: Item[]; stale: Item[]; stale_days: number }>("/api/attention");
export const getConfig = () =>
  api<{ tz: string; spaces: string[]; ai: boolean; fallback: boolean; autofile_confidence: number }>("/api/config");
export const getSpaces = () => api<{ spaces: string[] }>("/api/spaces");

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
export const ask = (question: string, space?: string) =>
  send<Answer>("POST", "/api/ask", { question, space: space || undefined });

export const editItem = (id: number, edit: Edit) => send<Item>("PATCH", `/api/items/${id}`, edit);
export const approveItem = (id: number, edit?: Edit) =>
  send<Item>("POST", `/api/items/${id}/approve`, edit);
export const rejectItem = (id: number) => send<Item>("POST", `/api/items/${id}/reject`);
export const deleteItem = (id: number) => send<{ ok: true; id: number }>("DELETE", `/api/items/${id}`);
export const getRecent = (limit = 50, before?: number) =>
  api<{ captures: Capture[]; next_before: number | null }>(`/api/recent?limit=${limit}${before ? `&before=${before}` : ""}`);
export const createSpace = (name: string) => send<{ spaces: string[]; name: string }>("POST", "/api/spaces", { name });
export const renameSpace = (old: string, name: string) =>
  send<{ spaces: string[]; name: string }>("PATCH", `/api/spaces/${encodeURIComponent(old)}`, { name });
export const deleteSpace = (name: string) => send<{ spaces: string[] }>("DELETE", `/api/spaces/${encodeURIComponent(name)}`);
