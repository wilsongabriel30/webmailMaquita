// chat-nuevo-chat.js — Buscar personas e iniciar chat directo.
// Extraído de chat-page.js (líneas 2206-2288) el 28/08/2026 SIN cambios de código; ámbito global compartido.
// Orden de carga: ver plantillas/chat/index.html (mismo orden que el archivo original).

    // ============================================
    // BUSCAR USUARIOS PARA NUEVO CHAT
    // ============================================
    async function searchUsersForChat(query) {
        const container = document.getElementById('userSearchResults');

        if (query.length < 2) {
            container.innerHTML = `
                <div class="text-center text-muted py-3">
                    <i class="fas fa-search fa-2x mb-2 opacity-50"></i>
                    <p class="mb-0 small">Escribe para buscar compañeros</p>
                </div>
            `;
            return;
        }

        container.innerHTML = `
            <div class="text-center py-3">
                <div class="spinner-border spinner-border-sm" role="status"></div>
            </div>
        `;

        try {
            const response = await fetch(`/api/chat/users/search?q=${encodeURIComponent(query)}`);
            const data = await response.json();

            if (data.success && data.users.length > 0) {
                container.innerHTML = data.users.map(user => {
                    const initials = getInitials(user.name);
                    const avatarContent = user.photo ?
                        `<img src="${user.photo}" alt="${user.name}" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';"><span class="avatar-initials" style="display:none;">${initials}</span>` : `<span class="avatar-initials">${initials}</span>`;

                    return `
                        <div class="user-search-item" onclick="startDirectChat(${user.id}, '${escapeHtml(user.name)}')">
                            <div class="avatar">${avatarContent}</div>
                            <div>
                                <div class="fw-bold">${escapeHtml(user.name)}</div>
                                <small class="text-muted">${escapeHtml(user.department || '')}</small>
                            </div>
                        </div>
                    `;
                }).join('');
            } else {
                container.innerHTML = `
                    <div class="text-center text-muted py-3">
                        <i class="fas fa-user-slash fa-2x mb-2 opacity-50"></i>
                        <p class="mb-0 small">No se encontraron resultados</p>
                    </div>
                `;
            }
        } catch (error) {
            console.error('Error buscando usuarios:', error);
            container.innerHTML = `
                <div class="text-center text-danger py-3">
                    <p class="mb-0 small">Error de conexión</p>
                </div>
            `;
        }
    }

    async function startDirectChat(userId, userName) {
        try {
            const response = await fetch('/api/chat/conversations/direct', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: userId })
            });

            const data = await response.json();

            if (data.success) {
                newChatModal.hide();
                await loadConversations();
                openConversation(data.conversation.id, 'direct');
            } else {
                toastr.error(data.error || 'Error al crear conversación');
            }
        } catch (error) {
            console.error('Error:', error);
            toastr.error('Error de conexión');
        }
    }

