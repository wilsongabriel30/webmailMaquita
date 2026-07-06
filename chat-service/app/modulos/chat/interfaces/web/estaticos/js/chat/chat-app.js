/**
 * ╔══════════════════════════════════════════════════════════════════════════════╗
 * ║                          CHAT APP - ORQUESTADOR                              ║
 * ║                   Aplicacion principal que integra todo                      ║
 * ╚══════════════════════════════════════════════════════════════════════════════╝
 *
 * Clase principal que orquesta todos los componentes del chat.
 * Punto de entrada para la aplicacion de chat.
 *
 * USO:
 *   // Inicializacion basica
 *   const chat = new ChatApp({
 *       container: '#chat-app',
 *       userId: 123,
 *       userName: 'Juan',
 *   });
 *   await chat.init();
 *
 *   // Con callbacks
 *   const chat = new ChatApp({
 *       container: '#chat-app',
 *       userId: 123,
 *       onReady: () => console.log('Chat listo!'),
 *       onError: (err) => console.error(err),
 *   });
 *
 * Autor: Wilson Arguello
 * Fecha: 2026-01-02
 */

import { eventBus } from './core/event-emitter.js';
import { EVENTS, DEBUG_CONFIG } from './core/config.js';
import { log } from './core/utils.js';
import { chatStore } from './state/chat-store.js';
import { webSocketService } from './services/websocket-service.js';
// API Service solo para upload de archivos - TODO lo demas via WebSocket
import { apiService } from './services/api-service.js';
import { MessageList } from './components/message-list.js';
import { MessageInput } from './components/message-input.js';
import { ConversationList } from './components/conversation-list.js';

// ============================================================================
// CLASE PRINCIPAL
// ============================================================================

export class ChatApp {
    constructor(options = {}) {
        this.container = typeof options.container === 'string'
            ? document.querySelector(options.container)
            : options.container;

        this.options = {
            debug: DEBUG_CONFIG.ENABLED,
            autoConnect: true,
            loadConversationsOnInit: true,
            ...options,
        };

        // Usuario
        this.userId = options.userId;
        this.userName = options.userName;
        this.userAvatar = options.userAvatar;

        // Componentes
        this.conversationList = null;
        this.messageList = null;
        this.messageInput = null;

        // Callbacks externos
        this.onReady = options.onReady || null;
        this.onError = options.onError || null;
        this.onConversationChange = options.onConversationChange || null;

        // Estado
        this._initialized = false;
        this._currentConversationId = null;

        log('[ChatApp] Instancia creada');
    }

    // ========================================================================
    // INICIALIZACION
    // ========================================================================

    /**
     * Inicializa la aplicacion de chat
     * @returns {Promise<void>}
     */
    async init() {
        if (this._initialized) {
            log('[ChatApp] Ya inicializado');
            return;
        }

        try {
            log('[ChatApp] Inicializando...');

            // Validar container
            if (!this.container) {
                throw new Error('Container no encontrado');
            }

            // Configurar usuario en store
            chatStore.setUser({
                id: this.userId,
                name: this.userName,
                avatar: this.userAvatar,
            });

            // Renderizar estructura
            this._renderLayout();

            // Inicializar componentes
            this._initComponents();

            // Configurar eventos globales
            this._setupGlobalEvents();

            // Conectar WebSocket
            if (this.options.autoConnect) {
                await this._connect();
            }

            // Cargar conversaciones
            if (this.options.loadConversationsOnInit) {
                await this._loadConversations();
            }

            this._initialized = true;
            log('[ChatApp] Inicializado correctamente');

            // Callback de ready
            this.onReady?.();

        } catch (error) {
            log('[ChatApp] Error de inicializacion:', error);
            this.onError?.(error);
            throw error;
        }
    }

