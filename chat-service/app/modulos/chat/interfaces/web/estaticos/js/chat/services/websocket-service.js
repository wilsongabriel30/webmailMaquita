/**
 * ╔══════════════════════════════════════════════════════════════════════════════╗
 * ║                     WEBSOCKET SERVICE - CHAT MODULAR                         ║
 * ║              100% WebSocket - Sin HTTP para operaciones de chat              ║
 * ╚══════════════════════════════════════════════════════════════════════════════╝
 *
 * IMPORTANTE: Este servicio maneja TODAS las operaciones de chat via WebSocket.
 * NO usa HTTP para ninguna operacion de chat (solo para upload de archivos).
 *
 * Caracteristicas:
 * - Conexion/reconexion automatica
 * - ACK instantaneo (optimistic updates)
 * - Cola offline con retry
 * - Carga de datos inicial via WebSocket
 * - Indicadores de typing
 * - Presencia online/offline
 * - Medicion de latencia
 * - CERO POLLING - Todo es push en tiempo real
 *
 * Autor: Wilson Arguello
 * Fecha: 2026-01-02
 */

import { EventEmitter, eventBus } from '../core/event-emitter.js';
import {
    WEBSOCKET_CONFIG,
    MESSAGE_CONFIG,
    UI_CONFIG,
    EVENTS,
    MESSAGE_STATUS,
    MESSAGE_TYPES,
} from '../core/config.js';
import { generateTempId, now, logWS, throttle } from '../core/utils.js';
import { chatStore } from '../state/chat-store.js';

// ============================================================================
// CLASE PRINCIPAL
// ============================================================================

class WebSocketService extends EventEmitter {
    constructor() {
        super();

        this.socket = null;
        this.connected = false;
        this.reconnectAttempts = 0;

        // Colas y tracking
        this.offlineQueue = [];
        this.pendingAcks = new Map();       // tempId -> { timeout, resolve, reject }
        this.pendingRequests = new Map();   // requestId -> { resolve, reject, timeout }

        // Timers
        this.heartbeatTimer = null;
        this.typingTimer = null;

        // Request ID counter
        this._requestId = 0;

        logWS('WebSocketService inicializado - Modo 100% WebSocket');
    }

    // ========================================================================
    // CONEXION
    // ========================================================================

    /**
     * Conecta al servidor WebSocket
     * @returns {Promise<void>}
     */
    connect() {
        return new Promise((resolve, reject) => {
            if (this.connected) {
                resolve();
                return;
            }

            if (typeof io === 'undefined') {
                reject(new Error('Socket.IO no disponible'));
                return;
            }

            logWS('Conectando...');
            chatStore.setConnectionStatus('connecting');

            try {
                this.socket = io({
                    transports: ['websocket'],  // SOLO WebSocket, sin polling
                    upgrade: false,             // No upgrade desde polling
                    reconnection: true,
                    reconnectionDelay: WEBSOCKET_CONFIG.RECONNECT_DELAY,
                    reconnectionDelayMax: WEBSOCKET_CONFIG.RECONNECT_MAX_DELAY,
                    reconnectionAttempts: WEBSOCKET_CONFIG.RECONNECT_ATTEMPTS,
                    timeout: WEBSOCKET_CONFIG.CONNECTION_TIMEOUT,
                    forceNew: false,
                });

                this._setupEventHandlers(resolve, reject);

            } catch (error) {
                logWS('Error creando socket:', error);
                chatStore.setConnectionStatus('disconnected', { lastError: error.message });
                reject(error);
            }
        });
    }

    disconnect() {
        logWS('Desconectando...');
        this._stopHeartbeat();
        this._clearTypingTimer();
        this._clearAllPendingRequests('Desconectado');

        if (this.socket) {
            this.socket.disconnect();
            this.socket = null;
        }

        this.connected = false;
        chatStore.setConnectionStatus('disconnected');
    }

    async reconnect() {
        this.disconnect();
        return this.connect();
    }

    // ========================================================================
    // EVENT HANDLERS
    // ========================================================================

