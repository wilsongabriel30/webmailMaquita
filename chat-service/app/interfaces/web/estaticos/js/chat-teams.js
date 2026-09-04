/* ============================================================================
 * T-45 · Comportamiento del look Teams en la conversación (01/09/2026).
 * Trabaja sobre los mensajes ya pintados, sin tocar el motor del chat:
 *   1. agrupa mensajes seguidos de la misma persona (≤ 5 min);
 *   2. pinta GIGANTE los mensajes que son solo emojis;
 *   3. pone separadores de día («Hoy», «Ayer», fecha) y «Leído por última vez»;
 *   4. muestra la mini-barra de reacciones al pasar el mouse;
 *   5. convierte :) :D <3 al escribir;
 *   6. activa el corrector ortográfico en español en la caja (T-45 punto 8).
 * ========================================================================== */
(function () {
    'use strict';

    var MINUTOS_AGRUPAR = 5;
    var REACCIONES = ['👍', '❤️', '😆', '😮', '😢'];
    var SOLO_EMOJIS = /^(?:[\p{Extended_Pictographic}️‍\u{1F3FB}-\u{1F3FF}]|\s){1,8}$/u;

    function fecha(el) {
        var t = el.getAttribute('data-creado') || '';
        var d = t ? new Date(t) : null;
        if (d && !isNaN(d)) return d;
        var meta = el.querySelector('.message-meta');
        return meta ? new Date() : null;   // sin dato fiable: no se agrupa por tiempo
    }

    function etiquetaDia(d) {
        var hoy = new Date(); hoy.setHours(0, 0, 0, 0);
        var dia = new Date(d); dia.setHours(0, 0, 0, 0);
        var difDias = Math.round((hoy - dia) / 86400000);
        if (difDias === 0) return 'Hoy';
        if (difDias === 1) return 'Ayer';
        return dia.toLocaleDateString('es-EC', { weekday: 'long', day: 'numeric', month: 'long' });
    }

    function esSoloEmoji(el) {
        var t = el.querySelector('.message-text');
        if (!t || el.querySelector('.message-media, .message-file')) return false;
        var texto = (t.textContent || '').trim();
        if (!texto || texto.length > 12) return false;
        try { return SOLO_EMOJIS.test(texto); } catch (e) { return false; }
    }

    function quienEnvia(el) {
        if (el.classList.contains('sent')) return 'yo';
        var n = el.querySelector('.message-sender');
        return n ? n.textContent.trim() : (el.getAttribute('data-sender') || 'otro');
    }

    function barraReacciones(el) {
        if (el.querySelector('.mq-barra-reacciones')) return;
        var id = el.getAttribute('data-message-id');
        if (!id) return;
        var barra = document.createElement('div');
        barra.className = 'mq-barra-reacciones';
        barra.innerHTML = REACCIONES.map(function (e) {
            return '<button type="button" title="Reaccionar ' + e + '" data-emoji="' + e + '">' + e + '</button>';
        }).join('') + '<button type="button" title="Más" data-mas="1">➕</button>';
        barra.addEventListener('click', function (ev) {
            var b = ev.target.closest('button'); if (!b) return;
            ev.preventDefault(); ev.stopPropagation();
            if (b.dataset.mas) {
                if (typeof window.toggleReactionPicker === 'function') window.toggleReactionPicker(Number(id), ev);
                return;
            }
            if (typeof window.addReaction === 'function') window.addReaction(Number(id), b.dataset.emoji);
            else if (typeof window.handleReactionClick === 'function') window.handleReactionClick(Number(id), b.dataset.emoji);
        });
        el.appendChild(barra);
    }

    function repasar() {
        var cont = document.getElementById('chatMessages');
        if (!cont) return;
        var mensajes = Array.prototype.slice.call(cont.querySelectorAll('.message'));
        var anterior = null, diaAnterior = '';
        mensajes.forEach(function (el) {
            // separador de día
            var d = fecha(el);
            if (d) {
                var dia = etiquetaDia(d);
                if (dia !== diaAnterior) {
                    var previo = el.previousElementSibling;
                    if (!previo || !previo.classList.contains('mq-separador')) {
                        var sep = document.createElement('div');
                        sep.className = 'mq-separador'; sep.textContent = dia;
                        el.parentNode.insertBefore(sep, el);
                    }
                    diaAnterior = dia;
                }
            }
            // agrupación con el anterior
            if (anterior && quienEnvia(anterior) === quienEnvia(el)) {
                var da = fecha(anterior), de = fecha(el);
                var seguidos = (!da || !de) ? true : (Math.abs(de - da) <= MINUTOS_AGRUPAR * 60000);
                el.classList.toggle('mq-agrupado', seguidos);
            } else {
                el.classList.remove('mq-agrupado');
            }
            el.classList.toggle('mq-solo-emoji', esSoloEmoji(el));
            barraReacciones(el);
            anterior = el;
        });
    }
    window.mqRepasarConversacion = repasar;

    // Se repasa cuando cambian los mensajes (sin tocar el motor del chat)
    function observar() {
        var cont = document.getElementById('chatMessages');
        if (!cont || cont.__mqObservado) return;
        cont.__mqObservado = true;
        var pendiente = null;
        new MutationObserver(function () {
            clearTimeout(pendiente);
            pendiente = setTimeout(repasar, 60);
        }).observe(cont, { childList: true, subtree: false });
        repasar();
    }

    // Caja de escribir: corrector en español (T-45 punto 8) y atajos de emoji
    var ATAJOS = [[/(^|\s):\)/g, '$1🙂'], [/(^|\s):D/g, '$1😄'], [/(^|\s):\(/g, '$1🙁'],
                  [/(^|\s);\)/g, '$1😉'], [/(^|\s)<3/g, '$1❤️'], [/(^|\s):p/gi, '$1😛']];
    function prepararCaja() {
        var caja = document.getElementById('messageInput');
        if (!caja || caja.__mqTeams) return;
        caja.__mqTeams = true;
        caja.setAttribute('spellcheck', 'true');
        caja.setAttribute('lang', 'es');
        caja.setAttribute('autocorrect', 'on');
        caja.addEventListener('input', function () {
            var v = caja.value, n = v;
            ATAJOS.forEach(function (a) { n = n.replace(a[0], a[1]); });
            if (n !== v) {
                var pos = caja.selectionStart + (n.length - v.length);
                caja.value = n;
                try { caja.setSelectionRange(pos, pos); } catch (e) {}
            }
        });
    }

    function iniciar() { observar(); prepararCaja(); }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', iniciar);
    else iniciar();
    setInterval(function () { observar(); prepararCaja(); }, 3000);   // por si la vista se rehace
})();
