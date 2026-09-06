/* T-45 punto 10 - Vistos inmediatos y claros (01/09/2026)
 *
 * Ya existia el circuito de estados (chat-vistos.js + msg_status). Faltaban las
 * dos cosas que pidio soporte:
 *   1. que «leido» se NOTE: los dos vistos encendidos + la palabra «Leido»
 *      («Leido por N» en grupos) junto a la hora.
 *   2. que sea INMEDIATO: sin el retardo de 250 ms + 200 ms aleatorios que
 *      traia updateMessageStatus, y reaccionando tambien a `messages_read`
 *      (que llega al room del remitente aunque no tenga la conversacion
 *      abierta).
 * No se toca chat-vistos.js ni chat-tiempo-real.js: se envuelve lo que hay. */
(function () {
    'use strict';

    var LEIDOS = Object.create(null);   // id de mensaje -> cuantos lo leyeron

    function esGrupo() {
        var c = document.querySelector('.chat-header, #chatHeader');
        return !!(c && c.dataset && c.dataset.tipo === 'group');
    }

    function textoLeido(veces) {
        return (esGrupo() && veces > 1) ? 'Leído por ' + veces : 'Leído';
    }

    /* pinta el estado de UN mensaje, sin esperas */
    function pintar(id, estado, veces) {
        var msg = document.querySelector('.message[data-message-id="' + id + '"]');
        if (!msg) return;
        var icono = msg.querySelector('.message-status');
        if (!icono) return;

        if (estado === 'read') {
            icono.className = 'fas fa-check-double message-status read';
            icono.title = 'Leído';
            var meta = msg.querySelector('.message-meta') || icono.parentNode;
            var etiqueta = meta.querySelector('.mq-leido');
            if (!etiqueta) {
                etiqueta = document.createElement('span');
                etiqueta.className = 'mq-leido';
                meta.appendChild(etiqueta);
            }
            etiqueta.textContent = textoLeido(veces || LEIDOS[id] || 1);
        } else if (estado === 'delivered' && !icono.classList.contains('read')) {
            icono.className = 'fas fa-check-double message-status delivered';
            icono.title = 'Entregado';
        }
    }

    /* marca como leidos todos los propios hasta un id (o todos, si no viene) */
    function pintarHasta(hasta, lector) {
        var propios = document.querySelectorAll('.message.sent[data-message-id]');
        Array.prototype.forEach.call(propios, function (msg) {
            var id = msg.getAttribute('data-message-id');
            if (hasta && Number(id) > Number(hasta)) return;
            var icono = msg.querySelector('.message-status');
            if (!icono) return;
            if (lector) {
                var vistos = LEIDOS[id + ':quienes'] || (LEIDOS[id + ':quienes'] = []);
                if (vistos.indexOf(lector) === -1) vistos.push(lector);
                LEIDOS[id] = vistos.length;
            }
            pintar(id, 'read', LEIDOS[id]);
        });
    }

    /* sin retardo: se sustituye el pintado lento por el inmediato */
    function acelerar() {
        if (window.updateMessageStatus && !window.updateMessageStatus.__mq) {
            var previo = window.updateMessageStatus;
            var rapido = function (id, estado) { pintar(id, estado); };
            rapido.__mq = true;
            rapido.original = previo;
            window.updateMessageStatus = rapido;
        }
    }

    function enganchar(s) {
        if (!s || s.__vistosClaros) return;
        s.__vistosClaros = true;

        s.on('msg_status', function (d) {
            if (!d) return;
            var ids = Array.isArray(d.ids) ? d.ids : (d.id ? [d.id] : []);
            var estado = d.status === 'read' ? 'read' : 'delivered';
            ids.forEach(function (id) { pintar(id, estado, d.readers); });
        });

        /* el aviso que llega al room user_<id> del remitente: es el que hace que
           el visto se encienda aunque no tenga la conversacion en pantalla */
        s.on('messages_read', function (d) {
            if (!d) return;
            pintarHasta(d.hasta_mensaje_id || d.until_message_id, d.reader_id || d.read_by);
        });
    }

    function buscarSocket() {
        acelerar();
        var s = window._chatSocketVistos
            || (window.chatApp && window.chatApp.socket)
            || (window.chat && window.chat.socket)
            || window.socket;
        if (s) enganchar(s);
    }

    document.addEventListener('DOMContentLoaded', buscarSocket);
    var intentos = 0;
    var reloj = setInterval(function () {
        buscarSocket();
        if (++intentos > 20 || (window._chatSocketVistos && window._chatSocketVistos.__vistosClaros)) {
            clearInterval(reloj);
        }
    }, 1000);

    window.mqPintarVisto = pintar;   // para las pruebas de humo
})();