    _setupEventHandlers(resolve, reject) {
        // === CONEXION ===
        this.socket.on('connect', () => {
            logWS('Conectado');
            const wasReconnect = this.connected === false && this.reconnectAttempts > 0;
            this.connected = true;
            this.reconnectAttempts = 0;
            chatStore.setConnectionStatus('connected');

            this._startHeartbeat();
            this._flushOfflineQueue();

            // Reconectar a conversacion actual y sincronizar mensajes perdidos
            const currentConv = chatStore.get('currentConversation');
            if (currentConv) {
                this.joinConversation(currentConv);

                // Si es reconexion, sincronizar mensajes que pudimos perder
                if (wasReconnect) {
                    const messages = chatStore.getMessages(currentConv);
                    const lastMsg = messages?.[messages.length - 1];
                    if (lastMsg?.id && !String(lastMsg.id).startsWith('temp_')) {
                        logWS('Sincronizando tras reconexion desde mensaje:', lastMsg.id);
                        this.syncConversation(currentConv, lastMsg.id);
                    }
                }
            }

            resolve();
        });

        this.socket.on('disconnect', (reason) => {
            logWS('Desconectado:', reason);
            this.connected = false;
            this._stopHeartbeat();
            chatStore.setConnectionStatus('disconnected', { reason });
        });

        this.socket.on('reconnect_attempt', (attempt) => {
            logWS('Reintentando...', attempt);
            this.reconnectAttempts = attempt;
            chatStore.setConnectionStatus('connecting');
            eventBus.emit(EVENTS.RECONNECTING, { attempt });
        });

        this.socket.on('connect_error', (error) => {
            logWS('Error conexion:', error.message);
            if (this.reconnectAttempts >= WEBSOCKET_CONFIG.RECONNECT_ATTEMPTS) {
                chatStore.setConnectionStatus('disconnected', { lastError: 'Max intentos' });
                reject(new Error('Max reconnect attempts'));
            }
        });

        // === RESPUESTAS A REQUESTS ===
        this.socket.on('response', (data) => {
            this._handleResponse(data);
        });

        // === MENSAJES ===
        this.socket.on('ack', (data) => {
            logWS('ACK:', data.t);
            this._handleAck(data);
        });

        this.socket.on('msg_saved', (data) => {
            logWS('Guardado:', data.t, '->', data.id);
            this._handleMessageSaved(data);
        });

        // NUEVO: Manejo de msg_failed para errores de envio
        this.socket.on('msg_failed', (data) => {
            logWS('FAILED:', data.t, data.code, data.reason);
            this._handleMessageFailed(data);
        });

        this.socket.on('msg', (data) => {
            this._handleNewMessage(data);
            // Confirmar delivery al servidor
            if (data.id) {
                this.socket.emit('delivered', { id: data.id, c: data.c });
            }
        });

        this.socket.on('new_message', (data) => {
            this._handleNewMessage(data);
            // Confirmar delivery
            if (data.id) {
                this.socket.emit('delivered', { id: data.id, c: data.conversationId });
            }
        });

        this.socket.on('message_edited', (data) => {
            this._handleMessageEdited(data);
        });

        this.socket.on('message_deleted', (data) => {
            this._handleMessageDeleted(data);
        });

        // NUEVO: Estados de mensaje (delivered/read)
        this.socket.on('msg_status', (data) => {
            this._handleMessageStatus(data);
        });

        this.socket.on('msg_status_batch', (data) => {
            this._handleMessageStatusBatch(data);
        });

        // NUEVO: Sync para reconexion
        this.socket.on('sync_messages', (data) => {
            logWS('Sync recibido:', data.total);
            this._handleSyncMessages(data);
        });

        // === DATOS CARGADOS ===
        this.socket.on('conversations_list', (data) => {
            logWS('Conversaciones recibidas:', data.length || data.conversaciones?.length);
            this._handleConversationsList(data);
        });

        this.socket.on('messages_list', (data) => {
            logWS('Mensajes recibidos:', data.mensajes?.length);
            this._handleMessagesList(data);
        });

        this.socket.on('conversation_data', (data) => {
            logWS('Datos conversacion:', data.id);
            this._handleConversationData(data);
        });

        // === TYPING ===
        this.socket.on('typ', (data) => {
            this._handleTyping(data, true);
        });

        this.socket.on('styp', (data) => {
            this._handleTyping(data, false);
        });

        this.socket.on('user_typing', (data) => {
            this._handleTyping({ u: data.user_id, c: data.conversation_id }, true);
        });

        this.socket.on('user_stopped_typing', (data) => {
            this._handleTyping({ u: data.user_id, c: data.conversation_id }, false);
        });

        // === PRESENCIA ===
        this.socket.on('online', (data) => {
            chatStore.setUserOnline(data.u || data.user_id);
        });

        this.socket.on('offline', (data) => {
            chatStore.setUserOffline(data.u || data.user_id);
        });

        this.socket.on('user_presence', (data) => {
            if (data.status === 'online') {
                chatStore.setUserOnline(data.user_id);
            } else {
                chatStore.setUserOffline(data.user_id);
            }
        });

        this.socket.on('presence_list', (data) => {
            logWS('Lista presencia:', data.users?.length);
            (data.users || data).forEach(u => {
                if (u.online) chatStore.setUserOnline(u.id);
            });
        });

        // === LECTURA ===
        this.socket.on('rd', (data) => {
            eventBus.emit(EVENTS.MESSAGES_READ, { userId: data.u, conversationId: data.c });
        });

        this.socket.on('messages_read', (data) => {
            eventBus.emit(EVENTS.MESSAGES_READ, data);
        });

        // === REACCIONES ===
        this.socket.on('reaction_added', (data) => {
            eventBus.emit(EVENTS.REACTION_ADDED, data);
        });

        this.socket.on('reaction_removed', (data) => {
            eventBus.emit(EVENTS.REACTION_REMOVED, data);
        });

        // === HEARTBEAT ===
        this.socket.on('heartbeat_ack', () => {});

        this.socket.on('pong_chat', () => {
            const latency = now() - this._lastPing;
            chatStore.setLatency(latency);
        });

        // === CONVERSACIONES ===
        this.socket.on('joined_conversation', (data) => {
            logWS('Unido a:', data.conversation_id || data.c);
        });

        this.socket.on('conversation_created', (data) => {
            logWS('Conversacion creada:', data.id);
            chatStore.setConversation(data);
            eventBus.emit(EVENTS.CONVERSATION_NEW, data);
        });

        this.socket.on('conversation_updated', (data) => {
            chatStore.setConversation(data);
            eventBus.emit(EVENTS.CONVERSATION_UPDATED, data);
        });

        // === BUSQUEDA ===
        this.socket.on('search_results', (data) => {
            logWS('Resultados busqueda:', data.total);
            this._handleResponse({ ...data, _requestId: data._requestId });
        });
    }