    _renderLayout() {
        this.container.innerHTML = `
            <div class="chat-app">
                <!-- Sidebar - Lista de conversaciones -->
                <aside class="chat-app__sidebar">
                    <div id="chat-conversations"></div>
                </aside>

                <!-- Main - Conversacion actual -->
                <main class="chat-app__main">
                    <!-- Header de conversacion -->
                    <header class="chat-app__header">
                        <div class="chat-app__header-info">
                            <div class="chat-app__header-avatar"></div>
                            <div class="chat-app__header-details">
                                <span class="chat-app__header-name">Selecciona una conversacion</span>
                                <span class="chat-app__header-status"></span>
                            </div>
                        </div>
                        <div class="chat-app__header-actions">
                            <button type="button" class="chat-app__header-btn" title="Buscar">
                                <i class="fas fa-search"></i>
                            </button>
                            <button type="button" class="chat-app__header-btn" title="Mas opciones">
                                <i class="fas fa-ellipsis-v"></i>
                            </button>
                        </div>
                    </header>

                    <!-- Area de mensajes -->
                    <div class="chat-app__messages" id="chat-messages">
                        <div class="chat-app__welcome">
                            <i class="fas fa-comments fa-4x text-muted mb-3"></i>
                            <h4>Bienvenido al Chat</h4>
                            <p class="text-muted">Selecciona una conversacion para comenzar a chatear</p>
                        </div>
                    </div>

                    <!-- Input de mensaje -->
                    <footer class="chat-app__footer" id="chat-input" style="display: none;">
                    </footer>
                </main>
            </div>
        `;

        // Referencias a elementos
        this.sidebar = this.container.querySelector('.chat-app__sidebar');
        this.mainArea = this.container.querySelector('.chat-app__main');
        this.header = this.container.querySelector('.chat-app__header');
        this.messagesArea = this.container.querySelector('.chat-app__messages');
        this.inputArea = this.container.querySelector('.chat-app__footer');
        this.welcomeScreen = this.container.querySelector('.chat-app__welcome');

        // Botones del header
        const headerBtns = this.header.querySelectorAll('.chat-app__header-btn');
        // Boton buscar mensajes
        headerBtns[0]?.addEventListener('click', () => this._onSearchMessages());
        // Boton mas opciones
        headerBtns[1]?.addEventListener('click', (e) => this._onMoreOptions(e));
    }

    _initComponents() {
        // Lista de conversaciones
        this.conversationList = new ConversationList({
            container: '#chat-conversations',
            onSelect: (conv) => this._onConversationSelect(conv),
            onNewChat: () => this._onNewChat(),
        });

        // Lista de mensajes
        this.messageList = new MessageList({
            container: '#chat-messages',
            onLoadMore: () => this._loadMoreMessages(),
            onMessageClick: (msg, el) => this._onMessageClick(msg, el),
            onReaction: (msg, emoji) => this._onReaction(msg, emoji),
        });

        // Input de mensaje
        this.messageInput = new MessageInput({
            container: '#chat-input',
            onSend: (text, data) => this._onSendMessage(text, data),
            onTyping: () => this._onTyping(),
            onStopTyping: () => this._onStopTyping(),
            onFileSelect: (files) => this._onFileSelect(files),
        });
    }

    _setupGlobalEvents() {
        // Eventos de conexion
        eventBus.on(EVENTS.CONNECT, () => {
            log('[ChatApp] Conectado');
            this._updateConnectionStatus(true);
        });

        eventBus.on(EVENTS.DISCONNECT, () => {
            log('[ChatApp] Desconectado');
            this._updateConnectionStatus(false);
        });

        // Eventos de mensajes
        eventBus.on(EVENTS.MESSAGE_RECEIVED, (msg) => {
            // Notificar si no es conversacion actual
            if (msg.conversationId !== this._currentConversationId) {
                this._showNotification(msg);
            }
        });

        // Eventos de presencia
        eventBus.on(EVENTS.USER_ONLINE, ({ userId }) => {
            this._updateHeaderStatus();
        });

        eventBus.on(EVENTS.USER_OFFLINE, ({ userId }) => {
            this._updateHeaderStatus();
        });

        // Eventos de typing
        eventBus.on(EVENTS.USER_TYPING, ({ conversationId, userId }) => {
            if (conversationId === this._currentConversationId) {
                this._showTypingIndicator(userId);
            }
        });

        eventBus.on(EVENTS.USER_STOP_TYPING, ({ conversationId, userId }) => {
            if (conversationId === this._currentConversationId) {
                this._hideTypingIndicator(userId);
            }
        });

        // Eventos de reacciones
        eventBus.on(EVENTS.REACTION_ADDED, (data) => {
            this._handleReactionAdded(data);
        });

        eventBus.on(EVENTS.REACTION_REMOVED, (data) => {
            this._handleReactionRemoved(data);
        });
    }

