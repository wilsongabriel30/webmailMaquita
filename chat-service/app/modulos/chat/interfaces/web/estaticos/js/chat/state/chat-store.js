/**
 * ╔══════════════════════════════════════════════════════════════════════════════╗
 * ║                        CHAT STORE - GESTOR DE ESTADO                         ║
 * ║                  Estado centralizado del modulo de chat                      ║
 * ╚══════════════════════════════════════════════════════════════════════════════╝
 *
 * Implementacion de store reactivo para el chat.
 * Patron: Single Source of Truth + Observer
 *
 * Estructura del estado:
 * {
 *     user: { id, name, avatar, status },
 *     conversations: Map<id, Conversation>,
 *     messages: Map<conversationId, Message[]>,
 *     currentConversation: id | null,
 *     onlineUsers: Set<userId>,
 *     typingUsers: Map<conversationId, Set<userId>>,
 *     unreadCounts: Map<conversationId, number>,
 *     connection: { status, latency },
 *     ui: { theme, sidebarOpen }
 * }
 *
 * USO:
 *   import { chatStore } from './state/chat-store.js';
 *
 *   // Obtener estado
 *   const user = chatStore.get('user');
 *
 *   // Actualizar estado
 *   chatStore.set('currentConversation', 123);
 *
 *   // Suscribirse a cambios
 *   chatStore.subscribe('messages', (messages) => { ... });
 *
 * Autor: Wilson Arguello
 * Fecha: 2026-01-02
 */

import { EventEmitter, eventBus } from '../core/event-emitter.js';
import { EVENTS, MESSAGE_STATUS, USER_STATUS, MESSAGE_CONFIG } from '../core/config.js';
import { logState, saveToStorage, getFromStorage } from '../core/utils.js';

// ============================================================================
// CLASE PRINCIPAL
// ============================================================================

class ChatStore extends EventEmitter {
    constructor() {
        super();

        // Estado inicial
        this._state = {
            // Usuario actual
            user: null,

            // Conversaciones: Map<id, ConversationData>
            conversations: new Map(),

            // Mensajes: Map<conversationId, Message[]>
            messages: new Map(),

            // Conversacion activa
            currentConversation: null,

            // Usuarios online: Set<userId>
            onlineUsers: new Set(),

            // Usuarios escribiendo: Map<conversationId, Map<userId, timestamp>>
            typingUsers: new Map(),

            // Contador no leidos: Map<conversationId, number>
            unreadCounts: new Map(),

            // Estado de conexion
            connection: {
                status: 'disconnected', // disconnected, connecting, connected
                latency: 0,
                lastError: null,
            },

            // Estado de UI
            ui: {
                theme: 'light',
                sidebarOpen: true,
                searchQuery: '',
                replyingTo: null,
                editingMessage: null,
            },

            // Mensajes pendientes (optimistic updates)
            pendingMessages: new Map(),
        };

        // Cargar estado persistido
        this._loadPersistedState();

        logState('ChatStore inicializado');
    }

    // ========================================================================
    // GETTERS BASICOS
    // ========================================================================

    /**
     * Obtiene un valor del estado
     * @param {string} key - Clave del estado
     * @returns {*}
     */
    get(key) {
        return this._state[key];
    }

    /**
     * Obtiene el estado completo (solo lectura)
     * @returns {Object}
     */
    getState() {
        return { ...this._state };
    }

    /**
     * Obtiene usuario actual
     * @returns {Object|null}
     */
    get user() {
        return this._state.user;
    }

    /**
     * Obtiene conversacion actual
     * @returns {Object|null}
     */
    get currentConversation() {
        if (!this._state.currentConversation) return null;
        return this._state.conversations.get(this._state.currentConversation);
    }

    /**
     * Obtiene mensajes de la conversacion actual
     * @returns {Array}
     */
    get currentMessages() {
        if (!this._state.currentConversation) return [];
        return this._state.messages.get(this._state.currentConversation) || [];
    }

    // ========================================================================
    // SETTERS Y MUTACIONES
    // ========================================================================

    /**
     * Establece un valor en el estado
     * @param {string} key - Clave
     * @param {*} value - Valor
     */
    set(key, value) {
        const oldValue = this._state[key];
        this._state[key] = value;

        logState(`Set ${key}:`, value);

        // Notificar cambio
        this.emit(`change:${key}`, { value, oldValue });
        this.emit('change', { key, value, oldValue });
        eventBus.emit(EVENTS.STATE_CHANGED, { key, value, oldValue });
    }

