/* =============================================================================
   T-49 · QUE SE NOTE: PINTAR DESDE EL EQUIPO ANTES DE QUE CONTESTE EL SERVIDOR
   -----------------------------------------------------------------------------
   QUE HACE: en cuanto la página existe, saca del equipo la lista de
   conversaciones y los mensajes de la que se abre, y los pinta YA. Mientras
   tanto la petición al servidor sigue su curso y, cuando llega, repinta con lo
   ultimo. La persona no espera a nadie.
   POR QUE:  guardar el cache no se nota si luego seguimos esperando al servidor.
   Esto es lo que convierte los 84 ms de red -y los segundos con red mala- en
   pintar de inmediato.
   COMO EVITA EL PARPADEO: solo pinta de lo guardado cuando NO hay nada en
   pantalla todavia. Si ya hay mensajes, no toca nada y deja que mande el
   servidor: mejor esperar un instante que ver saltar el contenido.
   DONDE SE LLAMA: lo carga plantillas/chat/index.html despues de los tres
   modulos del cache y de los guiones del chat, porque envuelve sus funciones.
   ============================================================================= */
(function (global) {
    'use strict';

    var listaPintada = false;

    function hayCache() {
        return !!(global.MaquitaCacheChat && global.MaquitaCacheChat.disponible());
    }

    function hiloVacio() {
        var hilo = document.getElementById('chatMessages');
        return !hilo || hilo.querySelectorAll('.message').length === 0;
    }

    /* --- la lista de conversaciones, nada mas abrir --- */
    async function pintarListaGuardada() {
        if (listaPintada || !hayCache()) return;
        try {
            var guardadas = await global.MaquitaCacheChat.leerLista();
            if (!guardadas || !guardadas.length) return;
            var contenedor = document.getElementById('conversationsList');
            // si ya hay conversaciones pintadas, el servidor gano la carrera: no se toca
            if (contenedor && contenedor.querySelector('.conversation-item')) return;
            // `conversations` y `renderConversations` viven en el ambito compartido de los
            // scripts del chat: se reutiliza SU pintado, no se inventa otro
            conversations = guardadas;
            if (typeof renderConversations === 'function') {
                renderConversations();
                listaPintada = true;
                marcar('lista');
            }
        } catch (e) {
            console.warn('T-49: no se pudo pintar la lista guardada', e);
        }
    }

    /* --- los mensajes de la conversacion que se abre --- */
    function envolverCargaDeMensajes() {
        if (typeof loadMessages !== 'function' || loadMessages.__mqCache) return false;
        var original = loadMessages;
        var envuelta = function (conversationId, beforeId) {
            // solo en la primera carga: al pedir mas hacia arriba (beforeId) no aplica
            if (!beforeId && hayCache() && hiloVacio()) {
                global.MaquitaCacheChat.leerMensajes(conversationId).then(function (guardados) {
                    if (guardados && guardados.length && hiloVacio()
                        && typeof renderMessages === 'function') {
                        renderMessages(guardados, true);
                        marcar('mensajes');
                    }
                }).catch(function () {});
            }
            return original.apply(this, arguments);
        };
        envuelta.__mqCache = true;
        loadMessages = envuelta;
        if (global.loadMessages) global.loadMessages = envuelta;
        return true;
    }

    /* Deja constancia de que se pinto desde el equipo. No se enseña a la persona
       -Teams tampoco lo hace-, pero sirve para medirlo en las pruebas y para poder
       responder «esto vino del cache» cuando alguien pregunte por que fue instantaneo. */
    function marcar(que) {
        global.__mqPintadoLocal = global.__mqPintadoLocal || {};
        global.__mqPintadoLocal[que] = Date.now();
    }

    function iniciar() {
        pintarListaGuardada();
        envolverCargaDeMensajes();
    }

    // cuanto antes: el sentido de esto es adelantarse a la red
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', iniciar);
    } else {
        iniciar();
    }
    var intentos = 0;
    var reloj = setInterval(function () {
        if (envolverCargaDeMensajes() || ++intentos > 20) clearInterval(reloj);
    }, 400);

    global.MaquitaPintadoLocal = {
        pintarLista: pintarListaGuardada,
        seUso: function () { return global.__mqPintadoLocal || {}; },
    };
})(window);