    // ========================================================================
    // SISTEMA DE REQUEST/RESPONSE VIA WEBSOCKET
    // ========================================================================

    /**
     * Envia un request y espera respuesta via WebSocket
     * @param {string} event - Evento a emitir
     * @param {Object} data - Datos a enviar
     * @param {number} timeout - Timeout en ms
     * @returns {Promise<Object>}
     */
    request(event, data = {}, timeout = 10000) {
        return new Promise((resolve, reject) => {
            if (!this.connected) {
                reject(new Error('No conectado'));
                return;
            }

            const requestId = ++this._requestId;
            const timeoutId = setTimeout(() => {
                this.pendingRequests.delete(requestId);
                reject(new Error('Timeout'));
            }, timeout);

            this.pendingRequests.set(requestId, { resolve, reject, timeout: timeoutId });

            this.socket.emit(event, { ...data, _requestId: requestId });
            logWS('Request:', event, requestId);
        });
    }

    _handleResponse(data) {
        const requestId = data._requestId;
        if (!requestId) return;

        const pending = this.pendingRequests.get(requestId);
        if (pending) {
            clearTimeout(pending.timeout);
            this.pendingRequests.delete(requestId);

            if (data.error) {
                pending.reject(new Error(data.error));
            } else {
                pending.resolve(data);
            }
        }
    }

