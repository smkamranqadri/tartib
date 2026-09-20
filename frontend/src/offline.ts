/** The capture queue.
 *
 *  Every capture is written here first and sent second. That is one path rather than an online
 *  one and an offline one, and it means a capture survives the tab being closed between typing
 *  and sending, which is true with full signal as well.
 *
 *  Safety comes from the server: each entry carries a `client_id` minted before the first
 *  attempt, and `POST /api/capture` answers 200 with the existing capture if it has seen that id
 *  before. So a send whose response was lost can be retried without making a second capture.
 *
 *  Not Background Sync: Safari does not have it, and the phone this is for is an iPhone.
 */
import { addThought, ApiError, capture as postCapture, editItem } from "./api";
import type { Edit } from "./types";

export type Pending = { client_id: string; text: string; created_at: string };

/** A change to an existing item, written down when the network would not take it (slice 25).
 *
 *  Keyed rather than appended, and that is the whole design: an edit's key is `edit:<item id>`,
 *  so a second change to the same item merges into the first instead of queueing behind it.
 *  Without that, ticking a task and then starring it queues two writes carrying the same
 *  `expected_updated_at`, the first lands, and the second is refused as stale -- the queue
 *  conflicting with itself over edits the same person made seconds apart.
 *
 *  A thought cannot merge, because the log is append-only and two thoughts are two entries, so
 *  those take a key of their own. */
export type PendingEdit = {
  id: string;
  item_id: number;
  kind: "edit" | "thought";
  edit?: Edit;
  body?: string;
  /** The item version this was made against, sent as `expected_updated_at` on replay. */
  base_updated_at: string | null;
  created_at: string;
  /** The server refused it as stale. It stays, and the item page offers Reload or Overwrite. */
  conflict?: boolean;
};

const DB = "tartib";
const STORE = "pending-captures";
const EDITS = "pending-edits";

let listeners = new Set<(pending: Pending[]) => void>();

