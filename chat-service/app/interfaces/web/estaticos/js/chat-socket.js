// chat-socket.js — Socket.IO: init, canal ultrarrápido y socket legado.
// Extraído de chat-page.js (líneas 130-423) el 28/08/2026 SIN cambios de código; ámbito global compartido.
// Orden de carga: ver plantillas/chat/index.html (mismo orden que el archivo original).

    // ============================================
    // CHAT ULTRA-RÁPIDO v2.0 - LATENCIA <10ms
    // ============================================
    let socket = null;
    let socketConnected = false;
    let chatRealtime = null;  // Instancia del chat ultra-rápido
    let useUltraFast = true;  // Flag para usar versión ultra-rápida

    function initSocket() {
        // ⚡⚡⚡ SOLO v3.0 - TODO LO DEMÁS DESACTIVADO
        if (typeof ChatUltraFast !== 'undefined') {
            console.log('⚡⚡⚡ SOLO v3.0 activo - legacy y v2.0 DESACTIVADOS');
            // NO inicializar nada aquí - v3.0 se maneja en initChatUltraFast()
            return;
        }
        // Fallback solo si v3.0 no está disponible
        initLegacySocket();
    }

    // ============================================
    // CHAT ULTRA-RÁPIDO v2.0 (Nuevo)
    // ============================================
    function initUltraFastChat() {
        try {
            chatRealtime = new ChatRealtime({
                userId: currentUserId,
                DEBUG: false  // Cambiar a true para debug
            });

            // Conectar
            chatRealtime.connect().then(() => {
                console.log('⚡ Chat Ultra-Rápido conectado');
                socketConnected = true;

                // Unirse a conversación si hay una abierta
                if (currentConversationId) {
                    chatRealtime.joinConversation(currentConversationId);
                }

                // Iniciar monitor de latencia
                chatRealtime.startLatencyMonitor(10000);
            }).catch(err => {
                console.error('Error conectando Ultra-Rápido, usando fallback:', err);
                useUltraFast = false;
                initLegacySocket();
            });

            // Eventos
            chatRealtime.on('onMessage', handleUltraFastMessage);
            chatRealtime.on('onTyping', handleUltraFastTyping);
            chatRealtime.on('onOnline', data => updateUserPresence(data.userId, true));
            chatRealtime.on('onOffline', data => updateUserPresence(data.userId, false));
            chatRealtime.on('onRead', data => {
                if (data.conversationId == currentConversationId) {
                    updateAllMessagesToRead();
                }
            });
            chatRealtime.on('onLatency', data => {
                console.log(`📶 Latencia: ${data.latency}ms`);
                // Mostrar latencia en UI si es necesario
                updateLatencyIndicator(data.latency);
            });
            chatRealtime.on('onDisconnect', () => {
                socketConnected = false;
                console.log('❌ Desconectado');
            });
            chatRealtime.on('onConnect', () => {
                socketConnected = true;
                console.log('⚡ Reconectado');
            });

            console.log('⚡ Chat Ultra-Rápido v2.0 inicializado');

        } catch (error) {
            console.error('❌ Error inicializando Ultra-Rápido:', error);
            useUltraFast = false;
            initLegacySocket();
        }
    }

    // Manejar mensaje ultra-rápido (con UI optimista)
    function handleUltraFastMessage(data) {
        // Si es actualización de ID temporal a real
        if (data.type === 'id_update') {
            const tempElement = document.querySelector(`[data-message-id="${data.tempId}"]`);
            if (tempElement) {
                tempElement.dataset.messageId = data.realId;
                tempElement.classList.remove('message-pending');
                tempElement.classList.add('message-sent');
            }
            return;
        }

        // Verificar si es mensaje propio
        const isOwnMessage = data.senderId == currentUserId;

        // ⚡ IMPORTANTE: No agregar mensajes propios
        // Ya fueron agregados por sendMessage() via HTTP
        if (isOwnMessage) {
            console.log('⚡ Mensaje propio via UltraFast - ignorando (ya en DOM)');
            return;
        }

        // Mensaje de otro usuario
        const message = {
            id: data.id,
            content: data.content,
            sender_id: data.senderId,
            created_at: new Date(data.timestamp).toISOString(),
            is_own_message: false,
            status: data.status,
            reply_to_id: data.reply_to_id || null
        };

        // Reproducir sonido
        playNotificationSound();

        // Si es de la conversación actual, agregar al DOM
        if (data.conversationId == currentConversationId) {
            const container = document.getElementById('chatMessages');
            if (!container) return;

            // Verificar que no exista ya
            const existingMsg = container.querySelector(`[data-message-id="${data.id}"]`);
            if (existingMsg) {
                console.log('⚡ Mensaje ya existe - ignorando');
                return;
            }

            container.insertAdjacentHTML('beforeend', renderSingleMessage(message));
            scrollToBottom(container, true);
        }

        // Actualizar lista de conversaciones
        loadConversations();
    }

    function handleUltraFastTyping(data) {
        if (data.conversationId == currentConversationId) {
            showTypingIndicator(data.userId, data.isTyping);
        }
    }

    // Indicador de latencia en UI
    function updateLatencyIndicator(latency) {
        // Indicador tecnico: oculto al usuario final. Solo se muestra con ?debug=1
        if (new URLSearchParams(location.search).get('debug') !== '1') return;
        let indicator = document.getElementById('latency-indicator');
        if (!indicator) {
            indicator = document.createElement('div');
            indicator.id = 'latency-indicator';
            indicator.style.cssText = 'position:fixed;bottom:10px;right:10px;padding:4px 8px;border-radius:4px;font-size:11px;z-index:9999;';
            document.body.appendChild(indicator);
        }

        if (latency < 50) {
            indicator.style.background = '#22c55e';
            indicator.style.color = 'white';
            indicator.textContent = `⚡ ${latency}ms`;
        } else if (latency < 150) {
            indicator.style.background = '#eab308';
            indicator.style.color = 'black';
            indicator.textContent = `📶 ${latency}ms`;
        } else {
            indicator.style.background = '#ef4444';
            indicator.style.color = 'white';
            indicator.textContent = `🐌 ${latency}ms`;
        }
    }

    // Actualizar estado del mensaje
    // updateMessageStatus(): la definición vigente vive en chat-tiempo-real.js (esta copia idéntica se quitó el 28/08/2026;
    // antes coexistían dos y ganaba la segunda).

    // ============================================
    // SOCKET.IO LEGACY (Fallback)
    // ============================================
    function initLegacySocket() {
        try {
            // Conectar a Socket.IO
            socket = io({
                transports: ['websocket', 'polling'],
                upgrade: true,
                reconnection: true,
                reconnectionDelay: 1000,
                reconnectionAttempts: 10
            });

            // Eventos de conexión
            socket.on('connect', function() {
                console.log('✅ Socket.IO conectado (legacy)');
                socketConnected = true;

                if (currentConversationId) {
                    socket.emit('join_conversation', { conversation_id: currentConversationId });
                }
            });

            socket.on('disconnect', function() {
                console.log('❌ Socket.IO desconectado');
                socketConnected = false;
            });

            socket.on('connect_error', function(error) {
                console.error('❌ Error de conexión Socket.IO:', error);
                socketConnected = false;
            });

            // Evento: Nuevo mensaje recibido (LEGACY - desactivado si v3.0 activo)
            socket.on('new_message', function(data) {
                // ⚡ Si v3.0 está activo, ignorar eventos legacy para evitar duplicados
                if (chatUltraFast && chatUltraFast.connected) {
                    console.log('⚡ Ignorando new_message legacy (v3.0 activo)');
                    return;
                }
                console.log('📨 Nuevo mensaje recibido:', data);
                handleNewMessage(data);
            });

            // Evento: Usuario en línea
            socket.on('user_online', function(data) {
                console.log('✅ Usuario en línea:', data.user_id);
                updateUserPresenceUI(data.user_id, true);
            });

            // Evento: Usuario fuera de línea
            socket.on('user_offline', function(data) {
                console.log('❌ Usuario fuera de línea:', data.user_id);
                updateUserPresenceUI(data.user_id, false);
            });

            // Evento: Cambio de presencia (nuevo formato unificado)
            socket.on('user_presence', function(data) {
                console.log('👤 Presencia:', data.user_id, data.online ? 'online' : 'offline');
                updateUserPresenceUI(data.user_id, data.online);
            });

            // Evento: Usuario escribiendo
            socket.on('user_typing', function(data) {
                if (data.conversation_id == currentConversationId) {
                    showTypingIndicator(data.user_id, data.is_typing);
                }
            });

            // Evento: Mensajes leídos
            socket.on('messages_read', function(data) {
                console.log('✓✓ Mensajes leídos en conversación:', data.conversation_id);
                if (data.conversation_id == currentConversationId) {
                    updateAllMessagesToRead();
                }
            });

            // Evento: Mensaje entregado
            socket.on('message_delivered', function(data) {
                console.log('✓ Mensaje entregado:', data.message_id);
                updateMessageToDelivered(data.message_id);
            });

            // Evento: Reacción agregada
            socket.on('reaction_added', function(data) {
                console.log('😀 Reacción agregada:', data);
                actualizarReaccionEnMensaje(data.message_id, data.emoji, data.user_id, true);
            });

            // Evento: Reacción eliminada
            socket.on('reaction_removed', function(data) {
                console.log('😶 Reacción eliminada:', data);
                actualizarReaccionEnMensaje(data.message_id, null, data.user_id, false);
            });

            console.log('🔌 Socket.IO legacy inicializado');
        } catch (error) {
            console.error('❌ Error inicializando Socket.IO:', error);
        }
    }

