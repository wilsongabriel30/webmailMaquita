/* T-101 · Funciones estables para la app de escritorio (atajos de teclado y mini ventana).
 * La app las llama por ExecuteScript; así no depende de nombres internos de la página, que pueden cambiar.
 * Se carga en el chat, en la ventana de llamada y en la de conferencia: cada función actúa solo donde tiene sentido
 * y devuelve true si hizo algo. window.MaquitaApp.version sube si cambia el contrato.
 *
 *   En el chat:      nuevoMensaje(), buscar(), abrirConversacion(id), irALlamadas(), irAArchivos(), cambiarTema(tema)
 *   En una llamada:  alternarMicrofono(), alternarCamara(), compartirPantalla(), colgar(), estadoLlamada()
 */
(function () {
    'use strict';
    function existe(nombre) { try { return typeof window[nombre] === 'function'; } catch (e) { return false; } }
    function llamar(nombre) { if (!existe(nombre)) return false; try { window[nombre].apply(window, [].slice.call(arguments, 1)); return true; } catch (e) { return false; } }
    function enLlamada() { return !!document.querySelector('.vc-controls'); }
    function incrustado() { return document.documentElement.classList.contains('chat-embed') ? '?embed=1' : ''; }

    var api = {
        version: 1,
        donde: function () { return enLlamada() ? (document.getElementById('grid') ? 'conferencia' : 'llamada') : (document.querySelector('.chat-container') ? 'chat' : 'otra'); },

        /* ---- chat ---- */
        nuevoMensaje: function () { return llamar('openNewChatModal'); },
        buscar: function () {
            var c = document.getElementById('searchConversations');
            if (!c) return false;
            c.focus(); c.select(); return true;
        },
        abrirConversacion: function (id) {
            var fila = document.querySelector('.conversation-item[data-conv-id="' + String(id).replace(/[^0-9]/g, '') + '"]');
            if (fila) { fila.click(); return true; }
            if (document.querySelector('.chat-container')) { location.href = '/chat/?conv=' + encodeURIComponent(id) + incrustado().replace('?', '&'); return true; }
            return false;
        },
        irALlamadas: function () { location.href = '/chat/llamadas' + incrustado(); return true; },
        irAArchivos: function () { location.href = '/chat/archivos' + incrustado(); return true; },
        cambiarTema: function (tema) {
            if (['clasico', 'fluent', 'fluent-oscuro', 'fluent-auto'].indexOf(tema) < 0) return false;
            try { localStorage.setItem('mq_chat_tema', tema); } catch (e) { return false; }
            location.reload(); return true;
        },

        /* ---- llamada y conferencia ---- */
        alternarMicrofono: function () { return enLlamada() && llamar('toggleMute'); },
        alternarCamara: function () { return enLlamada() && llamar('toggleCam'); },
        compartirPantalla: function () { return enLlamada() && llamar('toggleShare'); },
        colgar: function () { return enLlamada() && (llamar('colgar') || llamar('salir')); },
        estadoLlamada: function () {
            if (!enLlamada()) return null;
            var e = null; try { e = (typeof est !== 'undefined') ? est : null; } catch (x) { e = null; }
            var reloj = document.getElementById('vcTimer'), nombre = document.getElementById('tituloNombre') || document.getElementById('tituloSala');
            return {
                tipo: api.donde(),
                nombre: nombre ? nombre.textContent : '',
                tiempo: reloj ? reloj.textContent : '',
                conectada: !!(e && (e.conectada || (e.room && e.room.state === 'connected'))),
                microfonoApagado: !!(e && e.muted),
                camaraApagada: !!(e && (e.camOff === true || e.camOn === false)),
                participantes: document.querySelectorAll('.tile:not(.pantalla)').length || null
            };
        }
    };
    window.MaquitaApp = api;
})();
