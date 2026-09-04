// chat-meet.js — Llamadas / conferencias / Meet desde el chat y mensaje rápido.
// Extraído de chat-page.js (líneas 1-129) el 28/08/2026 SIN cambios de código; ámbito global compartido.
// Orden de carga: ver plantillas/chat/index.html (mismo orden que el archivo original).

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
            iniciarConferenciaDesdeChat(tipo);   // T-15: 'video' entra con camara
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
    async function iniciarConferenciaDesdeChat(tipo) {
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
                iniciarConferenciaGrupal(currentConversationId, participants, groupName, tipo);
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

