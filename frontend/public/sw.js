// Marca del producto. El despliegue sustituye este valor y el prefijo del
// nombre de cache con lo configurado en branding_settings.app_name; lo que hay
// escrito aqui es el valor por defecto, de modo que el fichero funciona tal cual
// aunque se copie a mano.
// OJO: NOMBRE_APP es solo texto visible. Los identificadores de almacenamiento
// del correo y del chat ("maquita-mail-offline", "maquita-cache") y el global
// MaquitaAlmacen NO se derivan de aqui y no deben renombrarse: hacerlo dejaria
// sin datos a quien ya los tenga guardados.
const NOMBRE_APP = "Maquita Mail";
const CACHE_NAME = "maquita-mail-v202609041254";  // T-49: nombre nuevo para descartar el cache anterior, que tenia correo en claro
const API_CACHE = CACHE_NAME + "-api";
const BASE = "/webmail/";

// T-35 (d): la portada SÍ se precachea (clave fija INDEX_KEY) para poder ARRANCAR SIN RED; el deploy cambia
// CACHE_NAME en cada publicación, así nunca se sirve un index viejo con bundles que ya no existen.
const INDEX_KEY = BASE + "index.html";
const STATIC_ASSETS = [
  BASE + "manifest.json"
];

// Lo que el service worker puede guardar.
//
// T-49 (02/09/2026): AQUI NO PUEDE HABER CONTENIDO DE CORREO. Se quitaron
// /api/mail/messages/, /api/mail/message/, /api/mail/attachment/ y /api/mail/preview/
// porque guardaban cuerpos y adjuntos EN CLARO en el almacen del service worker, al lado
// del cache que si va cifrado. Lo encontro el candado del cifrado abriendo los archivos
// del disco. El correo sin conexion no se resiente: sus datos viven en IndexedDB (T-35),
// que ahora esta cifrado.
//
// Se queda solo lo que no dice nada de nadie y hace falta para ARRANCAR sin red.
const CACHEABLE_API = [
  "/api/mail/folders",       // nombres de carpetas y cuantos sin leer
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
    caches.open(CACHE_NAME).then(async (cache) => {
      await cache.addAll(STATIC_ASSETS);
      try {
        const r = await fetch(BASE, { credentials: "include", cache: "no-store" });
        if (r.ok) await cache.put(INDEX_KEY, r.clone());
      } catch (e) { /* sin red al instalar: se guardará en la primera navegación con red */ }
    })
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
          return caches.match(event.request).then((c) => c || caches.match(event.request, { ignoreSearch: true })).then((cached) => {
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
          // Cache the navigation response for offline (clave fija: cualquier ruta del SPA arranca sin red)
          if (response.ok && url.pathname.startsWith(BASE)) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => { cache.put(INDEX_KEY, clone); });
          }
          return response;
        })
        .catch(() => caches.match(INDEX_KEY)
          .then((r) => r || caches.match(event.request, { ignoreSearch: true }))
          .then((r) => r || new Response("<h2 style='font-family:sans-serif;padding:2em'>Sin conexión y sin copia local todavía. Abre el correo una vez con internet.</h2>", { status: 503, headers: { "Content-Type": "text/html; charset=utf-8" } })))
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

// ── Web push (#17): notifica correo nuevo aunque la PWA esté cerrada ──────────
self.addEventListener("push", (event) => {
  let data = {};
  try { data = event.data ? event.data.json() : {}; } catch (e) { /* payload no JSON */ }
  const title = data.title || NOMBRE_APP;
  const options = {
    body: data.body || "",
    icon: "/webmail/icons/icon-192.png",
    badge: "/webmail/icons/icon-192.png",
    tag: "correo-nuevo",
    renotify: true,
    data: { url: data.url || "/webmail/" },
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || "/webmail/";
  event.waitUntil(
    clients.matchAll({ type: "window", includeUncontrolled: true }).then((list) => {
      for (const c of list) {
        if (c.url.includes("/webmail") && "focus" in c) {
          c.focus();
          if ("navigate" in c) { try { c.navigate(url); } catch (e) { /* cross-origin */ } }
          return;
        }
      }
      if (clients.openWindow) return clients.openWindow(url);
    })
  );
});
