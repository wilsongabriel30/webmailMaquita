// chat-tiempo-real.js — Mensajes entrantes en tiempo real, escribiendo…, estados entregado/leído.
// Extraído de chat-page.js (líneas 547-686) el 28/08/2026 SIN cambios de código; ámbito global compartido.
// Orden de carga: ver plantillas/chat/index.html (mismo orden que el archivo original).

    const shownMessageIds = new Set();

    function handleNewMessage(data) {
        const message = data.message;
        const conversationId = data.conversation_id;

        // Validar que hay mensaje
        if (!message) {
            console.log('📨 Sin mensaje - ignorando');
            return;
        }

        const messageId = String(message.id || '');

        // ⚡ VERIFICACIÓN 1: ¿Ya se mostró este mensaje?
        if (messageId && shownMessageIds.has(messageId)) {
            console.log('📨 Mensaje ya mostrado (Set) - ignorando:', messageId);
            return;
        }

        // ⚡ VERIFICACIÓN 2: ¿Es mensaje propio? (comparar como strings)
        const senderId = String(message.sender_id || message.sender?.id || '');
        const myId = String(currentUserId || '');
        const isOwnMessage = message.is_own_message || message.is_own ||
                            (senderId && myId && senderId === myId);

        console.log('📨 Debug: senderId=', senderId, 'myId=', myId, 'isOwn=', isOwnMessage);

        if (isOwnMessage) {
            console.log('📨 Mensaje PROPIO via Socket - ignorando:', messageId);
            if (messageId) shownMessageIds.add(messageId);
            return;
        }

        // ⚡ VERIFICACIÓN 3: ¿Ya existe en el DOM?
        const container = document.getElementById('chatMessages');
        if (container && messageId) {
            const existingMsg = container.querySelector(`[data-message-id="${messageId}"]`);
            if (existingMsg) {
                console.log('📨 Mensaje ya en DOM - ignorando:', messageId);
                shownMessageIds.add(messageId);
                return;
            }
        }

        // Marcar como mostrado ANTES de agregar
        if (messageId) shownMessageIds.add(messageId);

        // Reproducir sonido para mensajes de otras personas
        playNotificationSound();

        // Si es de la conversación actual, agregar el mensaje
        if (conversationId == currentConversationId && container) {
            container.insertAdjacentHTML('beforeend', renderSingleMessage(message));
            scrollToBottom(container, true);

            // Marcar como leído automáticamente
            if (socket && socketConnected) {
                socket.emit('message_read', { conversation_id: conversationId });
            }
        }

        // Actualizar lista de conversaciones (último mensaje y badge)
        loadConversations();
    }

    function showTypingIndicator(userId, isTyping) {
        const indicator = document.getElementById('typingIndicator');
        if (!indicator) return;

        if (isTyping) {
            indicator.textContent = 'Escribiendo...';
            indicator.style.display = 'block';
        } else {
            indicator.style.display = 'none';
        }
    }

    /**
     * Actualizar estado de mensajes individuales
     */
    function updateMessageStatus(messageId, status) {
        const message = document.querySelector(`.message[data-message-id="${messageId}"]`);
        if (!message) return;

        const statusIcon = message.querySelector('.message-status');
        if (!statusIcon) return;

        // Agregar animación de actualización
        statusIcon.classList.add('updating');

        setTimeout(() => {
            statusIcon.classList.remove('updating');

            // Actualizar icono y clases según el estado
            if (status === 'delivered') {
                // Doble check gris
                statusIcon.className = 'fas fa-check-double message-status delivered';
                statusIcon.title = 'Entregado';
            } else if (status === 'read') {
                // Doble check azul con animación
                statusIcon.className = 'fas fa-check-double message-status read';
                statusIcon.title = 'Leído';
            }
        }, 250);
    }

    /**
     * Marcar mensaje específico como entregado
     */
    function updateMessageToDelivered(messageId) {
        updateMessageStatus(messageId, 'delivered');
    }

    /**
     * Marcar todos los mensajes propios como leídos (cuando destinatario abre chat)
     */
    function updateAllMessagesToRead() {
        const messages = document.querySelectorAll('.message.sent');
        messages.forEach(msg => {
            const messageId = msg.getAttribute('data-message-id');
            const statusIcon = msg.querySelector('.message-status');

            if (statusIcon && !statusIcon.classList.contains('read')) {
                // Actualizar a leído con pequeño delay escalonado para efecto visual
                const delay = Math.random() * 200;
                setTimeout(() => {
                    updateMessageStatus(messageId, 'read');
                }, delay);
            }
        });
    }

    /**
     * Función legacy para compatibilidad
     */
    function updateMessageReadStatus(userId) {
        updateAllMessagesToRead();
    }

