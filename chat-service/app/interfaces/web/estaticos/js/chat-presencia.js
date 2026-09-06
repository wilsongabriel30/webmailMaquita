// chat-presencia.js — Presencia en línea.
// Extraído de chat-page.js (líneas 2701-2794) el 28/08/2026 SIN cambios de código; ámbito global compartido.
// Orden de carga: ver plantillas/chat/index.html (mismo orden que el archivo original).

    // ============================================
    // SISTEMA DE PRESENCIA ONLINE/OFFLINE
    // ============================================

    async function updateUserPresence() {
        /**
         * Actualiza el estado de presencia del usuario actual.
         * Se llama periódicamente para mantener al usuario como "online".
         */
        try {
            await fetch('/api/chat/presence/update', { method: 'POST' });
        } catch (error) {
            console.error('Error actualizando presencia:', error);
        }
    }

    async function updateOtherUsersPresence() {
        /**
         * Actualiza el estado de presencia de otros usuarios en las conversaciones.
         * Se llama periódicamente para mantener actualizado el indicador LED.
         */
        try {
            // Recargar conversaciones para obtener estados actualizados
            await loadConversations();
        } catch (error) {
            console.error('Error actualizando presencia de otros usuarios:', error);
        }
    }

    /**
     * Actualiza el indicador de presencia en la UI para un usuario específico.
     */
    function updateUserPresenceUI(userId, isOnline) {
        // Actualizar en la lista de conversaciones
        const conversationItems = document.querySelectorAll('.conversation-item');
        conversationItems.forEach(item => {
            const presenceIndicator = item.querySelector('.presence-indicator');
            if (presenceIndicator) {
                // Verificar si esta conversación pertenece al usuario
                const avatarSpan = presenceIndicator;
                // Actualizar clases
                if (avatarSpan.closest('.conversation-item')) {
                    // Buscar el user_id en las conversaciones cargadas
                    const convId = item.getAttribute('onclick')?.match(/openConversation\((\d+)/)?.[1];
                    if (convId) {
                        const conv = conversations?.find(c => c.id == convId);
                        if (conv && conv.other_user && conv.other_user.id == userId) {
                            presenceIndicator.classList.remove('online', 'offline');
                            presenceIndicator.classList.add(isOnline ? 'online' : 'offline');
                            presenceIndicator.title = isOnline ? 'En línea' : 'Desconectado';
                        }
                    }
                }
            }
        });

        // Actualizar en el header del chat activo si es el usuario actual
        const chatHeader = document.querySelector('.chat-main-header');
        if (chatHeader && currentConversationId) {
            const currentConv = conversations?.find(c => c.id == currentConversationId);
            if (currentConv && currentConv.other_user && currentConv.other_user.id == userId) {
                const headerPresence = chatHeader.querySelector('.presence-indicator');
                if (headerPresence) {
                    headerPresence.classList.remove('online', 'offline');
                    headerPresence.classList.add(isOnline ? 'online' : 'offline');
                }

                // Actualizar el estado real de la cabecera (#chatHeaderStatus) con ultima vez
                const headerStatusEl = document.getElementById('chatHeaderStatus');
                if (headerStatusEl) {
                    headerStatusEl.className = isOnline ? 'status-online' : 'status-offline';
                    const txt = isOnline ? 'En línea'
                        : (typeof formatUltimaVez === 'function' ? formatUltimaVez(new Date().toISOString()) : 'Desconectado');
                    headerStatusEl.innerHTML = (isOnline ? '<i class="fas fa-circle me-1" style="font-size:.5rem;"></i>' : '') +
                        '<span>' + txt + '</span>';
                    headerStatusEl.style.display = '';
                }
            }
        }
    }

    // Marcar como offline al cerrar la pestaña
    window.addEventListener('beforeunload', function() {
        /**
         * Marca al usuario como offline al cerrar la pestaña o navegador.
         * Usa sendBeacon para asegurar que la petición se envíe incluso al cerrar.
         */
        try {
            navigator.sendBeacon('/api/chat/presence/offline');
        } catch (error) {
            console.error('Error marcando offline:', error);
        }
    });