    _clearAllPendingRequests(reason) {
        this.pendingRequests.forEach(({ reject, timeout }) => {
            clearTimeout(timeout);
            reject(new Error(reason));
        });
        this.pendingRequests.clear();
    }

    // ========================================================================
    // CARGAR DATOS VIA WEBSOCKET (NO HTTP!)
    // ========================================================================

    /**
     * Carga lista de conversaciones via WebSocket
     * @returns {Promise<Array>}
     */
    async loadConversations() {
        if (!this.connected) {
            throw new Error('No conectado');
        }

        logWS('Solicitando conversaciones...');
        this.socket.emit('get_conversations', {});

        // Esperar respuesta via evento
        return new Promise((resolve, reject) => {
            const timeout = setTimeout(() => {
                reject(new Error('Timeout cargando conversaciones'));
            }, 10000);

            const handler = (data) => {
                clearTimeout(timeout);
                const conversations = data.conversaciones || data.data || data;
                resolve(Array.isArray(conversations) ? conversations : []);
            };

            this.socket.once('conversations_list', handler);
        });
    }

    /**
     * Carga mensajes de una conversacion via WebSocket
     * @param {number|string} conversationId
     * @param {Object} options - { limit, before, after }
     * @returns {Promise<Object>}
     */
    async loadMessages(conversationId, options = {}) {
        if (!this.connected) {
            throw new Error('No conectado');
        }

        logWS('Solicitando mensajes de:', conversationId);

        this.socket.emit('get_messages', {
            conversation_id: conversationId,
            c: conversationId,
            limit: options.limit || 50,
            before: options.before,
            after: options.after,
        });

        return new Promise((resolve, reject) => {
            const timeout = setTimeout(() => {
                reject(new Error('Timeout cargando mensajes'));
            }, 10000);

            const handler = (data) => {
                if (data.conversation_id == conversationId || data.c == conversationId) {
                    clearTimeout(timeout);
                    resolve({
                        mensajes: data.mensajes || data.messages || data.data || [],
                        hasMore: data.has_more || data.hasMore || false,
                        total: data.total || 0,
                    });
                }
            };

            this.socket.once('messages_list', handler);
        });
    }

    /**
     * Obtiene o crea conversacion directa via WebSocket
     * @param {number|string} userId
     * @returns {Promise<Object>}
     */
    async getOrCreateDirectConversation(userId) {
        if (!this.connected) {
            throw new Error('No conectado');
        }

        logWS('Obteniendo/creando chat directo con:', userId);

        this.socket.emit('get_or_create_direct', {
            user_id: userId,
            usuario_id: userId,
        });

        return new Promise((resolve, reject) => {
            const timeout = setTimeout(() => {
                reject(new Error('Timeout'));
            }, 10000);

            const handler = (data) => {
                clearTimeout(timeout);
                resolve(data.conversacion || data.conversation || data);
            };

            this.socket.once('conversation_data', handler);
            this.socket.once('conversation_created', handler);
        });
    }

    /**
     * Crea nueva conversacion grupal via WebSocket
     * @param {Object} data - { nombre, participantes }
     * @returns {Promise<Object>}
     */
    async createGroupConversation(data) {
        if (!this.connected) {
            throw new Error('No conectado');
        }

        this.socket.emit('create_group', data);

        return new Promise((resolve, reject) => {
            const timeout = setTimeout(() => reject(new Error('Timeout')), 10000);

            this.socket.once('conversation_created', (conv) => {
                clearTimeout(timeout);
                resolve(conv);
            });
        });
    }

