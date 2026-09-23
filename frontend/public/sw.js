/* App-shell service worker. Hashed assets are cached forever; navigations and API reads are
   network-first with the cached copy as a fallback. */
const CACHE = "tartib-shell-v1";
/* API reads live in their own cache, so the shell's precache can be reasoned about on its own
   and a stale read never survives a shell rebuild it was not made against. */
const API_CACHE = "tartib-api-v1";
/* Activation deletes every cache not in here. It used to be `k !== CACHE`, which would have
   deleted the API cache on every update -- intermittently, and only after a release, which is
   the worst way to find a bug. */
const KEEP = [CACHE, API_CACHE];
/* When a cached API response was stored. The app reads it to say how old what you are looking
   at is, rather than quietly serving yesterday. */
const CACHED_AT = "x-tartib-cached-at";
/* Where a tapped notification leaves the URL it wants opened. The page reads this when it
   wakes, which is the only thing that works on iOS: a home-screen app is frozen while this
   worker runs, so it cannot answer a message in time, and navigate() does nothing to it. */
const PENDING_NAV = "/__pending-nav";
/* Bumped by hand whenever this file changes -- and whenever the app does. A browser only
   re-installs a worker whose bytes differ, so a release that changes only the bundle leaves the
   old worker active: its precache still holds the previous build, and nothing offers the reload.
   The app shows this in Settings, so "is the phone actually running this worker?" is a question
   with an answer instead of a guess. */
const SW_VERSION = "2026-09-23.2";
const VERSION_KEY = "/__sw-version";
/* Where the page leaves the VAPID public key, so this worker can re-subscribe on its own when
   the push service rotates an endpoint. The page is not running when that happens. */
const VAPID_KEY = "/__vapid-key";

/* The first launch after an install is the one most likely to have no network, and it was the
   one that failed: nothing was cached until a navigation had already succeeded. Caching the
   shell alone is not enough either -- index.html only names hashed asset files, and without
   those the app is a blank page with a title. So the asset URLs are read out of the HTML. */
async function precache() {
  const cache = await caches.open(CACHE);
  const res = await fetch("/index.html", { cache: "no-cache" });
  if (!res.ok) return;
  const html = await res.text();
  await cache.put("/index.html", new Response(html, { headers: res.headers }));
  const assets = new Set(html.match(/\/assets\/[A-Za-z0-9._-]+/g) || []);
  const extras = [
    "/manifest.webmanifest", "/icon-192.png", "/icon-512.png", "/icon-180.png",
    /* The app is set in this face. Without it in the shell, an offline launch falls back to
       whatever mono the device has and every measurement in this layout shifts. */
    "/fonts/jetbrains-mono-latin-400-normal.woff2",
    "/fonts/jetbrains-mono-latin-600-normal.woff2",
  ];
  /* One missing file must not fail the install and leave the old worker in place forever. */
  await Promise.allSettled(
    [...assets, ...extras].map(async (url) => {
      const hit = await fetch(url, { cache: "no-cache" });
      if (hit.ok) await cache.put(url, hit);
    }),
  );
}

/* No skipWaiting. A worker that takes over mid-session can serve a shell whose assets the
   running page has never heard of; the page offers a reload instead and this waits for it. */
self.addEventListener("install", (event) => event.waitUntil(precache()));

self.addEventListener("message", (event) => {
  if (event.data?.type === "tartib:skip-waiting") self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys();
      await Promise.all(keys.filter((k) => !KEEP.includes(k)).map((k) => caches.delete(k)));
      const cache = await caches.open(CACHE);
      await cache.put(VERSION_KEY, new Response(SW_VERSION));
      await self.clients.claim();
    })(),
  );
});

/* A read is stored with the time it was stored, so the app can say how old it is. The header
   has to go on at put time: a cached Response's headers are what come back, and there is
   nowhere else to keep this that survives a restart. */
async function putStamped(cache, request, res) {
  const headers = new Headers(res.headers);
  headers.set(CACHED_AT, new Date().toISOString());
  const body = await res.clone().arrayBuffer();
  await cache.put(request, new Response(body, { status: res.status, statusText: res.statusText, headers }));
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);
  if (request.method !== "GET" || url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/api/")) {
    /* Sessions are not cached. A countdown is only true at the moment it is read, and a stale
       one is a lie rather than old news; starting and stopping needs the network anyway. */
    if (url.pathname.startsWith("/api/sessions/")) return;
    /* Nor the link picker and resolver (slice 33): one entry per keystroke, kept forever, and
       a lookup is only worth anything against the database as it is now. */
    if (url.pathname.startsWith("/api/links/")) return;
    event.respondWith(
      (async () => {
        const cache = await caches.open(API_CACHE);
        try {
          const res = await fetch(request);
          /* Only a good answer is worth keeping. A 401 or a 500 cached would be served back
             as though it were the truth for as long as the network stayed down. */
          if (res.ok) await putStamped(cache, request, res);
          return res;
        } catch (err) {
          const hit = await cache.match(request);
          if (hit) return hit;
          throw err;
        }
      })(),
    );
    return;
  }
  if (url.pathname.startsWith("/assets/")) {
    event.respondWith(
      caches.open(CACHE).then(async (cache) => {
        const hit = await cache.match(request);
        if (hit) return hit;
        const res = await fetch(request);
        if (res.ok) cache.put(request, res.clone());
        return res;
      }),
    );
    return;
  }
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request)
        .then((res) => {
          if (res.ok) caches.open(CACHE).then((cache) => cache.put("/index.html", res.clone()));
          return res;
        })
        .catch(() => caches.match("/index.html")),
    );
  }
});

