// chat-opciones-mensaje.js — Opciones de mensaje: editar, eliminar, info, buscar; exportaciones a window.
// Extraído de chat-page.js (líneas 3030-3336) el 28/08/2026 SIN cambios de código; ámbito global compartido.
// Orden de carga: ver plantillas/chat/index.html (mismo orden que el archivo original).

    // ============================================
    // EDITAR Y ELIMINAR MENSAJES
    // ============================================
    function showMessageOptions(event, buttonEl) {
        event.stopPropagation();

        // Leer datos del botón
        selectedMessageId = buttonEl.dataset.msgId;
        selectedMessageContent = buttonEl.dataset.msgContent.replace(/&#39;/g, "'").replace(/&quot;/g, '"');

        const menu = document.getElementById('messageOptionsMenu');
        const rect = buttonEl.getBoundingClientRect();

        // Posicionar el menú
        menu.style.top = (rect.bottom + 5) + 'px';
        menu.style.left = (rect.left - 100) + 'px';

        // Asegurar que no se salga de la pantalla
        if (parseInt(menu.style.left) < 10) {
            menu.style.left = '10px';
        }

        menu.classList.add('show');
    }

    function openEditMessageModal() {
        const menu = document.getElementById('messageOptionsMenu');
        menu.classList.remove('show');

        document.getElementById('editMessageContent').value = selectedMessageContent || '';
        editMessageModal.show();

        // Focus en el textarea
        setTimeout(() => {
            document.getElementById('editMessageContent').focus();
        }, 300);
    }

    async function saveEditedMessage() {
        let newContent = document.getElementById('editMessageContent').value.trim();

        // Sanitizar contenido
        newContent = sanitizeMessage(newContent);

        if (!newContent) {
            toastr.warning('El mensaje no puede estar vacio');
            return;
        }

        if (newContent === selectedMessageContent) {
            editMessageModal.hide();
            return;
        }

        // Validar ID del mensaje
        const messageId = validateId(selectedMessageId);
        if (!messageId) {
            toastr.error('Error: mensaje invalido');
            return;
        }

        try {
            const response = await fetch(`/api/chat/messages/${messageId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ content: newContent })
            });

            const data = await response.json();

            if (data.success) {
                toastr.success('Mensaje editado');
                editMessageModal.hide();

                // Actualizar el mensaje en el DOM
                const messageEl = document.querySelector(`[data-message-id="${selectedMessageId}"]`);
                if (messageEl) {
                    const textEl = messageEl.querySelector('.message-text');
                    if (textEl) {
                        textEl.textContent = newContent;
                    }

                    // Agregar badge de editado si no existe
                    const metaEl = messageEl.querySelector('.message-meta');
                    if (metaEl && !metaEl.querySelector('.edited-badge')) {
                        metaEl.insertAdjacentHTML('afterbegin', '<span class="edited-badge">editado</span> ');
                    }
                }

                // Actualizar lista de conversaciones
                loadConversations();
            } else {
                toastr.error(data.message || 'Error al editar mensaje');
            }
        } catch (error) {
            console.error('Error:', error);
            toastr.error('Error de conexión');
        }
    }

    function confirmDeleteMessage() {
        const menu = document.getElementById('messageOptionsMenu');
        menu.classList.remove('show');

        deleteMessageModal.show();
    }

    async function deleteMessage() {
        // Validar ID del mensaje
        const messageId = validateId(selectedMessageId);
        if (!messageId) {
            toastr.error('Error: mensaje invalido');
            return;
        }

        try {
            const response = await fetch(`/api/chat/messages/${messageId}?for_everyone=true`, {
                method: 'DELETE'
            });

            const data = await response.json();

            if (data.success) {
                toastr.success('Mensaje eliminado');
                deleteMessageModal.hide();

                // Actualizar el mensaje en el DOM
                const messageEl = document.querySelector(`[data-message-id="${selectedMessageId}"]`);
                if (messageEl) {
                    const contentEl = messageEl.querySelector('.message-content');
                    if (contentEl) {
                        // Remover el menú de acciones
                        const actionsEl = contentEl.querySelector('.message-actions');
                        if (actionsEl) actionsEl.remove();

                        // Cambiar el texto
                        const textEl = contentEl.querySelector('.message-text');
                        if (textEl) {
                            textEl.innerHTML = '<em class="text-muted"><i class="fas fa-ban me-1"></i>Mensaje eliminado</em>';
                        }
                    }
                }

                // Actualizar lista de conversaciones
                loadConversations();
            } else {
                toastr.error(data.message || 'Error al eliminar mensaje');
            }
        } catch (error) {
            console.error('Error:', error);
            toastr.error('Error de conexión');
        }
    }

    // Chat info
    function showChatInfo() {
        const conv = conversations.find(c => c.id === currentConversationId);
        if (!conv) return;

        // Obtener nombre para mostrar
        const displayName = conv.name || (conv.other_user ? conv.other_user.name : 'Usuario');

        let content = '';
        if (conv.conversation_type === 'direct') {
            content = `
                <div class="text-center">
                    <div class="avatar mx-auto mb-3" style="width: 80px; height: 80px; font-size: 2rem; background: var(--primary-color, #0061a1); border-radius: 50%; display: flex; align-items: center; justify-content: center; color: white;">
                        ${getInitials(displayName)}
                    </div>
                    <h5>${escapeHtml(displayName)}</h5>
                    <p class="text-muted">Chat directo</p>
                </div>
            `;
        } else {
            content = `
                <div class="text-center">
                    <div class="avatar mx-auto mb-3" style="width: 80px; height: 80px; font-size: 2rem; background: var(--secondary-color, #10b981); border-radius: 50%; display: flex; align-items: center; justify-content: center; color: white;">
                        <i class="fas fa-users"></i>
                    </div>
                    <h5>${escapeHtml(displayName)}</h5>
                    <p class="text-muted">${conv.participant_count || 0} participantes</p>
                </div>
            `;
        }

        document.getElementById('chatInfoContent').innerHTML = content;
        chatInfoModal.show();
    }

    // Acciones del chat
    function archiveChat() {
        toastr.info('Función de archivar próximamente');
    }

    function muteChat() {
        toastr.info('Función de silenciar próximamente');
    }

    function blockUser() {
        if (confirm('¿Estás seguro de bloquear a este usuario?')) {
            // Implementar bloqueo
            toastr.info('Función de bloqueo próximamente');
        }
    }

    function searchInChat() {
        abrirBuscadorMensajes(window.currentConversationId || null);
    }
    let _buscarMsgTimer = null;
    function abrirBuscadorMensajes(convId) {
        let ov = document.getElementById('buscadorMsgOverlay');
        if (ov) ov.remove();
        ov = document.createElement('div');
        ov.id = 'buscadorMsgOverlay';
        ov.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.4);z-index:100040;display:flex;align-items:flex-start;justify-content:center;padding-top:8vh;';
        ov.addEventListener('click', function(e){ if (e.target === ov) ov.remove(); });
        const tieneConv = !!convId;
        ov.innerHTML =
          '<div style="background:#fff;width:min(560px,94vw);max-height:80vh;border-radius:14px;display:flex;flex-direction:column;overflow:hidden;box-shadow:0 12px 40px rgba(0,0,0,.35);">' +
            '<div style="padding:12px 16px;border-bottom:1px solid #eee;display:flex;gap:8px;align-items:center;">' +
              '<i class="fas fa-search text-muted"></i>' +
              '<input id="buscarMsgInput" type="text" placeholder="Buscar en esta conversación..." style="flex:1;border:none;outline:none;font-size:.95rem;" autocomplete="off">' +
              '<button class="btn btn-sm btn-light" onclick="document.getElementById(\'buscadorMsgOverlay\').remove()"><i class="fas fa-times"></i></button>' +
            '</div>' +
            '<div id="buscarMsgResultados" style="overflow-y:auto;padding:6px 0;"><div class="text-center text-muted py-4 small">Escribe para buscar...</div></div>' +
          '</div>';
        document.body.appendChild(ov);
        window._buscarConvId = convId;
        // ambito FIJO: la lupa de la cabecera busca solo en esta conversacion
        window._ambitoBusqueda = tieneConv ? 'conv' : 'all';
        const inp = document.getElementById('buscarMsgInput');
        inp.focus();
        inp.addEventListener('input', function(){ clearTimeout(_buscarMsgTimer); _buscarMsgTimer = setTimeout(buscarMsgAhora, 220); });
    }
    window.abrirBuscadorMensajes = abrirBuscadorMensajes;

    async function buscarMsgAhora() {
        const inp = document.getElementById('buscarMsgInput');
        const cont = document.getElementById('buscarMsgResultados');
        if (!inp || !cont) return;
        const q = inp.value.trim();
        if (q.length < 2) { cont.innerHTML = '<div class="text-center text-muted py-4 small">Escribe al menos 2 letras...</div>'; return; }
        cont.innerHTML = '<div class="text-center py-3"><div class="spinner-border spinner-border-sm"></div></div>';
        let url = '/api/chat/buscar-mensajes?q=' + encodeURIComponent(q);
        if (window._ambitoBusqueda === 'conv' && window._buscarConvId) url += '&conversation_id=' + window._buscarConvId;
        try {
            const r = await fetch(url);
            const d = await r.json();
            const res = d.resultados || [];
            if (!res.length) { cont.innerHTML = '<div class="text-center text-muted py-4 small">Sin resultados</div>'; return; }
            cont.innerHTML = res.map(function(m){
                const f = m.fecha ? new Date(m.fecha) : null;
                const fecha = f ? (f.toLocaleDateString('es-EC',{day:'2-digit',month:'short'}) + ' ' + f.toLocaleTimeString('es-EC',{hour:'2-digit',minute:'2-digit'})) : '';
                const snippet = resaltarBusqueda(m.contenido || '', q);
                return '<div style="padding:9px 16px;border-bottom:1px solid #f3f3f3;cursor:pointer;" onmouseover="this.style.background=\'#f6f8fa\'" onmouseout="this.style.background=\'\'" onclick="irAMensajeBusqueda(' + m.conversation_id + ',\'' + (m.conversation_type||'direct') + '\')">' +
                    '<div style="display:flex;justify-content:space-between;gap:8px;"><strong style="font-size:.85rem;">' + escapeHtml(m.titulo) + '</strong>' +
                    '<span class="text-muted" style="font-size:.7rem;white-space:nowrap;">' + fecha + '</span></div>' +
                    '<div class="text-muted" style="font-size:.82rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">' + escapeHtml(m.remitente) + ': ' + snippet + '</div>' +
                  '</div>';
            }).join('');
        } catch (e) { cont.innerHTML = '<div class="text-center text-danger py-4 small">Error</div>'; }
    }
    window.buscarMsgAhora = buscarMsgAhora;

    function resaltarBusqueda(texto, q) {
        const t = escapeHtml(texto);
        try {
            const re = new RegExp('(' + q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'ig');
            return t.replace(re, '<mark style="background:#fff3a0;padding:0 1px;">$1</mark>');
        } catch (e) { return t; }
    }

    function irAMensajeBusqueda(convId, tipo) {
        const ov = document.getElementById('buscadorMsgOverlay');
        if (ov) ov.remove();
        if (typeof openConversation === 'function') openConversation(convId, tipo || 'direct');
    }
    window.irAMensajeBusqueda = irAMensajeBusqueda;

    // ========================================================
    // EXPORTAR FUNCIONES AL SCOPE GLOBAL (para onclick en HTML)
    // ========================================================
    window.sendMessage = sendMessage;
    window.handleMessageKeydown = handleMessageKeydown;
    window.autoResizeTextarea = autoResizeTextarea;
    window.sendTypingIndicator = sendTypingIndicator;
    window.toggleEmojiPicker = toggleEmojiPicker;
    window.attachImage = attachImage;
    window.attachFile = attachFile;
    window.archiveChat = archiveChat;
    window.muteChat = muteChat;
    window.blockUser = blockUser;
    window.searchInChat = searchInChat;
    window.openConversation = openConversation;
    window.openNewChatModal = openNewChatModal;
    window.searchUsersForChat = searchUsersForChat;
    window.startDirectChat = startDirectChat;
    window.filterConversations = filterConversations;
    window.loadConversations = loadConversations;
    window.showChatInfo = showChatInfo;
    window.iniciarConferenciaDesdeChat = iniciarConferenciaDesdeChat;