    /**
     * Busca mensajes via WebSocket
     * @param {string} query
     * @param {Object} options
     * @returns {Promise<Object>}
     */
    async searchMessages(query, options = {}) {
        if (!this.connected) {
            throw new Error('No conectado');
        }

        this.socket.emit('search_messages', {
            q: query,
            query: query,
            conversation_id: options.conversationId,
            limit: options.limit || 20,
        });

        return new Promise((resolve, reject) => {
            const timeout = setTimeout(() => reject(new Error('Timeout')), 10000);

            this.socket.once('search_results', (data) => {
                clearTimeout(timeout);
                resolve({
                    resultados: data.resultados || data.results || [],
                    total: data.total || 0,
                });
            });
        });
    }

    /**
     * Obtiene usuarios online via WebSocket
     * @param {Array} userIds - IDs de usuarios a consultar
     * @returns {Promise<Object>}
     */
    async getOnlineUsers(userIds = []) {
        if (!this.connected) return {};

        this.socket.emit('get_presence', { user_ids: userIds });

        return new Promise((resolve) => {
            const timeout = setTimeout(() => resolve({}), 5000);

            this.socket.once('presence_list', (data) => {
                clearTimeout(timeout);
                resolve(data);
            });
        });
    }

    // ========================================================================
    // HANDLERS DE DATOS
    // ========================================================================

    _handleConversationsList(data) {
        const conversations = data.conversaciones || data.data || data;
        if (Array.isArray(conversations)) {
            chatStore.setConversations(conversations);
        }
    }

    _handleMessagesList(data) {
        const conversationId = data.conversation_id || data.c;
        const messages = data.mensajes || data.messages || data.data || [];

        if (conversationId && Array.isArray(messages)) {
            chatStore.addMessages(conversationId, messages);
        }
    }

    _handleConversationData(data) {
        const conversation = data.conversacion || data.conversation || data;
        if (conversation && conversation.id) {
            chatStore.setConversation(conversation);
        }
    }

    // ========================================================================
    // HANDLERS DE MENSAJES
    // ========================================================================

    _handleAck(data) {
        const pending = this.pendingAcks.get(data.t);
        if (pending) {
            clearTimeout(pending.timeout);
            chatStore.updateMessage(data.t, { status: MESSAGE_STATUS.SENT });
            eventBus.emit(EVENTS.MESSAGE_ACK, { tempId: data.t });
        }
    }

    _handleMessageSaved(data) {
        const pending = this.pendingAcks.get(data.t);

        if (data.s === 'saved' && data.id) {
            chatStore.confirmMessage(data.t, data.id);
            eventBus.emit(EVENTS.MESSAGE_SAVED, { tempId: data.t, realId: data.id });

            if (pending) {
                pending.resolve({ tempId: data.t, realId: data.id });
            }
        } else {
            chatStore.failMessage(data.t, data.error || 'Error');
            eventBus.emit(EVENTS.MESSAGE_ERROR, { tempId: data.t, error: data.error });

            if (pending) {
                pending.reject(new Error(data.error || 'Error'));
            }
        }

        this.pendingAcks.delete(data.t);
    }

    _handleNewMessage(data) {
        const userId = chatStore.user?.id;

        // Ignorar mensajes propios
        if (data.from == userId || data.senderId == userId) {
            return;
        }

        const message = {
            id: data.id,
            tempId: data.t,
            conversationId: data.c || data.conversationId || data.conversation_id,
            content: data.m || data.content || data.contenido,
            senderId: data.from || data.senderId || data.sender_id,
            timestamp: data.ts || data.timestamp || now(),
            type: data.type || MESSAGE_TYPES.TEXT,
            status: MESSAGE_STATUS.DELIVERED,
        };

        chatStore.addMessage(message.conversationId, message);
        eventBus.emit(EVENTS.MESSAGE_RECEIVED, message);

        if (message.conversationId !== chatStore.get('currentConversation')) {
            chatStore.incrementUnread(message.conversationId);
        }
    }

    _handleMessageEdited(data) {
        chatStore.updateMessage(data.message_id || data.id, {
            content: data.content || data.contenido,
            editedAt: data.editedAt || now(),
        });
        eventBus.emit(EVENTS.MESSAGE_EDITED, data);
    }

