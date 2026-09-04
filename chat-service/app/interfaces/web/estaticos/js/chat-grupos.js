/* Chat institucional - Grupos y «Mis notas» (2026-08-27, T-09 / T-12)
 *  - Botón «Nuevo grupo» junto a «Nuevo chat» (abre la pestaña Grupo del modal existente).
 *  - «Mis notas»: chat con uno mismo, se crea solo y queda FIJADO arriba de la lista.
 *  - Info de grupo → modal de edición: nombre, descripción, foto, miembros (agregar/quitar), salir.
 * Envuelve funciones globales de chat-page.js sin modificarlo. */
(function () {
    'use strict';

    const NOTAS = 'notas-personales';
    let notasId = null;

    function esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
    function aviso(m, t) { if (window.toastr) toastr[t || 'info'](m); }
    function yo() { return Number(window.CHAT_USER_ID); }
    // chat-page.js declara `conversations` y `currentConversationId` con let (ámbito global léxico, no window)
    function convs() { try { return Array.isArray(conversations) ? conversations : []; } catch (e) { return []; } }
    function convActual() { try { return currentConversationId; } catch (e) { return null; } }

    // ---------- Botón «Nuevo grupo» ----------
    function inyectarBotonGrupo() {
        const btnChat = document.querySelector('button[onclick="openNewChatModal()"]');
        if (!btnChat || document.getElementById('btnNuevoGrupo')) return;
        const b = document.createElement('button');
        b.id = 'btnNuevoGrupo'; b.className = btnChat.className; b.title = 'Nuevo grupo';
        b.innerHTML = '<i class="fas fa-users"></i>';
        b.onclick = window.openNewGroupModal;
        btnChat.insertAdjacentElement('afterend', b);
    }
    window.openNewGroupModal = function () {
        if (typeof window.openNewChatModal === 'function') window.openNewChatModal();
        const tab = document.querySelector('#newChatTabs button[data-bs-target="#tabGroupChat"]');
        if (tab && window.bootstrap && bootstrap.Tab) bootstrap.Tab.getOrCreateInstance(tab).show();
        setTimeout(function () { const n = document.getElementById('groupName'); if (n) n.focus(); }, 300);
    };

    // ---------- «Iniciar un chat de grupo» desde un chat 1:1 (como Teams) ----------
    function inyectarBotonGrupoDesdeChat() {
        const acciones = document.querySelector('.chat-actions');
        if (!acciones || document.getElementById('btnChatGrupoDesde')) return;
        const b = document.createElement('button');
        b.id = 'btnChatGrupoDesde'; b.className = 'meet-btn'; b.title = 'Iniciar un chat de grupo con esta persona';
        b.style.cssText = 'color:#6f42c1;display:none;'; b.innerHTML = '<i class="fas fa-user-plus"></i>';
        b.onclick = window.iniciarChatGrupoDesdeActual;
        const primero = document.getElementById('btnLlamadaAudio');
        if (primero) acciones.insertBefore(b, primero); else acciones.appendChild(b);
    }
    window.iniciarChatGrupoDesdeActual = function () {
        const conv = convs().find(function (c) { return c.id === convActual(); });
        window.openNewGroupModal();
        if (conv && conv.other_user && typeof window.addGroupMember === 'function') {
            setTimeout(function () { window.addGroupMember(conv.other_user.id, conv.other_user.name || 'Usuario'); }, 350);
        }
    };

    // ---------- Mis notas ----------
    async function asegurarNotas() {
        try {
            const r = await fetch('/api/chat/conversations/notas', { method: 'POST', credentials: 'same-origin' });
            const d = await r.json();
            if (d.success) { notasId = d.id; if (d.creada && typeof window.loadConversations === 'function') window.loadConversations(); }
        } catch (e) { /* sin notas */ }
    }
    function esNotas(conv) { return conv && (conv.descripcion === NOTAS || conv.description === NOTAS || conv.id === notasId); }

    const renderOriginal = window.renderConversations;
    window.renderConversations = function () {
        // Nombre visible y orden: «Mis notas» siempre primero
        convs().forEach(function (c) { if (esNotas(c)) { c.name = 'Mis notas'; c.nombre = 'Mis notas'; c.display_name = 'Mis notas'; } });
        if (typeof renderOriginal === 'function') renderOriginal.apply(this, arguments);
        const cont = document.getElementById('conversationsList');
        if (!cont) return;
        cont.querySelectorAll('.conversation-item').forEach(function (it) {
            const id = Number(it.getAttribute('data-conv-id'));
            const conv = convs().find(function (c) { return c.id === id; });
            if (!esNotas(conv)) return;
            it.classList.add('conversation-notas');
            const av = it.querySelector('.conversation-avatar');
            if (av) av.innerHTML = '<i class="fas fa-sticky-note"></i>';
            const nombre = it.querySelector('.conversation-name, .conv-name, h6, strong');
            if (nombre && !nombre.querySelector('.badge-tu')) nombre.insertAdjacentHTML('beforeend', ' <span class="badge-tu">Tú</span>');
            cont.insertBefore(it, cont.firstChild);
        });
    };

    // Al abrir «Mis notas» no tiene sentido llamar ni conferenciar
    const abrirOriginal = window.openConversation;
    if (typeof abrirOriginal === 'function') {
        window.openConversation = function (id, tipo) {
            const r = abrirOriginal.apply(this, arguments);
            const conv = convs().find(function (c) { return c.id === Number(id); });
            const ocultar = esNotas(conv);
            ['btnLlamadaAudio', 'btnLlamadaVideo', 'btnConferenciaGrupal'].forEach(function (b) {
                const el = document.getElementById(b); if (el && ocultar) el.style.display = 'none';
            });
            const st = document.getElementById('chatHeaderStatus');
            if (st && ocultar) { st.textContent = 'Notas personales · solo tú las ves'; st.className = 'status-online'; }
            // Botón «chat de grupo» solo en chats directos (no en grupos ni en Mis notas)
            const bg = document.getElementById('btnChatGrupoDesde');
            if (bg) bg.style.display = (conv && conv.conversation_type === 'direct' && !ocultar) ? '' : 'none';
            // Cabecera de GRUPO (como Teams): los mismos botones de videollamada/llamada arrancan la llamada grupal
            // (iniciarLlamadaDesdeChat ya deriva a la conferencia LiveKit y timbra a todos). Se controla por clase + CSS
            // para que gane aunque chat-page.js cambie los estilos en línea después.
            document.body.classList.toggle('conv-grupo', !!(conv && conv.conversation_type === 'group' && !ocultar));
            document.body.classList.toggle('conv-notas', !!ocultar);
            return r;
        };
    }

    // ---------- Editar grupo (reemplaza «Info del chat» en grupos) ----------
    const infoOriginal = window.showChatInfo;
    window.showChatInfo = async function () {
        const id = convActual();
        const conv = convs().find(function (c) { return c.id === id; });
        if (!conv || conv.conversation_type !== 'group') { if (typeof infoOriginal === 'function') return infoOriginal.apply(this, arguments); return; }
        let d;
        try { d = await (await fetch('/api/chat/conversations/' + id + '/grupo', { credentials: 'same-origin' })).json(); } catch (e) { d = null; }
        if (!d || !d.success) { aviso((d && d.error) || 'No se pudo cargar el grupo', 'error'); return; }
        mostrarModalGrupo(d.grupo);
    };

    function mostrarModalGrupo(g) {
        let m = document.getElementById('modalEditarGrupo');
        if (m) m.remove();
        m = document.createElement('div');
        m.id = 'modalEditarGrupo'; m.className = 'modal fade'; m.tabIndex = -1;
        const admin = g.soy_admin && !g.notas;
        const avatar = g.avatar ? '<img src="' + esc(g.avatar) + '" alt="">' : '<i class="fas fa-users"></i>';
        m.innerHTML =
            '<div class="modal-dialog modal-dialog-centered"><div class="modal-content">' +
            '<div class="modal-header"><h5 class="modal-title"><i class="fas fa-users me-2"></i>' + (g.notas ? 'Mis notas' : 'Grupo') + '</h5>' +
            '<button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>' +
            '<div class="modal-body">' +
            '<div class="d-flex align-items-center gap-3 mb-3">' +
            '<div class="grupo-avatar" id="grupoAvatarBox">' + avatar + '</div>' +
            '<div class="flex-grow-1">' +
            '<input type="text" class="form-control mb-1" id="grupoNombre" maxlength="60" value="' + esc(g.nombre) + '"' + (admin ? '' : ' readonly') + '>' +
            (g.notas ? '' : '<input type="text" class="form-control form-control-sm" id="grupoDescripcion" maxlength="120" placeholder="Descripción" value="' + esc(g.descripcion) + '"' + (admin ? '' : ' readonly') + '>') +
            '</div></div>' +
            (admin ? '<div class="d-flex gap-2 mb-3"><button type="button" class="btn btn-sm btn-primary" onclick="guardarGrupo(' + g.id + ')"><i class="fas fa-save me-1"></i>Guardar</button>' +
                     '<button type="button" class="btn btn-sm btn-outline-secondary" onclick="document.getElementById(\'grupoFoto\').click()"><i class="fas fa-camera me-1"></i>Cambiar foto</button>' +
                     '<input type="file" id="grupoFoto" accept="image/*" style="display:none" onchange="subirFotoGrupo(' + g.id + ', this)"></div>' : '') +
            (g.notas ? '<p class="text-muted small mb-0">Este chat es solo tuyo: guarda notas, enlaces y archivos. Nadie más lo ve.</p>' :
            '<h6 class="mt-2">Miembros (' + g.miembros.length + ')</h6>' +
            (admin ? '<input type="text" class="form-control form-control-sm mb-2" id="grupoBuscarMiembro" placeholder="Agregar compañero…" oninput="buscarMiembroGrupo(' + g.id + ', this.value)" autocomplete="off"><div id="grupoResultadosMiembro"></div>' : '') +
            '<div class="grupo-miembros">' + g.miembros.map(function (p) {
                const foto = p.foto ? '<img src="' + esc(p.foto) + '" alt="">' : '<span>' + esc((p.nombre || 'U').charAt(0).toUpperCase()) + '</span>';
                return '<div class="grupo-miembro"><div class="grupo-miembro-avatar">' + foto + '</div>' +
                    '<div class="flex-grow-1"><div>' + esc(p.nombre) + (p.es_yo ? ' <span class="badge-tu">Tú</span>' : '') + '</div>' +
                    '<small class="text-muted">' + (p.es_admin ? 'Administrador' : 'Miembro') + '</small></div>' +
                    (admin && !p.es_yo ? '<button type="button" class="btn btn-sm btn-outline-danger" title="Quitar" onclick="quitarMiembroGrupo(' + g.id + ',' + p.id + ')"><i class="fas fa-user-minus"></i></button>' : '') +
                    '</div>';
            }).join('') + '</div>' +
            '<div class="mt-3 text-end"><button type="button" class="btn btn-sm btn-outline-danger" onclick="salirDelGrupo(' + g.id + ')"><i class="fas fa-sign-out-alt me-1"></i>Salir del grupo</button></div>') +
            '</div></div></div>';
        document.body.appendChild(m);
        bootstrap.Modal.getOrCreateInstance(m).show();
    }

    window.guardarGrupo = async function (id) {
        const nombre = (document.getElementById('grupoNombre') || {}).value || '';
        const desc = (document.getElementById('grupoDescripcion') || {}).value || '';
        const r = await fetch('/api/chat/conversations/' + id + '/grupo', { method: 'PUT', credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ nombre: nombre, descripcion: desc }) });
        const d = await r.json();
        if (!d.success) { aviso(d.error || 'No se pudo guardar', 'error'); return; }
        aviso('Grupo actualizado', 'success');
        const h = document.getElementById('chatHeaderName'); if (h) h.textContent = d.grupo.nombre;
        if (typeof window.loadConversations === 'function') window.loadConversations();
    };
    window.subirFotoGrupo = async function (id, input) {
        if (!input.files || !input.files[0]) return;
        const fd = new FormData(); fd.append('file', input.files[0]);
        const r = await fetch('/api/chat/conversations/' + id + '/avatar', { method: 'POST', credentials: 'same-origin', body: fd });
        const d = await r.json();
        if (!d.success) { aviso(d.error || 'No se pudo subir la foto', 'error'); return; }
        const box = document.getElementById('grupoAvatarBox'); if (box) box.innerHTML = '<img src="' + esc(d.avatar) + '" alt="">';
        aviso('Foto del grupo actualizada', 'success');
        if (typeof window.loadConversations === 'function') window.loadConversations();
    };
    window.buscarMiembroGrupo = async function (id, q) {
        const box = document.getElementById('grupoResultadosMiembro'); if (!box) return;
        if (!q || q.trim().length < 2) { box.innerHTML = ''; return; }
        const r = await fetch('/api/chat/users/search?q=' + encodeURIComponent(q.trim()), { credentials: 'same-origin' });
        const d = await r.json();
        const lista = d.users || d.usuarios || d.results || d.data || [];
        box.innerHTML = lista.slice(0, 8).map(function (u) {
            const uid = u.id || u.usuario_id, nombre = u.name || u.nombre || u.full_name || u.email;
            return '<div class="grupo-resultado" onclick="agregarMiembroGrupo(' + id + ',' + uid + ')"><i class="fas fa-user-plus me-2"></i>' + esc(nombre) + '</div>';
        }).join('') || '<div class="text-muted small p-1">Sin resultados</div>';
    };
    window.agregarMiembroGrupo = async function (id, uid) {
        const r = await fetch('/api/chat/conversations/' + id + '/participants', { method: 'POST', credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ usuario_id: uid }) });
        const d = await r.json();
        if (!(d.success || d.exito)) { aviso(d.mensaje || d.error || 'No se pudo agregar', 'error'); return; }
        aviso('Participante agregado', 'success'); window.showChatInfo();
    };
    window.quitarMiembroGrupo = async function (id, uid) {
        if (!confirm('¿Quitar a este participante del grupo?')) return;
        const r = await fetch('/api/chat/conversations/' + id + '/participants/' + uid, { method: 'DELETE', credentials: 'same-origin' });
        const d = await r.json();
        if (!(d.success || d.exito)) { aviso(d.mensaje || d.error || 'No se pudo quitar', 'error'); return; }
        aviso('Participante quitado', 'success'); window.showChatInfo();
    };
    window.salirDelGrupo = async function (id) {
        if (!confirm('¿Salir de este grupo?')) return;
        const r = await fetch('/api/chat/conversations/' + id + '/leave', { method: 'POST', credentials: 'same-origin' });
        const d = await r.json();
        if (!(d.success || d.exito)) { aviso(d.mensaje || d.error || 'No se pudo salir', 'error'); return; }
        const m = document.getElementById('modalEditarGrupo'); if (m) bootstrap.Modal.getOrCreateInstance(m).hide();
        if (typeof window.loadConversations === 'function') window.loadConversations();
        if (typeof window.volverAListaChat === 'function') window.volverAListaChat();
    };

    // Cambios del grupo en tiempo real (nombre/foto) → refrescar lista
    function engancharSocket() {
        const s = window._chatSocketVistos; if (!s || s.__grupos) return; s.__grupos = true;
        s.on('conversation_updated', function () { if (typeof window.loadConversations === 'function') window.loadConversations(); });
    }

    function iniciar() { inyectarBotonGrupo(); inyectarBotonGrupoDesdeChat(); asegurarNotas(); setTimeout(engancharSocket, 2500); setTimeout(engancharSocket, 6000); }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', iniciar); else iniciar();
})();
