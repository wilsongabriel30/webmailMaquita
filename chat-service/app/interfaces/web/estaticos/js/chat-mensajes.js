// chat-mensajes.js — Abrir conversación, cargar y renderizar mensajes.
// Extraído de chat-page.js (líneas 1030-1451) el 28/08/2026 SIN cambios de código; ámbito global compartido.
// Orden de carga: ver plantillas/chat/index.html (mismo orden que el archivo original).

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

            // [A-1] La URL venia del mensaje y se metia cruda en el atributo src y
            // DENTRO de una cadena de onclick: una comilla la rompia y ejecutaba
            // codigo en el navegador de todos los participantes. Ahora se admite
            // solo la galeria local, se escapa al pintar y el clic ya no interpola
            // la URL: la lee del propio elemento.
            if (gifUrl && /^\/static\/gifs\/[A-Za-z0-9._-]{1,120}$/.test(gifUrl)) {
                contentHtml = `
                    <div class="message-media message-gif">
                        <img src="${escapeHtml(gifUrl)}" alt="GIF"
                             style="max-width: 250px; max-height: 200px; border-radius: 8px; cursor: pointer; display: block;"
                             onclick="viewImage(this.getAttribute('src'))"
                             onerror="this.alt='Error al cargar GIF'; this.style.padding='20px';">
                    </div>
                `;
            } else if (gifUrl) {
                contentHtml = '<div class="message-text text-muted">GIF no disponible</div>';
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