/* Reminders. The payload is {title, url}; anything unreadable still shows something,
   because a notification that never appears is worse than a vague one. */
self.addEventListener("push", (event) => {
  let payload = {};
  try {
    const parsed = event.data ? event.data.json() : null;
    if (parsed && typeof parsed === "object") payload = parsed;
  } catch {
    /* not our shape */
  }
  const url = payload.url || "/";
  event.waitUntil(
    (async () => {
      /* A session ending while you are looking at the app is not news: the bar on screen
         already turned into the question. Being buzzed about the countdown you are watching
         is the nagging rule 4 exists to prevent. A reminder always shows. */
      if (String(payload.tag || "").startsWith("session-")) {
        const windows = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
        if (windows.some((c) => c.visibilityState === "visible")) return;
      }
      await self.registration.showNotification(payload.title || "Tartib", {
        body: payload.body,
        icon: "/icon-192.png",
        data: { url },
        /* The server tags per item, so a reminder replaces only itself. With no tag, nothing
           is ever replaced -- better a duplicate than a reminder the phone never showed. */
        tag: payload.tag,
        /* Without this, the same reminder re-fired would swap in silently. */
        renotify: !!payload.tag,
      });
    })(),
  );
});

/* Focus the tab that is already open and route it, rather than opening a second one.
   The URL is written down first: every way of telling a live page can fail -- focus can be
   refused, a frozen page cannot answer, navigate() throws on a client this worker does not
   control -- and the note survives all of them for the page to pick up when it wakes. */
self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || "/";
  event.waitUntil(
    (async () => {
      const cache = await caches.open(CACHE);
      await cache.put(PENDING_NAV, new Response(JSON.stringify({ url, at: Date.now() })));

      const windows = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
      const open = windows.find((c) => new URL(c.url).origin === self.location.origin);
      if (!open) {
        await self.clients.openWindow(url);
        return;
      }
      try {
        await open.focus();
      } catch {
        /* the browser may refuse; where it ends up still matters more */
      }
      if (new URL(open.url).pathname === new URL(url, self.location.origin).pathname) {
        await cache.delete(PENDING_NAV); // already there; leave no note to act on later
        return;
      }
      /* A live page routes in place from this and clears the note. A frozen one reads the
         note on resume instead. navigate() is a last resort: it is a full reload. */
      open.postMessage({ type: "tartib:navigate", url });
    })(),
  );
});

/* A push service is allowed to retire an endpoint and hand out a new one. When it does, the
   page is not running -- that is the whole point of push -- so nothing re-registers and
   reminders are simply off until Settings is next opened, with no sign that anything happened.
   This subscribes again and tells the server, using the key the page left in the cache.

   Safari does not fire this event today, so on the phone this is insurance rather than a fix;
   it is the desktop and Android browsers that rotate endpoints and say so. */
self.addEventListener("pushsubscriptionchange", (event) => {
  event.waitUntil(
    (async () => {
      const key = await applicationServerKey(event.oldSubscription);
      if (!key) return; // nothing to mint with; Settings will re-register on the next visit
      const sub = await self.registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: key,
      });
      const { endpoint, keys } = sub.toJSON();
      await fetch("/api/subscriptions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        /* Same-origin, so the signed session cookie rides along and this is authorised. */
        credentials: "include",
        body: JSON.stringify({ endpoint, keys }),
      });
    })(),
  );
});

/** The key to mint with: the one the page wrote down, or failing that the one the expiring
 *  subscription was made with. Returned as bytes, which is what subscribe() wants. */
async function applicationServerKey(oldSubscription) {
  try {
    const hit = await (await caches.open(CACHE)).match(VAPID_KEY);
    if (hit) return keyBytes(await hit.text());
  } catch {
    /* storage can be unavailable; fall through to the old subscription */
  }
  return oldSubscription?.options?.applicationServerKey || null;
}

/** base64url to bytes. The same conversion as push.ts, which cannot be imported here. */
function keyBytes(base64url) {
  const padded = base64url.replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(padded + "=".repeat((4 - (padded.length % 4)) % 4));
  const bytes = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i += 1) bytes[i] = raw.charCodeAt(i);
  return bytes;
}
