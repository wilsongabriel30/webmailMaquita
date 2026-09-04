/* Arrastrar y soltar archivos al chat (T-31, hermano de T-27).
 * - Sobre la conversación: superposición «Suelta para enviar a <conversación>»; al soltar, sube 1..N archivos por el
 *   endpoint de subida existente (uploadAndSendFile): imagen como imagen, el resto como archivo; progreso por archivo.
 * - Sobre la caja de escribir: adjuntar con vista previa (imagen → vista previa de T-27; otros → lista para confirmar).
 * Depende de: uploadAndSendFile, currentConversationId (chat-*.js), chatPrevisualizarImagen (chat-pegar-imagen.js). */
(function () {
    function esc(t) { return String(t == null ? '' : t).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
    function humano(n) { n = Number(n || 0); var u = ['B', 'KB', 'MB', 'GB'], i = 0; while (n >= 1024 && i < 3) { n /= 1024; i++; } return n.toFixed(i ? 1 : 0) + ' ' + u[i]; }
    function conFicheros(e) { var t = e.dataTransfer && e.dataTransfer.types; return !!t && Array.prototype.indexOf.call(t, 'Files') !== -1; }
    function convId() { try { return (typeof currentConversationId !== 'undefined' && currentConversationId) || window.currentConversationId || null; } catch (e) { return null; } }
    function nombreConv() {
        var el = document.querySelector('#chatHeaderName, #conversationName, .chat-header .chat-name, .chat-header h5, .chat-header h6, .chat-header .fw-bold');
        var t = el ? (el.textContent || '').trim() : '';
        return t || 'esta conversación';
    }
    function aviso(msg, tipo) { if (window.toastr) toastr[tipo || 'info'](msg); }

    // ---- superposición ----
    var capa = null, contador = 0;
    function mostrarCapa(destino) {
        if (!capa) {
            capa = document.createElement('div'); capa.id = 'chatDropOverlay';
            capa.style.cssText = 'position:fixed;inset:0;z-index:100250;background:rgba(26,115,232,.12);border:3px dashed #1a73e8;display:flex;align-items:center;justify-content:center;pointer-events:none';
            capa.innerHTML = '<div style="background:#fff;border-radius:14px;padding:18px 28px;box-shadow:0 8px 30px rgba(0,0,0,.2);font-size:1.05rem;color:#1a56c4;display:flex;align-items:center;gap:10px"><i class="fas fa-cloud-upload-alt fa-lg"></i><span id="chatDropTexto"></span></div>';
            document.body.appendChild(capa);
        }
        document.getElementById('chatDropTexto').textContent = destino === 'caja' ? 'Suelta para adjuntar (con vista previa)' : 'Suelta para enviar a ' + nombreConv();
        capa.style.display = 'flex';
    }
    function ocultarCapa() { contador = 0; if (capa) capa.style.display = 'none'; }

    // ---- envío ----
    async function enviarTodos(files) {
        var lista = Array.prototype.slice.call(files || []); if (!lista.length) return;
        if (!convId()) { aviso('Abre una conversación primero', 'warning'); return; }
        if (typeof uploadAndSendFile !== 'function') { aviso('No se pudo enviar (subida no disponible)', 'error'); return; }
        var ok = 0;
        for (var i = 0; i < lista.length; i++) {
            var f = lista[i];
            aviso('Enviando ' + (i + 1) + '/' + lista.length + ': ' + f.name + ' (' + humano(f.size) + ')', 'info');
            try { await uploadAndSendFile(f, /^image\//.test(f.type) ? 'image' : 'file'); ok++; } catch (e) { console.error('[chat-arrastrar]', e); }
        }
        if (lista.length > 1) aviso(ok + ' de ' + lista.length + ' archivos enviados', ok === lista.length ? 'success' : 'warning');
    }
    function confirmarLista(files) {
        var lista = Array.prototype.slice.call(files || []); if (!lista.length) return;
        if (lista.length === 1 && /^image\//.test(lista[0].type) && typeof window.chatPrevisualizarImagen === 'function') { window.chatPrevisualizarImagen(lista[0]); return; }
        var prev = document.getElementById('chatAdjuntarLista'); if (prev) prev.remove();
        var m = document.createElement('div'); m.id = 'chatAdjuntarLista';
        m.style.cssText = 'position:fixed;inset:0;z-index:100300;background:rgba(15,17,21,.6);display:flex;align-items:center;justify-content:center;padding:20px';
        m.innerHTML = '<div style="background:#fff;border-radius:14px;width:min(92vw,520px);box-shadow:0 12px 40px rgba(0,0,0,.35);overflow:hidden">'
            + '<div style="padding:12px 16px;border-bottom:1px solid #e8eaed"><b>Adjuntar ' + lista.length + ' archivo' + (lista.length === 1 ? '' : 's') + '</b> <small style="color:#5f6368">→ ' + esc(nombreConv()) + '</small></div>'
            + '<div style="max-height:50vh;overflow:auto;padding:8px 16px">' + lista.map(function (f) { return '<div style="display:flex;gap:8px;align-items:center;padding:6px 0;border-bottom:1px solid #f1f3f4"><i class="fas ' + (/^image\//.test(f.type) ? 'fa-image text-success' : 'fa-file text-secondary') + '"></i><span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + esc(f.name) + '</span><small style="color:#5f6368">' + humano(f.size) + '</small></div>'; }).join('') + '</div>'
            + '<div style="padding:10px 16px;display:flex;gap:8px;justify-content:flex-end"><button type="button" class="btn btn-light" id="chatAdjCancelar">Cancelar</button><button type="button" class="btn btn-primary" id="chatAdjEnviar"><i class="fas fa-paper-plane me-1"></i>Enviar</button></div></div>';
        document.body.appendChild(m);
        document.getElementById('chatAdjCancelar').onclick = function () { m.remove(); };
        document.getElementById('chatAdjEnviar').onclick = async function () { this.disabled = true; m.remove(); await enviarTodos(lista); };
    }

    function instalar() {
        var input = document.getElementById('messageInput');
        document.addEventListener('dragenter', function (e) { if (!conFicheros(e)) return; e.preventDefault(); contador++; mostrarCapa(input && (e.target === input || input.contains(e.target)) ? 'caja' : 'conv'); });
        document.addEventListener('dragover', function (e) { if (!conFicheros(e)) return; e.preventDefault(); e.dataTransfer.dropEffect = 'copy'; if (capa) document.getElementById('chatDropTexto').textContent = (input && (e.target === input || input.contains(e.target))) ? 'Suelta para adjuntar (con vista previa)' : 'Suelta para enviar a ' + nombreConv(); });
        document.addEventListener('dragleave', function (e) { if (!conFicheros(e)) return; contador--; if (contador <= 0) ocultarCapa(); });
        document.addEventListener('drop', function (e) {
            if (!conFicheros(e)) return;
            e.preventDefault(); e.stopPropagation(); ocultarCapa();
            var files = e.dataTransfer.files; if (!files || !files.length) return;
            if (!convId()) { aviso('Abre una conversación primero', 'warning'); return; }
            if (input && (e.target === input || input.contains(e.target))) confirmarLista(files); else enviarTodos(files);
        }, true);
        window.chatEnviarArchivosSoltados = enviarTodos;   // para pruebas y para el cliente
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', instalar); else instalar();
})();
