/**
 * Cliente WebSocket para Chat en Tiempo Real
 * Raíces - Maquita Cushunchic
 *
 * Maneja la conexion WebSocket con el servidor para:
 * - Mensajes en tiempo real
 * - Indicadores de escritura
 * - Presencia online/offline
 * - Notificaciones
 *
 * Dependencia: Socket.IO Client (incluir antes de este script)
 * <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
 *
 * Autor: Wilson Arguello
 * Fecha: 2026-01-02
 * Version: 1.0.0
 */

class ChatWebSocket {
    constructor(options = {}) {
        this.socket = null;
        this.connected = false;
        this.reconnecting = false;
        this.currentConversationId = null;

        // Opciones
        this.options = {
            autoConnect: true,
            heartbeatInterval: 30000,  // 30 segundos
            typingTimeout: 3000,       // 3 segundos sin escribir = dejar de typing
            debug: false,
            ...options
        };

        // Callbacks
        this.callbacks = {
            onConnect: () => {},
            onDisconnect: () => {},
            onNewMessage: (mensaje) => {},
            onMessageEdited: (mensaje) => {},
            onMessageDeleted: (data) => {},
            onUserTyping: (data) => {},
            onUserStoppedTyping: (data) => {},
            onUserPresence: (data) => {},
            onReactionAdded: (data) => {},
            onReactionRemoved: (data) => {},
            onMessagesRead: (data) => {},
            onNotification: (data) => {},
            onError: (error) => {},
        };

        // Timers
        this.heartbeatTimer = null;
        this.typingTimer = null;
        this.isTyping = false;

        // Auto conectar si esta habilitado
        if (this.options.autoConnect) {
            this.connect();
        }
    }

    /**
     * Conecta al servidor WebSocket
     */
    connect() {
        if (this.socket && this.connected) {
            this._log('Ya conectado');
            return;
        }

        this._log('Conectando...');

        this.socket = io({
            transports: ['websocket', 'polling'],
            upgrade: true,
            reconnection: true,
            reconnectionAttempts: 10,
            reconnectionDelay: 1000,
            reconnectionDelayMax: 5000,
        });

        this._setupEventListeners();
    }

    /**
     * Desconecta del servidor
     */
    disconnect() {
        if (this.socket) {
            this.socket.disconnect();
            this._stopHeartbeat();
        }
    }

    /**
     * Configura los listeners de eventos
     */
    _setupEventListeners() {
        // Conexion establecida
        this.socket.on('connect', () => {
            this._log('Conectado');
            this.connected = true;
            this.reconnecting = false;
            this._startHeartbeat();
            this.callbacks.onConnect();
        });

        // Confirmacion del servidor
        this.socket.on('connected', (data) => {
            this._log('Confirmado por servidor:', data);
        });

        // Desconexion
        this.socket.on('disconnect', (reason) => {
            this._log('Desconectado:', reason);
            this.connected = false;
            this._stopHeartbeat();
            this.callbacks.onDisconnect(reason);
        });

        // Reconexion
        this.socket.on('reconnect_attempt', (attempt) => {
            this._log('Intentando reconectar...', attempt);
            this.reconnecting = true;
        });

        this.socket.on('reconnect', () => {
            this._log('Reconectado');
            this.reconnecting = false;

            // Volver a unirse a la conversacion actual
            if (this.currentConversationId) {
                this.joinConversation(this.currentConversationId);
            }
        });

        // Error de conexion
        this.socket.on('connect_error', (error) => {
            this._log('Error de conexion:', error);
            this.callbacks.onError({ type: 'connection', error: error.message });
        });

        // Error general
        this.socket.on('error', (error) => {
            this._log('Error:', error);
            this.callbacks.onError(error);
        });

        // =====================================================================
        // EVENTOS DE MENSAJES
        // =====================================================================

        // Nuevo mensaje
        this.socket.on('new_message', (mensaje) => {
            this._log('Nuevo mensaje:', mensaje);
            this.callbacks.onNewMessage(mensaje);
        });

        // Mensaje editado
        this.socket.on('message_edited', (mensaje) => {
            this._log('Mensaje editado:', mensaje);
            this.callbacks.onMessageEdited(mensaje);
        });

        // Mensaje eliminado
        this.socket.on('message_deleted', (data) => {
            this._log('Mensaje eliminado:', data);
            this.callbacks.onMessageDeleted(data);
        });

        // Mensajes leidos
        this.socket.on('messages_read', (data) => {
            this._log('Mensajes leidos:', data);
            this.callbacks.onMessagesRead(data);
        });

        // =====================================================================
        // EVENTOS DE ESCRITURA
        // =====================================================================

        // Usuario escribiendo
        this.socket.on('user_typing', (data) => {
            this._log('Usuario escribiendo:', data);
            this.callbacks.onUserTyping(data);
        });

        // Usuario dejo de escribir
        this.socket.on('user_stopped_typing', (data) => {
            this._log('Usuario dejo de escribir:', data);
            this.callbacks.onUserStoppedTyping(data);
        });

        // =====================================================================
        // EVENTOS DE PRESENCIA
        // =====================================================================

        // Cambio de presencia
        this.socket.on('user_presence', (data) => {
            this._log('Presencia:', data);
            this.callbacks.onUserPresence(data);
        });

        // Respuesta a consulta de presencia
        this.socket.on('presence_info', (data) => {
            this._log('Info presencia:', data);
            // Se maneja con callback especifico
        });

        // =====================================================================
        // EVENTOS DE REACCIONES
        // =====================================================================

        // Reaccion agregada
        this.socket.on('reaction_added', (data) => {
            this._log('Reaccion agregada:', data);
            this.callbacks.onReactionAdded(data);
        });

        // Reaccion eliminada
        this.socket.on('reaction_removed', (data) => {
            this._log('Reaccion eliminada:', data);
            this.callbacks.onReactionRemoved(data);
        });

        // =====================================================================
        // OTROS EVENTOS
        // =====================================================================

        // Notificacion
        this.socket.on('notification', (data) => {
            this._log('Notificacion:', data);
            this.callbacks.onNotification(data);
        });

        // Heartbeat ACK
        this.socket.on('heartbeat_ack', (data) => {
            this._log('Heartbeat ACK');
        });

        // Confirmacion de union a conversacion
        this.socket.on('joined_conversation', (data) => {
            this._log('Unido a conversacion:', data);
        });
    }

