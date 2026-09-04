/* ============================================================================
 * T-45 (piezas finales) · Detalles del lienzo, al estilo Teams:
 *   1. marcador «Mensajes nuevos» al abrir una conversación con pendientes;
 *   2. botón «⌄ Ir al final» cuando subes a leer historia;
 *   3. vista previa del archivo DENTRO de la caja antes de enviarlo (con la X).
 * (El selector de emojis con buscador y categorías ya existía.)
 * No toca el motor del chat: envuelve lo que ya hay.
 * ========================================================================== */
(function () {
    'use strict';

    // ---------- 1. marcador «Mensajes nuevos» ----------
    function conversacionDe(id) {
        try { return (Array.isArray(conversations) ? conversations : []).find(function (c) { return String(c.id) === String(id); }); }
        catch (e) { return null; }
    }
    function marcarNuevos(sinLeer) {
        var cont = document.getElementById('chatMessages');
        if (!cont || !sinLeer || sinLeer < 1) return;
        var previo = cont.querySelector('.mq-nuevos');
        if (previo) previo.remove();
        var recibidos = Array.prototype.slice.call(cont.querySelectorAll('.message.received'));
        var desde = recibidos[recibidos.length - sinLeer];
        if (!desde) return;
        var marca = document.createElement('div');
        marca.className = 'mq-nuevos';
        marca.textContent = sinLeer === 1 ? '1 mensaje nuevo' : sinLeer + ' mensajes nuevos';
        desde.parentNode.insertBefore(marca, desde);
        marca.scrollIntoView({ block: 'center', behavior: 'smooth' });
    }
    var abrirOriginal = window.openConversation;
    if (typeof abrirOriginal === 'function') {
        window.openConversation = function (id, tipo) {
            var conv = conversacionDe(id);
            var sinLeer = conv ? (conv.unread_count || conv.no_leidos || conv.unread || 0) : 0;
            var r = abrirOriginal.apply(this, arguments);
            if (sinLeer > 0) setTimeout(function () { marcarNuevos(sinLeer); }, 1200);
            return r;
        };
    }

    // ---------- 2. «⌄ Ir al final» ----------
    function contenedorConScroll(el) {
        // quien scrollea puede ser el propio lienzo o su contenedor
        var n = el;
        for (var i = 0; i < 4 && n; i++) {
            var o = getComputedStyle(n).overflowY;
            if ((o === 'auto' || o === 'scroll') && n.scrollHeight > n.clientHeight + 40) return n;
            n = n.parentElement;
        }
        return el;
    }

    function prepararIrAlFinal() {
        var lienzo = document.getElementById('chatMessages');
        if (!lienzo || lienzo.__mqIrFinal) return;
        lienzo.__mqIrFinal = true;
        var cont = contenedorConScroll(lienzo);
        var boton = document.createElement('button');
        boton.className = 'mq-ir-final';
        boton.type = 'button';
        boton.title = 'Ir al último mensaje';
        boton.innerHTML = '<i class="fas fa-chevron-down"></i><span class="mq-ir-final-num" hidden></span>';
        boton.addEventListener('click', function () {
            cont.scrollTo({ top: cont.scrollHeight, behavior: 'smooth' });
        });
        (cont.parentNode || document.body).appendChild(boton);
        function revisar() {
            var lejos = cont.scrollHeight - cont.scrollTop - cont.clientHeight > 220;
            boton.classList.toggle('visible', lejos);
            if (!lejos) { var n = boton.querySelector('.mq-ir-final-num'); if (n) n.hidden = true; }
        }
        cont.addEventListener('scroll', revisar, { passive: true });
        window.mqRevisarIrAlFinal = revisar;
        new MutationObserver(function () {
            var lejos = cont.scrollHeight - cont.scrollTop - cont.clientHeight > 220;
            if (lejos) {
                var n = boton.querySelector('.mq-ir-final-num');
                if (n) { n.hidden = false; n.textContent = String((parseInt(n.textContent, 10) || 0) + 1); }
            }
            revisar();
        }).observe(lienzo, { childList: true });
        revisar();
    }

    // ---------- 3. vista previa del archivo dentro de la caja ----------
    function humano(n) {
        n = Number(n || 0); var u = ['B', 'KB', 'MB', 'GB'], i = 0;
        while (n >= 1024 && i < 3) { n /= 1024; i++; }
        return n.toFixed(i ? 1 : 0) + ' ' + u[i];
    }
    function tarjetaAdjunto(file, enviar) {
        quitarTarjeta();
        var caja = document.querySelector('.chat-input-wrapper') || document.getElementById('messageInput');
        if (!caja) return false;
        var t = document.createElement('div');
        t.className = 'mq-adjunto';
        t.innerHTML = '<i class="fas fa-file"></i><div class="mq-adjunto-datos"><b></b><small>' + humano(file.size) + '</small></div>' +
                      '<button type="button" class="mq-adjunto-enviar" title="Enviar">Enviar</button>' +
                      '<button type="button" class="mq-adjunto-quitar" title="Quitar">&times;</button>';
        t.querySelector('b').textContent = file.name;
        t.querySelector('.mq-adjunto-quitar').onclick = quitarTarjeta;
        t.querySelector('.mq-adjunto-enviar').onclick = function () {
            t.querySelector('.mq-adjunto-enviar').disabled = true;
            t.querySelector('.mq-adjunto-enviar').textContent = 'Enviando…';
            Promise.resolve(enviar()).finally(quitarTarjeta);
        };
        (caja.parentNode || document.body).insertBefore(t, caja);
        return true;
    }
    function quitarTarjeta() {
        var t = document.querySelector('.mq-adjunto');
        if (t) t.remove();
    }
    var seleccionOriginal = window.handleFileSelect;
    if (typeof seleccionOriginal === 'function' && !window.__mqAdjunto) {
        window.__mqAdjunto = true;
        window.handleFileSelect = function (ev) {
            var file = ev && ev.target && ev.target.files && ev.target.files[0];
            if (!file) return seleccionOriginal.apply(this, arguments);
            var entrada = ev.target;
            var puesta = tarjetaAdjunto(file, function () {
                return (typeof uploadAndSendFile === 'function')
                    ? uploadAndSendFile(file, file.type && file.type.indexOf('image') === 0 ? 'image' : 'document')
                    : null;
            });
            entrada.value = '';               // la selección ya está en la tarjeta
            if (!puesta) return seleccionOriginal.call(this, ev);
        };
    }

    function iniciar() { prepararIrAlFinal(); }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', iniciar);
    else iniciar();
    setInterval(prepararIrAlFinal, 3000);
})();
