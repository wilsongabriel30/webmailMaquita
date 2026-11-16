/* =============================================================================
   T-116 · SERVICE WORKER DEL CHAT  (el chat abre SIN INTERNET)
   -----------------------------------------------------------------------------
   QUE HACE: scope /chat/. Guarda el armazon (la pagina y sus estaticos) y lo
   sirve desde el equipo cuando no hay red, para que el chat cargue igual que el
   correo sin conexion. Los mensajes los pinta la pagina desde IndexedDB (T-49);
   aqui dejamos ademas en cache los ADJUNTOS ya vistos (<=10 MB) para verlos
   sin red. Los ENVIOS (POST) no se tocan aqui: los gestiona la pagina (outbox).
   POR QUE:  sin service worker, sin internet ni la pagina ni el JS cargan, y por
   mas que los mensajes esten guardados no hay app que los muestre.
   CLAVE:   red-primero en la navegacion (siempre fresco con red); cache-primero
   en estaticos (versionados con ?v=, asi una version nueva es otra entrada y la
   vieja se purga al subir la VERSION de abajo).
   ============================================================================= */
'use strict';

var VERSION = 'maquita-chat-v20261113-01';
var PREFIJO_PROPIO = 'maquita-chat-';   // lo que no cambia entre versiones: identifica las copias propias
var CACHE_APP = VERSION + '-app';        // armazon + estaticos (js/css/fuentes/iconos)
var CACHE_ADJ = VERSION + '-adjuntos';   // imagenes/archivos ya vistos
var ARMAZON = '/chat/';
var MAX_ADJ_BYTES = 10 * 1024 * 1024;    // 10 MB por adjunto
var MAX_ADJ_ENTRADAS = 400;              // tope aproximado del cache de adjuntos

self.addEventListener('install', function (e) {
    e.waitUntil((async function () {
        try {
            var c = await caches.open(CACHE_APP);
            var r = await fetch(ARMAZON, { credentials: 'include', cache: 'no-store' });
            if (r && r.ok) await c.put(ARMAZON, r.clone());
        } catch (_) { }
        self.skipWaiting();
    })());
});

self.addEventListener('activate', function (e) {
    e.waitUntil((async function () {
        var claves = await caches.keys();
        await Promise.all(claves
            // Solo las copias PROPIAS de versiones anteriores: el almacen de caches es uno por dominio y lo
            // comparte el service worker del correo (/webmail/). Borrar todo lo ajeno dejaba al correo sin
            // su copia para arrancar sin red (15/11/2026).
            .filter(function (k) { return k.indexOf(PREFIJO_PROPIO) === 0 && k.indexOf(VERSION) !== 0; })
            .map(function (k) { return caches.delete(k); }));
        await self.clients.claim();
    })());
});

function esEstatico(u) {
    var p = u.pathname;
    return p.indexOf('/static/js/') === 0 ||
           p.indexOf('/static/css/') === 0 ||
           p.indexOf('/static/fonts/') === 0 ||
           p.indexOf('/static/img') === 0 ||
           p.indexOf('/static/icon') === 0 ||
           p.indexOf('/static/gifs/') === 0;
}
function esAdjunto(u) {
    var p = u.pathname;
    return p.indexOf('/static/uploads/chat/') === 0 ||
           p.indexOf('/uploads/chat/') === 0;
}

self.addEventListener('fetch', function (e) {
    var req = e.request;
    if (req.method !== 'GET') return;            // los envios los gestiona la pagina (outbox)
    var u;
    try { u = new URL(req.url); } catch (_) { return; }
    if (u.origin !== self.location.origin) return;

    // 1) Navegacion: red primero, armazon de respaldo
    if (req.mode === 'navigate' || req.destination === 'document') {
        e.respondWith((async function () {
            try {
                var r = await fetch(req);
                if (r && r.ok) { var c = await caches.open(CACHE_APP); c.put(ARMAZON, r.clone()); }
                return r;
            } catch (_) {
                var c2 = await caches.open(CACHE_APP);
                var hit = await c2.match(ARMAZON) || await c2.match(req, { ignoreSearch: true });
                return hit || new Response(
                    '<h2 style="font-family:sans-serif;padding:2em">Sin conexión y sin copia local todavía. Abra el chat una vez con internet.</h2>',
                    { status: 503, headers: { 'Content-Type': 'text/html; charset=utf-8' } });
            }
        })());
        return;
    }

    // 2) Estaticos (versionados con ?v=): cache primero
    if (esEstatico(u)) {
        e.respondWith((async function () {
            var c = await caches.open(CACHE_APP);
            var hit = await c.match(req);
            if (hit) return hit;
            try {
                var r = await fetch(req);
                if (r && r.ok) c.put(req, r.clone());
                return r;
            } catch (_) { return hit || new Response('', { status: 504 }); }
        })());
        return;
    }

    // 3) Adjuntos ya vistos (<=10 MB): cache primero; se guardan al verlos
    if (esAdjunto(u)) {
        e.respondWith((async function () {
            var c = await caches.open(CACHE_ADJ);
            var hit = await c.match(req, { ignoreSearch: true });
            if (hit) return hit;
            try {
                var r = await fetch(req);
                if (r && r.ok) {
                    try {
                        var blob = await r.clone().blob();
                        if (blob.size > 0 && blob.size <= MAX_ADJ_BYTES) {
                            await c.put(req, new Response(blob, {
                                status: r.status, statusText: r.statusText, headers: r.headers
                            }));
                            trimAdjuntos();
                        }
                    } catch (_) { }
                }
                return r;
            } catch (_) { return new Response('', { status: 504 }); }
        })());
        return;
    }

    // 4) API del chat: red; si cae, 503 (la pagina pinta desde IndexedDB)
    if (u.pathname.indexOf('/api/chat/') === 0) {
        e.respondWith(fetch(req).catch(function () {
            return new Response(JSON.stringify({ error: 'Sin conexion', offline: true }),
                { status: 503, headers: { 'Content-Type': 'application/json' } });
        }));
        return;
    }
    // 5) El resto (socket.io, etc.): sin tocar, red normal
});

/* Purga aproximada del cache de adjuntos (la Cache API no da tamanos): si hay
   demasiadas entradas, borra las mas antiguas (orden de insercion de keys()). */
async function trimAdjuntos() {
    try {
        var c = await caches.open(CACHE_ADJ);
        var ks = await c.keys();
        if (ks.length > MAX_ADJ_ENTRADAS) {
            var sobran = ks.length - MAX_ADJ_ENTRADAS;
            for (var i = 0; i < sobran; i++) await c.delete(ks[i]);
        }
    } catch (_) { }
}

self.addEventListener('message', function (e) {
    if (e.data === 'skipWaiting') self.skipWaiting();
});
