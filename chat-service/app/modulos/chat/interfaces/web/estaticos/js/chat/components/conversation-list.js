/**
 * ╔══════════════════════════════════════════════════════════════════════════════╗
 * ║                   CONVERSATION LIST - COMPONENTE UI                          ║
 * ║                    Lista de conversaciones del usuario                       ║
 * ╚══════════════════════════════════════════════════════════════════════════════╝
 *
 * Componente que renderiza y gestiona la lista de conversaciones.
 *
 * Caracteristicas:
 * - Lista de chats con ultimo mensaje
 * - Indicador de no leidos
 * - Estado online/offline
 * - Busqueda/filtrado
 * - Typing indicator
 *
 * USO:
 *   const list = new ConversationList({
 *       container: '#conversations-container',
 *       onSelect: (conv) => openConversation(conv),
 *   });
 *
 * Autor: Wilson Arguello
 * Fecha: 2026-01-02
 */

import { EventEmitter, eventBus } from '../core/event-emitter.js';
import { EVENTS, CONVERSATION_TYPES } from '../core/config.js';
import { escapeHtml, truncate, timeAgo, getInitials, createElement } from '../core/utils.js';
import { chatStore } from '../state/chat-store.js';

// ============================================================================
// CLASE PRINCIPAL
// ============================================================================

export class ConversationList extends EventEmitter {
    constructor(options = {}) {
        super();

        this.container = typeof options.container === 'string'
            ? document.querySelector(options.container)
            : options.container;

        this.options = {
            showSearch: true,
            showNewChat: true,
            showOnlineStatus: true,
            ...options,
        };

        // Estado
        this._conversations = [];
        this._searchQuery = '';
        this._selectedId = null;

        // Callbacks
        this.onSelect = options.onSelect || null;
        this.onNewChat = options.onNewChat || null;

        this._init();
    }

    // ========================================================================
    // INICIALIZACION
    // ========================================================================

    _init() {
        if (!this.container) {
            console.error('[ConversationList] Container no encontrado');
            return;
        }

        this._render();
        this._setupEventListeners();
        this._subscribeToStore();
    }

    _render() {
        this.container.innerHTML = `
            <div class="conversation-list">
                <!-- Header -->
                <div class="conversation-list__header">
                    <h5 class="conversation-list__title">Chats</h5>
                    ${this.options.showNewChat ? `
                    <button type="button" class="conversation-list__new-btn" title="Nuevo chat">
                        <i class="fas fa-edit"></i>
                    </button>
                    ` : ''}
                </div>

                <!-- Busqueda -->
                ${this.options.showSearch ? `
                <div class="conversation-list__search">
                    <i class="fas fa-search"></i>
                    <input type="text" placeholder="Buscar conversacion..." class="conversation-list__search-input">
                </div>
                ` : ''}

                <!-- Lista -->
                <div class="conversation-list__content">
                    <div class="conversation-list__items"></div>
                    <div class="conversation-list__empty" style="display: none;">
                        <i class="fas fa-inbox fa-2x text-muted mb-2"></i>
                        <p class="text-muted">No hay conversaciones</p>
                    </div>
                </div>
            </div>
        `;

        // Referencias
        this.itemsContainer = this.container.querySelector('.conversation-list__items');
        this.emptyState = this.container.querySelector('.conversation-list__empty');
        this.searchInput = this.container.querySelector('.conversation-list__search-input');
        this.newChatBtn = this.container.querySelector('.conversation-list__new-btn');
    }

    _setupEventListeners() {
        // Click en items (delegacion)
        this.itemsContainer.addEventListener('click', (e) => {
            const item = e.target.closest('.conversation-item');
            if (item) {
                const id = item.dataset.id;
                this._selectConversation(id);
            }
        });

        // Busqueda
        if (this.searchInput) {
            this.searchInput.addEventListener('input', (e) => {
                this._searchQuery = e.target.value.toLowerCase();
                this._renderList();
            });
        }

        // Nuevo chat
        if (this.newChatBtn) {
            this.newChatBtn.addEventListener('click', () => {
                this.onNewChat?.();
                this.emit('newChat');
            });
        }
    }

