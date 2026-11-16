/* =============================================================================
   T-116 · REGISTRO DEL SERVICE WORKER DEL CHAT
   -----------------------------------------------------------------------------
   QUE HACE: registra /chat/sw.js (scope /chat/) para que el chat abra sin
   internet. No hace nada mas: el guardado de mensajes ya lo lleva el cache
   T-49 y los envios offline (outbox) se cablean en su propia fase.
   DONDE SE LLAMA: lo carga plantillas/chat/index.html al final.
   ============================================================================= */
(function () {
    'use strict';
    if (!('serviceWorker' in navigator)) return;
    try {
        navigator.serviceWorker.register('/chat/sw.js', { scope: '/chat/' })
            .then(function () { /* registrado */ })
            .catch(function (e) { try { console.warn('[chat-offline] SW no registrado:', e); } catch (_) { } });
    } catch (_) { }
})();