    // =========================================================================
    // METODOS PUBLICOS - CONVERSACIONES
    // =========================================================================

    /**
     * Une al usuario a una conversacion
     * @param {number} conversationId - ID de la conversacion
     */
    joinConversation(conversationId) {
        if (!this.connected) {
            this._log('No conectado, no se puede unir a conversacion');
            return;
        }

        this.currentConversationId = conversationId;
        this.socket.emit('join_conversation', { conversation_id: conversationId });
        this._log('Uniendose a conversacion:', conversationId);
    }

    /**
     * Sale de una conversacion
     * @param {number} conversationId - ID de la conversacion
     */
    leaveConversation(conversationId) {
        if (!this.connected) return;

        this.socket.emit('leave_conversation', { conversation_id: conversationId });

        if (this.currentConversationId === conversationId) {
            this.currentConversationId = null;
        }

        this._log('Saliendo de conversacion:', conversationId);
    }

    // =========================================================================
    // METODOS PUBLICOS - MENSAJES
    // =========================================================================

    /**
     * Envia un mensaje
     * @param {number} conversationId - ID de la conversacion
     * @param {string} content - Contenido del mensaje
     * @param {Object} options - Opciones adicionales
     * @param {string} options.type - Tipo de mensaje (default: 'text')
     * @param {number} options.replyTo - ID del mensaje al que responde
     */
    sendMessage(conversationId, content, options = {}) {
        if (!this.connected) {
            this.callbacks.onError({ type: 'send', message: 'No conectado' });
            return;
        }

        this.socket.emit('send_message', {
            conversation_id: conversationId,
            content: content,
            type: options.type || 'text',
            reply_to: options.replyTo || null
        });

        // Dejar de escribir
        this._stopTyping(conversationId);

        this._log('Mensaje enviado');
    }

    /**
     * Edita un mensaje
     * @param {number} messageId - ID del mensaje
     * @param {string} content - Nuevo contenido
     */
    editMessage(messageId, content) {
        if (!this.connected) return;

        this.socket.emit('edit_message', {
            message_id: messageId,
            content: content
        });

        this._log('Editando mensaje:', messageId);
    }

    /**
     * Elimina un mensaje
     * @param {number} messageId - ID del mensaje
     * @param {number} conversationId - ID de la conversacion
     * @param {boolean} forAll - Eliminar para todos
     */
    deleteMessage(messageId, conversationId, forAll = false) {
        if (!this.connected) return;

        this.socket.emit('delete_message', {
            message_id: messageId,
            conversation_id: conversationId,
            for_all: forAll
        });

        this._log('Eliminando mensaje:', messageId);
    }

    /**
     * Marca mensajes como leidos
     * @param {number} conversationId - ID de la conversacion
     * @param {number} untilMessageId - Hasta que mensaje (opcional)
     */
    markRead(conversationId, untilMessageId = null) {
        if (!this.connected) return;

        this.socket.emit('mark_read', {
            conversation_id: conversationId,
            until_message_id: untilMessageId
        });

        this._log('Marcando como leido');
    }

    // =========================================================================
    // METODOS PUBLICOS - ESCRITURA
    // =========================================================================

    /**
     * Indica que el usuario esta escribiendo
     * @param {number} conversationId - ID de la conversacion
     * @param {string} action - Tipo de accion (typing, recording_audio, etc.)
     */
    startTyping(conversationId, action = 'typing') {
        if (!this.connected || this.isTyping) return;

        this.isTyping = true;
        this.socket.emit('typing_start', {
            conversation_id: conversationId,
            action: action
        });

        // Configurar timeout para dejar de escribir automaticamente
        this._resetTypingTimer(conversationId);
    }

