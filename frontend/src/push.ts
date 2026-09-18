/** Web Push from the browser's side: permission, subscription, and telling the server.
 *
 * Permission is only ever requested from a click in Settings. Browsers require a gesture,
 * and a denial cannot be re-asked in code, so asking on load would spend the one chance.
 */
import { subscribePush, unsubscribePush } from "./api";

/* Both must match `sw.js`: the worker writes the note, the page reads it. */
const SHELL_CACHE = "tartib-shell-v1";
const PENDING_NAV = "/__pending-nav";
const VERSION_KEY = "/__sw-version";
const VAPID_KEY = "/__vapid-key";

/** Which service worker is actually installed here. Null means none has activated yet.
 *  Shown in Settings: a phone quietly sitting on an old worker is otherwise invisible, and
 *  it wasted a lot of time once. */
export async function workerVersion(): Promise<string> {
  let marked: string | null = null;
  if ("caches" in window) {
    try {
      const hit = await (await caches.open(SHELL_CACHE)).match(VERSION_KEY);
      marked = hit ? await hit.text() : null;
    } catch {
      marked = null;
    }
  }
  if (marked) return marked;
  // No marker but a worker is driving the page: it predates the marker, which is exactly the
  // stale worker this row exists to catch. Saying "not installed" would point the wrong way.
  const controlled = "serviceWorker" in navigator && !!navigator.serviceWorker.controller;
  return controlled ? "older than 2026-09-18.2" : "not installed";
}

/** Ask the browser to re-check `sw.js`. Without this a phone can sit on an old worker for
 *  as long as it likes, and every fix shipped in it is invisible. */
export async function refreshWorker(): Promise<void> {
  if (!("serviceWorker" in navigator)) return;
  try {
    const reg = await navigator.serviceWorker.getRegistration();
    await reg?.update();
  } catch {
    /* an update check is never worth an error in front of the user */
  }
}

/** The URL a tapped notification left behind, if it is still fresh. Taking it clears it, so
 *  it is acted on exactly once. This is how iOS gets there: the app is frozen while the
 *  worker handles the tap, so it can only find out once it is running again. */
export async function takePendingNav(): Promise<string | null> {
  if (!("caches" in window)) return null;
  try {
    const cache = await caches.open(SHELL_CACHE);
    const hit = await cache.match(PENDING_NAV);
    if (!hit) return null;
    await cache.delete(PENDING_NAV);
    const { url, at } = (await hit.json()) as { url?: unknown; at?: unknown };
    if (typeof url !== "string" || typeof at !== "number") return null;
    // An old note is a tap from some previous session; going there now would be a surprise.
    return Date.now() - at < 120_000 ? url : null;
  } catch {
    return null; // storage can be unavailable; never break the app over a nicety
  }
}

export type PushState = "loading" | "unsupported" | "no-key" | "default" | "granted" | "denied";

export function pushSupported(): boolean {
  return "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
}

/** What Settings shows. `no-key` means this install has no VAPID key, so nothing can subscribe;
 *  until the config call answers, the honest answer is that we do not know yet. */
export function pushState(vapidPublic: string | null | undefined): PushState {
  if (!pushSupported()) return "unsupported";
  if (vapidPublic === undefined) return "loading";
  if (!vapidPublic) return "no-key";
  return Notification.permission as "default" | "granted" | "denied";
}

/** The applicationServerKey has to be bytes, and the key travels as base64url. */
function keyBytes(base64url: string) {
  const padded = base64url.replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(padded + "=".repeat((4 - (padded.length % 4)) % 4));
  const bytes = new Uint8Array(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i += 1) bytes[i] = raw.charCodeAt(i);
  return bytes;
}

async function registration(): Promise<ServiceWorkerRegistration> {
  // The app shell registers the worker in production only, and enabling reminders must not
  // quietly install a caching worker over a dev server that would then serve stale assets.
  if (!import.meta.env.PROD) throw new Error("Reminders need a production build of the app.");
  const existing = await navigator.serviceWorker.getRegistration();
  return existing ?? (await navigator.serviceWorker.register("/sw.js"));
}