    _handleReactionAdded(data) {
        const { message_id, conversation_id, emoji, user_id } = data;
        if (conversation_id != this._currentConversationId) return;

        const messages = chatStore.getMessages(conversation_id);
        const message = messages.find(m => m.id == message_id);
        if (!message) return;

        const reactions = message.reactions || [];
        const existingIndex = reactions.findIndex(r => r.userId == user_id);

        if (existingIndex >= 0) {
            reactions[existingIndex].emoji = emoji;
        } else {
            reactions.push({ userId: user_id, emoji });
        }

        chatStore.updateMessage(message.tempId || message.id, { reactions });
        this.messageList?.render(chatStore.getMessages(conversation_id));
    }

    _handleReactionRemoved(data) {
        const { message_id, conversation_id, user_id } = data;
        if (conversation_id != this._currentConversationId) return;

        const messages = chatStore.getMessages(conversation_id);
        const message = messages.find(m => m.id == message_id);
        if (!message) return;

        const reactions = (message.reactions || []).filter(r => r.userId != user_id);
        chatStore.updateMessage(message.tempId || message.id, { reactions });
        this.messageList?.render(chatStore.getMessages(conversation_id));
    }

    // ========================================================================
    // CONEXION
    // ========================================================================

    async _connect() {
        try {
            await webSocketService.connect();
        } catch (error) {
            log('[ChatApp] Error conectando:', error);
            // No lanzar error, permitir modo offline
        }
    }

    _updateConnectionStatus(connected) {
        const indicator = this.header?.querySelector('.chat-app__header-status');
        if (indicator && !this._currentConversationId) {
            indicator.textContent = connected ? '' : 'Desconectado';
            indicator.className = `chat-app__header-status ${connected ? '' : 'text-danger'}`;
        }
    }

    // ========================================================================
    // CONVERSACIONES (100% WebSocket)
    // ========================================================================

    async _loadConversations() {
        try {
            // Cargar via WebSocket, NO HTTP
            const conversations = await webSocketService.loadConversations();
            chatStore.setConversations(conversations);
            log('[ChatApp] Conversaciones cargadas via WS:', conversations.length);
        } catch (error) {
            log('[ChatApp] Error cargando conversaciones:', error);
        }
    }

    async _onConversationSelect(conversation) {
        log('[ChatApp] Conversacion seleccionada:', conversation.id);

        this._currentConversationId = conversation.id;

        // Actualizar UI
        this._showConversation(conversation);

        // Unirse via WebSocket
        webSocketService.joinConversation(conversation.id);

        // Cargar mensajes
        await this._loadMessages(conversation.id);

        // Marcar como leido
        webSocketService.markRead(conversation.id);
        chatStore.clearUnread(conversation.id);

        // Callback externo
        this.onConversationChange?.(conversation);
    }

    _showConversation(conversation) {
        // Ocultar pantalla de bienvenida
        if (this.welcomeScreen) {
            this.welcomeScreen.style.display = 'none';
        }

        // Mostrar input
        this.inputArea.style.display = 'block';

        // Actualizar header
        const nameEl = this.header.querySelector('.chat-app__header-name');
        const avatarEl = this.header.querySelector('.chat-app__header-avatar');

        nameEl.textContent = conversation.nombre || conversation.name || 'Conversacion';
        avatarEl.textContent = conversation.nombre?.[0] || 'C';

        this._updateHeaderStatus();

        // Dar foco al input
        this.messageInput.focus();
    }

    _updateHeaderStatus() {
        const statusEl = this.header?.querySelector('.chat-app__header-status');
        if (!statusEl || !this._currentConversationId) return;

        const conversation = chatStore.getConversation(this._currentConversationId);
        if (!conversation) return;

        // Verificar usuarios escribiendo
        const typingUsers = chatStore.getTypingUsers(this._currentConversationId);
        if (typingUsers.length > 0) {
            statusEl.textContent = 'escribiendo...';
            statusEl.className = 'chat-app__header-status typing';
            return;
        }

        // Verificar online (para chats directos)
        if (conversation.participantId && chatStore.isUserOnline(conversation.participantId)) {
            statusEl.textContent = 'en linea';
            statusEl.className = 'chat-app__header-status online';
        } else {
            statusEl.textContent = '';
            statusEl.className = 'chat-app__header-status';
        }
    }

    _onNewChat() {
        log('[ChatApp] Nuevo chat solicitado');
        this._toggleNewChatPanel();
    }