    _subscribeToStore() {
        // Cambios en conversaciones
        chatStore.subscribe('conversations', () => {
            this._updateFromStore();
        });

        // Cambios en no leidos
        chatStore.subscribe('unreadCounts', () => {
            this._updateUnreadBadges();
        });

        // Cambios en usuarios escribiendo
        chatStore.subscribe('typingUsers', () => {
            this._updateTypingIndicators();
        });

        // Cambios en usuarios online
        chatStore.subscribe('onlineUsers', () => {
            this._updateOnlineStatus();
        });

        // Conversacion actual cambiada
        chatStore.subscribe('currentConversation', (convId) => {
            this._highlightSelected(convId);
        });
    }

    // ========================================================================
    // RENDERIZADO
    // ========================================================================

    /**
     * Renderiza lista de conversaciones
     * @param {Array} conversations - Conversaciones
     */
    render(conversations) {
        this._conversations = conversations;
        this._renderList();
    }

    _renderList() {
        // Filtrar si hay busqueda
        let filtered = this._conversations;
        if (this._searchQuery) {
            filtered = filtered.filter(c =>
                (c.nombre || c.name || '').toLowerCase().includes(this._searchQuery) ||
                (c.lastMessage?.content || '').toLowerCase().includes(this._searchQuery)
            );
        }

        if (filtered.length === 0) {
            this.itemsContainer.innerHTML = '';
            this.emptyState.style.display = 'flex';
            return;
        }

        this.emptyState.style.display = 'none';
        this.itemsContainer.innerHTML = filtered.map(c => this._getItemHTML(c)).join('');

        // Resaltar seleccionado
        this._highlightSelected(chatStore.get('currentConversation'));
    }

    _getItemHTML(conversation) {
        const id = conversation.id;
        const name = conversation.nombre || conversation.name || 'Sin nombre';
        const type = conversation.tipo || conversation.type || CONVERSATION_TYPES.DIRECT;
        const avatar = conversation.avatar;
        const lastMessage = conversation.lastMessage || conversation.ultimo_mensaje;
        const unread = chatStore.get('unreadCounts')?.get(id) || 0;
        const isOnline = type === CONVERSATION_TYPES.DIRECT &&
            conversation.participantId &&
            chatStore.isUserOnline(conversation.participantId);

        // Typing
        const typingUsers = chatStore.getTypingUsers(id);
        const isTyping = typingUsers.length > 0;

        // Avatar
        let avatarHTML;
        if (avatar) {
            avatarHTML = `<img src="${avatar}" alt="${escapeHtml(name)}" class="conversation-item__avatar-img">`;
        } else if (type === CONVERSATION_TYPES.GROUP) {
            avatarHTML = `<i class="fas fa-users"></i>`;
        } else {
            avatarHTML = getInitials(name);
        }

        // Ultimo mensaje
        let lastMessageHTML = '';
        if (isTyping) {
            lastMessageHTML = '<span class="conversation-item__typing">escribiendo...</span>';
        } else if (lastMessage) {
            const sender = lastMessage.senderId == chatStore.user?.id ? 'Tu: ' : '';
            lastMessageHTML = `<span>${sender}${escapeHtml(truncate(lastMessage.content || '', 30))}</span>`;
        }

        // Tiempo
        const timeHTML = lastMessage?.timestamp
            ? `<span class="conversation-item__time">${timeAgo(lastMessage.timestamp)}</span>`
            : '';

        // Badge no leidos
        const badgeHTML = unread > 0
            ? `<span class="conversation-item__badge">${unread > 99 ? '99+' : unread}</span>`
            : '';

        // Online indicator
        const onlineHTML = this.options.showOnlineStatus && isOnline
            ? '<span class="conversation-item__online"></span>'
            : '';

        return `
            <div class="conversation-item" data-id="${id}">
                <div class="conversation-item__avatar">
                    ${avatarHTML}
                    ${onlineHTML}
                </div>
                <div class="conversation-item__info">
                    <div class="conversation-item__top">
                        <span class="conversation-item__name">${escapeHtml(name)}</span>
                        ${timeHTML}
                    </div>
                    <div class="conversation-item__bottom">
                        <span class="conversation-item__message">${lastMessageHTML}</span>
                        ${badgeHTML}
                    </div>
                </div>
            </div>
        `;
    }

    // ========================================================================
    // SELECCION
    // ========================================================================

