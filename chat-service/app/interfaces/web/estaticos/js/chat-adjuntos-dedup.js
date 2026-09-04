/* Adjuntos sin duplicados (T-32). Antes de subir, calcula la huella SHA-256 del archivo y pregunta al servidor si ya lo
 * enviaste; si es así ofrece «Enviar el existente (recomendado)» — no ocupa espacio nuevo — o «Subir copia nueva».
 * Envuelve uploadAndSendFile (lo usan el clip, pegar y arrastrar). Depende de: uploadAndSendFile, currentConversationId,
 * renderSingleMessage, scrollToBottom, loadConversations (chat-*.js). */
(function () {
    if (typeof uploadAndSendFile !== 'function') return;
    var subirOriginal = uploadAndSendFile;
    var LIMITE = 200 * 1024 * 1024;
    function esc(t) { return String(t == null ? '' : t).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
    function humano(n) { n = Number(n || 0); var u = ['B', 'KB', 'MB', 'GB'], i = 0; while (n >= 1024 && i < 3) { n /= 1024; i++; } return n.toFixed(i ? 1 : 0) + ' ' + u[i]; }
    async function sha256(file) {
        if (!window.crypto || !crypto.subtle || file.size > LIMITE) return null;
        var buf = await file.arrayBuffer(); var h = await crypto.subtle.digest('SHA-256', buf);
        return Array.from(new Uint8Array(h)).map(function (b) { return b.toString(16).padStart(2, '0'); }).join('');
    }
    function preguntar(info, file) {
        return new Promise(function (resolver) {
            var m = document.createElement('div'); m.id = 'chatDedupDialogo';
            m.style.cssText = 'position:fixed;inset:0;z-index:100350;background:rgba(15,17,21,.6);display:flex;align-items:center;justify-content:center;padding:20px';
            var fecha = ''; try { fecha = new Date(info.fecha).toLocaleString('es-EC', { dateStyle: 'medium', timeStyle: 'short' }); } catch (e) { fecha = info.fecha || ''; }
            m.innerHTML = '<div style="background:#fff;border-radius:14px;width:min(92vw,520px);box-shadow:0 12px 40px rgba(0,0,0,.35);overflow:hidden">'
                + '<div style="padding:14px 18px;border-bottom:1px solid #e8eaed"><b><i class="fas fa-copy me-2 text-primary"></i>Ya enviaste este archivo</b></div>'
                + '<div style="padding:14px 18px;font-size:.95rem;color:#3c4043"><b>' + esc(file.name) + '</b> (' + esc(humano(file.size)) + ')<br>Lo enviaste el <b>' + esc(fecha) + '</b> a <b>' + esc(info.destinatario || '') + '</b>' + (info.veces > 1 ? ' (' + info.veces + ' veces)' : '') + '.<br><small style="color:#5f6368">Enviar el existente no ocupa espacio nuevo: se usa la misma copia.</small></div>'
                + '<div style="padding:10px 18px 16px;display:flex;flex-direction:column;gap:8px">'
                + '<button type="button" class="btn btn-primary" id="chatDedupExistente"><i class="fas fa-check me-1"></i>Enviar el existente (recomendado)</button>'
                + '<button type="button" class="btn btn-light" id="chatDedupNuevo"><i class="fas fa-upload me-1"></i>Subir una copia nueva (el archivo cambió)</button>'
                + '<button type="button" class="btn btn-link btn-sm text-muted" id="chatDedupCancelar">Cancelar</button></div></div>';
            document.body.appendChild(m);
            document.getElementById('chatDedupExistente').onclick = function () { m.remove(); resolver('existente'); };
            document.getElementById('chatDedupNuevo').onclick = function () { m.remove(); resolver('nuevo'); };
            document.getElementById('chatDedupCancelar').onclick = function () { m.remove(); resolver('cancelar'); };
        });
    }
    async function enviarExistente(sha, file, type) {
        var cid = (typeof currentConversationId !== 'undefined' && currentConversationId) || window.currentConversationId;
        var r = await fetch('/api/chat/conversations/' + cid + '/messages/adjuntar-existente', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ sha256: sha, nombre: file.name, message_type: type }) });
        var d = await r.json();
        if (d && d.success) {
            if (window.toastr) toastr.success('Archivo enviado (misma copia, sin espacio nuevo)');
            var cont = document.getElementById('chatMessages');
            if (cont && typeof renderSingleMessage === 'function') { cont.insertAdjacentHTML('beforeend', renderSingleMessage(d.message)); if (typeof scrollToBottom === 'function') scrollToBottom(cont, true); }
            if (typeof loadConversations === 'function') loadConversations();
            return true;
        }
        if (window.toastr) toastr.error((d && d.error) || 'No se pudo enviar el existente');
        return false;
    }
    uploadAndSendFile = async function (file, type) {
        try {
            var sha = await sha256(file);
            if (sha) {
                var r = await fetch('/api/chat/adjuntos/existe?sha256=' + sha);
                var info = r.ok ? await r.json() : null;
                if (info && info.existe) {
                    var dec = await preguntar(info, file);
                    if (dec === 'cancelar') return;
                    if (dec === 'existente') { if (await enviarExistente(sha, file, type)) return; }
                }
            }
        } catch (e) { console.warn('[dedup] se sube normal:', e); }
        return subirOriginal(file, type);
    };
    window.uploadAndSendFile = uploadAndSendFile;
})();
