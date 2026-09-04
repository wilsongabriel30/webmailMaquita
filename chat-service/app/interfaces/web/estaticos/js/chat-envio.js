// chat-envio.js — Envío de mensajes (ultrarrápido y normal) y teclado.
// Extraído de chat-page.js (líneas 1958-2205) el 28/08/2026 SIN cambios de código; ámbito global compartido.
// Orden de carga: ver plantillas/chat/index.html (mismo orden que el archivo original).

    // ============================================
    // ENVIAR MENSAJE - v3.0 WebSocket Ultra-Rápido
    // ============================================
    let chatUltraFast = null;  // Instancia global

    // Inicializar Chat Ultra-Rápido v3.0
    function initChatUltraFast() {
        if (typeof ChatUltraFast !== 'undefined' && !chatUltraFast) {
            chatUltraFast = new ChatUltraFast({ userId: currentUserId });

            chatUltraFast.connect().then(() => {
                console.log('⚡⚡⚡ Chat Ultra-Rápido v3.0 conectado');

                // ⚡ DETENER POLLING - WebSocket maneja todo
                stopFallbackPolling();

                // Unirse a conversación si hay una abierta o pendiente
                const convToJoin = currentConversationId || window._pendingJoinConversation;
                if (convToJoin) {
                    chatUltraFast.join(convToJoin);
                    console.log(`⚡ Auto-unido a sala de conversación ${convToJoin}`);
                    window._pendingJoinConversation = null;
                }

                // Monitorear latencia
                chatUltraFast.startLatencyMonitor(5000);
            }).catch(err => {
                console.error('❌ Error conectando WebSocket:', err);
                // Si falla WebSocket, activar polling como ÚLTIMO recurso
                console.log('⚠️ Activando polling de emergencia');
                startFallbackPolling();
            });

            // Handlers
            chatUltraFast.on('onConnect', () => {
                console.log('⚡ WebSocket reconectado');
                // Unirse automáticamente a la conversación actual
                const convToJoin = currentConversationId || window._pendingJoinConversation;
                if (convToJoin) {
                    chatUltraFast.join(convToJoin);
                    console.log(`⚡ Re-unido a sala de conversación ${convToJoin}`);
                    window._pendingJoinConversation = null;
                }
                // Detener polling si estaba activo
                stopFallbackPolling();
            });
            chatUltraFast.on('onDisconnect', (data) => {
                console.log('❌ WebSocket desconectado:', data.reason);
                // NO activar polling inmediatamente - esperar reconexión automática
            });
            chatUltraFast.on('onMessage', handleUltraFastIncoming);
            chatUltraFast.on('onAck', (data) => {
                console.log('⚡ ACK:', data.tempId);
                updateMessageStatusByTempId(data.tempId, 'sending');
            });
            chatUltraFast.on('onSaved', (data) => {
                console.log('⚡ Guardado:', data.tempId, '->', data.realId);
                updateTempIdToReal(data.tempId, data.realId);
            });
            chatUltraFast.on('onTyping', (data) => {
                if (data.conversationId == currentConversationId) {
                    showTypingIndicator(data.userId, data.isTyping);
                }
            });
            chatUltraFast.on('onLatency', (data) => {
                updateLatencyIndicator(data.latency);
            });
        }
    }

    // Manejar mensaje entrante via UltraFast
    function handleUltraFastIncoming(data) {
        const msgId = String(data.id || data.tempId || '');

        // Evitar duplicados
        if (msgId && shownMessageIds.has(msgId)) {
            console.log('⚡ Duplicado ignorado:', msgId);
            return;
        }

        if (msgId) shownMessageIds.add(msgId);

        // Solo procesar mensajes de otros
        if (data.senderId == currentUserId) return;

        playNotificationSound();

        if (data.conversationId == currentConversationId) {
            const container = document.getElementById('chatMessages');
            if (!container) return;

            // Verificar que no exista ya en DOM
            const msgIdStr = String(data.id || data.tempId);
            const existingMsg = container.querySelector(`[data-message-id="${msgIdStr}"]`);
            if (existingMsg) {
                console.log('⚡ Mensaje ya en DOM - ignorando:', msgIdStr);
                return;
            }

            const message = {
                id: data.id || data.tempId,
                content: data.content,
                sender_id: data.senderId,
                sender_name: data.senderName || 'Usuario',
                created_at: new Date(data.timestamp).toISOString(),
                is_own_message: false,
                message_type: data.type || 'text',
                gif_url: data.gif_url
            };

            console.log('⚡ handleUltraFastIncoming - Renderizando mensaje:', message);
            container.insertAdjacentHTML('beforeend', renderSingleMessage(message));
            scrollToBottom(container, true);
        }

        loadConversations();
    }

    // Actualizar ID temporal a real
    function updateTempIdToReal(tempId, realId) {
        const el = document.querySelector(`[data-message-id="temp_${tempId}"]`);
        if (el && realId) {
            el.dataset.messageId = realId;
            el.classList.remove('message-pending', 'message-sending');
            el.classList.add('message-sent');
            shownMessageIds.add(String(realId));

            const statusEl = el.querySelector('.message-status');
            if (statusEl) statusEl.innerHTML = '✓';
        }
    }

    // Actualizar estado por tempId
    function updateMessageStatusByTempId(tempId, status) {
        const el = document.querySelector(`[data-message-id="temp_${tempId}"]`);
        if (el) {
            el.classList.remove('message-pending');
            el.classList.add(`message-${status}`);
        }
    }

    async function sendMessage() {
        const input = document.getElementById('messageInput');
        let content = input.value.trim();

        if (!content || !currentConversationId) return;

        const conversationId = validateId(currentConversationId);
        if (!conversationId) {
            toastr.error('Error: conversacion invalida');
            return;
        }

        content = sanitizeMessage(content);
        if (!content) {
            toastr.warning('El mensaje no puede estar vacio');
            return;
        }

        const btn = document.getElementById('btnSendMessage');
        btn.disabled = true;

        // ⚡⚡⚡ ENVIAR VIA WEBSOCKET (v3.0) - MÁS RÁPIDO QUE HTTP
        if (chatUltraFast && chatUltraFast.connected) {
            const msg = chatUltraFast.send(conversationId, content, 'text');

            if (msg) {
                // UI OPTIMISTA: Mostrar inmediatamente
                const container = document.getElementById('chatMessages');
                const emptyState = container.querySelector('.chat-empty-state');
                if (emptyState) emptyState.remove();

                // Registrar para evitar duplicado
                shownMessageIds.add(msg.id);

                // Crear mensaje temporal
                const tempMessage = {
                    id: msg.id,
                    content: content,
                    message_type: 'text',
                    sender_id: currentUserId,
                    created_at: new Date().toISOString(),
                    is_own_message: true,
                    status: 'pending'
                };

                container.insertAdjacentHTML('beforeend', renderSingleMessage(tempMessage));
                scrollToBottom(container, true);

                // Limpiar input
                input.value = '';
                input.style.height = 'auto';
                btn.disabled = true;

                console.log('⚡ Mensaje enviado via WebSocket:', msg.tempId);
                loadConversations();
                return;
            }
        }

        // ⚠️ FALLBACK A HTTP si WebSocket no disponible
        console.log('⚠️ Fallback a HTTP');
        try {
            const response = await fetch(`/api/chat/conversations/${conversationId}/messages`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ content, message_type: 'text' })
            });

            const data = await response.json();

            if (data.success) {
                const container = document.getElementById('chatMessages');
                const emptyState = container.querySelector('.chat-empty-state');
                if (emptyState) emptyState.remove();

                if (data.message && data.message.id) {
                    shownMessageIds.add(String(data.message.id));
                }

                container.insertAdjacentHTML('beforeend', renderSingleMessage(data.message));
                scrollToBottom(container, true);
                input.value = '';
                input.style.height = 'auto';
                loadConversations();
            } else {
                toastr.error(data.error || 'Error al enviar mensaje');
            }
        } catch (error) {
            console.error('Error enviando mensaje:', error);
            toastr.error('Error de conexión');
        } finally {
            btn.disabled = !input.value.trim();
        }
    }

    function handleMessageKeydown(event) {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            // Usar window.sendMessage para permitir interceptacion por IA Chat
            if (typeof window.sendMessage === 'function') {
                window.sendMessage();
            } else {
                sendMessage();
            }
        }
    }

