/* T-101 · Aviso al enviar un documento con el MISMO NOMBRE que otro que ya está en la conversación.
 * Si el contenido es distinto, la persona elige: reemplazar el anterior (en el Drive queda como versión nueva),
 * guardar los dos (se renombra el nuevo) o enviar el anterior sin subir nada.
 * Envuelve uploadAndSendFile (clip, pegar y arrastrar). Se carga ANTES que chat-adjuntos-dedup.js: así, si la
 * persona decide subirlo, sigue pasando por la comprobación de «ya enviaste este archivo».
 * Solo documentos: fotos, vídeos y audios se llaman casi siempre igual («image.png») y no tiene sentido preguntar. */
(function () {
    'use strict';
    if (typeof uploadAndSendFile !== 'function') return;
    var siguiente = uploadAndSendFile;
    var LIMITE = 200 * 1024 * 1024;

    function texto(v) { var d = document.createElement('div'); d.textContent = v == null ? '' : String(v); return d.innerHTML; }
    function tamano(n) { n = Number(n || 0); var u = ['B', 'KB', 'MB', 'GB'], i = 0; while (n >= 1024 && i < 3) { n /= 1024; i++; } return (i ? n.toFixed(1).replace('.', ',') : n) + ' ' + u[i]; }
    function fecha(t) { try { return new Date(t).toLocaleString('es-EC', { dateStyle: 'medium', timeStyle: 'short' }); } catch (e) { return t || ''; } }
    function conversacion() { try { return (typeof currentConversationId !== 'undefined' && currentConversationId) || window.currentConversationId || null; } catch (e) { return window.currentConversationId || null; } }
    function esDocumento(f) { return !/^(image|video|audio)\//i.test(f.type || ''); }

    async function sha256(file) {
        if (!window.crypto || !crypto.subtle || file.size > LIMITE) return '';
        var h = await crypto.subtle.digest('SHA-256', await file.arrayBuffer());
        return Array.from(new Uint8Array(h)).map(function (b) { return b.toString(16).padStart(2, '0'); }).join('');
    }

    function preguntar(info, file) {
        return new Promise(function (resolver) {
            var a = info.archivo, m = document.createElement('div');
            m.className = 'mq-mn-fondo'; m.setAttribute('role', 'dialog'); m.setAttribute('aria-modal', 'true'); m.setAttribute('aria-label', 'Ya hay un archivo con ese nombre');
            m.innerHTML = '<div class="mq-mn-caja">' +
                '<h2 class="mq-mn-titulo">Ya hay un archivo con ese nombre</h2>' +
                '<p class="mq-mn-texto">En esta conversación ya está <b>' + texto(a.nombre) + '</b>, y el que vas a enviar es distinto.</p>' +
                '<div class="mq-mn-comparar">' +
                  '<div><span>El que ya está</span><b>' + texto(tamano(a.bytes)) + '</b><small>' + texto((a.propio ? 'Lo enviaste tú' : 'De ' + a.remitente) + ' · ' + fecha(a.fecha)) + '</small></div>' +
                  '<div><span>El nuevo</span><b>' + texto(tamano(file.size)) + '</b><small>' + texto('Modificado ' + fecha(file.lastModified)) + '</small></div>' +
                '</div>' +
                '<div class="mq-mn-opciones">' +
                  '<button type="button" class="mq-mn-boton mq-mn-principal" data-op="reemplazar"><b>Reemplazar el anterior</b><small>El nuevo pasa a ser la versión actual en el Drive; el anterior queda en su historial de versiones.</small></button>' +
                  '<button type="button" class="mq-mn-boton" data-op="ambos"><b>Guardar los dos</b><small>El nuevo se envía como «' + texto(info.nombre_libre) + '».</small></button>' +
                  '<button type="button" class="mq-mn-boton" data-op="anterior"><b>Enviar el anterior</b><small>No se sube nada: se vuelve a enviar el que ya estaba.</small></button>' +
                '</div>' +
                '<div class="mq-mn-pie"><button type="button" class="mq-mn-cancelar" data-op="cancelar">Cancelar</button></div></div>';
            function cerrar(op) { document.removeEventListener('keydown', tecla, true); m.remove(); resolver(op); }
            function tecla(e) { if (e.key === 'Escape') { e.stopPropagation(); cerrar('cancelar'); } }
            m.addEventListener('click', function (e) {
                var b = e.target.closest('[data-op]');
                if (b) cerrar(b.getAttribute('data-op')); else if (e.target === m) cerrar('cancelar');
            });
            document.addEventListener('keydown', tecla, true);
            document.body.appendChild(m);
            var primero = m.querySelector('.mq-mn-principal'); if (primero) primero.focus();
        });
    }

    async function enviarAnterior(conv, id) {
        var r = await fetch('/api/chat/conversations/' + conv + '/archivos/' + id + '/reenviar', { method: 'POST', credentials: 'same-origin' });
        var d = await r.json().catch(function () { return null; });
        if (r.ok && d && d.success && d.message) {
            var cont = document.getElementById('chatMessages');
            if (cont && typeof renderSingleMessage === 'function' && !cont.querySelector('[data-message-id="' + d.message.id + '"]')) {
                cont.insertAdjacentHTML('beforeend', renderSingleMessage(d.message));
                if (typeof scrollToBottom === 'function') scrollToBottom(cont);
            }
            if (typeof loadConversations === 'function') loadConversations();
            return true;
        }
        if (window.toastr) toastr.error((d && d.mensaje) || 'No se pudo enviar el anterior');
        return false;
    }

    uploadAndSendFile = async function (file, type) {
        try {
            var conv = conversacion();
            if (conv && file && file.name && esDocumento(file)) {
                var sha = await sha256(file);
                var r = await fetch('/api/chat/conversations/' + conv + '/archivos/existe?nombre=' + encodeURIComponent(file.name) +
                                    '&bytes=' + file.size + (sha ? '&sha256=' + sha : ''), { credentials: 'same-origin' });
                var info = r.ok ? await r.json() : null;
                if (info && info.existe && !info.mismo_contenido && info.archivo) {
                    var op = await preguntar(info, file);
                    if (op === 'cancelar') return;
                    if (op === 'anterior') { if (await enviarAnterior(conv, info.archivo.id)) return; return; }
                    if (op === 'ambos' && info.nombre_libre) {
                        file = new File([file], info.nombre_libre, { type: file.type, lastModified: file.lastModified });
                    }
                    // «reemplazar»: se sube con el mismo nombre; el Drive guarda el anterior como versión
                }
            }
        } catch (e) { console.warn('[mismo-nombre] se sube normal:', e); }
        return siguiente(file, type);
    };
    window.uploadAndSendFile = uploadAndSendFile;
})();
