/* Pegar una imagen (Ctrl+V) en el chat: vista previa antes de enviar (T-27).
 * Sustituye el envío inmediato: muestra la captura, permite cancelar o enviar; el mensaje
 * solo se crea cuando la subida termina bien (uploadAndSendFile ya lo garantiza). */
(function () {
    function esc(t) { return String(t == null ? '' : t).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
    function humano(n) { n = Number(n || 0); var u = ['B', 'KB', 'MB', 'GB'], i = 0; while (n >= 1024 && i < 3) { n /= 1024; i++; } return n.toFixed(i ? 1 : 0) + ' ' + u[i]; }
    function cerrar() { var m = document.getElementById('chatPegarImagen'); if (m) m.remove(); }

    function previsualizar(file) {
        cerrar();
        var url = URL.createObjectURL(file);
        var m = document.createElement('div');
        m.id = 'chatPegarImagen';
        m.style.cssText = 'position:fixed;inset:0;z-index:100300;background:rgba(15,17,21,.72);display:flex;align-items:center;justify-content:center;padding:20px';
        m.innerHTML = '<div style="background:#fff;border-radius:14px;max-width:min(92vw,720px);width:100%;box-shadow:0 12px 40px rgba(0,0,0,.35);overflow:hidden">'
            + '<div style="padding:12px 16px;border-bottom:1px solid #e8eaed;display:flex;align-items:center;gap:8px"><i class="fas fa-image" style="color:#1a73e8"></i><b>Enviar imagen</b><small style="margin-left:auto;color:#5f6368">' + esc(humano(file.size)) + '</small></div>'
            + '<div style="background:#f1f3f4;display:flex;justify-content:center;max-height:60vh;overflow:auto"><img src="' + url + '" alt="" style="max-width:100%;max-height:60vh;object-fit:contain"></div>'
            + '<div style="padding:10px 16px;display:flex;gap:8px;justify-content:flex-end">'
            + '<button type="button" id="chatPegarCancelar" class="btn btn-light">Cancelar</button>'
            + '<button type="button" id="chatPegarEnviar" class="btn btn-primary"><i class="fas fa-paper-plane me-1"></i>Enviar</button></div></div>';
        document.body.appendChild(m);
        var enviando = false;
        document.getElementById('chatPegarCancelar').onclick = function () { URL.revokeObjectURL(url); cerrar(); };
        m.addEventListener('click', function (ev) { if (ev.target === m) { URL.revokeObjectURL(url); cerrar(); } });
        document.getElementById('chatPegarEnviar').onclick = async function () {
            if (enviando) return; enviando = true;
            this.disabled = true; this.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Enviando…';
            try {
                if (typeof uploadAndSendFile === 'function') await uploadAndSendFile(file, 'image');
            } finally { URL.revokeObjectURL(url); cerrar(); }
        };
        document.addEventListener('keydown', function esc_(ev) { if (ev.key === 'Escape') { cerrar(); document.removeEventListener('keydown', esc_); } if (ev.key === 'Enter' && document.getElementById('chatPegarImagen')) { ev.preventDefault(); document.getElementById('chatPegarEnviar').click(); } });
    }

    window.chatPrevisualizarImagen = previsualizar;   // la usa chat-arrastrar.js (soltar imagen sobre la caja)

    function instalar() {
        var input = document.getElementById('messageInput'); if (!input || input.__pegarImagen) return;
        input.__pegarImagen = true;
        input.addEventListener('paste', function (e) {
            var items = e.clipboardData && e.clipboardData.items; if (!items) return;
            for (var i = 0; i < items.length; i++) {
                if (items[i].type && items[i].type.indexOf('image') === 0) {
                    var file = items[i].getAsFile(); if (!file) continue;
                    e.preventDefault(); e.stopImmediatePropagation();
                    if (typeof currentConversationId === 'undefined' || !currentConversationId) { if (window.toastr) toastr.warning('Selecciona una conversación primero'); return; }
                    if (!file.name || file.name === 'image.png') { try { file = new File([file], 'captura-' + new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19) + '.png', { type: file.type }); } catch (er) {} }
                    previsualizar(file);
                    return;
                }
            }
        }, true);
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', instalar); else instalar();
})();