    /**
     * Indica que el usuario dejo de escribir
     * @param {number} conversationId - ID de la conversacion
     */
    stopTyping(conversationId) {
        this._stopTyping(conversationId);
    }

    /**
     * Maneja el input del usuario (llamar en cada keypress)
     * @param {number} conversationId - ID de la conversacion
     */
    handleTypingInput(conversationId) {
        if (!this.connected) return;

        if (!this.isTyping) {
            this.startTyping(conversationId);
        }

        this._resetTypingTimer(conversationId);
    }

    // =========================================================================
    // METODOS PUBLICOS - REACCIONES
    // =========================================================================

    /**
     * Agrega una reaccion a un mensaje
     * @param {number} messageId - ID del mensaje
     * @param {number} conversationId - ID de la conversacion
     * @param {string} emoji - Emoji de la reaccion
     */
    addReaction(messageId, conversationId, emoji) {
        if (!this.connected) return;

        this.socket.emit('add_reaction', {
            message_id: messageId,
            conversation_id: conversationId,
            emoji: emoji
        });

        this._log('Agregando reaccion:', emoji);
    }

    /**
     * Elimina una reaccion de un mensaje
     * @param {number} messageId - ID del mensaje
     * @param {number} conversationId - ID de la conversacion
     */
    removeReaction(messageId, conversationId) {
        if (!this.connected) return;

        this.socket.emit('remove_reaction', {
            message_id: messageId,
            conversation_id: conversationId
        });

        this._log('Eliminando reaccion');
    }

    // =========================================================================
    // METODOS PUBLICOS - PRESENCIA
    // =========================================================================

    /**
     * Consulta la presencia de usuarios
     * @param {number[]} userIds - IDs de usuarios
     * @param {Function} callback - Callback con los resultados
     */
    getPresence(userIds, callback) {
        if (!this.connected) {
            callback({});
            return;
        }

        // Configurar listener temporal para la respuesta
        this.socket.once('presence_info', (data) => {
            callback(data);
        });

        this.socket.emit('get_presence', { user_ids: userIds });
    }

    // =========================================================================
    // METODOS PUBLICOS - CALLBACKS
    // =========================================================================

    /**
     * Registra callbacks para eventos
     * @param {string} event - Nombre del evento
     * @param {Function} callback - Funcion callback
     */
    on(event, callback) {
        const callbackName = 'on' + event.charAt(0).toUpperCase() + event.slice(1);
        if (this.callbacks.hasOwnProperty(callbackName)) {
            this.callbacks[callbackName] = callback;
        } else {
            this._log('Evento no reconocido:', event);
        }
    }

    // =========================================================================
    // METODOS PRIVADOS
    // =========================================================================

    _startHeartbeat() {
        this._stopHeartbeat();
        this.heartbeatTimer = setInterval(() => {
            if (this.connected) {
                this.socket.emit('heartbeat');
            }
        }, this.options.heartbeatInterval);
    }

    _stopHeartbeat() {
        if (this.heartbeatTimer) {
            clearInterval(this.heartbeatTimer);
            this.heartbeatTimer = null;
        }
    }

    _stopTyping(conversationId) {
        if (!this.isTyping) return;

        this.isTyping = false;

        if (this.typingTimer) {
            clearTimeout(this.typingTimer);
            this.typingTimer = null;
        }

        if (this.connected && conversationId) {
            this.socket.emit('typing_stop', { conversation_id: conversationId });
        }
    }

    _resetTypingTimer(conversationId) {
        if (this.typingTimer) {
            clearTimeout(this.typingTimer);
        }

        this.typingTimer = setTimeout(() => {
            this._stopTyping(conversationId);
        }, this.options.typingTimeout);
    }

    _log(...args) {
        if (this.options.debug) {
            console.log('[ChatWS]', ...args);
        }
    }
}


// Exportar para uso global
window.ChatWebSocket = ChatWebSocket;


// ============================================================================
// EJEMPLO DE USO
// ============================================================================

/*
// Inicializar
const chat = new ChatWebSocket({
    debug: true,
    autoConnect: true
});

// Configurar callbacks
chat.on('connect', () => {
    console.log('Conectado al chat');
    chat.joinConversation(123);
});

chat.on('newMessage', (mensaje) => {
    console.log('Nuevo mensaje:', mensaje);
    // Agregar mensaje a la UI
    agregarMensajeUI(mensaje);
});

chat.on('userTyping', (data) => {
    console.log(data.user_name + ' esta escribiendo...');
    mostrarIndicadorEscritura(data.user_id);
});

chat.on('userStoppedTyping', (data) => {
    ocultarIndicadorEscritura(data.user_id);
});

// Enviar mensaje
document.getElementById('btn-enviar').addEventListener('click', () => {
    const texto = document.getElementById('input-mensaje').value;
    chat.sendMessage(123, texto);
    document.getElementById('input-mensaje').value = '';
});

// Detectar escritura
document.getElementById('input-mensaje').addEventListener('input', () => {
    chat.handleTypingInput(123);
});

// Agregar reaccion
chat.addReaction(456, 123, '👍');
*/