    _handleMessageDeleted(data) {
        chatStore.removeMessage(
            data.conversation_id || data.conversationId,
            data.message_id || data.id
        );
        eventBus.emit(EVENTS.MESSAGE_DELETED, data);
    }

    _handleTyping(data, isTyping) {
        const conversationId = data.c || data.conversationId;
        const userId = data.u || data.userId;

        if (isTyping) {
            chatStore.setUserTyping(conversationId, userId);
            setTimeout(() => {
                chatStore.clearUserTyping(conversationId, userId);
            }, UI_CONFIG.TYPING_INDICATOR_DURATION);
        } else {
            chatStore.clearUserTyping(conversationId, userId);
        }
    }

    // ========================================================================
    // HANDLERS NUEVOS: msg_failed, sync, status
    // ========================================================================

    /**
     * Maneja cuando un mensaje falla al enviarse
     */
    _handleMessageFailed(data) {
        const tempId = data.t;
        const pending = this.pendingAcks.get(tempId);

        // Actualizar estado en store
        chatStore.failMessage(tempId, data.reason);

        // Emitir evento para UI
        eventBus.emit(EVENTS.MESSAGE_ERROR, {
            tempId,
            reason: data.reason,
            code: data.code,
            retry: data.retry,
        });

        // Si es reintentable y no excedemos limite, reintentar
        if (data.retry && pending && pending.retries < 3) {
            pending.retries = (pending.retries || 0) + 1;
            logWS('Reintentando mensaje:', tempId, 'intento', pending.retries);

            setTimeout(() => {
                const msg = chatStore.getMessage(tempId);
                if (msg) {
                    this.socket.emit('send', {
                        c: msg.conversationId,
                        m: msg.content,
                        t: tempId,
                        type: msg.type,
                    });
                }
            }, 1000 * pending.retries); // Backoff exponencial simple
        } else {
            // No reintentar mas
            if (pending) {
                clearTimeout(pending.timeout);
                pending.reject(new Error(data.reason));
                this.pendingAcks.delete(tempId);
            }
        }
    }

    /**
     * Maneja mensajes sincronizados tras reconexion
     */
    _handleSyncMessages(data) {
        const conversationId = data.c;
        const mensajes = data.mensajes || [];

        if (!conversationId || mensajes.length === 0) return;

        // Agregar mensajes faltantes al store
        mensajes.forEach(msg => {
            const exists = chatStore.getMessage(msg.id);
            if (!exists) {
                chatStore.addMessage(conversationId, {
                    id: msg.id,
                    conversationId,
                    content: msg.contenido || msg.content,
                    senderId: msg.remitente_id || msg.senderId,
                    timestamp: msg.creado_en || msg.timestamp,
                    type: msg.tipo || msg.type || 'text',
                    status: MESSAGE_STATUS.DELIVERED,
                });
            }
        });

        eventBus.emit(EVENTS.MESSAGES_SYNCED, {
            conversationId,
            count: mensajes.length,
            syncedAt: data.synced_at,
        });
    }

    /**
     * Maneja actualizacion de estado individual (delivered/read)
     */
    _handleMessageStatus(data) {
        const messageId = data.id;
        const status = data.status; // 'delivered' or 'read'

        chatStore.updateMessage(messageId, {
            status: status === 'read' ? MESSAGE_STATUS.READ : MESSAGE_STATUS.DELIVERED,
        });

        eventBus.emit(EVENTS.MESSAGE_STATUS_UPDATED, {
            messageId,
            status,
            by: data.by,
            timestamp: data.ts,
        });
    }

