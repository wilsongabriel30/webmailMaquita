// chat-lista.js — Modal nuevo chat, pestañas, archivadas, filtro, leído, sondeo de respaldo, badge.
// Extraído de chat-page.js (líneas 2402-2700) el 28/08/2026 SIN cambios de código; ámbito global compartido.
// Orden de carga: ver plantillas/chat/index.html (mismo orden que el archivo original).

    // ============================================
    // FUNCIONES AUXILIARES
    // ============================================
    function openNewChatModal() {
        document.getElementById('searchUsers').value = '';
        document.getElementById('userSearchResults').innerHTML = `
            <div class="text-center text-muted py-3">
                <i class="fas fa-search fa-2x mb-2 opacity-50"></i>
                <p class="mb-0 small">Escribe para buscar compañeros</p>
            </div>
        `;
        newChatModal.show();
    }

    function switchTab(tab) {
        const prev = currentTab;
        currentTab = tab;
        document.querySelectorAll('.chat-tab').forEach(t => t.classList.remove('active'));
        const tabBtn = document.querySelector(`.chat-tab[data-tab="${tab}"]`);
        if (tabBtn) tabBtn.classList.add('active');

        // Pestaña ARCHIVADOS: cargar las conversaciones archivadas del usuario
        if (tab === 'archived') {
            window._viendoArchivadas = true;
            cargarArchivadas();
            return;
        }
        // Si venimos de archivados, recargar las conversaciones normales
        if (window._viendoArchivadas) {
            window._viendoArchivadas = false;
            if (typeof loadConversations === 'function') { loadConversations(); return; }
        }

        // Manejar tab de IA de forma especial
        if (tab === 'ia') {
            // Usar el modulo de IA Chat
            if (typeof showIAConversations === 'function') {
                showIAConversations();
            }
            // Emitir evento para que el modulo IA pueda reaccionar
            document.dispatchEvent(new CustomEvent('chatTabChanged', { detail: { tab: 'ia' } }));
        } else {
            // Limpiar modo IA si estaba activo
            const activeArea = document.getElementById('chatActiveArea');
            if (activeArea && activeArea.dataset.mode === 'ia') {
                delete activeArea.dataset.mode;
            }
            renderConversations();
        }
    }

    async function cargarArchivadas() {
        try {
            const cont = document.getElementById('conversationsList');
            if (cont) cont.innerHTML = '<div class="text-center text-muted py-4"><div class="spinner-border spinner-border-sm"></div></div>';
            const r = await fetch('/api/chat/conversations?archivadas=1');
            const d = await r.json();
            conversations = d.conversations || d.conversaciones || [];
            renderConversations();
            if (!conversations.length && cont) {
                cont.innerHTML = '<div class="text-center text-muted py-4"><i class="fas fa-box-archive fa-2x mb-2 opacity-50"></i><p class="mb-0 small">No tienes conversaciones archivadas</p></div>';
            }
        } catch (e) { console.error('archivadas:', e); }
    }
    window.cargarArchivadas = cargarArchivadas;

    let _searchContactosTimer = null;
    function filterConversations(query) {
        const q = (query || '').trim().toLowerCase();
        // Filtrar conversaciones existentes por nombre
        document.querySelectorAll('#conversationsList .conversation-item').forEach(item => {
            if (item.closest('#contactosBusqueda')) return;
            const nameEl = item.querySelector('.conversation-name');
            const name = nameEl ? nameEl.textContent.toLowerCase() : '';
            item.style.display = name.includes(q) ? 'flex' : 'none';
        });
        // Quitar seccion previa de companeros
        const prev = document.getElementById('contactosBusqueda');
        if (prev) prev.remove();
        if (q.length < 2) return;
        // Buscar companeros (con debounce) y mostrarlos abajo, como WhatsApp
        clearTimeout(_searchContactosTimer);
        _searchContactosTimer = setTimeout(function(){ buscarCompanerosEnLista(query); }, 300);
    }

    async function buscarCompanerosEnLista(query) {
        try {
            const r = await fetch('/api/chat/users/search?q=' + encodeURIComponent(query));
            const d = await r.json();
            const cont = document.getElementById('conversationsList');
            const prev = document.getElementById('contactosBusqueda');
            if (prev) prev.remove();
            if (!d || !d.success || !d.users || !d.users.length) return;
            // No duplicar a quienes ya tienen conversacion
            const yaConvers = new Set((conversations || []).filter(c => c.other_user).map(c => c.other_user.id));
            const nuevos = d.users.filter(u => !yaConvers.has(u.id));
            if (!nuevos.length) return;
            const sec = document.createElement('div');
            sec.id = 'contactosBusqueda';
            sec.innerHTML = '<div class="search-section-title">Compañeros</div>' + nuevos.map(function(u){
                const ini = getInitials(u.name);
                const av = u.photo
                    ? '<img src="' + u.photo + '" onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'flex\';"><span class="avatar-initials" style="display:none;">' + ini + '</span>'
                    : '<span class="avatar-initials">' + ini + '</span>';
                const nm = escapeHtml(u.name).replace(/'/g, "\\'");
                return '<div class="conversation-item" onclick="startDirectChat(' + u.id + ', \'' + nm + '\')">' +
                    '<div class="conversation-avatar">' + av + '</div>' +
                    '<div class="conversation-info">' +
                    '<div class="conversation-name">' + escapeHtml(nombreCorto(u.name)) + '</div>' +
                    '<div class="conversation-preview">' + escapeHtml(u.department || 'Iniciar chat') + '</div>' +
                    '</div></div>';
            }).join('');
            cont.appendChild(sec);
        } catch (e) { console.error('buscar companeros:', e); }
    }
    window.buscarCompanerosEnLista = buscarCompanerosEnLista;

    async function markAsRead(conversationId) {
        try {
            await fetch(`/api/chat/conversations/${conversationId}/read`, { method: 'POST' });

            // Actualizar contador en lista
            const conv = conversations.find(c => c.id === conversationId);
            if (conv) conv.unread_count = 0;
            renderConversations();
            updateUnreadBadge();
        } catch (error) {
            console.error('Error marcando como leído:', error);
        }
    }

    // Variable para controlar el polling de fallback
    let fallbackPollingInterval = null;
    let lastKnownMessageId = 0;

    function startFallbackPolling() {
        if (fallbackPollingInterval) return; // Ya está activo

        // ⚡ Si WebSocket v3.0 está conectado, NO usar polling
        if (chatUltraFast && chatUltraFast.connected) {
            console.log('⚡ WebSocket v3.0 activo - polling desactivado');
            return;
        }

        // Polling cada 10 segundos para reducir carga en servidor
        console.log('🔄 Polling: 10000ms (fallback - reducido para evitar sobrecarga)');
        fallbackPollingInterval = setInterval(checkNewMessages, 10000);

        // También verificar inmediatamente (una sola vez)
        checkNewMessages();
    }

    function stopFallbackPolling() {
        if (fallbackPollingInterval) {
            clearInterval(fallbackPollingInterval);
            fallbackPollingInterval = null;
            console.log('✅ Polling de fallback detenido (Socket.IO conectado)');
        }
    }

    async function checkNewMessages() {
        try {
            // Verificar mensajes en TODAS las conversaciones para notificaciones
            const response = await fetch('/api/chat/conversations');
            const data = await response.json();

            if (data.success && data.conversations) {
                let hasNewMessages = false;

                data.conversations.forEach(conv => {
                    if (conv.unread_count > 0) {
                        hasNewMessages = true;
                    }
                });

                // Actualizar lista de conversaciones
                conversations = data.conversations;
                renderConversations();

                // Si hay una conversación abierta, cargar mensajes nuevos
                if (currentConversationId) {
                    await checkCurrentConversationMessages();
                }
            }
        } catch (error) {
            console.error('Error verificando nuevos mensajes:', error);
        }
    }

    async function checkCurrentConversationMessages() {
        if (!currentConversationId) return;

        try {
            const response = await fetch(`/api/chat/conversations/${currentConversationId}/messages?limit=20`);
            const data = await response.json();

            console.log('🔍 Polling - Mensajes recibidos:', data.messages?.length || 0);

            if (data.success && data.messages && data.messages.length > 0) {
                const container = document.getElementById('chatMessages');
                if (!container) return;

                const existingMessages = container.querySelectorAll('.message[data-message-id]');
                const existingIds = new Set(
                    Array.from(existingMessages).map(m => String(m.dataset.messageId))
                );

                // ⚡ También incluir IDs temporales para evitar duplicados de UI optimista
                existingMessages.forEach(m => {
                    const id = m.dataset.messageId;
                    if (id && id.startsWith('temp_')) {
                        existingIds.add(id);
                    }
                });

                // ⚡ Filtrar mensajes que ya están mostrados O son propios recientes
                const now = Date.now();
                const newMessages = data.messages.filter(m => {
                    const msgId = String(m.id);

                    // Ya mostrado por ID real
                    if (existingIds.has(msgId)) return false;

                    // Ya registrado en shownMessageIds
                    if (shownMessageIds.has(msgId)) return false;

                    // ⚡ Mensaje propio reciente (últimos 10 segundos) - probablemente ya mostrado via UI optimista
                    const isOwn = m.is_own_message || m.is_own || String(m.sender_id) === String(currentUserId);
                    if (isOwn) {
                        const msgTime = new Date(m.created_at).getTime();
                        if (now - msgTime < 10000) {
                            console.log('⚡ Mensaje propio reciente ignorado:', msgId);
                            shownMessageIds.add(msgId);
                            // Actualizar el ID temporal si existe
                            const tempEl = container.querySelector('.message[data-message-id^="temp_"]:last-child');
                            if (tempEl) {
                                tempEl.dataset.messageId = msgId;
                            }
                            return false;
                        }
                    }

                    return true;
                });

                if (newMessages.length > 0) {
                    let hasOtherUserMessages = false;

                    newMessages.forEach(msg => {
                        console.log('➕ Agregando mensaje:', msg.id, 'de', msg.sender?.name || 'desconocido');
                        shownMessageIds.add(String(msg.id));
                        container.insertAdjacentHTML('beforeend', renderSingleMessage(msg));

                        // Verificar si es mensaje de otro usuario
                        if (!msg.is_own_message && !msg.is_own) {
                            hasOtherUserMessages = true;
                        }
                    });

                    scrollToBottom(container, true);

                    // Reproducir sonido si hay mensajes de otros usuarios
                    if (hasOtherUserMessages) {
                        console.log('🔔 Reproduciendo sonido de notificación');
                        playNotificationSound();
                    }
                }
            }
        } catch (error) {
            console.error('Error cargando mensajes de conversación:', error);
        }
    }

    function sendTypingIndicator() {
        clearTimeout(typingTimeout);

        if (currentConversationId) {
            fetch(`/api/chat/conversations/${currentConversationId}/typing`, { method: 'POST' });

            typingTimeout = setTimeout(() => {
                // Typing stopped
            }, 3000);
        }
    }

    function autoResizeTextarea(textarea) {
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
    }

    function updateUnreadBadge() {
        const totalUnread = conversations.reduce((sum, c) => sum + (c.unread_count || 0), 0);
        const badge = document.getElementById('chatBadge');
        if (badge) {
            badge.textContent = totalUnread;
            badge.style.display = totalUnread > 0 ? 'block' : 'none';
        }
    }

