/* Service Worker DESACTIVADO (2026-06-12) - se autodesinstala y limpia cache */
self.addEventListener("install", function(e){ self.skipWaiting(); });
self.addEventListener("activate", function(e){
    e.waitUntil((async function(){
        try { var keys = await caches.keys(); await Promise.all(keys.map(function(k){ return caches.delete(k); })); } catch(err){}
        try { await self.registration.unregister(); } catch(err){}
        try { var cs = await self.clients.matchAll(); cs.forEach(function(c){ c.navigate(c.url); }); } catch(err){}
    })());
});