    /**
     * Maneja actualizacion de estado en batch (mas eficiente)
     */
    _handleMessageStatusBatch(data) {
        const conversationId = data.c;
        const upToId = data.up_to_id;
        const status = data.status;

        // Actualizar todos los mensajes hasta upToId
        const messages = chatStore.getMessages(conversationId) || [];
        messages.forEach(msg => {
            if (msg.id <= upToId && msg.senderId === chatStore.user?.id) {
                chatStore.updateMessage(msg.id, {
                    status: status === 'read' ? MESSAGE_STATUS.READ : MESSAGE_STATUS.DELIVERED,
                });
            }
        });

        eventBus.emit(EVENTS.MESSAGE_STATUS_BATCH, {
            conversationId,
            upToId,
            status,
            by: data.by,
        });
    }

    // ========================================================================
    // SYNC / RECONEXION
    // ========================================================================

    /**
     * Sincroniza mensajes perdidos tras reconexion
     * @param {number|string} conversationId
     * @param {number} lastMessageId - Ultimo mensaje que el cliente tiene
     */
    syncConversation(conversationId, lastMessageId) {
        if (!this.connected) return;

        this.socket.emit('sync_chat', {
            c: conversationId,
            last_message_id: lastMessageId,
        });
    }

    /**
     * Marca mensajes como leidos en batch (mas eficiente)
     * @param {number|string} conversationId
     * @param {number} upToMessageId - Marcar todos hasta este ID
     */
    markReadBatch(conversationId, upToMessageId) {
        if (!this.connected) return;

        this.socket.emit('mark_read_batch', {
            c: conversationId,
            up_to_id: upToMessageId,
        });
        chatStore.clearUnread(conversationId);
    }

    // ========================================================================
    // ENVIO DE MENSAJES (100% WebSocket)
    // ========================================================================

    /**
     * Envia mensaje via WebSocket
     * @param {number|string} conversationId
     * @param {string} content
     * @param {Object} options
     * @returns {Promise<Object>}
     */
    sendMessage(conversationId, content, options = {}) {
        return new Promise((resolve, reject) => {
            if (!content?.trim()) {
                reject(new Error('Contenido vacio'));
                return;
            }

            const tempId = generateTempId();
            const timestamp = now();
            const type = options.type || MESSAGE_TYPES.TEXT;

            const message = {
                tempId,
                id: `temp_${tempId}`,
                conversationId,
                content: content.trim(),
                senderId: chatStore.user?.id,
                timestamp,
                type,
                status: MESSAGE_STATUS.PENDING,
                replyTo: options.replyTo || null,
            };

            // UI optimista
            chatStore.addMessage(conversationId, message);
            eventBus.emit(EVENTS.MESSAGE_SENT, message);

            // Timeout para ACK
            const timeout = setTimeout(() => {
                this.pendingAcks.delete(tempId);
                chatStore.failMessage(tempId, 'Timeout');
                reject(new Error('Timeout'));
            }, MESSAGE_CONFIG.MESSAGE_TIMEOUT);

            this.pendingAcks.set(tempId, { timeout, resolve, reject });

            if (this.connected) {
                chatStore.updateMessage(tempId, { status: MESSAGE_STATUS.SENDING });

                this.socket.emit('send', {
                    c: conversationId,
                    m: content.trim(),
                    t: tempId,
                    type,
                    reply_to: options.replyTo,
                });

                this._clearTypingTimer();
            } else {
                this._queueOffline(message);
            }

            logWS('Enviado:', tempId);
        });
    }

    editMessage(messageId, content) {
        if (!this.connected) return;
        this.socket.emit('edit_message', { message_id: messageId, content });
    }

    deleteMessage(messageId, conversationId, forAll = false) {
        if (!this.connected) return;
        this.socket.emit('delete_message', {
            message_id: messageId,
            conversation_id: conversationId,
            for_all: forAll,
        });
    }

    // ========================================================================
    // CONVERSACIONES
    // ========================================================================

    joinConversation(conversationId) {
        if (!this.connected) return;
        this.socket.emit('join_conversation', { conversation_id: conversationId });
        this.socket.emit('join', { c: conversationId });
        logWS('Join:', conversationId);
    }

    leaveConversation(conversationId) {
        if (!this.connected) return;
        this.socket.emit('leave_conversation', { conversation_id: conversationId });
        this.socket.emit('leave', { c: conversationId });
    }

