// chat-conversaciones.js — Cargar y pintar la lista de conversaciones.
// Extraído de chat-page.js (líneas 937-1029) el 28/08/2026 SIN cambios de código; ámbito global compartido.
// Orden de carga: ver plantillas/chat/index.html (mismo orden que el archivo original).

    // ============================================
    // CARGAR CONVERSACIONES
    // ============================================
    async function loadConversations() {
        try {
            const response = await fetch('/api/chat/conversations');
            const data = await response.json();

            if (data.success || data.exito) {
                conversations = data.conversations || data.conversaciones || [];
                renderConversations();
                updateUnreadBadge();
            }
        } catch (error) {
            console.error('Error cargando conversaciones:', error);
            document.getElementById('conversationsList').innerHTML = `
                <div class="text-center py-5 text-danger">
                    <i class="fas fa-exclamation-circle fa-2x mb-2"></i>
                    <p class="mb-0 small">Error al cargar conversaciones</p>
                </div>
            `;
        }
    }

    function renderConversations() {
        const container = document.getElementById('conversationsList');
        let filtered = conversations;

        // Filtrar por tab
        if (currentTab === 'direct') {
            filtered = conversations.filter(c => c.conversation_type === 'direct');
        } else if (currentTab === 'groups') {
            filtered = conversations.filter(c => c.conversation_type === 'group');
        }

        if (filtered.length === 0) {
            container.innerHTML = `
                <div class="text-center py-5 text-muted">
                    <i class="fas fa-inbox fa-2x mb-2 opacity-50"></i>
                    <p class="mb-0 small">No hay conversaciones</p>
                    <button class="btn btn-sm btn-primary mt-2" onclick="openNewChatModal()">
                        <i class="fas fa-plus me-1"></i>Iniciar Chat
                    </button>
                </div>
            `;
            return;
        }

        // IA Maquita OCULTO (2026-06-12) a pedido: no se inyecta el contacto del asistente
        let iaContactHtml = '';

        container.innerHTML = iaContactHtml + filtered.map(conv => {
            // Obtener nombre para mostrar (el backend devuelve 'name')
            const displayName = conv.name || (conv.other_user ? conv.other_user.name : 'Usuario');
            const initials = getInitials(displayName);
            const isGroup = conv.conversation_type === 'group';
            const activeClass = conv.id === currentConversationId ? 'active' : '';
            const unreadBadge = conv.unread_count > 0 ?
                `<span class="conversation-badge">${conv.unread_count}</span>` : '';

            // El backend devuelve 'avatar' no 'avatar_url'
            const avatarUrl = conv.avatar || (conv.other_user ? conv.other_user.photo : null);
            // Usar img con onerror para fallback a iniciales si la imagen falla
            const avatarContent = avatarUrl ?
                `<img src="${avatarUrl}" alt="${displayName}" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';"><span class="avatar-initials" style="display:none;">${initials}</span>` : initials;

            // Indicador de presencia (solo para chats directos)
            const isOnline = conv.other_user && conv.other_user.online;
            const presenceIndicator = !isGroup && conv.other_user ?
                `<span class="presence-indicator ${isOnline ? 'online' : 'offline'}" title="${isOnline ? 'En línea' : 'Desconectado'}"></span>` : '';

            // El backend devuelve 'last_message_preview' no 'last_message'
            const lastMessage = conv.last_message_preview || 'Sin mensajes';

            return `
                <div class="conversation-item ${activeClass}" data-conv-id="${conv.id}" data-conv-type="${conv.conversation_type}" data-conv-name="${escapeHtml(isGroup ? displayName : nombreCorto(displayName))}" title="Clic derecho para opciones" onclick="openConversation(${conv.id}, '${conv.conversation_type}')">
                    <div class="conversation-avatar ${isGroup ? 'group' : ''}">
                        ${avatarContent}
                        ${presenceIndicator}
                    </div>
                    <div class="conversation-info">
                        <div class="conversation-name">${escapeHtml(isGroup ? displayName : nombreCorto(displayName))}</div>
                        <div class="conversation-preview">${escapeHtml(lastMessage)}</div>
                    </div>
                    <div class="conversation-meta">
                        <div class="conversation-time">${formatTime(conv.ultimo_mensaje_en || conv.last_message_at)}</div>
                        ${unreadBadge}
                    </div>
                </div>
            `;
        }).join('');
    }