    /**
     * Actualiza parcialmente el estado
     * @param {Object} partial - Objeto con valores a actualizar
     */
    update(partial) {
        Object.entries(partial).forEach(([key, value]) => {
            this.set(key, value);
        });
    }

    // ========================================================================
    // USUARIO
    // ========================================================================

    /**
     * Establece el usuario actual
     * @param {Object} userData - Datos del usuario
     */
    setUser(userData) {
        this.set('user', {
            id: userData.id,
            name: userData.name || userData.nombre,
            avatar: userData.avatar || userData.foto,
            email: userData.email || userData.correo,
            status: USER_STATUS.ONLINE,
        });
    }

    /**
     * Actualiza estado del usuario
     * @param {string} status - Nuevo estado
     */
    setUserStatus(status) {
        if (this._state.user) {
            this.set('user', { ...this._state.user, status });
        }
    }

    // ========================================================================
    // CONVERSACIONES
    // ========================================================================

    /**
     * Agrega o actualiza una conversacion
     * @param {Object} conversation - Datos de conversacion
     */
    setConversation(conversation) {
        const conversations = new Map(this._state.conversations);
        conversations.set(conversation.id, {
            ...conversations.get(conversation.id),
            ...conversation,
            updatedAt: Date.now(),
        });
        this.set('conversations', conversations);
    }

    /**
     * Agrega multiples conversaciones
     * @param {Array} conversationList - Lista de conversaciones
     */
    setConversations(conversationList) {
        const conversations = new Map(this._state.conversations);
        conversationList.forEach(conv => {
            conversations.set(conv.id, {
                ...conversations.get(conv.id),
                ...conv,
            });
        });
        this.set('conversations', conversations);
    }

    /**
     * Obtiene conversacion por ID
     * @param {number|string} id - ID de conversacion
     * @returns {Object|null}
     */
    getConversation(id) {
        return this._state.conversations.get(id) || null;
    }