    // ========================================================================
    // TYPING
    // ========================================================================

    startTyping = throttle((conversationId) => {
        if (!this.connected) return;

        this.socket.emit('typing_start', { conversation_id: conversationId });
        this.socket.emit('typing', { c: conversationId });

        this._clearTypingTimer();
        this.typingTimer = setTimeout(() => {
            this.stopTyping(conversationId);
        }, UI_CONFIG.TYPING_TIMEOUT);
    }, UI_CONFIG.TYPING_THROTTLE);

    stopTyping(conversationId) {
        if (!this.connected) return;
        this.socket.emit('typing_stop', { conversation_id: conversationId });
        this.socket.emit('stop_typing', { c: conversationId });
        this._clearTypingTimer();
    }

    _clearTypingTimer() {
        if (this.typingTimer) {
            clearTimeout(this.typingTimer);
            this.typingTimer = null;
        }
    }

    // ========================================================================
    // LECTURA Y REACCIONES
    // ========================================================================

    markRead(conversationId, untilMessageId = null) {
        if (!this.connected) return;
        this.socket.emit('mark_read', { conversation_id: conversationId, until_message_id: untilMessageId });
        this.socket.emit('read', { c: conversationId });
        chatStore.clearUnread(conversationId);
    }

    addReaction(messageId, conversationId, emoji) {
        if (!this.connected) return;
        this.socket.emit('add_reaction', { message_id: messageId, conversation_id: conversationId, emoji });
    }

    removeReaction(messageId, conversationId) {
        if (!this.connected) return;
        this.socket.emit('remove_reaction', { message_id: messageId, conversation_id: conversationId });
    }

    // ========================================================================
    // HEARTBEAT
    // ========================================================================

    _startHeartbeat() {
        this._stopHeartbeat();
        this.heartbeatTimer = setInterval(() => {
            if (this.connected) {
                this.socket.emit('heartbeat');
            }
        }, WEBSOCKET_CONFIG.HEARTBEAT_INTERVAL);
    }

    _stopHeartbeat() {
        if (this.heartbeatTimer) {
            clearInterval(this.heartbeatTimer);
            this.heartbeatTimer = null;
        }
    }

    ping() {
        return new Promise((resolve) => {
            if (!this.connected) {
                resolve(-1);
                return;
            }

            this._lastPing = now();
            this.socket.emit('ping_chat');

            const handler = () => {
                resolve(now() - this._lastPing);
            };

            this.socket.once('pong_chat', handler);
            setTimeout(() => {
                this.socket.off('pong_chat', handler);
                resolve(-1);
            }, 5000);
        });
    }

    // ========================================================================
    // COLA OFFLINE
    // ========================================================================

    _queueOffline(message) {
        if (this.offlineQueue.length >= MESSAGE_CONFIG.OFFLINE_QUEUE_MAX) {
            this.offlineQueue.shift();
        }
        this.offlineQueue.push(message);
        logWS('Encolado:', message.tempId);
    }

    _flushOfflineQueue() {
        while (this.offlineQueue.length > 0) {
            const msg = this.offlineQueue.shift();
            this.socket.emit('send', {
                c: msg.conversationId,
                m: msg.content,
                t: msg.tempId,
                type: msg.type,
            });
            chatStore.updateMessage(msg.tempId, { status: MESSAGE_STATUS.SENDING });
        }
    }

    // ========================================================================
    // ESTADO
    // ========================================================================

    isConnected() {
        return this.connected;
    }

    getStats() {
        return {
            connected: this.connected,
            reconnectAttempts: this.reconnectAttempts,
            offlineQueueLength: this.offlineQueue.length,
            pendingAcks: this.pendingAcks.size,
            pendingRequests: this.pendingRequests.size,
        };
    }
}

// ============================================================================
// SINGLETON
// ============================================================================

export const webSocketService = new WebSocketService();

if (typeof window !== 'undefined') {
    window.__webSocketService = webSocketService;
}

export default webSocketService;
