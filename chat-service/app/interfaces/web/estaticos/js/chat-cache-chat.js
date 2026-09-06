/* =============================================================================
   T-49 · EL CHAT, INSTANTANEO Y CIFRADO
   -----------------------------------------------------------------------------
   QUE HACE: guarda en el equipo (cifradas) la lista de conversaciones y los
   ultimos mensajes de cada una, para pintarlos AL INSTANTE al abrir; mientras
   tanto pide al servidor lo de verdad y lo actualiza por detras.
   POR QUE:  medido, el servidor tarda 43 ms en dar la lista y 84 en los
   mensajes; con red mala eso se dispara. Lo guardado en el equipo se pinta en
   cuanto la pagina existe, sin esperar a nadie.
   DONDE SE LLAMA: lo carga plantillas/chat/index.html despues de cache-llave.js,
   cache-cifrado.js y cache-almacen.js, que son sus tres pilares.
   ============================================================================= */
(function (global) {
    'use strict';

    var CLAVE_LISTA = 'chat:conversaciones';
    var MAX_MENSAJES = 60;      // los ultimos de cada conversacion: lo que se ve al abrir
    var MAX_CONVERSACIONES = 30;

    function disponible() {
        return !!(global.MaquitaAlmacen && global.MaquitaCifrado && global.MaquitaLlave
                  && global.crypto && global.crypto.subtle);
    }

    /* --- la lista de conversaciones --- */
    async function guardarLista(conversaciones) {
        if (!disponible()) return;
        try {
            await global.MaquitaAlmacen.guardar(
                CLAVE_LISTA, (conversaciones || []).slice(0, MAX_CONVERSACIONES),
                {area: 'chat', fecha: Date.now()});
        } catch (e) { avisar('guardar la lista', e); }
    }

    async function leerLista() {
        if (!disponible()) return null;
        try {
            return await global.MaquitaAlmacen.leer(CLAVE_LISTA);
        } catch (e) { avisar('leer la lista', e); return null; }
    }

    /* --- los mensajes de una conversacion --- */
    async function guardarMensajes(conversacionId, mensajes) {
        if (!disponible() || !conversacionId) return;
        try {
            var ultimos = (mensajes || []).slice(-MAX_MENSAJES);
            // el texto va al indice como huellas, para poder buscar sin descifrar
            var texto = ultimos.map(function (m) {
                return (m.content || m.contenido || '');
            }).join(' ');
            await global.MaquitaAlmacen.guardar(
                'chat:mensajes:' + conversacionId, ultimos,
                {area: 'chat', grupo: 'conv-' + conversacionId, texto: texto, fecha: Date.now()});
        } catch (e) { avisar('guardar los mensajes', e); }
    }

    async function leerMensajes(conversacionId) {
        if (!disponible() || !conversacionId) return null;
        try {
            return await global.MaquitaAlmacen.leer('chat:mensajes:' + conversacionId);
        } catch (e) { avisar('leer los mensajes', e); return null; }
    }

    /* --- la cola de envio: lo que se escribio sin conexion --- */
    async function encolar(mensaje) {
        if (!disponible()) return false;
        var id = 'chat:cola:' + (mensaje.client_id || Date.now());
        // `fijo` = no se borra NUNCA por falta de espacio: es de la persona y aun no salio
        await global.MaquitaAlmacen.guardar(id, mensaje,
            {area: 'chat', fijo: true, estado: 'pendiente', fecha: Date.now()});
        return id;
    }

    function avisar(que, e) {
        // el cache es un lujo: si algo falla, el chat sigue funcionando contra el servidor
        console.warn('T-49: no se pudo ' + que + ' en el equipo (se sigue sin cache)', e);
    }

    /* --- enganche con lo que ya existe, sin tocarlo ---
       Se envuelve `fetch` solo para las dos llamadas que interesan: asi el cache se
       llena solo, sin que ningun otro archivo tenga que enterarse de que existe. */
    function engancharFetch() {
        if (global.__mqFetchCache) return;
        global.__mqFetchCache = true;
        var original = global.fetch;
        global.fetch = function (entrada, opciones) {
            var url = typeof entrada === 'string' ? entrada : (entrada && entrada.url) || '';
            var respuesta = original.apply(this, arguments);
            if (!disponible() || !url || (opciones && opciones.method && opciones.method !== 'GET')) {
                return respuesta;
            }
            if (url.indexOf('/api/chat/conversations') >= 0 && url.indexOf('/messages') < 0) {
                respuesta.then(function (r) {
                    r.clone().json().then(function (d) {
                        guardarLista(d.conversations || d.conversaciones || []);
                    }).catch(function () {});
                }).catch(function () {});
            } else {
                var m = url.match(/\/api\/chat\/conversations\/(\d+)\/messages/);
                if (m) {
                    respuesta.then(function (r) {
                        r.clone().json().then(function (d) {
                            guardarMensajes(m[1], d.messages || d.mensajes || []);
                        }).catch(function () {});
                    }).catch(function () {});
                }
            }
            return respuesta;
        };
    }

    document.addEventListener('DOMContentLoaded', function () {
        if (disponible()) engancharFetch();
    });

    global.MaquitaCacheChat = {
        guardarLista: guardarLista, leerLista: leerLista,
        guardarMensajes: guardarMensajes, leerMensajes: leerMensajes,
        encolar: encolar, disponible: disponible,
    };
})(window);