    // ========================================================================
    // PANEL NUEVO CHAT - Busqueda inline en sidebar
    // ========================================================================

    _toggleNewChatPanel() {
        const sidebar = this.container.querySelector('.chat-app__sidebar');
        const existingPanel = sidebar.querySelector('.new-chat-panel');

        if (existingPanel) {
            // Si ya esta abierto, cerrarlo
            existingPanel.remove();
            sidebar.querySelector('#chat-conversations').style.display = '';
            return;
        }

        // Ocultar lista de conversaciones
        sidebar.querySelector('#chat-conversations').style.display = 'none';

        // Crear panel inline
        const panel = document.createElement('div');
        panel.className = 'new-chat-panel';
        panel.innerHTML = `
            <div class="new-chat-panel__header">
                <button type="button" class="new-chat-panel__back" title="Volver">
                    <i class="fas fa-arrow-left"></i>
                </button>
                <span>Nuevo chat</span>
            </div>
            <div class="new-chat-panel__search">
                <i class="fas fa-search"></i>
                <input type="text" class="new-chat-panel__input" placeholder="Buscar por nombre o email...">
            </div>
            <div class="new-chat-panel__results">
                <div class="new-chat-panel__hint">
                    <i class="fas fa-user-friends"></i>
                    <span>Busca un compañero para chatear</span>
                </div>
            </div>
        `;

        sidebar.appendChild(panel);

        const backBtn = panel.querySelector('.new-chat-panel__back');
        const input = panel.querySelector('.new-chat-panel__input');
        const results = panel.querySelector('.new-chat-panel__results');

        // Cerrar panel
        const cerrar = () => {
            panel.remove();
            sidebar.querySelector('#chat-conversations').style.display = '';
        };
        backBtn.addEventListener('click', cerrar);

        // Busqueda con debounce
        let _timer = null;
        input.addEventListener('input', () => {
            clearTimeout(_timer);
            const q = input.value.trim();
            if (q.length < 2) {
                results.innerHTML = `<div class="new-chat-panel__hint"><i class="fas fa-user-friends"></i><span>Escribe al menos 2 caracteres</span></div>`;
                return;
            }
            results.innerHTML = `<div class="new-chat-panel__hint"><i class="fas fa-spinner fa-spin"></i><span>Buscando...</span></div>`;
            _timer = setTimeout(() => this._buscarUsuarios(q, results, cerrar), 300);
        });

        setTimeout(() => input.focus(), 50);
    }

