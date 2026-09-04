/* T-48 - Pintar el puntito de estado (02/09/2026)
 *
 * El servidor manda `estado` (conectado / ausente / ocupado) junto a cada persona, y calcula
 * el AUTO-AUSENTE y el AUTO-OCUPADO: aqui NO se decide nada, solo se pinta lo que llega.
 * Cuando alguien cambia su estado, el servidor avisa por el socket con `estado_presencia` y
 * el puntito cambia solo, sin recargar.
 */
(function () {
    'use strict';

    var TEXTO = {disponible: 'Disponible', ocupado: 'Ocupado', no_molestar: 'No molestar',
                 vuelvo_enseguida: 'Vuelvo enseguida', ausente: 'Ausente',
                 desconectado: 'Desconectado'};
    var ESTADOS = Object.create(null);   // usuario -> estado conocido

    function pintarUno(el, estado) {
        el.classList.add('mq-estado');
        el.dataset.estado = estado || 'desconocido';
        el.title = TEXTO[estado] || 'Sin dato';
    }

    /* pinta a todos los que lleven data-usuario en la pantalla */
    function pintar(usuarioId, estado) {
        if (!usuarioId) return;
        ESTADOS[usuarioId] = estado;
        var sel = '[data-usuario-id="' + usuarioId + '"], [data-user-id="' + usuarioId + '"]';
        Array.prototype.forEach.call(document.querySelectorAll(sel), function (el) {
            var destino = el.querySelector('.avatar, .conversation-avatar, img') || el;
            pintarUno(destino, estado);
        });
        var texto = document.querySelector('.mq-estado-texto[data-usuario-id="' + usuarioId + '"]');
        if (texto) {
            texto.dataset.estado = estado;
            texto.textContent = TEXTO[estado] || 'Sin dato';
        }
    }

    /* pide de una vez el estado de todas las personas visibles */
    async function refrescarVisibles() {
        var ids = new Set();
        Array.prototype.forEach.call(
            document.querySelectorAll('[data-usuario-id], [data-user-id]'), function (el) {
                var id = el.dataset.usuarioId || el.dataset.userId;
                if (id && /^\d+$/.test(id)) ids.add(Number(id));
            });
        if (!ids.size) return;
        try {
            var r = await fetch('/api/chat/estado/varios', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({usuarios: Array.from(ids)})
            });
            var d = await r.json();
            Object.keys(d.estados || {}).forEach(function (id) { pintar(Number(id), d.estados[id]); });
        } catch (e) {
            console.warn('estados de presencia:', e);
        }
    }

    /* el aviso del servidor cuando alguien cambia de estado */
    function engancharSocket() {
        var s = window._chatSocketVistos || (window.chatApp && window.chatApp.socket) || window.socket;
        if (!s || s.__estados) return false;
        s.__estados = true;
        s.on('estado_presencia', function (d) {
            if (d && d.usuario_id) pintar(Number(d.usuario_id), d.estado);
        });
        return true;
    }

    document.addEventListener('DOMContentLoaded', function () {
        refrescarVisibles();
        engancharSocket();
    });
    /* de vez en cuando, por si alguien se quedo quieto y paso a Ausente solo */
    setInterval(refrescarVisibles, 60000);
    var intentos = 0;
    var reloj = setInterval(function () {
        if (engancharSocket() || ++intentos > 20) clearInterval(reloj);
    }, 1000);

    window.mqPintarEstado = pintar;          // para las pruebas de humo
    window.mqRefrescarEstados = refrescarVisibles;
})();