/** Base64url of the key a subscription was minted with, for comparison against the server's. */
function subscribedKey(sub: PushSubscription): string | null {
  const raw = sub.options?.applicationServerKey;
  if (!raw) return null;
  const bytes = new Uint8Array(raw as ArrayBuffer);
  let binary = "";
  for (const b of bytes) binary += String.fromCharCode(b);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

/** Base64url with any padding removed, so a key pasted into `.env` with `=` on the end is not
 *  mistaken for a different key and re-minted on every visit to Settings. */
function sameKey(a: string | null, b: string): boolean {
  return a !== null && a.replace(/=+$/, "") === b.replace(/=+$/, "");
}

export async function currentSubscription(): Promise<PushSubscription | null> {
  if (!pushSupported()) return null;
  const reg = await navigator.serviceWorker.getRegistration();
  return (await reg?.pushManager.getSubscription()) ?? null;
}

/** The subscription this install should have, minted with the key the server is signing with.
 *
 *  A subscription is bound to the key that made it. If the server's pair was regenerated, the
 *  old subscription still looks healthy here while every push is rejected with a 403 -- which
 *  is not 404 or 410, so the server keeps the row and the card keeps saying "on" while nothing
 *  is ever delivered. The only way out is to drop it and mint a new one.
 */
async function mintSubscription(
  reg: ServiceWorkerRegistration,
  vapidPublic: string,
): Promise<PushSubscription> {
  let sub = await reg.pushManager.getSubscription();
  if (sub && !sameKey(subscribedKey(sub), vapidPublic)) {
    const dead = sub.endpoint;
    await sub.unsubscribe().catch(() => undefined);
    // Tell the server too. A push to a subscription made with the old key comes back 403,
    // not 410, so nothing on that side would ever prune the row on its own.
    await unsubscribePush(dead).catch(() => undefined);
    sub = null;
  }
  return (
    sub ??
    (await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: keyBytes(vapidPublic),
    }))
  );
}

async function register(sub: PushSubscription): Promise<void> {
  const { endpoint, keys } = sub.toJSON() as { endpoint: string; keys: { p256dh: string; auth: string } };
  await subscribePush(endpoint, keys);
}

/** Leave the key where `sw.js` can find it. When a push service retires an endpoint the page
 *  is not running, so the worker has to re-subscribe on its own, and it needs this to do it. */
async function rememberKey(vapidPublic: string): Promise<void> {
  if (!("caches" in window)) return;
  try {
    await (await caches.open(SHELL_CACHE)).put(VAPID_KEY, new Response(vapidPublic));
  } catch {
    /* a nicety for a rotation that may never happen; never worth failing a subscribe over */
  }
}

/** Ask, subscribe, and register with the server. Returns the resulting permission state. */
export async function enablePush(vapidPublic: string): Promise<PushState> {
  const permission = await Notification.requestPermission();
  if (permission !== "granted") return permission as "default" | "denied";

  const reg = await registration();
  await navigator.serviceWorker.ready;
  await register(await mintSubscription(reg, vapidPublic));
  await rememberKey(vapidPublic);
  return "granted";
}

/** Re-register a subscription the browser already has. The server deletes rows that a push
 *  service rejects, and endpoints rotate, so without this the card can read "on" while the
 *  server knows nothing. Idempotent: the endpoint is unique and the row is upserted.
 *
 *  Only when notifications are actually permitted: re-registering a subscription a blocked
 *  browser still holds would have the server pushing into a void forever. */
export async function resyncSubscription(vapidPublic: string): Promise<boolean> {
  if (!pushSupported() || Notification.permission !== "granted") return false;
  const existing = await currentSubscription();
  if (!existing) return false; // never resurrect one the user turned off
  const reg = await navigator.serviceWorker.getRegistration();
  if (!reg) return false;
  // Permission is already granted, so re-minting after a key rotation needs no gesture.
  await register(await mintSubscription(reg, vapidPublic));
  await rememberKey(vapidPublic);
  return true;
}

/** Unsubscribe the browser first. If the server call then fails, the row is left pointing at
 *  a dead endpoint, which the next push prunes on its 410 -- whereas the other order can leave
 *  the browser subscribed to a server that forgot, and the next visit to Settings would
 *  helpfully re-register it, turning reminders back on for someone who just turned them off. */
export async function disablePush(): Promise<void> {
  const sub = await currentSubscription();
  if (!sub) return;
  const { endpoint } = sub;
  await sub.unsubscribe();
  await unsubscribePush(endpoint);
}
