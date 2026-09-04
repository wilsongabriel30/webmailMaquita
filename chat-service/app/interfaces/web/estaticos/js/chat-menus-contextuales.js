// chat-menus-contextuales.js — Volver a lista (móvil), menús contextuales, cámara, audio, copiar.
// Extraído de chat-page.js (líneas 3337-3524) el 28/08/2026 SIN cambios de código; ámbito global compartido.
// Orden de carga: ver plantillas/chat/index.html (mismo orden que el archivo original).


// Movil: volver a la lista de conversaciones
function volverAListaChat() {
    var cc = document.querySelector('.chat-container');
    if (cc) cc.classList.remove('mobile-chat-open');
}
window.volverAListaChat = volverAListaChat;


// ============================================================
// CLIC DERECHO en una conversacion: Archivar / Vaciar / Eliminar
// (todo es SOFT: nada se borra de la BD; recuperable en panel admin)
// ============================================================
function cerrarMenuConvCtx() { const m = document.getElementById('convCtxMenu'); if (m) m.remove(); }

document.addEventListener('contextmenu', function(e) {
    // Clic derecho en un MENSAJE: reaccionar / copiar / reenviar (como el mini-chat)
    const msgEl = e.target.closest('.message[data-message-id]');
    if (msgEl) { e.preventDefault(); mostrarMenuMensajeCtx(e, msgEl); return; }
    const item = e.target.closest('.conversation-item[data-conv-id]');
    if (!item) return;
    e.preventDefault();
    cerrarMenuConvCtx();
    const cid = item.getAttribute('data-conv-id');
    const cname = item.getAttribute('data-conv-name') || 'esta conversación';
    const menu = document.createElement('div');
    menu.id = 'convCtxMenu';
    menu.style.cssText = 'position:fixed;z-index:100060;background:#fff;color:#222;border-radius:10px;box-shadow:0 6px 24px rgba(0,0,0,.25);padding:6px 0;min-width:190px;font-size:.9rem;';
    const it = function(icon, label, fn, color) {
        return '<div style="padding:9px 16px;cursor:pointer;display:flex;gap:10px;align-items:center;' + (color ? 'color:' + color + ';' : '') + '" onmouseover="this.style.background=\'#f0f2f5\'" onmouseout="this.style.background=\'\'" onclick="' + fn + '"><i class="fas ' + icon + '" style="width:16px;opacity:.7;"></i>' + label + '</div>';
    };
    const _arch = window._viendoArchivadas;
    menu.innerHTML =
        it(_arch ? 'fa-box-open' : 'fa-box-archive', _arch ? 'Desarchivar' : 'Archivar', 'archivarConv(' + cid + ',' + (_arch ? 'false' : 'true') + ');cerrarMenuConvCtx();') +
        it('fa-eraser', 'Vaciar conversación', 'vaciarConv(' + cid + ',\'' + cname.replace(/'/g, "\\'") + '\');cerrarMenuConvCtx();') +
        '<div style="height:1px;background:rgba(0,0,0,.07);margin:4px 0;"></div>' +
        it('fa-trash-alt', 'Eliminar conversación', 'eliminarConv(' + cid + ',\'' + cname.replace(/'/g, "\\'") + '\');cerrarMenuConvCtx();', '#dc2626');
    document.body.appendChild(menu);
    let x = e.clientX, y = e.clientY;
    const mw = menu.offsetWidth, mh = menu.offsetHeight;
    if (x + mw > window.innerWidth) x = window.innerWidth - mw - 8;
    if (y + mh > window.innerHeight) y = window.innerHeight - mh - 8;
    menu.style.left = x + 'px'; menu.style.top = y + 'px';
});
document.addEventListener('click', cerrarMenuConvCtx);

async function archivarConv(cid, archivar) {
    if (archivar === undefined) archivar = true;
    try {
        await fetch('/api/chat/conversations/' + cid + '/archivar', {
            method: 'POST', headers: {'Content-Type':'application/json'}, credentials: 'same-origin',
            body: JSON.stringify({ archivar: archivar })
        });
        if (typeof toastr !== 'undefined') toastr.success(archivar ? 'Conversación archivada' : 'Conversación desarchivada');
        if (window._viendoArchivadas && typeof cargarArchivadas === 'function') cargarArchivadas();
        else if (typeof loadConversations === 'function') loadConversations();
    } catch (e) { console.error(e); }
}

async function vaciarConv(cid, nombre) {
    if (!confirm('¿Vaciar la conversación con ' + (nombre||'') + '? Dejarás de ver los mensajes anteriores (no se borran del sistema).')) return;
    try {
        await fetch('/api/chat/conversations/' + cid + '/vaciar', { method: 'POST', credentials: 'same-origin' });
        if (typeof toastr !== 'undefined') toastr.success('Conversación vaciada');
        if (window.currentConversationId == cid && typeof loadMessages === 'function') loadMessages(cid);
        if (typeof loadConversations === 'function') loadConversations();
    } catch (e) { console.error(e); }
}

async function eliminarConv(cid, nombre) {
    if (!confirm('¿Eliminar la conversación con ' + (nombre||'') + ' de tu lista? Se podrá recuperar desde el panel de administración.')) return;
    try {
        await fetch('/api/chat/conversations/' + cid + '/eliminar', { method: 'POST', credentials: 'same-origin' });
        if (typeof toastr !== 'undefined') toastr.success('Conversación eliminada de tu lista');
        if (typeof loadConversations === 'function') loadConversations();
        // Si estaba abierta, volver al estado vacio
        if (window.currentConversationId == cid) {
            const ea = document.getElementById('chatEmptyState'); if (ea) ea.style.display = 'flex';
            const aa = document.getElementById('chatActiveArea'); if (aa) aa.style.display = 'none';
            window.currentConversationId = null;
        }
    } catch (e) { console.error(e); }
}
window.archivarConv = archivarConv; window.vaciarConv = vaciarConv; window.eliminarConv = eliminarConv;
window.cerrarMenuConvCtx = cerrarMenuConvCtx;

// ============================================================
// Barra WhatsApp: camara, grabacion de audio, toggle enviar/microfono
// ============================================================
function abrirCamara() {
    const el = document.getElementById("cameraInput");
    if (el) el.click();
}
window.abrirCamara = abrirCamara;

function actualizarBotonEnvio() {
    const ta = document.getElementById("messageInput");
    const send = document.getElementById("btnSendMessage");
    const mic = document.getElementById("btnMicAudio");
    const hayTexto = ta && ta.value.trim().length > 0;
    if (send) send.style.display = hayTexto ? "inline-flex" : "none";
    if (mic) mic.style.display = hayTexto ? "none" : "inline-flex";
}
window.actualizarBotonEnvio = actualizarBotonEnvio;

let _grabAudioChat = null;
async function toggleGrabacionAudio() {
    if (_grabAudioChat) { try { _grabAudioChat.recorder.stop(); } catch (e) {} return; }
    if (!window.currentConversationId) { if (typeof toastr !== "undefined") toastr.warning("Abre una conversación primero"); return; }
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const mime = (window.MediaRecorder && MediaRecorder.isTypeSupported("audio/webm;codecs=opus")) ? "audio/webm;codecs=opus" : "audio/webm";
        const recorder = new MediaRecorder(stream, { mimeType: mime });
        const chunks = [];
        recorder.ondataavailable = function (e) { if (e.data && e.data.size) chunks.push(e.data); };
        recorder.onstop = async function () {
            stream.getTracks().forEach(function (t) { t.stop(); });
            const btn = document.getElementById("btnMicAudio");
            if (btn) btn.classList.remove("grabando");
            _grabAudioChat = null;
            const blob = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
            if (!blob.size) return;
            const file = new File([blob], "audio_" + Date.now() + ".webm", { type: "audio/webm" });
            if (typeof uploadAndSendFile === "function") await uploadAndSendFile(file, "audio");
        };
        recorder.start();
        _grabAudioChat = { recorder: recorder, stream: stream };
        const btn = document.getElementById("btnMicAudio");
        if (btn) btn.classList.add("grabando");
        if (typeof toastr !== "undefined") toastr.info("Grabando... toca el micrófono de nuevo para enviar");
    } catch (e) { if (typeof toastr !== "undefined") toastr.error("No se pudo acceder al micrófono"); }
}
window.toggleGrabacionAudio = toggleGrabacionAudio;


// ============================================================
// CLIC DERECHO en un MENSAJE (chat grande): Reaccionar / Copiar / Reenviar
// ============================================================
function mostrarMenuMensajeCtx(e, msgEl) {
    cerrarMenuConvCtx();
    const mid = msgEl.getAttribute('data-message-id');
    if (!mid) return;
    const menu = document.createElement('div');
    menu.id = 'convCtxMenu';
    menu.style.cssText = 'position:fixed;z-index:100060;background:#fff;color:#222;border-radius:12px;box-shadow:0 6px 24px rgba(0,0,0,.25);padding:6px 0;min-width:190px;font-size:.9rem;';
    const emojis = ['\u2764\ufe0f', '\ud83d\udc4d', '\ud83d\ude02', '\ud83d\ude2e', '\ud83d\ude22', '\ud83d\ude4f'];
    let html = '<div style="display:flex;gap:6px;padding:6px 12px;justify-content:space-between;">' +
        emojis.map(function(em){ return '<span style="cursor:pointer;font-size:1.35rem;line-height:1;" onmouseover="this.style.transform=\'scale(1.25)\'" onmouseout="this.style.transform=\'\'" onclick="reaccionarMsgCtx(' + mid + ',\'' + em + '\')">' + em + '</span>'; }).join('') +
        '</div><div style="height:1px;background:rgba(0,0,0,.08);margin:4px 0;"></div>';
    const it = function(icon, label, fn, color){ return '<div style="padding:9px 16px;cursor:pointer;display:flex;gap:10px;align-items:center;' + (color?'color:'+color+';':'') + '" onmouseover="this.style.background=\'#f0f2f5\'" onmouseout="this.style.background=\'\'" onclick="' + fn + '"><i class="fas ' + icon + '" style="width:16px;opacity:.7;"></i>' + label + '</div>'; };
    html += it('fa-copy', 'Copiar', 'copiarMensajeChat(' + mid + ');cerrarMenuConvCtx();');
    if (typeof window.mostrarModalReenvio === 'function' || typeof mostrarModalReenvio === 'function') {
        html += it('fa-share', 'Reenviar', 'mostrarModalReenvio(' + mid + ');cerrarMenuConvCtx();');
    }
    menu.innerHTML = html;
    document.body.appendChild(menu);
    let x = e.clientX, y = e.clientY;
    const mw = menu.offsetWidth, mh = menu.offsetHeight;
    if (x + mw > window.innerWidth) x = window.innerWidth - mw - 8;
    if (y + mh > window.innerHeight) y = window.innerHeight - mh - 8;
    if (y < 8) y = 8;
    menu.style.left = x + 'px'; menu.style.top = y + 'px';
}
window.mostrarMenuMensajeCtx = mostrarMenuMensajeCtx;

function reaccionarMsgCtx(mid, emoji) {
    cerrarMenuConvCtx();
    if (typeof addReaction === 'function') addReaction(mid, emoji);
}
window.reaccionarMsgCtx = reaccionarMsgCtx;

function copiarMensajeChat(mid) {
    const el = document.querySelector('.message[data-message-id="' + mid + '"] .message-content');
    if (!el) return;
    const clon = el.cloneNode(true);
    clon.querySelectorAll('.message-actions, .message-meta, .btn-add-reaction, .message-reactions, .reaction-picker').forEach(function(n){ n.remove(); });
    const texto = (clon.textContent || '').trim();
    if (!texto) return;
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(texto).then(function(){ if (typeof toastr!=='undefined') toastr.success('Copiado'); }).catch(function(){});
    } else {
        const ta = document.createElement('textarea'); ta.value = texto; document.body.appendChild(ta); ta.select();
        try { document.execCommand('copy'); if (typeof toastr!=='undefined') toastr.success('Copiado'); } catch(e){}
        ta.remove();
    }
}
window.copiarMensajeChat = copiarMensajeChat;

