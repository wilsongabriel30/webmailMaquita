/* Chat institucional - Responder / citar mensajes (2026-08-27)
 * Clic derecho sobre un mensaje -> "Responder": muestra una barra de cita sobre el
 * input, envía reply_to (WebSocket u HTTP) y pinta la cita en el mensaje. Se apoya en
 * las funciones globales de chat-page.js sin modificarlas (envolturas). */
(function () {
    'use strict';

    let respuestaA = null;            // {id, sender_name, content}
    const cacheCitas = {};            // id -> cita (para mensajes que llegan en vivo)

    function esc(s) {
        return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    // ---------- Cita a partir de lo que ya está en pantalla ----------
    function citaDesdeDom(mid) {
        const el = document.querySelector('.message[data-message-id="' + mid + '"]');
        if (!el) return null;
        const propio = el.classList.contains('sent');
        let nombre = propio ? 'Tú' : ((el.querySelector('.message-sender') || {}).textContent || '').trim();
        if (!nombre) {
            const cab = document.querySelector('#chatHeaderName, .chat-header-name, .chat-header h5, .chat-header h6');
            nombre = cab ? cab.textContent.trim() : 'Usuario';
        }
        let texto = '';
        const t = el.querySelector('.message-text');
        if (t) texto = t.textContent.trim();
        else if (el.querySelector('.message-gif')) texto = 'GIF';
        else if (el.querySelector('.message-media img')) texto = 'Imagen';
        else if (el.querySelector('audio')) texto = 'Audio';
        else if (el.querySelector('.message-media, .message-file, .message-document')) texto = 'Archivo';
        return { id: Number(mid), sender_name: nombre, content: texto.slice(0, 200) };
    }

    function htmlCita(c, pendiente) {
        return '<div class="msg-cita" data-cita-de="' + esc(c.id) + '"' + (pendiente ? ' data-cita-pendiente="1"' : '') +
               ' onclick="event.stopPropagation();irAMensajeCitado(' + Number(c.id) + ')" title="Ir al mensaje original">' +
               '<div class="msg-cita-nombre">' + esc(c.sender_name || '') + '</div>' +
               '<div class="msg-cita-texto">' + esc(c.content || '…') + '</div></div>';
    }

    // ---------- Barra de cita sobre el input ----------
    function pintarBarra() {
        let barra = document.getElementById('barraRespuesta');
        if (!respuestaA) { if (barra) barra.remove(); return; }
        if (!barra) {
            const cont = document.querySelector('.chat-input-container');
            if (!cont) return;
            barra = document.createElement('div');
            barra.id = 'barraRespuesta';
            cont.insertBefore(barra, cont.firstChild);
        }
        barra.innerHTML = '<div class="barra-respuesta-cuerpo"><i class="fas fa-reply"></i><div>' +
            '<div class="msg-cita-nombre">Respondiendo a ' + esc(respuestaA.sender_name) + '</div>' +
            '<div class="msg-cita-texto">' + esc(respuestaA.content || '…') + '</div></div></div>' +
            '<button type="button" class="barra-respuesta-cerrar" onclick="cancelarRespuesta()" title="Cancelar (Esc)"><i class="fas fa-times"></i></button>';
    }

    window.responderMensaje = function (mid) {
        if (typeof cerrarMenuConvCtx === 'function') cerrarMenuConvCtx();
        respuestaA = citaDesdeDom(mid) || { id: Number(mid), sender_name: '', content: '' };
        pintarBarra();
        const input = document.getElementById('messageInput');
        if (input) input.focus();
    };

    window.cancelarRespuesta = function () { respuestaA = null; pintarBarra(); };

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && respuestaA) { e.stopPropagation(); window.cancelarRespuesta(); }
    }, true);

    window.irAMensajeCitado = function (mid) {
        const el = document.querySelector('.message[data-message-id="' + mid + '"]');
        if (!el) { if (window.toastr) toastr.info('El mensaje original no está cargado en pantalla'); return; }
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        el.classList.add('msg-resaltado');
        setTimeout(function () { el.classList.remove('msg-resaltado'); }, 1600);
    };

    // ---------- Menú contextual: agregar "Responder" ----------
    const menuOriginal = window.mostrarMenuMensajeCtx;
    window.mostrarMenuMensajeCtx = function (e, msgEl) {
        if (typeof menuOriginal === 'function') menuOriginal(e, msgEl);
        const menu = document.getElementById('convCtxMenu');
        const mid = msgEl && msgEl.getAttribute('data-message-id');
        if (!menu || !mid || /^temp_/.test(mid)) return;
        const sep = menu.querySelector('div[style*="height:1px"]');
        const item = document.createElement('div');
        item.style.cssText = 'padding:9px 16px;cursor:pointer;display:flex;gap:10px;align-items:center;';
        item.innerHTML = '<i class="fas fa-reply" style="width:16px;opacity:.7;"></i>Responder';
        item.onmouseover = function () { this.style.background = '#f0f2f5'; };
        item.onmouseout = function () { this.style.background = ''; };
        item.onclick = function () { window.responderMensaje(mid); };
        if (sep && sep.nextSibling) menu.insertBefore(item, sep.nextSibling); else menu.appendChild(item);
    };

    // ---------- Envío: adjuntar reply_to ----------
    // WebSocket (chat-ultrafast.js): envolver send() del prototipo
    function envolverUltraFast() {
        const Clase = window.ChatUltraFast || window.ChatRealtime;
        if (!Clase || !Clase.prototype || Clase.prototype.__conCita) return false;
        const sendOriginal = Clase.prototype.send;
        Clase.prototype.send = function (conversationId, content, type, options) {
            options = options || {};
            if (respuestaA && !options.reply_to && (type || 'text') === 'text') options.reply_to = respuestaA.id;
            return sendOriginal.call(this, conversationId, content, type, options);
        };
        Clase.prototype.__conCita = true;
        return true;
    }
    if (!envolverUltraFast()) document.addEventListener('DOMContentLoaded', envolverUltraFast);

    // HTTP (fallback de sendMessage): envolver fetch solo para el POST de mensajes
    const fetchOriginal = window.fetch;
    window.fetch = function (url, opts) {
        try {
            if (respuestaA && opts && opts.method === 'POST' && typeof url === 'string' && /\/api\/chat\/conversations\/\d+\/messages$/.test(url) &&
                typeof opts.body === 'string') {
                const b = JSON.parse(opts.body);
                if (b && b.message_type === 'text' && !b.reply_to_id) { b.reply_to_id = respuestaA.id; opts.body = JSON.stringify(b); }
            }
        } catch (e) { /* cuerpo no JSON: se envía tal cual */ }
        return fetchOriginal.apply(this, arguments);
    };

    // ---------- Render: pintar la cita dentro del mensaje ----------
    const renderOriginal = window.renderSingleMessage;
    window.renderSingleMessage = function (msg) {
        // Mensaje propio recién enviado (UI optimista): lleva la cita activa
        if (msg && respuestaA && msg.is_own_message && (msg.status === 'pending' || /^temp_/.test(String(msg.id))) && !msg.reply_to_id) {
            msg.reply_to_id = respuestaA.id;
            msg.reply_to = respuestaA;
            respuestaA = null;
            pintarBarra();
        }
        let html = renderOriginal(msg);
        const rid = msg && msg.reply_to_id;
        if (!rid) return html;
        let cita = msg.reply_to || cacheCitas[rid] || citaDesdeDom(rid);
        const pendiente = !cita;
        if (!cita) cita = { id: rid, sender_name: '', content: '…' };
        else cacheCitas[rid] = cita;
        html = html.replace('<div class="message-content">', '<div class="message-content">' + htmlCita(cita, pendiente));
        if (pendiente) setTimeout(function () { completarCita(rid); }, 0);
        return html;
    };

    function completarCita(rid) {
        fetchOriginal('/api/chat/messages/' + rid + '/cita', { credentials: 'same-origin' })
            .then(function (r) { return r.json(); })
            .then(function (d) {
                if (!d.success) return;
                cacheCitas[rid] = d.cita;
                document.querySelectorAll('.msg-cita[data-cita-pendiente="1"][data-cita-de="' + rid + '"]').forEach(function (el) {
                    el.outerHTML = htmlCita(d.cita, false);
                });
            }).catch(function () {});
    }

    // Al cambiar de conversación se descarta la cita pendiente
    const abrirOriginal = window.openConversation || window.selectConversation;
    if (typeof abrirOriginal === 'function') {
        const nombre = window.openConversation ? 'openConversation' : 'selectConversation';
        window[nombre] = function () { window.cancelarRespuesta(); return abrirOriginal.apply(this, arguments); };
    }
})();
