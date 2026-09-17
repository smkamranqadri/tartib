/* App-shell service worker. Hashed assets are cached forever; navigations are
   network-first with the cached shell as a fallback. API calls are never cached. */
const CACHE = "tartib-shell-v1";
/* Where a tapped notification leaves the URL it wants opened. The page reads this when it
   wakes, which is the only thing that works on iOS: a home-screen app is frozen while this
   worker runs, so it cannot answer a message in time, and navigate() does nothing to it. */
const PENDING_NAV = "/__pending-nav";
/* Bumped by hand whenever this file changes. The app shows it in Settings, so "is the phone
   actually running this worker?" is a question with an answer instead of a guess. */
const SW_VERSION = "2026-09-18.3";
const VERSION_KEY = "/__sw-version";

self.addEventListener("install", () => self.skipWaiting());

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys();
      await Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)));
      const cache = await caches.open(CACHE);
      await cache.put(VERSION_KEY, new Response(SW_VERSION));
      await self.clients.claim();
    })(),
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);
  if (request.method !== "GET" || url.origin !== self.location.origin || url.pathname.startsWith("/api/")) {
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
    self.registration.showNotification(payload.title || "Tartib", {
      body: payload.body,
      icon: "/icon-192.png",
      data: { url },
      /* The server tags per item, so a reminder replaces only itself. With no tag, nothing
         is ever replaced -- better a duplicate than a reminder the phone never showed. */
      tag: payload.tag,
      /* Without this, the same reminder re-fired would swap in silently. */
      renotify: !!payload.tag,
    }),
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
      if (new URL(open.url).pathname === url) {
        await cache.delete(PENDING_NAV); // already there; leave no note to act on later
        return;
      }
      /* A live page routes in place from this and clears the note. A frozen one reads the
         note on resume instead. navigate() is a last resort: it is a full reload. */
      open.postMessage({ type: "tartib:navigate", url });
    })(),
  );
});
