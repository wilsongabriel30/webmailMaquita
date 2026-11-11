/* T-101 · Pestañas «Archivos» y «Fotos» de una conversación: lista completa desde el servidor.
 * Antes solo se ocultaban los mensajes sin archivo de entre los ya cargados en pantalla (chat-encabezado-teams.js),
 * así que en una conversación larga no salían los antiguos. Aquí, al elegir esas pestañas, se muestra en su lugar
 * un panel con todos (chat-archivos-nucleo.js). No toca el encabezado: escucha los clics en sus pestañas. */
(function () {
    'use strict';
    var panel = null, lista = null, vista = 'chat', conversacionMostrada = null;

    function conversacionActual() {
        try { return (typeof currentConversationId !== 'undefined' && currentConversationId) || window.currentConversationId || null; } catch (e) { return window.currentConversationId || null; }
    }
    function area() { return document.getElementById('chatActiveArea'); }

    function verEnChat(a) {
        var chat = document.querySelector('.mq-pestana[data-vista="chat"]');
        if (chat) chat.click();
        // el mensaje puede no estar cargado todavía: se intenta dos veces
        var intentos = 0;
        (function ir() {
            intentos++;
            var m = document.querySelector('.chat-messages .message[data-message-id="' + a.mensaje_id + '"]');
            if (m) {
                if (typeof window.irAMensajeCitado === 'function') { try { window.irAMensajeCitado(a.mensaje_id); return; } catch (e) {} }
                m.scrollIntoView({ block: 'center' });
            } else if (intentos < 2) { setTimeout(ir, 600); }
            else if (window.toastr) { window.toastr.info('Ese mensaje es antiguo: sube en la conversación para llegar a él.'); }
        })();
    }

    function mostrar(cual) {
        var a = area(), conv = conversacionActual();
        vista = cual;
        if (!a) return;
        if (cual === 'chat' || !conv || !window.MaquitaArchivos) {
            a.classList.remove('mq-viendo-archivos');
            if (panel) panel.hidden = true;
            return;
        }
        if (!panel) {
            panel = document.createElement('div');
            panel.id = 'mqArchivosPanel';
            var hilo = document.getElementById('chatMessages');
            if (hilo && hilo.parentNode) hilo.parentNode.insertBefore(panel, hilo); else a.appendChild(panel);
        }
        panel.hidden = false;
        a.classList.add('mq-viendo-archivos');
        if (!lista) {
            lista = window.MaquitaArchivos.crear(panel, {
                conversacion: conv, clase: cual, verEnChat: verEnChat, mostrarConversacion: false,
                vacio: { archivos: 'Todavía no se han compartido archivos en esta conversación.',
                         fotos: 'Todavía no se han compartido fotos en esta conversación.' }
            });
        } else {
            if (conv !== conversacionMostrada) lista.conversacion(conv);
            lista.clase(cual);
        }
        conversacionMostrada = conv;
    }

    document.addEventListener('click', function (e) {
        var b = e.target.closest && e.target.closest('.mq-pestana');
        if (b && b.dataset && b.dataset.vista) mostrar(b.dataset.vista);
    });

    // Al cambiar de conversación con la pestaña abierta, se carga la lista de la nueva.
    setInterval(function () {
        if (vista === 'chat') return;
        var conv = conversacionActual();
        var activa = document.querySelector('.mq-pestana.activa');
        var cual = activa && activa.dataset ? activa.dataset.vista : 'chat';
        if (cual === 'chat' || !conv) { mostrar('chat'); return; }
        if (conv !== conversacionMostrada) mostrar(cual);
    }, 400);
})();