    _selectConversation(id) {
        const conversation = this._conversations.find(c => c.id == id);
        if (!conversation) return;

        this._selectedId = id;
        chatStore.setCurrentConversation(id);

        this.onSelect?.(conversation);
        this.emit('select', { conversation });
    }

    _highlightSelected(id) {
        // Remover seleccion anterior
        const prev = this.itemsContainer.querySelector('.conversation-item--selected');
        if (prev) prev.classList.remove('conversation-item--selected');

        // Agregar seleccion nueva
        if (id) {
            const item = this.itemsContainer.querySelector(`[data-id="${id}"]`);
            if (item) item.classList.add('conversation-item--selected');
        }
    }

    // ========================================================================
    // ACTUALIZACIONES PARCIALES
    // ========================================================================

    _updateUnreadBadges() {
        const unreadCounts = chatStore.get('unreadCounts');

        this._conversations.forEach(conv => {
            const item = this.itemsContainer.querySelector(`[data-id="${conv.id}"]`);
            if (!item) return;

            const unread = unreadCounts?.get(conv.id) || 0;
            let badge = item.querySelector('.conversation-item__badge');

            if (unread > 0) {
                if (!badge) {
                    badge = document.createElement('span');
                    badge.className = 'conversation-item__badge';
                    item.querySelector('.conversation-item__bottom').appendChild(badge);
                }
                badge.textContent = unread > 99 ? '99+' : unread;
            } else if (badge) {
                badge.remove();
            }
        });
    }

    _updateTypingIndicators() {
        this._conversations.forEach(conv => {
            const item = this.itemsContainer.querySelector(`[data-id="${conv.id}"]`);
            if (!item) return;

            const typingUsers = chatStore.getTypingUsers(conv.id);
            const messageEl = item.querySelector('.conversation-item__message');

            if (typingUsers.length > 0) {
                messageEl.innerHTML = '<span class="conversation-item__typing">escribiendo...</span>';
            } else {
                // Restaurar ultimo mensaje
                const lastMessage = conv.lastMessage || conv.ultimo_mensaje;
                if (lastMessage) {
                    const sender = lastMessage.senderId == chatStore.user?.id ? 'Tu: ' : '';
                    messageEl.innerHTML = `<span>${sender}${escapeHtml(truncate(lastMessage.content || '', 30))}</span>`;
                }
            }
        });
    }

    _updateOnlineStatus() {
        if (!this.options.showOnlineStatus) return;

        this._conversations.forEach(conv => {
            if (conv.tipo !== CONVERSATION_TYPES.DIRECT) return;

            const item = this.itemsContainer.querySelector(`[data-id="${conv.id}"]`);
            if (!item) return;

            const isOnline = conv.participantId && chatStore.isUserOnline(conv.participantId);
            let indicator = item.querySelector('.conversation-item__online');

            if (isOnline && !indicator) {
                indicator = document.createElement('span');
                indicator.className = 'conversation-item__online';
                item.querySelector('.conversation-item__avatar').appendChild(indicator);
            } else if (!isOnline && indicator) {
                indicator.remove();
            }
        });
    }

    // ========================================================================
    // INTEGRACION CON STORE
    // ========================================================================

    _updateFromStore() {
        const conversations = chatStore.getConversationList();
        this.render(conversations);
    }

    // ========================================================================
    // METODOS PUBLICOS
    // ========================================================================

    /**
     * Actualiza una conversacion especifica
     * @param {Object} conversation - Conversacion actualizada
     */
    updateConversation(conversation) {
        const index = this._conversations.findIndex(c => c.id === conversation.id);
        if (index >= 0) {
            this._conversations[index] = { ...this._conversations[index], ...conversation };
        } else {
            this._conversations.unshift(conversation);
        }

        // Reordenar por ultima actividad
        this._conversations.sort((a, b) =>
            (b.lastMessage?.timestamp || b.updatedAt || 0) -
            (a.lastMessage?.timestamp || a.updatedAt || 0)
        );

        this._renderList();
    }

    /**
     * Limpia la busqueda
     */
    clearSearch() {
        if (this.searchInput) {
            this.searchInput.value = '';
        }
        this._searchQuery = '';
        this._renderList();
    }

    // ========================================================================
    // LIMPIEZA
    // ========================================================================

    destroy() {
        this.container.innerHTML = '';
        this.removeAllListeners();
    }
}

export default ConversationList;
