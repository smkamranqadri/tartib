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
import { ApiError, capture as postCapture } from "./api";

export type Pending = { client_id: string; text: string; created_at: string };

const DB = "tartib";
const STORE = "pending-captures";

let listeners = new Set<(pending: Pending[]) => void>();

function newId(): string {
  const c = globalThis.crypto;
  if (c && "randomUUID" in c) return c.randomUUID();
  return `c-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

function open(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB, 1);
    req.onupgradeneeded = () => {
      if (!req.result.objectStoreNames.contains(STORE)) {
        req.result.createObjectStore(STORE, { keyPath: "client_id" });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function withStore<T>(mode: IDBTransactionMode, fn: (s: IDBObjectStore) => IDBRequest): Promise<T> {
  const db = await open();
  return new Promise<T>((resolve, reject) => {
    const tx = db.transaction(STORE, mode);
    const req = fn(tx.objectStore(STORE));
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

export type FlushResult = { sent: number[]; rejected: string[]; stalled: boolean };

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
      if (result.sent.length || result.rejected.length) onFlushed(result);
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