    async _buscarUsuarios(query, resultsContainer, cerrarPanel) {
        try {
            const resp = await fetch(`/api/chat/search/users?q=${encodeURIComponent(query)}&limit=20`, {
                credentials: 'same-origin'
            });
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();

            const usuarios = data.users || data.usuarios || [];
            if (usuarios.length === 0) {
                const safeQuery = query.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
                resultsContainer.innerHTML = `<div class="new-chat-panel__hint"><i class="fas fa-search"></i><span>Sin resultados para "${safeQuery}"</span></div>`;
                return;
            }

            resultsContainer.innerHTML = usuarios.map(u => {
                const initials = (u.name || '?').split(' ').map(w => w[0]).join('').substring(0, 2).toUpperCase();
                return `
                <div class="new-chat-panel__user" data-user-id="${u.id}">
                    <div class="new-chat-panel__avatar">
                        ${u.photo ? `<img src="${u.photo}" alt="" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">` : ''}
                        <span class="new-chat-panel__initials" ${u.photo ? 'style="display:none"' : ''}>${initials}</span>
                    </div>
                    <div class="new-chat-panel__info">
                        <span class="new-chat-panel__name">${u.name || u.username}</span>
                        <span class="new-chat-panel__detail">${u.department || u.email || ''}</span>
                    </div>
                </div>`;
            }).join('');

            // Click en usuario -> abrir chat directo
            resultsContainer.querySelectorAll('.new-chat-panel__user').forEach(el => {
                el.addEventListener('click', async () => {
                    const userId = parseInt(el.dataset.userId);
                    log('[ChatApp] Iniciando chat con usuario:', userId);
                    el.classList.add('new-chat-panel__user--loading');
                    try {
                        await this.openDirectChat(userId);
                        cerrarPanel();
                    } catch (err) {
                        log('[ChatApp] Error abriendo chat directo:', err);
                        el.classList.remove('new-chat-panel__user--loading');
                    }
                });
            });

        } catch (error) {
            log('[ChatApp] Error buscando usuarios:', error);
            resultsContainer.innerHTML = `<div class="new-chat-panel__hint"><i class="fas fa-exclamation-triangle"></i><span>Error al buscar</span></div>`;
        }
    }

    // ========================================================================
    // HEADER ACTIONS - Buscar mensajes y opciones
    // ========================================================================

    _onSearchMessages() {
        if (!this._currentConversationId) return;

        const existing = this.mainArea.querySelector('.chat-search-bar');
        if (existing) {
            existing.remove();
            return;
        }

        const bar = document.createElement('div');
        bar.className = 'chat-search-bar';
        bar.innerHTML = `
            <input type="text" class="chat-search-bar__input" placeholder="Buscar en esta conversacion...">
            <button type="button" class="chat-search-bar__close"><i class="fas fa-times"></i></button>
        `;
        this.header.insertAdjacentElement('afterend', bar);

        const input = bar.querySelector('.chat-search-bar__input');
        const closeBtn = bar.querySelector('.chat-search-bar__close');

        closeBtn.addEventListener('click', () => bar.remove());
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') bar.remove();
        });

        let _t = null;
        input.addEventListener('input', () => {
            clearTimeout(_t);
            const q = input.value.trim();
            _t = setTimeout(() => {
                // Filtrar mensajes visibles por texto
                const msgs = this.messagesArea.querySelectorAll('.message');
                msgs.forEach(m => {
                    const text = m.textContent.toLowerCase();
                    m.style.display = (!q || text.includes(q.toLowerCase())) ? '' : 'none';
                });
            }, 200);
        });

        setTimeout(() => input.focus(), 50);
    }

    _onMoreOptions(e) {
        // Remover menu existente
        const existing = document.querySelector('.chat-options-menu');
        if (existing) { existing.remove(); return; }

        if (!this._currentConversationId) return;

        const menu = document.createElement('div');
        menu.className = 'chat-options-menu';
        menu.innerHTML = `
            <div class="chat-options-menu__item" data-action="info">
                <i class="fas fa-info-circle"></i> Info del chat
            </div>
            <div class="chat-options-menu__item" data-action="mute">
                <i class="fas fa-bell-slash"></i> Silenciar
            </div>
            <div class="chat-options-menu__item" data-action="clear">
                <i class="fas fa-broom"></i> Limpiar chat
            </div>
        `;

        // Posicionar cerca del boton
        const rect = e.currentTarget.getBoundingClientRect();
        menu.style.position = 'fixed';
        menu.style.top = (rect.bottom + 4) + 'px';
        menu.style.right = (window.innerWidth - rect.right) + 'px';
        menu.style.zIndex = '10001';

        document.body.appendChild(menu);

        // Cerrar al click fuera
        const cerrar = (ev) => {
            if (!menu.contains(ev.target)) {
                menu.remove();
                document.removeEventListener('click', cerrar, true);
            }
        };
        setTimeout(() => document.addEventListener('click', cerrar, true), 10);

        // Acciones
        menu.querySelectorAll('.chat-options-menu__item').forEach(item => {
            item.addEventListener('click', () => {
                const action = item.dataset.action;
                log('[ChatApp] Menu accion:', action);
                menu.remove();
                if (action === 'info') {
                    this._showConversationInfo();
                }
            });
        });
    }

    _showConversationInfo() {
        const conv = chatStore.getConversation(this._currentConversationId);
        if (!conv) return;
        const name = conv.nombre || conv.name || 'Conversacion';
        const type = conv.tipo || conv.type || 'directa';
        alert(`Chat: ${name}\nTipo: ${type}\nID: ${this._currentConversationId}`);
    }

    // ========================================================================
    // MENSAJES (100% WebSocket)
    // ========================================================================

    async _loadMessages(conversationId, before = null) {
        try {
            // Cargar via WebSocket, NO HTTP
            const { mensajes, hasMore } = await webSocketService.loadMessages(conversationId, {
                limit: 50,
                before: before,
            });

            chatStore.addMessages(conversationId, mensajes);
            log('[ChatApp] Mensajes cargados via WS:', mensajes.length);

            return hasMore;
        } catch (error) {
            log('[ChatApp] Error cargando mensajes:', error);
            return false;
        }
    }

    async _loadMoreMessages() {
        if (!this._currentConversationId) return;

        const messages = chatStore.getMessages(this._currentConversationId);
        if (messages.length === 0) return;

        const oldestMessage = messages[0];
        return this._loadMessages(this._currentConversationId, oldestMessage.id);
    }

    async _onSendMessage(text, data) {
        if (!this._currentConversationId) return;

        try {
            if (data.editingId) {
                // Editar mensaje existente
                webSocketService.editMessage(data.editingId, text);
            } else {
                // Enviar nuevo mensaje
                await webSocketService.sendMessage(
                    this._currentConversationId,
                    text,
                    { replyTo: data.replyTo }
                );
            }
        } catch (error) {
            log('[ChatApp] Error enviando mensaje:', error);
            this.onError?.(error);
        }
    }

    _onMessageClick(message, element) {
        log('[ChatApp] Click en mensaje:', message.id);
        // TODO: Mostrar menu de opciones
    }

    _onReaction(message, emoji) {
        if (!this._currentConversationId) return;
        webSocketService.addReaction(message.id, this._currentConversationId, emoji);
    }

    // ========================================================================
    // TYPING
    // ========================================================================

    _onTyping() {
        if (!this._currentConversationId) return;
        webSocketService.startTyping(this._currentConversationId);
    }

    _onStopTyping() {
        if (!this._currentConversationId) return;
        webSocketService.stopTyping(this._currentConversationId);
    }

    _showTypingIndicator(userId) {
        this._updateHeaderStatus();
    }

    _hideTypingIndicator(userId) {
        this._updateHeaderStatus();
    }

    // ========================================================================
    // ARCHIVOS
    // ========================================================================

    async _onFileSelect(files) {
        log('[ChatApp] Archivos seleccionados:', files.length);

        for (const file of files) {
            try {
                const result = await apiService.uploadFile(file, {
                    conversationId: this._currentConversationId,
                });

                // Enviar mensaje con archivo
                // TODO: Implementar envio de archivo
                log('[ChatApp] Archivo subido:', result);
            } catch (error) {
                log('[ChatApp] Error subiendo archivo:', error);
                this.onError?.(error);
            }
        }
    }

    // ========================================================================
    // NOTIFICACIONES
    // ========================================================================

    _showNotification(message) {
        // Notificacion del navegador si esta permitido
        if ('Notification' in window && Notification.permission === 'granted') {
            const conversation = chatStore.getConversation(message.conversationId);
            new Notification(conversation?.nombre || 'Nuevo mensaje', {
                body: message.content,
                icon: '/static/img/chat-icon.png',
            });
        }
    }

    // ========================================================================
    // METODOS PUBLICOS
    // ========================================================================

    /**
     * Abre una conversacion especifica
     * @param {number|string} conversationId - ID de conversacion
     */
    async openConversation(conversationId) {
        const conversation = chatStore.getConversation(conversationId);
        if (conversation) {
            await this._onConversationSelect(conversation);
        }
    }

    /**
     * Abre o crea conversacion directa con usuario (via WebSocket)
     * @param {number|string} userId - ID de usuario
     */
    async openDirectChat(userId) {
        try {
            // Via WebSocket, NO HTTP
            const conversation = await webSocketService.getOrCreateDirectConversation(userId);
            chatStore.setConversation(conversation);
            await this._onConversationSelect(conversation);
        } catch (error) {
            log('[ChatApp] Error abriendo chat directo:', error);
            this.onError?.(error);
        }
    }

    /**
     * Envia un mensaje a la conversacion actual
     * @param {string} text - Texto del mensaje
     */
    sendMessage(text) {
        if (!this._currentConversationId) return;
        this._onSendMessage(text, {});
    }

    /**
     * Obtiene estadisticas
     * @returns {Object}
     */
    getStats() {
        return {
            ...webSocketService.getStats(),
            currentConversation: this._currentConversationId,
            totalUnread: chatStore.getTotalUnread(),
        };
    }

    /**
     * Desconecta y limpia recursos
     */
    destroy() {
        webSocketService.disconnect();

        this.conversationList?.destroy();
        this.messageList?.destroy();
        this.messageInput?.destroy();

        this.container.innerHTML = '';
        this._initialized = false;

        log('[ChatApp] Destruido');
    }
}

// ============================================================================
// EXPORT
// ============================================================================

// Hacer disponible globalmente
if (typeof window !== 'undefined') {
    window.ChatApp = ChatApp;
}

export default ChatApp;
