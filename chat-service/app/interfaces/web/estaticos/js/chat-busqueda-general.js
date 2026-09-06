/* T-45 punto 9 (afinacion) - Lo transversal vive en el buscador de la izquierda (01/09/2026)
 *
 * Reparto de ambitos acordado con soporte:
 *   - La lupa de la cabecera busca UNICAMENTE dentro de la conversacion abierta.
 *   - Este buscador («Buscar conversaciones...») es el transversal: titulos de
 *     conversaciones, CONTENIDO de todos los chats y personas del directorio.
 *
 * Lo que ya existia (filtrar titulos y proponer companeros) se conserva: aqui solo se
 * suma la seccion «Mensajes», que es lo que faltaba. Al abrir a una persona se usa
 * /conversations/direct, que recupera la conversacion existente en vez de crear otra.
 */
(function () {
    'use strict';

    var TIEMPO = 320;
    var reloj = null;

    function escapar(t) {
        var d = document.createElement('div');
        d.textContent = t == null ? '' : String(t);
        return d.innerHTML;
    }

    function resaltar(texto, termino) {
        var limpio = escapar(texto);
        if (!termino) return limpio;
        var patron = termino.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        return limpio.replace(new RegExp('(' + patron + ')', 'ig'), '<mark>$1</mark>');
    }

    function recorte(texto, termino) {
        var t = (texto || '').replace(/\s+/g, ' ').trim();
        var i = t.toLowerCase().indexOf((termino || '').toLowerCase());
        if (i > 40) t = '…' + t.slice(i - 30);
        return t.length > 120 ? t.slice(0, 120) + '…' : t;
    }

    function quitarSeccion() {
        var s = document.getElementById('mensajesBusqueda');
        if (s) s.remove();
    }

    async function buscarEnTodos(termino) {
        quitarSeccion();
        var q = (termino || '').trim();
        if (q.length < 2) return;
        var lista = document.getElementById('conversationsList');
        if (!lista) return;
        try {
            var r = await fetch('/api/chat/buscar-mensajes?q=' + encodeURIComponent(q));
            var d = await r.json();
            var res = (d && d.resultados) || [];
            if (!res.length) return;

            var sec = document.createElement('div');
            sec.id = 'mensajesBusqueda';
            sec.innerHTML = '<div class="search-section-title">Mensajes</div>' +
                res.slice(0, 20).map(function (m) {
                    var f = m.fecha ? new Date(m.fecha) : null;
                    var fecha = f ? f.toLocaleDateString('es-EC', {day: '2-digit', month: 'short'}) : '';
                    return '<div class="conversation-item mq-resultado-mensaje" ' +
                        'data-conv="' + m.conversation_id + '" data-msg="' + m.id + '">' +
                        '<div class="conversation-info">' +
                        '<div class="conversation-name">' + escapar(m.titulo || 'Conversación') +
                        '<span class="mq-fecha-resultado">' + fecha + '</span></div>' +
                        '<div class="conversation-preview">' +
                        escapar((m.remitente || '') + ': ') + resaltar(recorte(m.contenido, q), q) +
                        '</div></div></div>';
                }).join('');

            /* el clic lleva AL mensaje dentro de su conversacion */
            sec.addEventListener('click', function (ev) {
                var fila = ev.target.closest('.mq-resultado-mensaje');
                if (!fila) return;
                abrirEn(Number(fila.dataset.conv), Number(fila.dataset.msg));
            });
            lista.appendChild(sec);
        } catch (e) {
            console.error('buscar en todos los chats:', e);
        }
    }

    /* abre la conversacion y salta al mensaje, resaltandolo (clase ya existente
       `msg-resaltado`); si la vista tarda en pintar, se reintenta unos segundos */
    function abrirEn(conv, msg) {
        if (typeof window.openConversation === 'function') {
            window.openConversation(conv, 'direct');
        } else {
            window.location.href = '/chat/conversation/' + conv + '?msg=' + msg;
            return;
        }
        var intentos = 0;
        var espera = setInterval(function () {
            var el = document.querySelector('.message[data-message-id="' + msg + '"]');
            if (el) {
                clearInterval(espera);
                el.scrollIntoView({block: 'center', behavior: 'smooth'});
                el.classList.add('msg-resaltado');
                setTimeout(function () { el.classList.remove('msg-resaltado'); }, 2000);
            } else if (++intentos > 24) {
                clearInterval(espera);
            }
        }, 250);
    }

    /* se envuelve el filtro existente sin tocar chat-lista.js */
    function envolver() {
        if (typeof window.filterConversations !== 'function' || window.filterConversations.__mq) return false;
        var previo = window.filterConversations;
        var nuevo = function (valor) {
            var r = previo.apply(this, arguments);
            clearTimeout(reloj);
            var q = (valor || '').trim();
            if (q.length < 2) quitarSeccion();
            else reloj = setTimeout(function () { buscarEnTodos(q); }, TIEMPO);
            return r;
        };
        nuevo.__mq = true;
        window.filterConversations = nuevo;
        return true;
    }

    if (!envolver()) {
        var intentos = 0;
        var espera = setInterval(function () {
            if (envolver() || ++intentos > 20) clearInterval(espera);
        }, 500);
    }

    window.mqBuscarEnTodos = buscarEnTodos;   // para las pruebas de humo
})();
