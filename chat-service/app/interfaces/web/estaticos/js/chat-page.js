/* Chat institucional - JS extraido de chat/index.html (2026-06-12) */
/* current_user.id llega por window.CHAT_USER_ID (definido inline en la plantilla) */
    // ============================================
    // MAQUITA MEET - VIDEOLLAMADAS DESDE CHAT PRINCIPAL
    // ============================================

    // Variables para guardar info del usuario del chat actual
    let currentChatTrabajadorId = null;
    let currentChatUserType = 'trabajador';  // 'trabajador' o 'admin'

    // Función para iniciar llamada desde el chat principal
    // Soporta tanto trabajadores como usuarios admin/externos
    async function iniciarLlamadaDesdeChat(tipo) {
        if (!currentConversationId) {
            alert('Por favor selecciona un chat primero');
            return;
        }

        // Si es grupo, usar conferencia
        if (currentConversationType === 'group') {
            iniciarConferenciaDesdeChat();
            return;
        }

        var userId = currentChatTrabajadorId;
        if (!userId) {
            alert('No se pudo identificar al usuario destino');
            return;
        }

        // Usar el motor de llamadas (ventana dedicada, definido en base.html)
        if (typeof iniciarLlamadaWebRTC === 'function') {
            var convLlamada = conversations.find(c => c.id === currentConversationId);
            var nombreDest = convLlamada ? (convLlamada.name ||
                (convLlamada.other_user ? convLlamada.other_user.name : null)) : null;
            await iniciarLlamadaWebRTC(String(userId), String(userId), tipo, nombreDest, currentConversationId);
        } else {
            alert('Sistema de llamadas no disponible. Recargue la pagina.');
        }
    }

    // Iniciar conferencia de audio desde un chat grupal
    async function iniciarConferenciaDesdeChat() {
        if (!currentConversationId || currentConversationType !== 'group') {
            alert('Solo disponible en chats grupales');
            return;
        }

        const conv = conversations.find(c => c.id === currentConversationId);
        if (!conv) return;

        // Obtener participantes del grupo via API
        try {
            const resp = await fetch('/api/chat/conversations/' + currentConversationId);
            const data = await resp.json();
            const convData = data.conversacion || data.conversation || {};
            const participantes = convData.participantes || [];
            const myId = window.CHAT_USER_ID;

            const participants = participantes
                .filter(p => {
                    const pid = p.usuario_id || p.id;
                    return pid && pid != myId;
                })
                .map(p => ({
                    id: p.usuario_id || p.id,
                    name: p.nombre || p.name || 'Usuario'
                }));

            if (participants.length === 0) {
                alert('No hay otros participantes en este grupo');
                return;
            }

            if (participants.length > 49) {
                alert('La conferencia soporta maximo 50 participantes.');
                return;
            }

            const groupName = conv.name || conv.nombre || 'Grupo';
            if (typeof iniciarConferenciaGrupal === 'function') {
                iniciarConferenciaGrupal(currentConversationId, participants, groupName);
            } else {
                alert('Sistema de conferencias no disponible. Recargue la pagina.');
            }
        } catch (e) {
            console.error('Error obteniendo participantes:', e);
            alert('Error al obtener participantes del grupo');
        }
    }

    // Abrir Maquita Meet sin llamar a alguien específico
    async function abrirMaquitaMeetDesdeChat() {
        try {
            const response = await fetch('/api/chat/meet/token', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({})
            });

            const data = await response.json();
            if (data.success) {
                window.open(data.url, '_blank');
            }
        } catch (error) {
            console.error('Error:', error);
        }
    }

    // Enviar mensaje rápido (para enlaces de llamada)
    async function enviarMensajeRapido(contenido) {
        if (!currentConversationId) return;

        try {
            await fetch('/api/chat/send-message', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    conversation_id: currentConversationId,
                    content: contenido
                })
            });
            // Recargar mensajes
            loadMessages(currentConversationId);
        } catch (error) {
            console.error('Error enviando mensaje:', error);
        }
    }

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
            status: data.status
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
    function updateMessageStatus(messageId, status) {
        const element = document.querySelector(`[data-message-id="${messageId}"]`);
        if (element) {
            element.classList.remove('message-pending', 'message-sending', 'message-sent', 'message-delivered', 'message-read', 'message-failed');
            element.classList.add(`message-${status}`);

            // Actualizar icono de estado
            const statusIcon = element.querySelector('.message-status');
            if (statusIcon) {
                switch(status) {
                    case 'pending': statusIcon.innerHTML = '⏳'; break;
                    case 'sending': statusIcon.innerHTML = '↑'; break;
                    case 'sent': statusIcon.innerHTML = '✓'; break;
                    case 'delivered': statusIcon.innerHTML = '✓✓'; break;
                    case 'read': statusIcon.innerHTML = '<span style="color:#34b7f1">✓✓</span>'; break;
                    case 'failed': statusIcon.innerHTML = '❌'; break;
                }
            }
        }
    }

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

    // ============================================
    // HISTORIAL DE LLAMADAS (tabla chat_llamadas)
    // ============================================
    async function abrirHistorialLlamadas() {
        let ov = document.getElementById('histLlamadasOverlay');
        if (ov) ov.remove();
        ov = document.createElement('div');
        ov.id = 'histLlamadasOverlay';
        ov.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:99990;display:flex;align-items:center;justify-content:center;';
        ov.addEventListener('click', (e) => { if (e.target === ov) ov.remove(); });
        ov.innerHTML = `
            <div style="background:var(--bg-color,#fff);color:var(--text-color,#222);width:min(560px,92vw);max-height:80vh;border-radius:14px;display:flex;flex-direction:column;box-shadow:0 12px 40px rgba(0,0,0,.35);overflow:hidden;">
                <div style="display:flex;align-items:center;justify-content:space-between;padding:14px 18px;border-bottom:1px solid rgba(0,0,0,.08);">
                    <div class="btn-group btn-group-sm">
                        <button id="tabLlamadas" class="btn btn-primary" onclick="cambiarTabHistorial('llamadas')"><i class="fas fa-phone me-1"></i>Llamadas</button>
                        <button id="tabGrabaciones" class="btn btn-light" onclick="cambiarTabHistorial('grabaciones')"><i class="fas fa-video me-1"></i>Grabaciones</button>
                    </div>
                    <button class="btn btn-sm btn-light" onclick="document.getElementById('histLlamadasOverlay').remove()"><i class="fas fa-times"></i></button>
                </div>
                <div id="histLlamadasLista" style="overflow-y:auto;padding:6px 0;">
                    <div class="text-center text-muted py-4"><div class="spinner-border spinner-border-sm"></div> Cargando…</div>
                </div>
            </div>`;
        document.body.appendChild(ov);

        try {
            const resp = await fetch('/api/chat/llamadas/historial?limit=80', { credentials: 'same-origin' });
            const data = await resp.json();
            renderHistorialLlamadas(data.llamadas || []);
        } catch (e) {
            document.getElementById('histLlamadasLista').innerHTML =
                '<div class="text-center text-muted py-4">No se pudo cargar el historial</div>';
        }
    }

    function renderHistorialLlamadas(llamadas) {
        const cont = document.getElementById('histLlamadasLista');
        if (!cont) return;
        if (!llamadas.length) {
            cont.innerHTML = '<div class="text-center text-muted py-4">Aún no hay llamadas registradas</div>';
            return;
        }
        cont.innerHTML = llamadas.map(l => {
            const esConf = l.tipo === 'conferencia';
            const icono = esConf ? 'fa-users' : (l.tipo === 'video' ? 'fa-video' : 'fa-phone');
            const flecha = l.direccion === 'saliente'
                ? '<i class="fas fa-arrow-up" style="transform:rotate(45deg);color:#28a745;"></i>'
                : '<i class="fas fa-arrow-down" style="transform:rotate(45deg);color:' + (l.perdida ? '#ef4444' : '#0061a1') + ';"></i>';
            let estado = '';
            if (l.estado === 'completada') {
                const m = String(Math.floor(l.duracion_segundos / 60)).padStart(2, '0');
                const sg = String(l.duracion_segundos % 60).padStart(2, '0');
                estado = m + ':' + sg;
            } else if (l.perdida) {
                estado = '<span style="color:#ef4444;font-weight:600;">Perdida</span>';
            } else {
                estado = l.estado === 'rechazada' ? 'No disponible' : 'Sin respuesta';
            }
            const f = l.creado_en ? new Date(l.creado_en) : null;
            const fecha = f ? f.toLocaleDateString('es-EC', { day: '2-digit', month: 'short' }) + ' ' +
                f.toLocaleTimeString('es-EC', { hour: '2-digit', minute: '2-digit' }) : '';
            const nombre = esConf ? 'Conferencia grupal' : (l.otro && l.otro.nombre ? l.otro.nombre : 'Usuario');
            const puedeLlamar = !esConf && l.otro && l.otro.id;
            const botones = puedeLlamar ? `
                <button class="btn btn-sm btn-light" title="Llamar" onclick="llamarDesdeHistorial(${l.otro.id}, '${(nombre || '').replace(/'/g, "\\'")}', 'audio')"><i class="fas fa-phone" style="color:#28a745;"></i></button>
                <button class="btn btn-sm btn-light" title="Videollamada" onclick="llamarDesdeHistorial(${l.otro.id}, '${(nombre || '').replace(/'/g, "\\'")}', 'video')"><i class="fas fa-video" style="color:#0061a1;"></i></button>` : '';
            return `
                <div style="display:flex;align-items:center;gap:12px;padding:9px 18px;border-bottom:1px solid rgba(0,0,0,.05);">
                    <div style="width:22px;text-align:center;">${flecha}</div>
                    <div style="width:24px;text-align:center;"><i class="fas ${icono}" style="opacity:.6;"></i></div>
                    <div style="flex:1;min-width:0;">
                        <div style="font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;${l.perdida ? 'color:#ef4444;' : ''}">${nombre}</div>
                        <div class="small text-muted">${estado} · ${fecha}</div>
                    </div>
                    ${botones}
                </div>`;
        }).join('');
    }

    function cambiarTabHistorial(tab) {
        document.getElementById('tabLlamadas').className = tab === 'llamadas' ? 'btn btn-primary' : 'btn btn-light';
        document.getElementById('tabGrabaciones').className = tab === 'grabaciones' ? 'btn btn-primary' : 'btn btn-light';
        const lista = document.getElementById('histLlamadasLista');
        lista.innerHTML = '<div class="text-center text-muted py-4"><div class="spinner-border spinner-border-sm"></div> Cargando...</div>';
        if (tab === 'llamadas') {
            fetch('/api/chat/llamadas/historial?limit=80', { credentials: 'same-origin' })
                .then(r => r.json()).then(d => renderHistorialLlamadas(d.llamadas || []))
                .catch(() => lista.innerHTML = '<div class="text-center text-muted py-4">Error</div>');
        } else {
            fetch('/api/chat/grabacion/listar', { credentials: 'same-origin' })
                .then(r => r.json()).then(d => renderGrabaciones(d.grabaciones || []))
                .catch(() => lista.innerHTML = '<div class="text-center text-muted py-4">Error</div>');
        }
    }

    function renderGrabaciones(grabs) {
        const cont = document.getElementById('histLlamadasLista');
        if (!grabs.length) { cont.innerHTML = '<div class="text-center text-muted py-4">Aun no hay grabaciones</div>'; return; }
        cont.innerHTML = grabs.map(function(gr) {
            const icono = gr.es_conferencia ? 'fa-users' : 'fa-video';
            const f = gr.creado_en ? new Date(gr.creado_en) : null;
            const fecha = f ? f.toLocaleDateString('es-EC', {day:'2-digit',month:'short'}) + ' ' + f.toLocaleTimeString('es-EC', {hour:'2-digit',minute:'2-digit'}) : '';
            const nombre = gr.es_conferencia ? 'Conferencia' : 'Llamada';
            const listo = gr.estado === 'completada';
            const accion = listo
                ? '<a class="btn btn-sm btn-light" href="/api/chat/grabacion/descargar/' + gr.id + '" title="Descargar"><i class="fas fa-download" style="color:#0061a1;"></i></a>'
                : '<span class="badge bg-danger">grabando</span>';
            return '<div style="display:flex;align-items:center;gap:12px;padding:9px 18px;border-bottom:1px solid rgba(0,0,0,.05);">' +
                '<div style="width:24px;text-align:center;"><i class="fas ' + icono + '" style="opacity:.6;"></i></div>' +
                '<div style="flex:1;min-width:0;"><div style="font-weight:600;">' + nombre + '</div>' +
                '<div class="small text-muted">' + fecha + '</div></div>' + accion + '</div>';
        }).join('');
    }

    function llamarDesdeHistorial(userId, nombre, tipo) {
        const ov = document.getElementById('histLlamadasOverlay');
        if (ov) ov.remove();
        if (typeof iniciarLlamadaWebRTC === 'function') {
            iniciarLlamadaWebRTC(String(userId), String(userId), tipo, nombre, '');
        }
    }

    // Set global para rastrear mensajes ya mostrados (evita duplicados)
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

    // ============================================
    // VARIABLES GLOBALES
    // ============================================
    let currentConversationId = null;
    let currentConversationType = null;
    let conversations = [];
    let currentTab = 'all';
    let typingTimeout = null;
    let messagePollingInterval = null;
    let newChatModal = null;
    let editMessageModal = null;
    let deleteMessageModal = null;
    let selectedMessageId = null;
    let selectedMessageContent = null;
    let chatInfoModal = null;

    // Usuario actual para reacciones y mensajes
    const currentUserId = window.CHAT_USER_ID;

    // ============================================
    // SONIDO DE NOTIFICACIÓN (MEJORADO)
    // ============================================
    let notificationSound = null;
    let originalTitle = document.title;
    let unreadNotifications = 0;
    let soundEnabled = true;  // Control de sonido
    let lastSoundTime = 0;    // Anti-spam de sonido

    function initNotificationSound() {
        try {
            notificationSound = new Audio('/static/sounds/notification.mp3');
            notificationSound.volume = 0.7;
            notificationSound.preload = 'auto';

            // Precargar el audio
            notificationSound.load();

            // Verificar que el audio se puede reproducir
            notificationSound.addEventListener('canplaythrough', () => {
                console.log('🔊 Sonido de notificación precargado correctamente');
            });

            notificationSound.addEventListener('error', (e) => {
                console.error('❌ Error cargando sonido:', e);
                soundEnabled = false;
            });

            // Habilitar sonido con la primera interacción del usuario
            const enableSoundOnInteraction = () => {
                if (notificationSound) {
                    // Reproducir silenciosamente para desbloquear el audio
                    const originalVolume = notificationSound.volume;
                    notificationSound.volume = 0;
                    notificationSound.play().then(() => {
                        notificationSound.pause();
                        notificationSound.currentTime = 0;
                        notificationSound.volume = originalVolume;
                        console.log('🔊 Audio desbloqueado por interacción del usuario');
                    }).catch(() => {});
                }
                document.removeEventListener('click', enableSoundOnInteraction);
                document.removeEventListener('keydown', enableSoundOnInteraction);
            };

            document.addEventListener('click', enableSoundOnInteraction);
            document.addEventListener('keydown', enableSoundOnInteraction);

        } catch (e) {
            console.error('Error inicializando sonido:', e);
            soundEnabled = false;
        }
    }

    function playNotificationSound() {
        // Anti-spam: no reproducir más de 1 vez por segundo
        const now = Date.now();
        if (now - lastSoundTime < 1000) {
            console.log('🔇 Sonido omitido (anti-spam)');
            return;
        }
        lastSoundTime = now;

        // Reproducir sonido
        if (notificationSound && soundEnabled) {
            try {
                // Clonar el audio para permitir múltiples reproducciones
                const soundClone = notificationSound.cloneNode();
                soundClone.volume = 0.7;
                soundClone.play().then(() => {
                    console.log('🔔 Sonido de notificación reproducido');
                }).catch(err => {
                    console.log('No se pudo reproducir sonido:', err.message);
                });
            } catch (e) {
                console.error('Error reproduciendo sonido:', e);
            }
        }

        // Actualizar título de la página para mostrar mensajes nuevos
        unreadNotifications++;
        document.title = `(${unreadNotifications}) Nuevo mensaje - Chat`;

        // Mostrar notificación del navegador si está permitido
        showBrowserNotification();

        // Restaurar título cuando el usuario vuelva a la pestaña
        if (!document.hasFocus()) {
            const restoreTitle = () => {
                unreadNotifications = 0;
                document.title = originalTitle;
                window.removeEventListener('focus', restoreTitle);
            };
            window.addEventListener('focus', restoreTitle);
        } else {
            // Si ya tiene foco, restaurar después de 3 segundos
            setTimeout(() => {
                unreadNotifications = 0;
                document.title = originalTitle;
            }, 3000);
        }
    }

    // Notificaciones del navegador
    function showBrowserNotification() {
        if (!('Notification' in window)) return;

        if (Notification.permission === 'granted') {
            new Notification('Nuevo mensaje', {
                body: 'Tienes un nuevo mensaje en el chat',
                icon: '/static/images/logo-maquita-icon.png',
                tag: 'chat-notification',
                silent: true  // El sonido ya lo manejamos nosotros
            });
        } else if (Notification.permission !== 'denied') {
            Notification.requestPermission();
        }
    }

    // Solicitar permisos de notificación al cargar
    if ('Notification' in window && Notification.permission === 'default') {
        // No solicitar inmediatamente, esperar interacción
        document.addEventListener('click', function requestNotifPermission() {
            Notification.requestPermission();
            document.removeEventListener('click', requestNotifPermission);
        }, { once: true });
    }

    // ============================================
    // INICIALIZACIÓN
    // ============================================
    document.addEventListener('DOMContentLoaded', function() {
        newChatModal = new bootstrap.Modal(document.getElementById('newChatModal'));
        chatInfoModal = new bootstrap.Modal(document.getElementById('chatInfoModal'));
        editMessageModal = new bootstrap.Modal(document.getElementById('editMessageModal'));
        deleteMessageModal = new bootstrap.Modal(document.getElementById('deleteMessageModal'));

        // Inicializar sonido de notificación
        initNotificationSound();

        // ✅ INICIALIZAR SOCKET.IO PARA TIEMPO REAL
        initSocket();

        // ⚡⚡⚡ INICIALIZAR CHAT ULTRA-RÁPIDO v3.0 (WebSocket puro)
        initChatUltraFast();

        loadConversations();

        // ⚡⚡⚡ POLLING como fallback temporal
        // Esperar 10 segundos antes de activar polling (dar tiempo al WebSocket)
        setTimeout(() => {
            if (!chatUltraFast || !chatUltraFast.connected) {
                console.log('⚠️ v3.0 aún no conectó - activando polling temporal');
                startFallbackPolling();
                // Cuando WebSocket conecte, polling se detendrá automáticamente (ver onConnect handler)
            } else {
                console.log('⚡ v3.0 conectado - polling DESACTIVADO permanentemente');
            }
        }, 10000);

        // Actualizar presencia del usuario actual cada 2 minutos
        updateUserPresence();
        setInterval(updateUserPresence, 120000); // 2 minutos

        // Actualizar estado de presencia de otros usuarios cada 30 segundos
        setInterval(updateOtherUsersPresence, 30000); // 30 segundos

        // Habilitar/deshabilitar botón de enviar
        document.getElementById('messageInput').addEventListener('input', function() {
            document.getElementById('btnSendMessage').disabled = !this.value.trim();
        });

        // Inicializar emojis
        initializeEmojis();

        // Cerrar pickers al hacer click fuera
        document.addEventListener('click', function(e) {
            const emojiPicker = document.getElementById('emojiPicker');
            const gifPicker = document.getElementById('gifPicker');
            const emojiBtn = document.querySelector('.emoji-btn');
            const gifBtn = document.querySelector('.gif-btn');

            // Cerrar emoji picker si click fuera
            if (emojiPicker && !emojiPicker.contains(e.target) && !emojiBtn.contains(e.target)) {
                emojiPicker.style.display = 'none';
                emojiBtn.classList.remove('active');
            }

            // Cerrar gif picker si click fuera
            if (gifPicker && !gifPicker.contains(e.target) && !gifBtn.contains(e.target)) {
                gifPicker.style.display = 'none';
                gifBtn.classList.remove('active');
            }
        });

        // Event listener para pegar imágenes con Ctrl+V
        document.getElementById('messageInput').addEventListener('paste', async function(e) {
            const items = e.clipboardData?.items;
            if (!items) return;

            for (let item of items) {
                if (item.type.indexOf('image') !== -1) {
                    e.preventDefault();

                    const file = item.getAsFile();
                    if (file) {
                        console.log('Imagen pegada en chat principal:', file.name, file.type, file.size);

                        // Verificar que hay una conversación abierta
                        if (!currentConversationId) {
                            toastr.warning('Por favor selecciona una conversación primero');
                            return;
                        }

                        // Enviar la imagen
                        await uploadAndSendFile(file, 'image');
                    }
                    break;
                }
            }
        });

        // Cerrar menú contextual al hacer clic fuera
        document.addEventListener('click', function(e) {
            const menu = document.getElementById('messageOptionsMenu');
            if (menu && !e.target.closest('.message-actions') && !e.target.closest('.message-options-menu')) {
                menu.classList.remove('show');
            }
        });
    });

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

    // ============================================
    // ABRIR CONVERSACIÓN
    // ============================================
    // Formatea "ultima vez" estilo WhatsApp
    function formatUltimaVez(lastSeen) {
        if (!lastSeen) return 'Desconectado';
        var d = new Date(lastSeen);
        if (isNaN(d.getTime())) return 'Desconectado';
        var ahora = new Date();
        var hora = d.toLocaleTimeString('es-EC', { hour: '2-digit', minute: '2-digit' });
        var hoy = ahora.toDateString() === d.toDateString();
        var ayer = new Date(ahora); ayer.setDate(ahora.getDate() - 1);
        var esAyer = ayer.toDateString() === d.toDateString();
        if (hoy) return 'Últ. vez hoy a las ' + hora;
        if (esAyer) return 'Últ. vez ayer a las ' + hora;
        return 'Últ. vez ' + d.toLocaleDateString('es-EC', { day: '2-digit', month: 'short' }) + ' a las ' + hora;
    }
    window.formatUltimaVez = formatUltimaVez;

    async function openConversation(conversationId, conversationType) {
        console.log('🔓 openConversation - conversationId:', conversationId, 'type:', conversationType);
        currentConversationId = conversationId;
        currentConversationType = conversationType;

        // Mostrar área de chat
        document.getElementById('chatEmptyState').style.display = 'none';
        document.getElementById('chatActiveArea').style.display = 'flex';

        // Movil: ocultar la lista y mostrar el chat a pantalla completa
        if (window.innerWidth <= 768) {
            var _cc = document.querySelector('.chat-container');
            if (_cc) _cc.classList.add('mobile-chat-open');
        }

        // Marcar como activa en la lista
        document.querySelectorAll('.conversation-item').forEach(item => {
            item.classList.remove('active');
        });
        event?.target?.closest('.conversation-item')?.classList.add('active');

        // Actualizar header
        const conv = conversations.find(c => c.id === conversationId);
        if (conv) {
            // Guardar info del otro usuario para llamadas
            currentChatTrabajadorId = conv.other_user ? conv.other_user.id : null;
            currentChatUserType = conv.other_user?.user_type || 'trabajador';  // Tipo de usuario
            console.log('📞 Usuario del chat actual:', currentChatTrabajadorId, 'tipo:', currentChatUserType);

            // Mostrar/ocultar botones segun tipo de conversacion
            const isGroup = conversationType === 'group';
            const btnAudio = document.getElementById('btnLlamadaAudio');
            const btnVideo = document.getElementById('btnLlamadaVideo');
            const btnConf = document.getElementById('btnConferenciaGrupal');
            if (btnConf) btnConf.style.display = isGroup ? '' : 'none';
            if (btnAudio) btnAudio.style.display = isGroup ? 'none' : '';
            if (btnVideo) btnVideo.style.display = isGroup ? 'none' : '';

            // El backend devuelve 'name' y para directos también 'other_user.name'
            const displayName = conv.name || (conv.other_user ? conv.other_user.name : 'Usuario');

            const headerNameEl = document.getElementById('chatHeaderName');
            const headerInitialsEl = document.getElementById('chatHeaderInitials');
            const headerAvatarEl = document.getElementById('chatHeaderAvatar');

            if (headerNameEl) headerNameEl.textContent = (conversationType !== 'group' ? nombreCorto(displayName) : displayName);

            const initials = getInitials(displayName);
            if (headerInitialsEl) headerInitialsEl.textContent = initials;

            // El backend devuelve 'avatar' y para directos 'other_user.photo'
            const avatarUrl = conv.avatar || (conv.other_user ? conv.other_user.photo : null);
            if (headerAvatarEl) {
                if (avatarUrl) {
                    headerAvatarEl.innerHTML =
                        `<img src="${avatarUrl}" alt="${displayName}" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';"><span class="avatar-initials" style="display:none;">${initials}</span>`;
                } else {
                    headerAvatarEl.innerHTML =
                        `<span class="avatar-initials">${initials}</span>`;
                }
            }

            // Estado EN LINEA / DESCONECTADO en la cabecera (como Teams/WhatsApp Web)
            const headerStatusEl = document.getElementById('chatHeaderStatus');
            if (headerStatusEl) {
                if (conversationType !== 'group' && conv.other_user) {
                    const online = !!conv.other_user.online;
                    headerStatusEl.className = online ? 'status-online' : 'status-offline';
                    const txtEstado = online ? 'En línea' : formatUltimaVez(conv.other_user.last_seen);
                    headerStatusEl.innerHTML = (online ? '<i class="fas fa-circle me-1" style="font-size:.5rem;"></i>' : '') +
                        '<span>' + txtEstado + '</span>';
                    headerStatusEl.style.display = '';
                    window._chatOtroUserId = conv.other_user.id;
                    window._chatOtroLastSeen = conv.other_user.last_seen;
                } else {
                    headerStatusEl.style.display = 'none';
                }
            }
        }

        // Cargar mensajes
        console.log('🔓 openConversation - Iniciando loadMessages...');
        await loadMessages(conversationId);
        console.log('🔓 openConversation - loadMessages completado');
        console.log('🔓 openConversation - chatMessages innerHTML length:', document.getElementById('chatMessages')?.innerHTML.length);

        // ✅ UNIRSE A LA SALA DE SOCKET.IO PARA TIEMPO REAL
        // Siempre intentar unirse - si no está conectado, se unirá cuando conecte
        if (chatUltraFast) {
            if (chatUltraFast.connected) {
                chatUltraFast.join(conversationId);
                console.log(`⚡ Unido a sala de conversación ${conversationId} via v3.0`);
            } else {
                console.log(`⏳ WebSocket pendiente - se unirá a sala ${conversationId} cuando conecte`);
                // Guardar para unirse cuando conecte
                window._pendingJoinConversation = conversationId;
            }
        }
        // Fallback a socket legacy si chatUltraFast no existe
        if (socket && socketConnected) {
            socket.emit('join_conversation', { conversation_id: conversationId });
            console.log(`🔌 Unido a sala de conversación ${conversationId} via legacy`);
        }

        // Marcar como leídos
        markAsRead(conversationId);

        // Emitir evento de lectura por Socket.IO
        if (socket && socketConnected) {
            socket.emit('message_read', { conversation_id: conversationId });
        }

        // Focus en input
        document.getElementById('messageInput').focus();
    }

    async function loadMessages(conversationId, beforeId = null) {
        try {
            let url = `/api/chat/conversations/${conversationId}/messages`;
            if (beforeId) url += `?before=${beforeId}`;

            console.log('📨 loadMessages - URL:', url);

            const response = await fetch(url);
            const data = await response.json();

            console.log('📨 loadMessages - Response:', data);
            console.log('📨 loadMessages - success:', data.success, 'exito:', data.exito);
            console.log('📨 loadMessages - messages:', data.messages?.length, 'mensajes:', data.mensajes?.length);

            if (data.success || data.exito) {
                const mensajes = data.messages || data.mensajes || [];
                console.log('📨 loadMessages - Renderizando', mensajes.length, 'mensajes');
                console.log('📨 loadMessages - Tipo de mensajes:', typeof mensajes, Array.isArray(mensajes));
                if (mensajes.length > 0) {
                    console.log('📨 loadMessages - Ejemplo mensaje[0]:', JSON.stringify(mensajes[0]));
                }
                renderMessages(mensajes, !beforeId);
            } else {
                console.error('📨 loadMessages - Error en response:', data.mensaje || data.error);
                // Mostrar el error en el contenedor
                const container = document.getElementById('chatMessages');
                if (container) {
                    container.innerHTML = `<div style="color:red;padding:20px;">Error cargando mensajes: ${data.mensaje || data.error}</div>`;
                }
            }
        } catch (error) {
            console.error('Error cargando mensajes:', error);
        }
    }

    function renderMessages(messages, replace = true) {
        const container = document.getElementById('chatMessages');

        console.log('🎨 renderMessages - container:', container);
        console.log('🎨 renderMessages - container existe:', !!container);
        console.log('🎨 renderMessages - container visible:', container ? container.offsetParent !== null : false);
        console.log('🎨 renderMessages - container parent display:', container ? window.getComputedStyle(container.parentElement).display : 'N/A');
        console.log('🎨 renderMessages - chatActiveArea display:', document.getElementById('chatActiveArea')?.style.display);
        console.log('🎨 renderMessages - messages count:', messages.length);
        console.log('🎨 renderMessages - replace:', replace);
        if (messages.length > 0) {
            console.log('🎨 renderMessages - primer mensaje:', JSON.stringify(messages[0]).substring(0, 200));
        }

        // VERIFICACIÓN CRÍTICA: Si no existe el container, salir
        if (!container) {
            console.error('❌ renderMessages - CONTAINER NO ENCONTRADO! El elemento #chatMessages no existe.');
            return;
        }

        if (messages.length === 0 && replace) {
            container.innerHTML = `
                <div class="chat-empty-state">
                    <i class="fas fa-comments" style="font-size: 2rem;"></i>
                    <p class="mt-2">No hay mensajes aún. ¡Envía el primero!</p>
                </div>
            `;
            return;
        }

        // IMPORTANTE: Invertir el orden - los mensajes vienen del más nuevo al más antiguo,
        // pero necesitamos renderizarlos del más antiguo al más nuevo para que
        // el scroll al fondo muestre los mensajes más recientes
        const sortedMessages = [...messages].reverse();

        // Agrupar mensajes por fecha
        const grouped = {};
        sortedMessages.forEach(msg => {
            try {
                const createdAt = msg.created_at || new Date().toISOString();
                const date = new Date(createdAt).toLocaleDateString('es-ES', {
                    weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'
                });
                if (!grouped[date]) grouped[date] = [];
                grouped[date].push(msg);
            } catch (groupErr) {
                console.error('❌ Error agrupando mensaje:', groupErr, msg);
            }
        });

        let html = '';
        // Ordenar las fechas cronológicamente (más antigua primero)
        const sortedDates = Object.keys(grouped).sort((a, b) => {
            return new Date(grouped[a][0].created_at) - new Date(grouped[b][0].created_at);
        });

        for (const date of sortedDates) {
            const msgs = grouped[date];
            html += `<div class="message-date-divider"><span>${date}</span></div>`;
            msgs.forEach(msg => {
                html += renderSingleMessage(msg);
            });
        }

        console.log('🎨 renderMessages - HTML generado, longitud:', html.length);
        console.log('🎨 renderMessages - HTML (primeros 500 chars):', html.substring(0, 500));

        if (replace) {
            console.log('🎨 renderMessages - Reemplazando innerHTML del container');
            console.log('🎨 renderMessages - grouped tiene', Object.keys(grouped).length, 'fechas');

            // Debug: Si no hay contenido generado, mostrar mensaje de prueba
            if (!html || html.trim() === '') {
                console.error('❌ renderMessages - HTML VACÍO! Mostrando debug...');
                container.innerHTML = '<div style="color:red;padding:20px;">DEBUG: HTML vacío generado. Revisa la consola.</div>';
                return;
            }

            container.innerHTML = html;
            console.log('🎨 renderMessages - innerHTML asignado, container.innerHTML.length:', container.innerHTML.length);

            // Verificar que realmente se asignó
            setTimeout(() => {
                console.log('🎨 renderMessages - VERIFICACIÓN POST-RENDER: innerHTML.length =', container.innerHTML.length);
                console.log('🎨 renderMessages - container.children.length =', container.children.length);
            }, 100);

            // Scroll al fondo después de que el DOM se actualice completamente
            scrollToBottom(container);
        } else {
            container.insertAdjacentHTML('afterbegin', html);
        }
    }

    // Función centralizada para scroll al fondo con garantía de render completo
    function scrollToBottom(container, smooth = false) {
        if (!container) container = document.getElementById('chatMessages');
        if (!container) return;

        console.log('📜 scrollToBottom - ANTES: scrollTop=', container.scrollTop, 'scrollHeight=', container.scrollHeight, 'clientHeight=', container.clientHeight);

        // Usar requestAnimationFrame para asegurar que el DOM esté actualizado
        requestAnimationFrame(() => {
            // Segundo frame para garantizar que el layout esté calculado
            requestAnimationFrame(() => {
                console.log('📜 scrollToBottom - EN RAF: scrollTop=', container.scrollTop, 'scrollHeight=', container.scrollHeight);
                if (smooth) {
                    container.scrollTo({
                        top: container.scrollHeight,
                        behavior: 'smooth'
                    });
                } else {
                    container.scrollTop = container.scrollHeight;
                }
                console.log('📜 scrollToBottom - DESPUÉS: scrollTop=', container.scrollTop);
            });
        });
    }

    function renderSingleMessage(msg) {
        try {
        // Debug temporal
        console.log('🔧 renderSingleMessage - msg:', msg);

        // El backend devuelve 'is_own_message' no 'is_own'
        const isSent = msg.is_own_message || msg.is_own || false;
        const messageClass = isSent ? 'sent' : 'received';

        // El backend devuelve sender como objeto: { id, name, photo }
        const senderName = msg.sender ? msg.sender.name : (msg.sender_name || 'Usuario');
        const senderPhoto = msg.sender ? msg.sender.photo : (msg.sender_photo || null);
        const initials = getInitials(senderName);
        const time = formatMessageTime(msg.created_at);

        // Status de lectura con clases mejoradas
        let statusIcon = '';
        if (isSent) {
            if (msg.read_at || msg.is_read || msg.read_by_count > 0) {
                // Doble check azul - LEÍDO
                statusIcon = '<i class="fas fa-check-double message-status read" title="Leído"></i>';
            } else if (msg.delivered_at || msg.delivered_count > 0) {
                // Doble check gris - ENTREGADO
                statusIcon = '<i class="fas fa-check-double message-status delivered" title="Entregado"></i>';
            } else {
                // Un check gris - ENVIADO
                statusIcon = '<i class="fas fa-check message-status sent" title="Enviado"></i>';
            }
        }

        const avatarHtml = !isSent ? `
            <div class="message-avatar" style="background: var(--primary-color, #0061a1);">
                ${senderPhoto ? `<img src="${senderPhoto}" alt="${senderName}" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';"><span class="avatar-initials" style="display:none;">${initials}</span>` : `<span class="avatar-initials">${initials}</span>`}
            </div>
        ` : '';

        const senderHtml = !isSent && currentConversationType === 'group' ?
            `<div class="message-sender">${escapeHtml(senderName)}</div>` : '';

        // Contenido del mensaje (texto, imagen, archivo, gif)
        let contentHtml = '';
        if (msg.message_type === 'text') {
            contentHtml = `<div class="message-text">${escapeHtml(msg.content)}</div>`;
        } else if (msg.message_type === 'gif') {
            // GIF desde Tenor - buscar URL en media o directamente en gif_url
            let gifUrl = null;
            if (msg.media && msg.media.length > 0) {
                gifUrl = msg.media[0].file_path;
            } else if (msg.gif_url) {
                gifUrl = msg.gif_url;
            }

            if (gifUrl) {
                contentHtml = `
                    <div class="message-media message-gif">
                        <img src="${gifUrl}" alt="GIF"
                             style="max-width: 250px; max-height: 200px; border-radius: 8px; cursor: pointer; display: block;"
                             onclick="viewImage('${gifUrl}')"
                             onerror="this.alt='Error al cargar GIF'; this.style.padding='20px';">
                    </div>
                `;
            } else {
                // Sin URL: no mostrar la descripcion como texto
                contentHtml = '';
            }
        } else if (msg.message_type === 'image' && msg.media && msg.media.length > 0) {
            const mediaItem = msg.media[0];
            // Asegurar que la ruta tenga la barra inicial
            const imagePath = mediaItem.file_path.startsWith('/') ? mediaItem.file_path : '/' + mediaItem.file_path;
            contentHtml = `
                <div class="message-media">
                    <img src="${imagePath}" alt="Imagen"
                         style="max-width: 250px; max-height: 250px; border-radius: 8px; cursor: pointer; object-fit: cover; display: block;"
                         onclick="viewImage('${imagePath}')"
                         onerror="console.error('Error cargando imagen:', this.src)">
                </div>
                ${msg.content ? `<div class="message-text mt-1">${escapeHtml(msg.content)}</div>` : ''}
            `;
        } else if ((msg.message_type === 'file' || msg.message_type === 'document') && msg.media && msg.media.length > 0) {
            const mediaItem = msg.media[0];
            // Asegurar que la ruta tenga la barra inicial
            const filePath = mediaItem.file_path.startsWith('/') ? mediaItem.file_path : '/' + mediaItem.file_path;
            contentHtml = `
                <div class="message-file d-flex align-items-center p-2 bg-light rounded">
                    <i class="fas fa-file fa-2x me-2 text-primary"></i>
                    <div>
                        <div class="fw-bold small">${escapeHtml(mediaItem.file_name)}</div>
                        <a href="${filePath}" target="_blank" download class="small">Descargar</a>
                    </div>
                </div>
            `;
        }

        // Menú de opciones solo para mensajes propios
        // Usamos data-content para evitar problemas con comillas en el mensaje
        const escapedContent = (msg.content || '').replace(/'/g, '&#39;').replace(/"/g, '&quot;');
        const messageActions = isSent && !msg.is_deleted ? `
            <div class="message-actions">
                <button class="btn-message-action" data-msg-id="${msg.id}" data-msg-content="${escapedContent}" onclick="showMessageOptions(event, this)">
                    <i class="fas fa-chevron-down"></i>
                </button>
            </div>
        ` : '';

        // Indicador de editado
        const editedBadge = msg.is_edited ? '<span class="edited-badge">editado</span>' : '';

        // Reacciones al mensaje
        const reactionsHtml = renderMessageReactions(msg);

        return `
            <div class="message ${messageClass}" data-message-id="${msg.id}">
                ${avatarHtml}
                <div class="message-content">
                    ${senderHtml}
                    ${messageActions}
                    ${contentHtml}
                    <div class="message-meta">
                        ${editedBadge} ${time} ${statusIcon}
                    </div>
                    ${reactionsHtml}
                    <button class="btn-add-reaction" onclick="toggleReactionPicker(${msg.id}, event)" title="Reaccionar">
                        <i class="far fa-smile"></i>
                    </button>
                </div>
            </div>
        `;
        } catch (error) {
            console.error('❌ Error en renderSingleMessage:', error, 'msg:', msg);
            return `<div class="message error">Error renderizando mensaje ${msg?.id}</div>`;
        }
    }

    // ============================================
    // REACCIONES A MENSAJES
    // ============================================

    function renderMessageReactions(msg) {
        // Manejar reactions como objeto, array o null/undefined
        let reactions = msg.reactions;

        // Si no hay reacciones, retornar vacío
        if (!reactions) {
            return '';
        }

        // Si es un objeto (no array), convertirlo a array
        if (!Array.isArray(reactions)) {
            // Si es un objeto vacío, retornar vacío
            if (typeof reactions === 'object' && Object.keys(reactions).length === 0) {
                return '';
            }
            // Convertir objeto a array de reacciones
            reactions = Object.entries(reactions).map(([emoji, data]) => ({
                emoji: emoji,
                count: data.count || 1,
                user_ids: data.user_ids || []
            }));
        }

        // Si el array está vacío, retornar vacío
        if (reactions.length === 0) {
            return '';
        }

        const reactionsHtml = reactions.map(reaction => {
            const isMyReaction = reaction.user_ids && reaction.user_ids.includes(currentUserId);
            const activeClass = isMyReaction ? 'my-reaction' : '';
            return `
                <div class="message-reaction ${activeClass}"
                     onclick="handleReactionClick(${msg.id}, '${reaction.emoji}')"
                     title="${reaction.count} ${reaction.count === 1 ? 'persona' : 'personas'}">
                    <span class="reaction-emoji">${reaction.emoji}</span>
                    <span class="reaction-count">${reaction.count}</span>
                </div>
            `;
        }).join('');

        return `<div class="message-reactions">${reactionsHtml}</div>`;
    }

    async function toggleReactionPicker(messageId, event) {
        event.stopPropagation();

        // Crear picker si no existe
        let picker = document.getElementById(`reaction-picker-${messageId}`);
        if (!picker) {
            picker = document.createElement('div');
            picker.id = `reaction-picker-${messageId}`;
            picker.className = 'reaction-picker';
            picker.innerHTML = `
                <div class="reaction-emoji-list">
                    ${['❤️', '👍', '😂', '😮', '😢', '😡', '🙏', '🎉'].map(emoji =>
                        `<div class="reaction-emoji-item" onclick="addReaction(${messageId}, '${emoji}')">${emoji}</div>`
                    ).join('')}
                </div>
            `;

            const messageDiv = event.currentTarget.closest('.message');
            messageDiv.appendChild(picker);

            // Cerrar al hacer click fuera
            setTimeout(() => {
                document.addEventListener('click', function closePickerHandler(e) {
                    if (!picker.contains(e.target) && e.target !== event.currentTarget) {
                        picker.remove();
                        document.removeEventListener('click', closePickerHandler);
                    }
                });
            }, 100);
        } else {
            picker.remove();
        }
    }

    async function addReaction(messageId, emoji) {
        try {
            console.log('Agregando reacción:', messageId, emoji);

            const response = await fetch(`/api/chat/messages/${messageId}/reactions`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ emoji })
            });

            const result = await response.json();

            if (result.success) {
                console.log('Reacción agregada exitosamente');
                // Cerrar el picker
                const picker = document.getElementById(`reaction-picker-${messageId}`);
                if (picker) picker.remove();

                // Actualizar inmediatamente la UI (no esperar Socket.IO)
                actualizarReaccionEnMensaje(messageId, emoji, currentUserId, true);
            } else {
                console.error('Error agregando reacción:', result.error || result.mensaje);
                alert('Error al agregar reacción: ' + (result.error || result.mensaje || 'Error desconocido'));
            }
        } catch (error) {
            console.error('Error en addReaction:', error);
            alert('Error de conexión al agregar reacción');
        }
    }

    async function handleReactionClick(messageId, emoji) {
        try {
            // Verificar si ya tengo esta reacción
            const messageDiv = document.querySelector(`.message[data-message-id="${messageId}"]`);
            if (!messageDiv) return;

            const reactionDiv = Array.from(messageDiv.querySelectorAll('.message-reaction'))
                .find(r => r.textContent.includes(emoji));

            const isMyReaction = reactionDiv && reactionDiv.classList.contains('my-reaction');

            if (isMyReaction) {
                // Eliminar mi reacción
                const response = await fetch(`/api/chat/messages/${messageId}/reactions`, {
                    method: 'DELETE'
                });

                const result = await response.json();
                if (result.success) {
                    console.log('Reacción eliminada exitosamente');
                    // Actualizar inmediatamente la UI
                    actualizarReaccionEnMensaje(messageId, emoji, currentUserId, false);
                }
            } else {
                // Agregar reacción
                await addReaction(messageId, emoji);
            }
        } catch (error) {
            console.error('Error en handleReactionClick:', error);
        }
    }

    /**
     * Actualiza las reacciones de un mensaje en la UI.
     * Se usa tanto para actualizaciones locales como vía Socket.IO.
     * Ahora actualiza SOLO el mensaje afectado sin recargar todos.
     */
    async function actualizarReaccionEnMensaje(messageId, emoji, userId, agregar) {
        const messageDiv = document.querySelector(`.message[data-message-id="${messageId}"]`);
        if (!messageDiv) {
            console.log('💜 Mensaje no encontrado en DOM:', messageId);
            return;
        }

        console.log('💜 Actualizando reacciones del mensaje:', messageId);

        try {
            // Obtener las reacciones actualizadas del servidor
            const response = await fetch(`/api/chat/messages/${messageId}/reactions`);
            const data = await response.json();

            if (data.success && data.reactions) {
                // Buscar el contenedor de reacciones actual
                let reactionsContainer = messageDiv.querySelector('.message-reactions');

                // Si hay reacciones, crear/actualizar el contenedor
                if (data.reactions.length > 0) {
                    const reactionsHtml = data.reactions.map(reaction => {
                        const isMyReaction = reaction.user_ids && reaction.user_ids.includes(currentUserId);
                        const activeClass = isMyReaction ? 'my-reaction' : '';
                        return `
                            <div class="message-reaction ${activeClass}"
                                 onclick="handleReactionClick(${messageId}, '${reaction.emoji}')"
                                 title="${reaction.count} ${reaction.count === 1 ? 'persona' : 'personas'}">
                                ${reaction.emoji} ${reaction.count}
                            </div>
                        `;
                    }).join('');

                    if (reactionsContainer) {
                        // Actualizar contenedor existente
                        reactionsContainer.innerHTML = reactionsHtml;
                    } else {
                        // Crear nuevo contenedor - insertarlo después del contenido del mensaje
                        const messageContent = messageDiv.querySelector('.message-content');
                        if (messageContent) {
                            const newContainer = document.createElement('div');
                            newContainer.className = 'message-reactions';
                            newContainer.innerHTML = reactionsHtml;
                            messageContent.insertAdjacentElement('afterend', newContainer);
                        }
                    }
                } else if (reactionsContainer) {
                    // Si no hay reacciones, eliminar el contenedor
                    reactionsContainer.remove();
                }
            }
        } catch (error) {
            console.error('Error actualizando reacciones:', error);
        }
    }

    async function loadMessageReactions(messageId) {
        try {
            const response = await fetch(`/api/chat/messages/${messageId}/reactions`);
            const result = await response.json();

            if (result.success && result.reactions) {
                return result.reactions;
            }
            return [];
        } catch (error) {
            console.error('Error cargando reacciones:', error);
            return [];
        }
    }

    // ============================================
    // EMOJI PICKER - SELECTOR DE EMOJIS
    // ============================================

    const emojiData = {
        smileys: ['😀', '😃', '😄', '😁', '😆', '😅', '🤣', '😂', '🙂', '🙃', '😉', '😊', '😇', '🥰', '😍', '🤩', '😘', '😗', '😚', '😙', '🥲', '😋', '😛', '😜', '🤪', '😝', '🤑', '🤗', '🤭', '🤫', '🤔', '🤐', '🤨', '😐', '😑', '😶', '😏', '😒', '🙄', '😬', '🤥', '😌', '😔', '😪', '🤤', '😴', '😷', '🤒', '🤕', '🤢', '🤮', '🤧', '🥵', '🥶', '😶‍🌫️', '🥴', '😵', '😵‍💫', '🤯', '🤠', '🥳', '🥸', '😎', '🤓', '🧐'],
        gestures: ['👋', '🤚', '🖐', '✋', '🖖', '👌', '🤌', '🤏', '✌️', '🤞', '🤟', '🤘', '🤙', '👈', '👉', '👆', '🖕', '👇', '☝️', '👍', '👎', '✊', '👊', '🤛', '🤜', '👏', '🙌', '👐', '🤲', '🤝', '🙏', '✍️', '💅', '🤳', '💪', '🦾', '🦿', '🦵', '🦶', '👂', '🦻', '👃', '🧠', '🦷', '🦴', '👀', '👁️', '👅', '👄'],
        people: ['👤', '👥', '🫂', '👶', '👧', '🧒', '👦', '👩', '🧑', '👨', '👩‍🦱', '🧑‍🦱', '👨‍🦱', '👩‍🦰', '🧑‍🦰', '👨‍🦰', '👱‍♀️', '👱', '👱‍♂️', '👩‍🦳', '🧑‍🦳', '👨‍🦳', '👩‍🦲', '🧑‍🦲', '👨‍🦲', '🧔‍♀️', '🧔', '🧔‍♂️', '👵', '🧓', '👴', '👲', '👳‍♀️', '👳', '👳‍♂️', '🧕', '👮‍♀️', '👮', '👮‍♂️', '👷‍♀️', '👷', '👷‍♂️', '💂‍♀️', '💂', '💂‍♂️', '🕵️‍♀️', '🕵️', '🕵️‍♂️'],
        animals: ['🐶', '🐱', '🐭', '🐹', '🐰', '🦊', '🐻', '🐼', '🐻‍❄️', '🐨', '🐯', '🦁', '🐮', '🐷', '🐽', '🐸', '🐵', '🙈', '🙉', '🙊', '🐒', '🐔', '🐧', '🐦', '🐤', '🐣', '🐥', '🦆', '🦅', '🦉', '🦇', '🐺', '🐗', '🐴', '🦄', '🐝', '🐛', '🦋', '🐌', '🐞', '🐜', '🦟', '🦗', '🕷', '🦂', '🐢', '🐍', '🦎', '🦖', '🦕', '🐙', '🦑', '🦐', '🦞', '🦀', '🐡', '🐠', '🐟', '🐬', '🐳', '🐋', '🦈', '🐊', '🐅', '🐆', '🦓', '🦍', '🦧', '🦣', '🐘', '🦛', '🦏', '🐪', '🐫', '🦒', '🦘', '🦬', '🐃', '🐂', '🐄', '🐎', '🐖', '🐏', '🐑', '🦙', '🐐', '🦌', '🐕', '🐩', '🦮', '🐕‍🦺', '🐈', '🐈‍⬛', '🐓', '🦃', '🦚', '🦜', '🦢', '🦩', '🕊', '🐇', '🦝', '🦨', '🦡', '🦫', '🦦', '🦥', '🐁', '🐀', '🐿', '🦔'],
        food: ['🍇', '🍈', '🍉', '🍊', '🍋', '🍌', '🍍', '🥭', '🍎', '🍏', '🍐', '🍑', '🍒', '🍓', '🫐', '🥝', '🍅', '🫒', '🥥', '🥑', '🍆', '🥔', '🥕', '🌽', '🌶', '🫑', '🥒', '🥬', '🥦', '🧄', '🧅', '🍄', '🥜', '🌰', '🍞', '🥐', '🥖', '🫓', '🥨', '🥯', '🥞', '🧇', '🧀', '🍖', '🍗', '🥩', '🥓', '🍔', '🍟', '🍕', '🌭', '🥪', '🌮', '🌯', '🫔', '🥙', '🧆', '🥚', '🍳', '🥘', '🍲', '🫕', '🥣', '🥗', '🍿', '🧈', '🧂', '🥫', '🍱', '🍘', '🍙', '🍚', '🍛', '🍜', '🍝', '🍠', '🍢', '🍣', '🍤', '🍥', '🥮', '🍡', '🥟', '🥠', '🥡', '🦀', '🦞', '🦐', '🦑', '🦪', '🍦', '🍧', '🍨', '🍩', '🍪', '🎂', '🍰', '🧁', '🥧', '🍫', '🍬', '🍭', '🍮', '🍯', '🍼', '🥛', '☕', '🫖', '🍵', '🍶', '🍾', '🍷', '🍸', '🍹', '🍺', '🍻', '🥂', '🥃', '🥤', '🧋', '🧃', '🧉', '🧊'],
        activities: ['⚽', '🏀', '🏈', '⚾', '🥎', '🎾', '🏐', '🏉', '🥏', '🎱', '🏓', '🏸', '🏒', '🏑', '🥍', '🏏', '🥅', '⛳', '🏹', '🎣', '🤿', '🥊', '🥋', '🎽', '🛹', '🛼', '🛷', '⛸', '🥌', '🎿', '⛷', '🏂', '🪂', '🏋️‍♀️', '🏋️', '🏋️‍♂️', '🤼‍♀️', '🤼', '🤼‍♂️', '🤸‍♀️', '🤸', '🤸‍♂️', '⛹️‍♀️', '⛹️', '⛹️‍♂️', '🤺', '🤾‍♀️', '🤾', '🤾‍♂️', '🏌️‍♀️', '🏌️', '🏌️‍♂️', '🏇', '🧘‍♀️', '🧘', '🧘‍♂️', '🏄‍♀️', '🏄', '🏄‍♂️', '🏊‍♀️', '🏊', '🏊‍♂️', '🤽‍♀️', '🤽', '🤽‍♂️', '🚣‍♀️', '🚣', '🚣‍♂️', '🧗‍♀️', '🧗', '🧗‍♂️', '🚵‍♀️', '🚵', '🚵‍♂️', '🚴‍♀️', '🚴', '🚴‍♂️', '🏆', '🥇', '🥈', '🥉', '🏅', '🎖', '🏵', '🎗', '🎫', '🎟', '🎪', '🤹', '🤹‍♂️', '🤹‍♀️', '🎭', '🩰', '🎨', '🎬', '🎤', '🎧', '🎼', '🎹', '🥁', '🎷', '🎺', '🎸', '🪕', '🎻', '🎲', '♟', '🎯', '🎳', '🎮', '🎰', '🧩'],
        travel: ['🚗', '🚕', '🚙', '🚌', '🚎', '🏎', '🚓', '🚑', '🚒', '🚐', '🛻', '🚚', '🚛', '🚜', '🦯', '🦽', '🦼', '🛴', '🚲', '🛵', '🏍', '🛺', '🚨', '🚔', '🚍', '🚘', '🚖', '🚡', '🚠', '🚟', '🚃', '🚋', '🚞', '🚝', '🚄', '🚅', '🚈', '🚂', '🚆', '🚇', '🚊', '🚉', '✈️', '🛫', '🛬', '🛩', '💺', '🛰', '🚀', '🛸', '🚁', '🛶', '⛵', '🚤', '🛥', '🛳', '⛴', '🚢', '⚓', '⛽', '🚧', '🚦', '🚥', '🚏', '🗿', '🗽', '🗼', '🏰', '🏯', '🏟', '🎡', '🎢', '🎠', '⛲', '⛱', '🏖', '🏝', '🏜', '🌋', '⛰', '🏔', '🗻', '🏕', '⛺', '🛖', '🏠', '🏡', '🏘', '🏚', '🏗', '🏭', '🏢', '🏬', '🏣', '🏤', '🏥', '🏦', '🏨', '🏪', '🏫', '🏩', '💒', '🏛', '⛪', '🕌', '🕍', '🛕', '🕋', '⛩', '🛤', '🛣', '🗾', '🎑', '🏞', '🌅', '🌄', '🌠', '🎇', '🎆', '🌇', '🌆', '🏙', '🌃', '🌌', '🌉', '🌁'],
        objects: ['⌚', '📱', '📲', '💻', '⌨️', '🖥', '🖨', '🖱', '🖲', '🕹', '🗜', '💽', '💾', '💿', '📀', '📼', '📷', '📸', '📹', '🎥', '📽', '🎞', '📞', '☎️', '📟', '📠', '📺', '📻', '🎙', '🎚', '🎛', '🧭', '⏱', '⏲', '⏰', '🕰', '⌛', '⏳', '📡', '🔋', '🔌', '💡', '🔦', '🕯', '🪔', '🧯', '🛢', '💸', '💵', '💴', '💶', '💷', '🪙', '💰', '💳', '🪪', '💎', '⚖️', '🪜', '🧰', '🪛', '🔧', '🔨', '⚒', '🛠', '⛏', '🪚', '🔩', '⚙️', '🪤', '🧱', '⛓', '🧲', '🔫', '💣', '🧨', '🪓', '🔪', '🗡', '⚔️', '🛡', '🚬', '⚰️', '🪦', '⚱️', '🏺', '🔮', '📿', '🧿', '💈', '⚗️', '🔭', '🔬', '🕳', '🩹', '🩺', '💊', '💉', '🩸', '🧬', '🦠', '🧫', '🧪', '🌡', '🧹', '🪠', '🧺', '🧻', '🚽', '🚰', '🚿', '🛁', '🛀', '🧼', '🪥', '🪒', '🧽', '🪣', '🧴', '🛎', '🔑', '🗝', '🚪', '🪑', '🛋', '🛏', '🛌', '🧸', '🪆', '🖼', '🪞', '🪟', '🛍', '🛒', '🎁', '🎈', '🎏', '🎀', '🪄', '🪅', '🎊', '🎉', '🎎', '🏮', '🎐', '🧧', '✉️', '📩', '📨', '📧', '💌', '📥', '📤', '📦', '🏷', '🪧', '📪', '📫', '📬', '📭', '📮', '📯', '📜', '📃', '📄', '📑', '🧾', '📊', '📈', '📉', '🗒', '🗓', '📆', '📅', '🗑', '📇', '🗃', '🗳', '🗄', '📋', '📁', '📂', '🗂', '🗞', '📰', '📓', '📔', '📒', '📕', '📗', '📘', '📙', '📚', '📖', '🔖', '🧷', '🔗', '📎', '🖇', '📐', '📏', '🧮', '📌', '📍', '✂️', '🖊', '🖋', '✒️', '🖌', '🖍', '📝', '✏️', '🔍', '🔎', '🔏', '🔐', '🔒', '🔓'],
        symbols: ['❤️', '🧡', '💛', '💚', '💙', '💜', '🖤', '🤍', '🤎', '💔', '❤️‍🔥', '❤️‍🩹', '❣️', '💕', '💞', '💓', '💗', '💖', '💘', '💝', '💟', '☮️', '✝️', '☪️', '🕉', '☸️', '✡️', '🔯', '🕎', '☯️', '☦️', '🛐', '⛎', '♈', '♉', '♊', '♋', '♌', '♍', '♎', '♏', '♐', '♑', '♒', '♓', '🆔', '⚛️', '🉑', '☢️', '☣️', '📴', '📳', '🈶', '🈚', '🈸', '🈺', '🈷️', '✴️', '🆚', '💮', '🉐', '㊙️', '㊗️', '🈴', '🈵', '🈹', '🈲', '🅰️', '🅱️', '🆎', '🆑', '🅾️', '🆘', '❌', '⭕', '🛑', '⛔', '📛', '🚫', '💯', '💢', '♨️', '🚷', '🚯', '🚳', '🚱', '🔞', '📵', '🚭', '❗', '❕', '❓', '❔', '‼️', '⁉️', '🔅', '🔆', '〽️', '⚠️', '🚸', '🔱', '⚜️', '🔰', '♻️', '✅', '🈯', '💹', '❇️', '✳️', '❎', '🌐', '💠', 'Ⓜ️', '🌀', '💤', '🏧', '🚾', '♿', '🅿️', '🛗', '🈳', '🈂️', '🛂', '🛃', '🛄', '🛅', '🚹', '🚺', '🚼', '⚧', '🚻', '🚮', '🎦', '📶', '🈁', '🔣', 'ℹ️', '🔤', '🔡', '🔠', '🆖', '🆗', '🆙', '🆒', '🆕', '🆓', '0️⃣', '1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟', '🔢', '#️⃣', '*️⃣', '⏏️', '▶️', '⏸', '⏯', '⏹', '⏺', '⏭', '⏮', '⏩', '⏪', '⏫', '⏬', '◀️', '🔼', '🔽', '➡️', '⬅️', '⬆️', '⬇️', '↗️', '↘️', '↙️', '↖️', '↕️', '↔️', '↪️', '↩️', '⤴️', '⤵️', '🔀', '🔁', '🔂', '🔄', '🔃', '🎵', '🎶', '➕', '➖', '➗', '✖️', '♾', '💲', '💱', '™️', '©️', '®️', '〰️', '➰', '➿', '🔚', '🔙', '🔛', '🔝', '🔜', '✔️', '☑️', '🔘', '🔴', '🟠', '🟡', '🟢', '🔵', '🟣', '⚫', '⚪', '🟤', '🔺', '🔻', '🔸', '🔹', '🔶', '🔷', '🔳', '🔲', '▪️', '▫️', '◾', '◽', '◼️', '◻️', '🟥', '🟧', '🟨', '🟩', '🟦', '🟪', '⬛', '⬜', '🟫', '🔈', '🔇', '🔉', '🔊', '🔔', '🔕', '📣', '📢', '👁️‍🗨️', '💬', '💭', '🗯', '♠️', '♣️', '♥️', '♦️', '🃏', '🎴', '🀄'],
        flags: ['🏁', '🚩', '🎌', '🏴', '🏳️', '🏳️‍🌈', '🏳️‍⚧️', '🏴‍☠️', '🇦🇨', '🇦🇩', '🇦🇪', '🇦🇫', '🇦🇬', '🇦🇮', '🇦🇱', '🇦🇲', '🇦🇴', '🇦🇶', '🇦🇷', '🇦🇸', '🇦🇹', '🇦🇺', '🇦🇼', '🇦🇽', '🇦🇿', '🇧🇦', '🇧🇧', '🇧🇩', '🇧🇪', '🇧🇫', '🇧🇬', '🇧🇭', '🇧🇮', '🇧🇯', '🇧🇱', '🇧🇲', '🇧🇳', '🇧🇴', '🇧🇶', '🇧🇷', '🇧🇸', '🇧🇹', '🇧🇻', '🇧🇼', '🇧🇾', '🇧🇿', '🇨🇦', '🇨🇨', '🇨🇩', '🇨🇫', '🇨🇬', '🇨🇭', '🇨🇮', '🇨🇰', '🇨🇱', '🇨🇲', '🇨🇳', '🇨🇴', '🇨🇵', '🇨🇷', '🇨🇺', '🇨🇻', '🇨🇼', '🇨🇽', '🇨🇾', '🇨🇿', '🇩🇪', '🇩🇬', '🇩🇯', '🇩🇰', '🇩🇲', '🇩🇴', '🇩🇿', '🇪🇦', '🇪🇨', '🇪🇪', '🇪🇬', '🇪🇭', '🇪🇷', '🇪🇸', '🇪🇹', '🇪🇺', '🇫🇮', '🇫🇯', '🇫🇰', '🇫🇲', '🇫🇴', '🇫🇷', '🇬🇦', '🇬🇧', '🇬🇩', '🇬🇪', '🇬🇫', '🇬🇬', '🇬🇭', '🇬🇮', '🇬🇱', '🇬🇲', '🇬🇳', '🇬🇵', '🇬🇶', '🇬🇷', '🇬🇸', '🇬🇹', '🇬🇺', '🇬🇼', '🇬🇾', '🇭🇰', '🇭🇲', '🇭🇳', '🇭🇷', '🇭🇹', '🇭🇺', '🇮🇨', '🇮🇩', '🇮🇪', '🇮🇱', '🇮🇲', '🇮🇳', '🇮🇴', '🇮🇶', '🇮🇷', '🇮🇸', '🇮🇹', '🇯🇪', '🇯🇲', '🇯🇴', '🇯🇵', '🇰🇪', '🇰🇬', '🇰🇭', '🇰🇮', '🇰🇲', '🇰🇳', '🇰🇵', '🇰🇷', '🇰🇼', '🇰🇾', '🇰🇿', '🇱🇦', '🇱🇧', '🇱🇨', '🇱🇮', '🇱🇰', '🇱🇷', '🇱🇸', '🇱🇹', '🇱🇺', '🇱🇻', '🇱🇾', '🇲🇦', '🇲🇨', '🇲🇩', '🇲🇪', '🇲🇫', '🇲🇬', '🇲🇭', '🇲🇰', '🇲🇱', '🇲🇲', '🇲🇳', '🇲🇴', '🇲🇵', '🇲🇶', '🇲🇷', '🇲🇸', '🇲🇹', '🇲🇺', '🇲🇻', '🇲🇼', '🇲🇽', '🇲🇾', '🇲🇿', '🇳🇦', '🇳🇨', '🇳🇪', '🇳🇫', '🇳🇬', '🇳🇮', '🇳🇱', '🇳🇴', '🇳🇵', '🇳🇷', '🇳🇺', '🇳🇿', '🇴🇲', '🇵🇦', '🇵🇪', '🇵🇫', '🇵🇬', '🇵🇭', '🇵🇰', '🇵🇱', '🇵🇲', '🇵🇳', '🇵🇷', '🇵🇸', '🇵🇹', '🇵🇼', '🇵🇾', '🇶🇦', '🇷🇪', '🇷🇴', '🇷🇸', '🇷🇺', '🇷🇼', '🇸🇦', '🇸🇧', '🇸🇨', '🇸🇩', '🇸🇪', '🇸🇬', '🇸🇭', '🇸🇮', '🇸🇯', '🇸🇰', '🇸🇱', '🇸🇲', '🇸🇳', '🇸🇴', '🇸🇷', '🇸🇸', '🇸🇹', '🇸🇻', '🇸🇽', '🇸🇾', '🇸🇿', '🇹🇦', '🇹🇨', '🇹🇩', '🇹🇫', '🇹🇬', '🇹🇭', '🇹🇯', '🇹🇰', '🇹🇱', '🇹🇲', '🇹🇳', '🇹🇴', '🇹🇷', '🇹🇹', '🇹🇻', '🇹🇼', '🇹🇿', '🇺🇦', '🇺🇬', '🇺🇲', '🇺🇳', '🇺🇸', '🇺🇾', '🇺🇿', '🇻🇦', '🇻🇨', '🇻🇪', '🇻🇬', '🇻🇮', '🇻🇳', '🇻🇺', '🇼🇫', '🇼🇸', '🇽🇰', '🇾🇪', '🇾🇹', '🇿🇦', '🇿🇲', '🇿🇼', '🏴󠁧󠁢󠁥󠁮󠁧󠁿', '🏴󠁧󠁢󠁳󠁣󠁴󠁿', '🏴󠁧󠁢󠁷󠁬󠁳󠁿']
    };

    let currentEmojiCategory = 'smileys';
    let gifSearchTimeout = null;

    function initializeEmojis() {
        loadEmojis(currentEmojiCategory);
    }

    function loadEmojis(category) {
        const content = document.getElementById('emojiPickerContent');
        if (!content) return;

        currentEmojiCategory = category;
        const emojis = emojiData[category] || emojiData.smileys;

        content.innerHTML = emojis.map(emoji =>
            `<div class="emoji-item" onclick="insertEmoji('${emoji}')">${emoji}</div>`
        ).join('');

        // Actualizar categoría activa
        document.querySelectorAll('.emoji-category').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.category === category);
        });
    }

    function toggleEmojiPicker() {
        const picker = document.getElementById('emojiPicker');
        const gifPicker = document.getElementById('gifPicker');
        const btn = document.querySelector('.chat-input-actions .emoji-btn');
        const gifBtn = document.querySelector('.chat-input-actions .gif-btn');

        if (!picker) {
            console.error('Emoji picker no encontrado');
            return;
        }

        // Cerrar GIF picker si está abierto
        if (gifPicker && gifPicker.style.display === 'block') {
            gifPicker.style.display = 'none';
            if (gifBtn) gifBtn.classList.remove('active');
        }

        // Toggle emoji picker
        if (picker.style.display === 'none' || !picker.style.display) {
            picker.style.display = 'block';
            if (btn) btn.classList.add('active');
            console.log('Emoji picker abierto');
        } else {
            picker.style.display = 'none';
            if (btn) btn.classList.remove('active');
            console.log('Emoji picker cerrado');
        }
    }

    function filterEmojis(category) {
        loadEmojis(category);
    }

    function searchEmojis(query) {
        const content = document.getElementById('emojiPickerContent');
        if (!content) return;

        if (!query.trim()) {
            loadEmojis(currentEmojiCategory);
            return;
        }

        // Buscar en todas las categorías
        let allEmojis = [];
        Object.values(emojiData).forEach(categoryEmojis => {
            allEmojis = allEmojis.concat(categoryEmojis);
        });

        // Para simplificar, solo mostramos todos los emojis cuando hay búsqueda
        // En una implementación real, filtrarías por nombre del emoji
        content.innerHTML = allEmojis.map(emoji =>
            `<div class="emoji-item" onclick="insertEmoji('${emoji}')">${emoji}</div>`
        ).join('');
    }

    function insertEmoji(emoji) {
        const input = document.getElementById('messageInput');
        const cursorPos = input.selectionStart;
        const textBefore = input.value.substring(0, cursorPos);
        const textAfter = input.value.substring(cursorPos);

        input.value = textBefore + emoji + textAfter;
        input.focus();

        // Posicionar cursor después del emoji
        const newPos = cursorPos + emoji.length;
        input.setSelectionRange(newPos, newPos);

        // Habilitar botón de enviar si hay contenido
        document.getElementById('btnSendMessage').disabled = !input.value.trim();

        // Mantener el picker abierto para insertar más emojis
        // Si prefieres cerrar automáticamente, descomenta:
        // toggleEmojiPicker();
    }

    // ============================================
    // GIF PICKER - SELECTOR DE GIFS (TENOR API)
    // ============================================

    const TENOR_API_KEY = 'AIzaSyAyimkuYQYF_FXVALexPuGQctUWRURdCYQ'; // API Key pública de Google
    const TENOR_CLIENT_KEY = 'faro_maquita_chat';

    function toggleGifPicker() {
        const picker = document.getElementById('gifPicker');
        const emojiPicker = document.getElementById('emojiPicker');
        const btn = document.querySelector('.chat-input-actions .gif-btn');
        const emojiBtn = document.querySelector('.chat-input-actions .emoji-btn');

        if (!picker) {
            console.error('GIF picker no encontrado');
            return;
        }

        // Cerrar emoji picker si está abierto
        if (emojiPicker.style.display === 'block') {
            emojiPicker.style.display = 'none';
            emojiBtn.classList.remove('active');
        }

        // Toggle GIF picker
        if (picker.style.display === 'none' || !picker.style.display) {
            picker.style.display = 'block';
            btn.classList.add('active');
            // Cargar GIFs trending por defecto
            if (!picker.dataset.loaded) {
                loadTrendingGifs();
                picker.dataset.loaded = 'true';
            }
        } else {
            picker.style.display = 'none';
            btn.classList.remove('active');
        }
    }

    function searchGifs(query) {
        clearTimeout(gifSearchTimeout);

        if (!query.trim()) {
            loadTrendingGifs();
            return;
        }

        gifSearchTimeout = setTimeout(() => {
            performGifSearch(query);
        }, 500); // Debounce de 500ms
    }

    async function loadTrendingGifs() {
        const content = document.getElementById('gifPickerContent');
        if (!content) return;

        content.innerHTML = '<div class="gif-loading"><i class="fas fa-spinner fa-spin fa-2x"></i></div>';

        try {
            const response = await fetch(
                `https://tenor.googleapis.com/v2/featured?key=${TENOR_API_KEY}&client_key=${TENOR_CLIENT_KEY}&limit=20`
            );

            if (!response.ok) throw new Error('Error al cargar GIFs');

            const data = await response.json();
            displayGifs(data.results);
        } catch (error) {
            console.error('Error cargando GIFs trending:', error);
            content.innerHTML = '<div class="gif-placeholder"><p class="text-muted">Error al cargar GIFs</p></div>';
        }
    }

    async function performGifSearch(query) {
        const content = document.getElementById('gifPickerContent');
        if (!content) return;

        content.innerHTML = '<div class="gif-loading"><i class="fas fa-spinner fa-spin fa-2x"></i></div>';

        try {
            const response = await fetch(
                `https://tenor.googleapis.com/v2/search?q=${encodeURIComponent(query)}&key=${TENOR_API_KEY}&client_key=${TENOR_CLIENT_KEY}&limit=20&locale=es_ES`
            );

            if (!response.ok) throw new Error('Error en búsqueda de GIFs');

            const data = await response.json();

            if (data.results.length === 0) {
                content.innerHTML = '<div class="gif-placeholder"><i class="fas fa-sad-tear fa-2x mb-2 text-muted"></i><p class="text-muted">No se encontraron GIFs</p></div>';
            } else {
                displayGifs(data.results);
            }
        } catch (error) {
            console.error('Error buscando GIFs:', error);
            content.innerHTML = '<div class="gif-placeholder"><p class="text-muted">Error en búsqueda</p></div>';
        }
    }

    function displayGifs(gifs) {
        const content = document.getElementById('gifPickerContent');
        if (!content) return;

        content.innerHTML = gifs.map((gif, index) => {
            const gifUrl = gif.media_formats.tinygif.url; // Versión pequeña para preview
            const fullUrl = gif.media_formats.gif.url; // URL completa para enviar
            const description = (gif.content_description || 'GIF').replace(/"/g, '&quot;').replace(/'/g, '&apos;');
            return `
                <div class="gif-item" data-gif-url="${fullUrl}" data-description="${description}" onclick="sendGifFromElement(this)">
                    <img src="${gifUrl}" alt="${description}" loading="lazy">
                </div>
            `;
        }).join('');
    }

    function sendGifFromElement(element) {
        const gifUrl = element.dataset.gifUrl;
        const description = element.dataset.description || 'GIF';
        console.log('Click en GIF:', gifUrl, description);
        sendGif(gifUrl, description);
    }

    async function sendGif(gifUrl, description) {
        console.log('Enviando GIF:', gifUrl, description);

        if (!currentConversationId) {
            toastr.warning('Selecciona una conversación primero');
            return;
        }

        // Cerrar el picker
        const picker = document.getElementById('gifPicker');
        const btn = document.querySelector('.chat-input-actions .gif-btn');

        if (picker) picker.style.display = 'none';
        if (btn) btn.classList.remove('active');

        // Mostrar loading
        toastr.info('Enviando GIF...');

        try {
            const response = await fetch(`/api/chat/conversations/${currentConversationId}/messages`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    content: '',
                    message_type: 'gif',
                    gif_url: gifUrl
                })
            });

            const data = await response.json();

            if (data.success) {
                toastr.success('GIF enviado!');
                const container = document.getElementById('chatMessages');
                container.insertAdjacentHTML('beforeend', renderSingleMessage(data.message));
                scrollToBottom(container, true);
                loadConversations();
            } else {
                toastr.error(data.error || 'Error al enviar GIF');
            }
        } catch (error) {
            console.error('Error enviando GIF:', error);
            toastr.error('Error de conexión');
        }
    }

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

    // ============================================
    // FUNCIONES DE SEGURIDAD
    // ============================================

    /**
     * Escapa caracteres HTML peligrosos para prevenir XSS.
     * Esta es una capa de seguridad del lado del cliente.
     */
    function escapeHtml(text) {
        if (!text) return '';
        if (typeof text !== 'string') text = String(text);

        const htmlEntities = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#x27;',
            '/': '&#x2F;',
            '`': '&#x60;',
            '=': '&#x3D;'
        };

        return text.replace(/[&<>"'`=\/]/g, char => htmlEntities[char]);
    }

    /**
     * Sanitiza texto para prevenir inyecciones en atributos HTML.
     */
    function sanitizeAttribute(text) {
        if (!text) return '';
        // Remover caracteres peligrosos para atributos
        return escapeHtml(text).replace(/[\n\r\t]/g, ' ');
    }

    /**
     * Valida que un valor sea un ID numerico valido.
     */
    function validateId(value) {
        if (!value) return null;
        const id = parseInt(value, 10);
        return (!isNaN(id) && id > 0) ? id : null;
    }

    /**
     * Sanitiza el contenido de un mensaje antes de enviarlo.
     * Remueve scripts y contenido peligroso.
     */
    function sanitizeMessage(content) {
        if (!content) return '';
        if (typeof content !== 'string') content = String(content);

        // Remover tags de script
        content = content.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '');

        // Remover event handlers
        content = content.replace(/\s*on\w+\s*=\s*["'][^"']*["']/gi, '');

        // Remover javascript: URLs
        content = content.replace(/javascript:/gi, '');

        // Limitar longitud
        const MAX_LENGTH = 5000;
        if (content.length > MAX_LENGTH) {
            content = content.substring(0, MAX_LENGTH);
        }

        return content.trim();
    }

    /**
     * Valida extension de archivo permitida.
     */
    function isAllowedFileExtension(filename) {
        if (!filename) return false;
        const ext = filename.split('.').pop().toLowerCase();
        const allowed = [
            // Imagenes
            'jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp',
            // Documentos
            'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt', 'csv',
            // Video
            'mp4', 'webm', 'mov', 'avi',
            // Audio
            'mp3', 'wav', 'ogg', 'm4a'
        ];
        return allowed.includes(ext);
    }

    /**
     * Valida tamaño de archivo.
     */
    function isAllowedFileSize(file, maxMB = 25) {
        if (!file) return false;
        const maxBytes = maxMB * 1024 * 1024;
        return file.size <= maxBytes;
    }

    // Utilidades
    function getInitials(name) {
        if (!name) return '?';
        const safeName = escapeHtml(name);
        const parts = safeName.split(' ').filter(p => p);
        if (parts.length >= 2) {
            return (parts[0][0] + parts[1][0]).toUpperCase();
        }
        return safeName.substring(0, 2).toUpperCase();
    }

    // Nombre corto tipo WhatsApp: 1er nombre + 1er apellido, en Title Case
    function nombreCorto(nombre) {
        if (!nombre) return 'Usuario';
        var w = String(nombre).trim().split(/\s+/);
        var tc = function(x){ return x ? x.charAt(0).toUpperCase() + x.slice(1).toLowerCase() : x; };
        if (w.length >= 3) return tc(w[0]) + ' ' + tc(w[2]);   // 1er nombre + 1er apellido
        if (w.length === 2) return tc(w[0]) + ' ' + tc(w[1]);
        return tc(w[0]);
    }
    window.nombreCorto = nombreCorto;

    function formatTime(dateString) {
        if (!dateString) return '';
        const date = new Date(dateString);
        const now = new Date();
        const diff = now - date;

        if (diff < 86400000) { // Menos de 24 horas
            return date.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' });
        } else if (diff < 604800000) { // Menos de 7 días
            return date.toLocaleDateString('es-ES', { weekday: 'short' });
        }
        return date.toLocaleDateString('es-ES', { day: '2-digit', month: '2-digit' });
    }

    function formatMessageTime(dateString) {
        if (!dateString) return '';
        return new Date(dateString).toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' });
    }

    // Archivos
    function attachFile() {
        document.getElementById('fileInput').click();
    }

    function attachImage() {
        document.getElementById('imageInput').click();
    }

    async function handleFileSelect(event) {
        const file = event.target.files[0];
        if (!file || !currentConversationId) return;

        // Validar extension
        if (!isAllowedFileExtension(file.name)) {
            toastr.error('Tipo de archivo no permitido');
            event.target.value = '';
            return;
        }

        // Validar tamaño (25MB max)
        if (!isAllowedFileSize(file, 25)) {
            toastr.error('El archivo es demasiado grande (max 25MB)');
            event.target.value = '';
            return;
        }

        await uploadAndSendFile(file, 'file');
        event.target.value = '';
    }

    async function handleImageSelect(event) {
        const file = event.target.files[0];
        if (!file || !currentConversationId) return;

        // Validar que sea imagen
        const imageExts = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp'];
        const ext = file.name.split('.').pop().toLowerCase();
        if (!imageExts.includes(ext)) {
            toastr.error('Solo se permiten imagenes (JPG, PNG, GIF, WebP)');
            event.target.value = '';
            return;
        }

        // Validar tamaño (10MB max para imagenes)
        if (!isAllowedFileSize(file, 10)) {
            toastr.error('La imagen es demasiado grande (max 10MB)');
            event.target.value = '';
            return;
        }

        await uploadAndSendFile(file, 'image');
        event.target.value = '';
    }

    async function uploadAndSendFile(file, type) {
        // Validar ID de conversacion
        const conversationId = validateId(currentConversationId);
        if (!conversationId) {
            toastr.error('Error: conversacion invalida');
            return;
        }

        const formData = new FormData();
        formData.append('file', file);
        formData.append('message_type', type);

        try {
            toastr.info('Subiendo archivo...');

            const response = await fetch(`/api/chat/conversations/${conversationId}/messages/upload`, {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (data.success) {
                toastr.success('Archivo enviado');
                const container = document.getElementById('chatMessages');
                container.insertAdjacentHTML('beforeend', renderSingleMessage(data.message));
                scrollToBottom(container, true);
                loadConversations();
            } else {
                toastr.error(data.error || 'Error al subir archivo');
            }
        } catch (error) {
            console.error('Error:', error);
            toastr.error('Error de conexión');
        }
    }

    function viewImage(url) {
        window.open(url, '_blank');
    }

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
              '<input id="buscarMsgInput" type="text" placeholder="Buscar mensajes..." style="flex:1;border:none;outline:none;font-size:.95rem;" autocomplete="off">' +
              '<button class="btn btn-sm btn-light" onclick="document.getElementById(\'buscadorMsgOverlay\').remove()"><i class="fas fa-times"></i></button>' +
            '</div>' +
            (tieneConv ?
              '<div style="padding:6px 16px;border-bottom:1px solid #f3f3f3;font-size:.8rem;">' +
                '<label style="cursor:pointer;"><input type="radio" name="ambitoBusq" checked onchange="window._ambitoBusqueda=\'conv\';buscarMsgAhora()"> En este chat</label>' +
                '<label style="cursor:pointer;margin-left:14px;"><input type="radio" name="ambitoBusq" onchange="window._ambitoBusqueda=\'all\';buscarMsgAhora()"> Todas las conversaciones</label>' +
              '</div>' : '') +
            '<div id="buscarMsgResultados" style="overflow-y:auto;padding:6px 0;"><div class="text-center text-muted py-4 small">Escribe para buscar...</div></div>' +
          '</div>';
        document.body.appendChild(ov);
        window._buscarConvId = convId;
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
    window.toggleGifPicker = toggleGifPicker;
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


// Movil: volver a la lista de conversaciones
function volverAListaChat() {
    var cc = document.querySelector('.chat-container');
    if (cc) cc.classList.remove('mobile-chat-open');
}
window.volverAListaChat = volverAListaChat;


// ============================================================
// CLIC DERECHO en una conversacion: Archivar / Vaciar / Eliminar
// (todo es SOFT: nada se borra de la BD; recuperable en panel admin)
// ============================================================
function cerrarMenuConvCtx() { const m = document.getElementById('convCtxMenu'); if (m) m.remove(); }

document.addEventListener('contextmenu', function(e) {
    // Clic derecho en un MENSAJE: reaccionar / copiar / reenviar (como el mini-chat)
    const msgEl = e.target.closest('.message[data-message-id]');
    if (msgEl) { e.preventDefault(); mostrarMenuMensajeCtx(e, msgEl); return; }
    const item = e.target.closest('.conversation-item[data-conv-id]');
    if (!item) return;
    e.preventDefault();
    cerrarMenuConvCtx();
    const cid = item.getAttribute('data-conv-id');
    const cname = item.getAttribute('data-conv-name') || 'esta conversación';
    const menu = document.createElement('div');
    menu.id = 'convCtxMenu';
    menu.style.cssText = 'position:fixed;z-index:100060;background:#fff;color:#222;border-radius:10px;box-shadow:0 6px 24px rgba(0,0,0,.25);padding:6px 0;min-width:190px;font-size:.9rem;';
    const it = function(icon, label, fn, color) {
        return '<div style="padding:9px 16px;cursor:pointer;display:flex;gap:10px;align-items:center;' + (color ? 'color:' + color + ';' : '') + '" onmouseover="this.style.background=\'#f0f2f5\'" onmouseout="this.style.background=\'\'" onclick="' + fn + '"><i class="fas ' + icon + '" style="width:16px;opacity:.7;"></i>' + label + '</div>';
    };
    const _arch = window._viendoArchivadas;
    menu.innerHTML =
        it(_arch ? 'fa-box-open' : 'fa-box-archive', _arch ? 'Desarchivar' : 'Archivar', 'archivarConv(' + cid + ',' + (_arch ? 'false' : 'true') + ');cerrarMenuConvCtx();') +
        it('fa-eraser', 'Vaciar conversación', 'vaciarConv(' + cid + ',\'' + cname.replace(/'/g, "\\'") + '\');cerrarMenuConvCtx();') +
        '<div style="height:1px;background:rgba(0,0,0,.07);margin:4px 0;"></div>' +
        it('fa-trash-alt', 'Eliminar conversación', 'eliminarConv(' + cid + ',\'' + cname.replace(/'/g, "\\'") + '\');cerrarMenuConvCtx();', '#dc2626');
    document.body.appendChild(menu);
    let x = e.clientX, y = e.clientY;
    const mw = menu.offsetWidth, mh = menu.offsetHeight;
    if (x + mw > window.innerWidth) x = window.innerWidth - mw - 8;
    if (y + mh > window.innerHeight) y = window.innerHeight - mh - 8;
    menu.style.left = x + 'px'; menu.style.top = y + 'px';
});
document.addEventListener('click', cerrarMenuConvCtx);

async function archivarConv(cid, archivar) {
    if (archivar === undefined) archivar = true;
    try {
        await fetch('/api/chat/conversations/' + cid + '/archivar', {
            method: 'POST', headers: {'Content-Type':'application/json'}, credentials: 'same-origin',
            body: JSON.stringify({ archivar: archivar })
        });
        if (typeof toastr !== 'undefined') toastr.success(archivar ? 'Conversación archivada' : 'Conversación desarchivada');
        if (window._viendoArchivadas && typeof cargarArchivadas === 'function') cargarArchivadas();
        else if (typeof loadConversations === 'function') loadConversations();
    } catch (e) { console.error(e); }
}

async function vaciarConv(cid, nombre) {
    if (!confirm('¿Vaciar la conversación con ' + (nombre||'') + '? Dejarás de ver los mensajes anteriores (no se borran del sistema).')) return;
    try {
        await fetch('/api/chat/conversations/' + cid + '/vaciar', { method: 'POST', credentials: 'same-origin' });
        if (typeof toastr !== 'undefined') toastr.success('Conversación vaciada');
        if (window.currentConversationId == cid && typeof loadMessages === 'function') loadMessages(cid);
        if (typeof loadConversations === 'function') loadConversations();
    } catch (e) { console.error(e); }
}

async function eliminarConv(cid, nombre) {
    if (!confirm('¿Eliminar la conversación con ' + (nombre||'') + ' de tu lista? Se podrá recuperar desde el panel de administración.')) return;
    try {
        await fetch('/api/chat/conversations/' + cid + '/eliminar', { method: 'POST', credentials: 'same-origin' });
        if (typeof toastr !== 'undefined') toastr.success('Conversación eliminada de tu lista');
        if (typeof loadConversations === 'function') loadConversations();
        // Si estaba abierta, volver al estado vacio
        if (window.currentConversationId == cid) {
            const ea = document.getElementById('chatEmptyState'); if (ea) ea.style.display = 'flex';
            const aa = document.getElementById('chatActiveArea'); if (aa) aa.style.display = 'none';
            window.currentConversationId = null;
        }
    } catch (e) { console.error(e); }
}
window.archivarConv = archivarConv; window.vaciarConv = vaciarConv; window.eliminarConv = eliminarConv;
window.cerrarMenuConvCtx = cerrarMenuConvCtx;

// ============================================================
// Barra WhatsApp: camara, grabacion de audio, toggle enviar/microfono
// ============================================================
function abrirCamara() {
    const el = document.getElementById("cameraInput");
    if (el) el.click();
}
window.abrirCamara = abrirCamara;

function actualizarBotonEnvio() {
    const ta = document.getElementById("messageInput");
    const send = document.getElementById("btnSendMessage");
    const mic = document.getElementById("btnMicAudio");
    const hayTexto = ta && ta.value.trim().length > 0;
    if (send) send.style.display = hayTexto ? "inline-flex" : "none";
    if (mic) mic.style.display = hayTexto ? "none" : "inline-flex";
}
window.actualizarBotonEnvio = actualizarBotonEnvio;

let _grabAudioChat = null;
async function toggleGrabacionAudio() {
    if (_grabAudioChat) { try { _grabAudioChat.recorder.stop(); } catch (e) {} return; }
    if (!window.currentConversationId) { if (typeof toastr !== "undefined") toastr.warning("Abre una conversación primero"); return; }
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const mime = (window.MediaRecorder && MediaRecorder.isTypeSupported("audio/webm;codecs=opus")) ? "audio/webm;codecs=opus" : "audio/webm";
        const recorder = new MediaRecorder(stream, { mimeType: mime });
        const chunks = [];
        recorder.ondataavailable = function (e) { if (e.data && e.data.size) chunks.push(e.data); };
        recorder.onstop = async function () {
            stream.getTracks().forEach(function (t) { t.stop(); });
            const btn = document.getElementById("btnMicAudio");
            if (btn) btn.classList.remove("grabando");
            _grabAudioChat = null;
            const blob = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
            if (!blob.size) return;
            const file = new File([blob], "audio_" + Date.now() + ".webm", { type: "audio/webm" });
            if (typeof uploadAndSendFile === "function") await uploadAndSendFile(file, "audio");
        };
        recorder.start();
        _grabAudioChat = { recorder: recorder, stream: stream };
        const btn = document.getElementById("btnMicAudio");
        if (btn) btn.classList.add("grabando");
        if (typeof toastr !== "undefined") toastr.info("Grabando... toca el micrófono de nuevo para enviar");
    } catch (e) { if (typeof toastr !== "undefined") toastr.error("No se pudo acceder al micrófono"); }
}
window.toggleGrabacionAudio = toggleGrabacionAudio;


// ============================================================
// CLIC DERECHO en un MENSAJE (chat grande): Reaccionar / Copiar / Reenviar
// ============================================================
function mostrarMenuMensajeCtx(e, msgEl) {
    cerrarMenuConvCtx();
    const mid = msgEl.getAttribute('data-message-id');
    if (!mid) return;
    const menu = document.createElement('div');
    menu.id = 'convCtxMenu';
    menu.style.cssText = 'position:fixed;z-index:100060;background:#fff;color:#222;border-radius:12px;box-shadow:0 6px 24px rgba(0,0,0,.25);padding:6px 0;min-width:190px;font-size:.9rem;';
    const emojis = ['\u2764\ufe0f', '\ud83d\udc4d', '\ud83d\ude02', '\ud83d\ude2e', '\ud83d\ude22', '\ud83d\ude4f'];
    let html = '<div style="display:flex;gap:6px;padding:6px 12px;justify-content:space-between;">' +
        emojis.map(function(em){ return '<span style="cursor:pointer;font-size:1.35rem;line-height:1;" onmouseover="this.style.transform=\'scale(1.25)\'" onmouseout="this.style.transform=\'\'" onclick="reaccionarMsgCtx(' + mid + ',\'' + em + '\')">' + em + '</span>'; }).join('') +
        '</div><div style="height:1px;background:rgba(0,0,0,.08);margin:4px 0;"></div>';
    const it = function(icon, label, fn, color){ return '<div style="padding:9px 16px;cursor:pointer;display:flex;gap:10px;align-items:center;' + (color?'color:'+color+';':'') + '" onmouseover="this.style.background=\'#f0f2f5\'" onmouseout="this.style.background=\'\'" onclick="' + fn + '"><i class="fas ' + icon + '" style="width:16px;opacity:.7;"></i>' + label + '</div>'; };
    html += it('fa-copy', 'Copiar', 'copiarMensajeChat(' + mid + ');cerrarMenuConvCtx();');
    if (typeof window.mostrarModalReenvio === 'function' || typeof mostrarModalReenvio === 'function') {
        html += it('fa-share', 'Reenviar', 'mostrarModalReenvio(' + mid + ');cerrarMenuConvCtx();');
    }
    menu.innerHTML = html;
    document.body.appendChild(menu);
    let x = e.clientX, y = e.clientY;
    const mw = menu.offsetWidth, mh = menu.offsetHeight;
    if (x + mw > window.innerWidth) x = window.innerWidth - mw - 8;
    if (y + mh > window.innerHeight) y = window.innerHeight - mh - 8;
    if (y < 8) y = 8;
    menu.style.left = x + 'px'; menu.style.top = y + 'px';
}
window.mostrarMenuMensajeCtx = mostrarMenuMensajeCtx;

function reaccionarMsgCtx(mid, emoji) {
    cerrarMenuConvCtx();
    if (typeof addReaction === 'function') addReaction(mid, emoji);
}
window.reaccionarMsgCtx = reaccionarMsgCtx;

function copiarMensajeChat(mid) {
    const el = document.querySelector('.message[data-message-id="' + mid + '"] .message-content');
    if (!el) return;
    const clon = el.cloneNode(true);
    clon.querySelectorAll('.message-actions, .message-meta, .btn-add-reaction, .message-reactions, .reaction-picker').forEach(function(n){ n.remove(); });
    const texto = (clon.textContent || '').trim();
    if (!texto) return;
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(texto).then(function(){ if (typeof toastr!=='undefined') toastr.success('Copiado'); }).catch(function(){});
    } else {
        const ta = document.createElement('textarea'); ta.value = texto; document.body.appendChild(ta); ta.select();
        try { document.execCommand('copy'); if (typeof toastr!=='undefined') toastr.success('Copiado'); } catch(e){}
        ta.remove();
    }
}
window.copiarMensajeChat = copiarMensajeChat;