    /**
     * Obtiene lista de conversaciones ordenadas
     * @returns {Array}
     */
    getConversationList() {
        return Array.from(this._state.conversations.values())
            .sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0));
    }

    /**
     * Establece conversacion activa
     * @param {number|string|null} conversationId - ID o null
     */
    setCurrentConversation(conversationId) {
        const previous = this._state.currentConversation;

        this.set('currentConversation', conversationId);

        // Emitir eventos especificos
        if (previous) {
            eventBus.emit(EVENTS.CONVERSATION_LEFT, { conversationId: previous });
        }
        if (conversationId) {
            eventBus.emit(EVENTS.CONVERSATION_JOINED, { conversationId });
        }
    }

    // ========================================================================
    // MENSAJES
    // ========================================================================

    /**
     * Agrega un mensaje a una conversacion
     * @param {number|string} conversationId - ID de conversacion
     * @param {Object} message - Mensaje a agregar
     */
    addMessage(conversationId, message) {
        const messages = new Map(this._state.messages);
        const convMessages = [...(messages.get(conversationId) || [])];

        // Evitar duplicados
        const existingIndex = convMessages.findIndex(
            m => (m.id && m.id === message.id) || (m.tempId && m.tempId === message.tempId)
        );

        if (existingIndex >= 0) {
            // Actualizar mensaje existente
            convMessages[existingIndex] = { ...convMessages[existingIndex], ...message };
        } else {
            // Agregar nuevo
            convMessages.push(message);
        }

        // Ordenar por timestamp
        convMessages.sort((a, b) => (a.timestamp || 0) - (b.timestamp || 0));

        // Limitar cache
        if (convMessages.length > MESSAGE_CONFIG.CACHE_MESSAGES) {
            convMessages.splice(0, convMessages.length - MESSAGE_CONFIG.CACHE_MESSAGES);
        }

        messages.set(conversationId, convMessages);
        this.set('messages', messages);

        // Actualizar conversacion
        this._updateConversationLastMessage(conversationId, message);

        logState(`Mensaje agregado a ${conversationId}:`, message.id || message.tempId);
    }

    /**
     * Agrega multiples mensajes
     * @param {number|string} conversationId - ID de conversacion
     * @param {Array} messageList - Lista de mensajes
     */
    addMessages(conversationId, messageList) {
        const messages = new Map(this._state.messages);
        const convMessages = [...(messages.get(conversationId) || [])];

        messageList.forEach(message => {
            const existingIndex = convMessages.findIndex(
                m => (m.id && m.id === message.id)
            );

            if (existingIndex < 0) {
                convMessages.push(message);
            }
        });

        convMessages.sort((a, b) => (a.timestamp || 0) - (b.timestamp || 0));

        messages.set(conversationId, convMessages);
        this.set('messages', messages);
    }

    /**
     * Obtiene mensajes de una conversacion
     * @param {number|string} conversationId - ID
     * @returns {Array}
     */
    getMessages(conversationId) {
        return this._state.messages.get(conversationId) || [];
    }

    /**
     * Actualiza estado de un mensaje
     * @param {string} tempId - ID temporal
     * @param {Object} updates - Actualizaciones
     */
    updateMessage(tempId, updates) {
        const messages = new Map(this._state.messages);

        for (const [convId, convMessages] of messages) {
            const index = convMessages.findIndex(m => m.tempId === tempId || m.id === tempId);
            if (index >= 0) {
                const updated = [...convMessages];
                updated[index] = { ...updated[index], ...updates };
                messages.set(convId, updated);
                this.set('messages', messages);
                return;
            }
        }
    }

    /**
     * Marca mensaje como entregado/guardado
     * @param {string} tempId - ID temporal
     * @param {number|string} realId - ID real de BD
     */
    confirmMessage(tempId, realId) {
        this.updateMessage(tempId, {
            id: realId,
            status: MESSAGE_STATUS.SENT,
        });

        // Remover de pendientes
        this._state.pendingMessages.delete(tempId);
    }

    /**
     * Marca mensaje como error
     * @param {string} tempId - ID temporal
     * @param {string} error - Mensaje de error
     */
    failMessage(tempId, error) {
        this.updateMessage(tempId, {
            status: MESSAGE_STATUS.ERROR,
            error: error,
        });
    }

    /**
     * Elimina un mensaje
     * @param {number|string} conversationId - ID conversacion
     * @param {number|string} messageId - ID mensaje
     */
    removeMessage(conversationId, messageId) {
        const messages = new Map(this._state.messages);
        const convMessages = messages.get(conversationId);

        if (convMessages) {
            const filtered = convMessages.filter(m => m.id !== messageId && m.tempId !== messageId);
            messages.set(conversationId, filtered);
            this.set('messages', messages);
        }
    }

    // ========================================================================
    // PRESENCIA Y TYPING
    // ========================================================================

    /**
     * Marca usuario como online
     * @param {number|string} userId - ID de usuario
     */
    setUserOnline(userId) {
        const onlineUsers = new Set(this._state.onlineUsers);
        onlineUsers.add(userId);
        this.set('onlineUsers', onlineUsers);
        eventBus.emit(EVENTS.USER_ONLINE, { userId });
    }

    /**
     * Marca usuario como offline
     * @param {number|string} userId - ID de usuario
     */
    setUserOffline(userId) {
        const onlineUsers = new Set(this._state.onlineUsers);
        onlineUsers.delete(userId);
        this.set('onlineUsers', onlineUsers);
        eventBus.emit(EVENTS.USER_OFFLINE, { userId });
    }

    /**
     * Verifica si usuario esta online
     * @param {number|string} userId - ID de usuario
     * @returns {boolean}
     */
    isUserOnline(userId) {
        return this._state.onlineUsers.has(userId);
    }

    /**
     * Establece que usuario esta escribiendo
     * @param {number|string} conversationId - ID conversacion
     * @param {number|string} userId - ID usuario
     */
    setUserTyping(conversationId, userId) {
        const typingUsers = new Map(this._state.typingUsers);
        if (!typingUsers.has(conversationId)) {
            typingUsers.set(conversationId, new Map());
        }
        typingUsers.get(conversationId).set(userId, Date.now());
        this.set('typingUsers', typingUsers);
        eventBus.emit(EVENTS.USER_TYPING, { conversationId, userId });
    }

    /**
     * Quita indicador de escribiendo
     * @param {number|string} conversationId - ID conversacion
     * @param {number|string} userId - ID usuario
     */
    clearUserTyping(conversationId, userId) {
        const typingUsers = new Map(this._state.typingUsers);
        if (typingUsers.has(conversationId)) {
            typingUsers.get(conversationId).delete(userId);
        }
        this.set('typingUsers', typingUsers);
        eventBus.emit(EVENTS.USER_STOP_TYPING, { conversationId, userId });
    }

    /**
     * Obtiene usuarios escribiendo en una conversacion
     * @param {number|string} conversationId - ID
     * @returns {Array<number|string>}
     */
    getTypingUsers(conversationId) {
        const convTyping = this._state.typingUsers.get(conversationId);
        return convTyping ? Array.from(convTyping.keys()) : [];
    }

    // ========================================================================
    // NO LEIDOS
    // ========================================================================

    /**
     * Establece contador de no leidos
     * @param {number|string} conversationId - ID
     * @param {number} count - Cantidad
     */
    setUnreadCount(conversationId, count) {
        const unreadCounts = new Map(this._state.unreadCounts);
        unreadCounts.set(conversationId, count);
        this.set('unreadCounts', unreadCounts);
    }

    /**
     * Incrementa contador de no leidos
     * @param {number|string} conversationId - ID
     */
    incrementUnread(conversationId) {
        const current = this._state.unreadCounts.get(conversationId) || 0;
        this.setUnreadCount(conversationId, current + 1);
    }

    /**
     * Limpia no leidos de una conversacion
     * @param {number|string} conversationId - ID
     */
    clearUnread(conversationId) {
        this.setUnreadCount(conversationId, 0);
        eventBus.emit(EVENTS.MESSAGES_READ, { conversationId });
    }

    /**
     * Obtiene total de mensajes no leidos
     * @returns {number}
     */
    getTotalUnread() {
        let total = 0;
        this._state.unreadCounts.forEach(count => total += count);
        return total;
    }

    // ========================================================================
    // CONEXION
    // ========================================================================

    /**
     * Actualiza estado de conexion
     * @param {string} status - Estado
     * @param {Object} extra - Datos adicionales
     */
    setConnectionStatus(status, extra = {}) {
        this.set('connection', {
            ...this._state.connection,
            status,
            ...extra,
        });

        // Emitir eventos
        if (status === 'connected') {
            eventBus.emit(EVENTS.CONNECT);
        } else if (status === 'disconnected') {
            eventBus.emit(EVENTS.DISCONNECT, extra);
        }
    }

    /**
     * Actualiza latencia
     * @param {number} latency - Latencia en ms
     */
    setLatency(latency) {
        this.set('connection', {
            ...this._state.connection,
            latency,
        });
    }

    // ========================================================================
    // UI
    // ========================================================================

    /**
     * Actualiza estado de UI
     * @param {Object} updates - Actualizaciones
     */
    updateUI(updates) {
        this.set('ui', {
            ...this._state.ui,
            ...updates,
        });
    }

    /**
     * Cambia tema
     * @param {string} theme - 'light' | 'dark'
     */
    setTheme(theme) {
        this.updateUI({ theme });
        saveToStorage('chat_theme', theme);
        eventBus.emit(EVENTS.UI_THEME_CHANGED, { theme });
    }

    /**
     * Establece mensaje para responder
     * @param {Object|null} message - Mensaje o null
     */
    setReplyingTo(message) {
        this.updateUI({ replyingTo: message });
    }

    /**
     * Establece mensaje para editar
     * @param {Object|null} message - Mensaje o null
     */
    setEditingMessage(message) {
        this.updateUI({ editingMessage: message });
    }

    // ========================================================================
    // PERSISTENCIA
    // ========================================================================

    _loadPersistedState() {
        // Cargar tema
        const theme = getFromStorage('chat_theme', 'light');
        this._state.ui.theme = theme;

        // Cargar borradores (opcional)
        // ...
    }

    _updateConversationLastMessage(conversationId, message) {
        const conversation = this._state.conversations.get(conversationId);
        if (conversation) {
            this.setConversation({
                ...conversation,
                lastMessage: {
                    content: message.content,
                    senderId: message.senderId,
                    timestamp: message.timestamp,
                },
                updatedAt: message.timestamp || Date.now(),
            });
        }
    }

    // ========================================================================
    // SUSCRIPCIONES
    // ========================================================================

    /**
     * Suscribe a cambios en una clave especifica
     * @param {string} key - Clave del estado
     * @param {Function} callback - Callback
     * @returns {Function} - Funcion para desuscribirse
     */
    subscribe(key, callback) {
        return this.on(`change:${key}`, ({ value }) => callback(value));
    }

    /**
     * Suscribe a cualquier cambio
     * @param {Function} callback - Callback
     * @returns {Function} - Funcion para desuscribirse
     */
    subscribeAll(callback) {
        return this.on('change', callback);
    }

    // ========================================================================
    // RESET
    // ========================================================================

    /**
     * Resetea el estado a valores iniciales
     */
    reset() {
        this._state.conversations.clear();
        this._state.messages.clear();
        this._state.onlineUsers.clear();
        this._state.typingUsers.clear();
        this._state.unreadCounts.clear();
        this._state.pendingMessages.clear();
        this._state.currentConversation = null;
        this._state.user = null;

        this.emit('reset');
        logState('Estado reseteado');
    }
}

// ============================================================================
// SINGLETON
// ============================================================================

export const chatStore = new ChatStore();

// Hacer accesible globalmente para debug
if (typeof window !== 'undefined') {
    window.__chatStore = chatStore;
}

export default chatStore;
