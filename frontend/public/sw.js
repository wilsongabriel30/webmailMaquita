const CACHE_NAME = "maquita-mail-v10";
const BASE = "/webmail/";
const STATIC_ASSETS = [
  BASE,
  BASE + "index.html",
  BASE + "manifest.json"
];

// Install - cache static assets
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS);
    })
  );
  self.skipWaiting();
});

// Activate - clean old caches
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.filter((key) => key !== CACHE_NAME && key !== CACHE_NAME + "-api").map((key) => caches.delete(key))
      );
    })
  );
  self.clients.claim();
});

// Fetch strategy: Network First for API, Cache First for static assets
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // Skip non-GET requests
  if (event.request.method !== "GET") return;

  // Skip external URLs - let the browser handle them directly
  // Fixes CSP violations for external images in email signatures
  if (url.origin !== self.location.origin) return;

  // API calls - Network first, fall back to cache
  if (url.pathname.startsWith("/api/")) {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME + "-api").then((cache) => {
              cache.put(event.request, clone);
            });
          }
          return response;
        })
        .catch(() => {
          return caches.match(event.request);
        })
    );
    return;
  }

  // Static assets - Cache first, fall back to network
  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) return cached;
      return fetch(event.request).then((response) => {
        if (response.ok) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, clone);
          });
        }
        return response;
      });
    }).catch(() => {
      // If both fail and its a navigation, show cached app shell
      if (event.request.destination === "document") {
        return caches.match(BASE);
      }
    })
  );
});

// Background sync for offline actions
self.addEventListener("sync", (event) => {
  if (event.tag === "sync-actions") {
    // Will be handled by the app when it regains connectivity
    console.log("[SW] Background sync triggered");
  }
});
