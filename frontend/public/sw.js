const CACHE_NAME = "maquita-mail-v22";
const BASE = "/webmail/";
// NO cachear index.html — siempre servir desde red para evitar
// que coexistan dos versiones de bundles JS (bug SPA dual-bundle).
// Solo cachear manifest y assets inmutables (con hash en nombre).
const STATIC_ASSETS = [
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
      // Eliminar TODOS los caches que no sean la versión actual
      return Promise.all(
        keys.filter((key) => key !== CACHE_NAME && key !== CACHE_NAME + "-api")
            .map((key) => { console.log("[SW] Deleting old cache:", key); return caches.delete(key); })
      );
    }).then(() => {
      // También limpiar el cache API viejo para evitar datos stale
      return caches.open(CACHE_NAME + "-api").then((cache) =>
        cache.keys().then((requests) => Promise.all(requests.map((r) => cache.delete(r))))
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

  // Skip external URLs completely
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
          return caches.match(event.request).then((r) => r || new Response("Offline", { status: 503 }));
        })
    );
    return;
  }

  // Navigation requests (HTML) — SIEMPRE red primero para evitar bundles stale
  if (event.request.destination === "document" || event.request.mode === "navigate") {
    event.respondWith(
      fetch(event.request)
        .catch(() => caches.match(BASE + "index.html")
          .then((r) => r || new Response("Offline", { status: 503 })))
    );
    return;
  }

  // Static assets (JS/CSS con hash) — Cache first, fall back to network
  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) return cached;
      return fetch(event.request).then((response) => {
        if (response.ok && event.request.url.match(/\.[a-f0-9]{8,}\./)) {
          // Solo cachear assets con hash en nombre (inmutables)
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, clone);
          });
        }
        return response;
      });
    }).catch(() => new Response("", { status: 404 }))
  );
});

// Background sync for offline actions
self.addEventListener("sync", (event) => {
  if (event.tag === "sync-actions") {
    console.log("[SW] Background sync triggered");
  }
});
