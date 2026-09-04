// chat-grupos-crear.js — Crear grupo: miembros y alta.
// Extraído de chat-page.js (líneas 2289-2401) el 28/08/2026 SIN cambios de código; ámbito global compartido.
// Orden de carga: ver plantillas/chat/index.html (mismo orden que el archivo original).

    // ============================================
    // CREAR GRUPO
    // ============================================
    let selectedGroupMembers = [];

    async function searchUsersForGroup(query) {
        const container = document.getElementById('groupMemberResults');

        if (query.length < 2) {
            container.innerHTML = '';
            return;
        }

        try {
            const response = await fetch(`/api/chat/users/search?q=${encodeURIComponent(query)}`);
            const data = await response.json();

            if (data.success && data.users.length > 0) {
                container.innerHTML = data.users
                    .filter(u => !selectedGroupMembers.find(m => m.id === u.id))
                    .map(user => {
                        const initials = getInitials(user.name);
                        const avatarContent = user.photo ?
                            `<img src="${user.photo}" alt="${user.name}" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';"><span class="avatar-initials" style="display:none;">${initials}</span>` : `<span class="avatar-initials">${initials}</span>`;
                        return `
                            <div class="user-search-item" onclick="addGroupMember(${user.id}, '${escapeHtml(user.name)}')">
                                <div class="avatar" style="width: 32px; height: 32px; font-size: 0.8rem;">${avatarContent}</div>
                                <div>
                                    <div class="small fw-bold">${escapeHtml(user.name)}</div>
                                </div>
                            </div>
                        `;
                    }).join('');
            } else {
                container.innerHTML = '';
            }
        } catch (error) {
            console.error('Error:', error);
        }
    }

    function addGroupMember(id, name) {
        if (selectedGroupMembers.find(m => m.id === id)) return;

        selectedGroupMembers.push({ id, name });
        renderSelectedMembers();
        document.getElementById('searchGroupMembers').value = '';
        document.getElementById('groupMemberResults').innerHTML = '';
    }

    function removeGroupMember(id) {
        selectedGroupMembers = selectedGroupMembers.filter(m => m.id !== id);
        renderSelectedMembers();
    }

    function renderSelectedMembers() {
        const container = document.getElementById('selectedGroupMembers');
        container.innerHTML = selectedGroupMembers.map(member => `
            <span class="badge bg-primary d-flex align-items-center gap-1">
                ${escapeHtml(member.name)}
                <i class="fas fa-times" style="cursor: pointer;" onclick="removeGroupMember(${member.id})"></i>
            </span>
        `).join('');
    }

    async function createGroup() {
        const name = document.getElementById('groupName').value.trim();
        const description = document.getElementById('groupDescription').value.trim();

        if (!name) {
            toastr.warning('Ingresa un nombre para el grupo');
            return;
        }

        if (selectedGroupMembers.length < 1) {
            toastr.warning('Agrega al menos un participante');
            return;
        }

        try {
            const response = await fetch('/api/chat/conversations/group', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name,
                    description,
                    participant_ids: selectedGroupMembers.map(m => m.id)
                })
            });

            const data = await response.json();

            if (data.success) {
                toastr.success('Grupo creado exitosamente');
                newChatModal.hide();

                // Limpiar formulario
                document.getElementById('groupName').value = '';
                document.getElementById('groupDescription').value = '';
                selectedGroupMembers = [];
                renderSelectedMembers();

                await loadConversations();
                openConversation(data.conversation.id, 'group');
            } else {
                toastr.error(data.error || 'Error al crear grupo');
            }
        } catch (error) {
            console.error('Error:', error);
            toastr.error('Error de conexión');
        }
    }

