/** The service worker's update handover.
 *
 *  The worker used to call `skipWaiting()` on install, so a new one took over the moment it
 *  arrived. That is invisible, which sounds kind until the running page asks for an asset the
 *  new shell has never heard of. Now the new worker waits, the app offers a reload, and the
 *  handover happens when the user says so -- or on the next launch, which is how it will
 *  usually go.
 */

let waiting: ServiceWorker | null = null;
const listeners = new Set<(ready: boolean) => void>();

function announce(sw: ServiceWorker | null) {
  waiting = sw;
  for (const cb of listeners) cb(!!sw);
}

/** Called when a new worker is ready, and again if it goes away. Returns an unsubscribe. */
export function onUpdateReady(cb: (ready: boolean) => void): () => void {
  listeners.add(cb);
  cb(!!waiting);
  return () => listeners.delete(cb);
}

/** Hand over to the waiting worker and reload onto it. */
export function applyUpdate(): void {
  if (!waiting) return;
  /* Only a handover we asked for reloads the page. `controllerchange` also fires the first
     time a worker claims a page that had none, and reloading on that would restart the app
     on its very first visit for no reason anyone could see. */
  navigator.serviceWorker.addEventListener("controllerchange", () => window.location.reload(), {
    once: true,
  });
  waiting.postMessage({ type: "tartib:skip-waiting" });
}

export function registerWorker(): void {
  if (!("serviceWorker" in navigator)) return;
  navigator.serviceWorker
    .register("/sw.js")
    .then((reg) => {
      if (reg.waiting) announce(reg.waiting);
      reg.addEventListener("updatefound", () => {
        const fresh = reg.installing;
        if (!fresh) return;
        fresh.addEventListener("statechange", () => {
          /* Installed with a controller already present means this one is waiting its turn.
             Installed with none is the first install, which is not an update to offer. */
          if (fresh.state === "installed" && navigator.serviceWorker.controller) announce(fresh);
          if (fresh.state === "redundant") announce(null);
        });
      });
    })
    .catch(() => {
      /* the offline shell is a nicety, never a requirement */
    });
}
