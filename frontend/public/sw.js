const CACHE_NAME = "maquita-mail-v37";
const API_CACHE = CACHE_NAME + "-api";
const BASE = "/webmail/";

// NO cachear index.html para evitar bundles stale.
const STATIC_ASSETS = [
  BASE + "manifest.json"
];

// API endpoints to cache for offline access
const CACHEABLE_API = [
  "/api/mail/messages/",
  "/api/mail/message/",
  "/api/mail/folders",
  "/api/contacts/avatars",
  "/api/settings/signature",
  "/api/branding",
  "/api/auth/me",
];

function shouldCacheApi(url) {
  return CACHEABLE_API.some(prefix => url.includes(prefix));
}

// Install
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

// Activate - clean old caches
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.filter((key) => key !== CACHE_NAME && key !== API_CACHE)
          .map((key) => { console.log("[SW] Deleting old cache:", key); return caches.delete(key); })
      )
    )
  );
  self.clients.claim();
});

// Fetch strategy
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // Skip non-GET requests — but intercept POST /api/mail/send when offline
  if (event.request.method !== "GET") {
    // Queue offline sends
    if (event.request.method === "POST" && url.pathname === "/api/mail/send") {
      if (!navigator.onLine) {
        event.respondWith(
          event.request.json().then((payload) => {
            // Store in outbox via message to clients
            self.clients.matchAll().then((clients) => {
              clients.forEach((client) => {
                client.postMessage({
                  type: 'queue-outbox',
                  payload: payload,
                });
              });
            });
            return new Response(JSON.stringify({ queued: true, offline: true }), {
              status: 200,
              headers: { 'Content-Type': 'application/json' },
            });
          }).catch(() => {
            return new Response(JSON.stringify({ error: "No se pudo encolar" }), {
              status: 503,
              headers: { 'Content-Type': 'application/json' },
            });
          })
        );
        return;
      }
    }
    return;
  }

  // Skip external URLs
  if (url.origin !== self.location.origin) return;

  // API calls - Network first with intelligent cache fallback
  if (url.pathname.startsWith("/api/") && shouldCacheApi(url.pathname)) {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(API_CACHE).then((cache) => {
              cache.put(event.request, clone);
            });
          }
          return response;
        })
        .catch(() => {
          return caches.match(event.request).then((cached) => {
            if (cached) {
              // Add header to indicate this is from cache
              const headers = new Headers(cached.headers);
              headers.set('X-Offline-Cache', 'true');
              return new Response(cached.body, {
                status: cached.status,
                statusText: cached.statusText,
                headers: headers,
              });
            }
            return new Response(JSON.stringify({ error: "Sin conexion", offline: true }), {
              status: 503,
              headers: { 'Content-Type': 'application/json' },
            });
          });
        })
    );
    return;
  }

  // Other API calls (not cacheable) — network only with offline error
  if (url.pathname.startsWith("/api/")) {
    event.respondWith(
      fetch(event.request).catch(() => {
        return new Response(JSON.stringify({ error: "Sin conexion", offline: true }), {
          status: 503,
          headers: { 'Content-Type': 'application/json' },
        });
      })
    );
    return;
  }

  // Navigation requests — network first
  if (event.request.destination === "document" || event.request.mode === "navigate") {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          // Cache the navigation response for offline
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, clone);
          });
          return response;
        })
        .catch(() => caches.match(event.request)
          .then((r) => r || caches.match(BASE + "index.html"))
          .then((r) => r || new Response("Offline", { status: 503 })))
    );
    return;
  }

  // Static assets — Cache first, network fallback
  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) return cached;
      return fetch(event.request).then((response) => {
        if (response.ok) {
          // Cache hashed assets and icons
          if (event.request.url.match(/\.[a-f0-9]{8,}\./) || event.request.url.includes('/icons/')) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => {
              cache.put(event.request, clone);
            });
          }
        }
        return response;
      });
    }).catch(() => new Response("", { status: 404 }))
  );
});

// Background sync
self.addEventListener("sync", (event) => {
  if (event.tag === "sync-outbox") {
    event.waitUntil(
      self.clients.matchAll().then((clients) => {
        clients.forEach((client) => {
          client.postMessage({ type: 'trigger-sync' });
        });
      })
    );
  }
});

// Listen for messages from the app
self.addEventListener("message", (event) => {
  if (event.data === "skipWaiting") {
    self.skipWaiting();
  }
});