function newId(): string {
  const c = globalThis.crypto;
  if (c && "randomUUID" in c) return c.randomUUID();
  return `c-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

function open(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    /* v2 adds the edit queue. Additive on purpose: a phone upgrading from v1 may be holding
       captures that were typed offline and never sent, and losing those is the exact thing this
       file exists to prevent. Nothing is deleted or recreated here. */
    const req = indexedDB.open(DB, 2);
    req.onupgradeneeded = () => {
      if (!req.result.objectStoreNames.contains(STORE)) {
        req.result.createObjectStore(STORE, { keyPath: "client_id" });
      }
      if (!req.result.objectStoreNames.contains(EDITS)) {
        req.result.createObjectStore(EDITS, { keyPath: "id" });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function withStore<T>(mode: IDBTransactionMode, fn: (s: IDBObjectStore) => IDBRequest, store = STORE): Promise<T> {
  const db = await open();
  return new Promise<T>((resolve, reject) => {
    const tx = db.transaction(store, mode);
    const req = fn(tx.objectStore(store));
    req.onsuccess = () => resolve(req.result as T);
    req.onerror = () => reject(req.error);
    tx.oncomplete = () => db.close();
  });
}

/** Insertion order, which is the order they are sent in: what you typed first is filed first. */
export async function list(): Promise<Pending[]> {
  try {
    const all = await withStore<Pending[]>("readonly", (s) => s.getAll());
    return all.sort((a, b) => a.created_at.localeCompare(b.created_at));
  } catch {
    return []; // storage can be unavailable; the app must still work
  }
}

async function notify(): Promise<void> {
  const pending = await list();
  for (const cb of listeners) cb(pending);
}

/** Watch the queue. Fires immediately with what is in it. */
export function onPending(cb: (pending: Pending[]) => void): () => void {
  listeners.add(cb);
  void list().then(cb);
  return () => listeners.delete(cb);
}

/** Write it down. Returns null when storage is unavailable, and the caller sends directly --
 *  a browser with no IndexedDB should still be able to capture, just without the safety net. */
export async function enqueue(text: string): Promise<Pending | null> {
  const entry: Pending = { client_id: newId(), text, created_at: new Date().toISOString() };
  try {
    await withStore("readwrite", (s) => s.add(entry));
    await notify();
    return entry;
  } catch {
    return null;
  }
}

async function drop(client_id: string): Promise<void> {
  try {
    await withStore("readwrite", (s) => s.delete(client_id));
    await notify();
  } catch {
    /* it will be retried and the server will recognise it; not worth failing over */
  }
}

/** A failure the server gave us an answer for, and would give again. Retrying forever would
 *  wedge everything behind it, so it leaves the queue and the caller says so. 401 is not one of
 *  these: the session came back once and it can again. Nor is 429, which means "later". */
function permanent(err: unknown): boolean {
  return err instanceof ApiError && err.status >= 400 && err.status < 500 && err.status !== 401 && err.status !== 429;
}

export type FlushResult = { sent: number[]; rejected: string[]; stalled: boolean; edits?: EditFlushResult };

/** Send what is queued, oldest first, stopping at the first one that does not go. Stopping
 *  keeps the order: a later capture must not overtake an earlier one still waiting. */
export async function flush(): Promise<FlushResult> {
  const result: FlushResult = { sent: [], rejected: [], stalled: false };
  for (const entry of await list()) {
    try {
      const { id } = await postCapture(entry.text, entry.client_id);
      await drop(entry.client_id);
      result.sent.push(id);
    } catch (err) {
      if (permanent(err)) {
        await drop(entry.client_id);
        result.rejected.push(err instanceof Error ? err.message : "rejected");
        continue; // it can never succeed; the ones behind it still can
      }
      result.stalled = true;
      break;
    }
  }
  return result;
}

/* ---- the edit queue (slice 25) ---------------------------------------------------------- */

let editListeners = new Set<(edits: PendingEdit[]) => void>();

export async function listEdits(): Promise<PendingEdit[]> {
  try {
    const all = await withStore<PendingEdit[]>("readonly", (s) => s.getAll(), EDITS);
    return all.sort((a, b) => a.created_at.localeCompare(b.created_at));
  } catch {
    return [];
  }
}

async function notifyEdits(): Promise<void> {
  const edits = await listEdits();
  for (const cb of editListeners) cb(edits);
}

/** Watch the edit queue. Fires immediately with what is in it. */
export function onPendingEdits(cb: (edits: PendingEdit[]) => void): () => void {
  editListeners.add(cb);
  void listEdits().then(cb);
  return () => editListeners.delete(cb);
}

/** Write down a change to an item. A second change to the same item merges into the first and
 *  keeps its original base version, so the queue never conflicts with itself. */
/** `base_updated_at` is the version to send back as `expected_updated_at`, or null for a change
 *  that is not worth refusing over. A tick or a star passes null deliberately: those go out
 *  unchecked when online (slice 19 put the check on the text, not on a checkbox), and a queued
 *  one must behave the same or the queue invents a conflict the live app would never raise. */
export async function enqueueEdit(item_id: number, edit: Edit, base_updated_at: string | null): Promise<boolean> {
  const id = `edit:${item_id}`;
  try {
    const existing = await withStore<PendingEdit | undefined>("readonly", (s) => s.get(id), EDITS);
    const entry: PendingEdit = existing
      ? { ...existing, edit: { ...existing.edit, ...edit }, base_updated_at: existing.base_updated_at ?? base_updated_at, conflict: false }
      : { id, item_id, kind: "edit", edit, base_updated_at, created_at: new Date().toISOString() };
    await withStore("readwrite", (s) => s.put(entry), EDITS);
    await notifyEdits();
    return true;
  } catch {
    return false;
  }
}

/** A thought is append-only, so each one is its own entry and none of them merge. */
export async function enqueueThought(item_id: number, body: string): Promise<boolean> {
  const entry: PendingEdit = {
    id: `thought:${newId()}`,
    item_id,
    kind: "thought",
    body,
    base_updated_at: null,
    created_at: new Date().toISOString(),
  };
  try {
    await withStore("readwrite", (s) => s.add(entry), EDITS);
    await notifyEdits();
    return true;
  } catch {
    return false;
  }
}

async function dropEdit(id: string): Promise<void> {
  try {
    await withStore("readwrite", (s) => s.delete(id), EDITS);
    await notifyEdits();
  } catch {
    /* it will be retried; the server takes the same write twice without harm */
  }
}

async function markConflict(entry: PendingEdit): Promise<void> {
  try {
    await withStore("readwrite", (s) => s.put({ ...entry, conflict: true }), EDITS);
    await notifyEdits();
  } catch {
    /* nothing to do: it stays queued either way */
  }
}

/** Clear a conflicted edit once the person has answered it on the item page. */
export async function resolveEdit(item_id: number): Promise<void> {
  await dropEdit(`edit:${item_id}`);
}

export type EditFlushResult = { sent: number; conflicts: number[]; rejected: string[]; stalled: boolean };

/** Replay the queue oldest-first.
 *
 *  Unlike captures, a refusal here does not stop the queue. Captures stop because order is the
 *  guarantee -- an earlier capture must not be overtaken. Edits are already coalesced per item,
 *  so a conflict on one item says nothing about the next, and stopping would strand every other
 *  change behind a decision only the person can make. A network failure still stops it, because
 *  that is not about the write at all. */
export async function flushEdits(): Promise<EditFlushResult> {
  const result: EditFlushResult = { sent: 0, conflicts: [], rejected: [], stalled: false };
  for (const entry of await listEdits()) {
    if (entry.conflict) {
      result.conflicts.push(entry.item_id);
      continue; // waiting on Reload or Overwrite
    }
    try {
      if (entry.kind === "thought") {
        await addThought(entry.item_id, entry.body ?? "");
      } else {
        await editItem(entry.item_id, { ...entry.edit, expected_updated_at: entry.base_updated_at ?? undefined });
      }
      await dropEdit(entry.id);
      result.sent += 1;
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        await markConflict(entry);
        result.conflicts.push(entry.item_id);
        continue;
      }
      if (permanent(err)) {
        await dropEdit(entry.id);
        result.rejected.push(err instanceof Error ? err.message : "rejected");
        continue;
      }
      result.stalled = true;
      break;
    }
  }
  return result;
}

/** Flush whenever the network or the app comes back, and tell the app what landed so its lists
 *  can catch up. The same wake points `push.ts` watches, because iOS fires no reliable resume
 *  event a home-screen app can hear. */
export function watchForReconnect(onFlushed: (result: FlushResult) => void): () => void {
  let running = false;
  const run = async () => {
    if (running || !navigator.onLine) return;
    running = true;
    try {
      const result = await flush();
      /* Captures first, then edits. A capture becomes an item, and an edit can only ever be to
         an item that already exists, so this order is the one that cannot strand anything. */
      const edits = await flushEdits();
      if (result.sent.length || result.rejected.length || edits.sent || edits.conflicts.length) {
        onFlushed({ ...result, edits });
      }
    } finally {
      running = false;
    }
  };
  const wake = () => {
    if (document.visibilityState === "visible") void run();
  };
  window.addEventListener("online", run);
  document.addEventListener("visibilitychange", wake);
  window.addEventListener("focus", wake);
  window.addEventListener("pageshow", wake);
  void run();
  return () => {
    window.removeEventListener("online", run);
    document.removeEventListener("visibilitychange", wake);
    window.removeEventListener("focus", wake);
    window.removeEventListener("pageshow", wake);
  };
}
