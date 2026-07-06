/**
 * ╔══════════════════════════════════════════════════════════════════════════════╗
 * ║                      MESSAGE LIST - COMPONENTE UI                            ║
 * ║                    Lista de mensajes de una conversacion                     ║
 * ╚══════════════════════════════════════════════════════════════════════════════╝
 *
 * Componente que renderiza y gestiona la lista de mensajes.
 *
 * Caracteristicas:
 * - Render optimizado (solo actualiza lo necesario)
 * - Scroll infinito hacia arriba
 * - Auto-scroll hacia abajo en nuevos mensajes
 * - Agrupacion por fecha
 * - Estados de mensaje (enviando, enviado, error)
 * - Soporte para edicion y eliminacion
 *
 * USO:
 *   const messageList = new MessageList({
 *       container: '#messages-container',
 *       onLoadMore: () => loadMoreMessages(),
 *       onMessageClick: (msg) => showOptions(msg),
 *   });
 *
 * Autor: Wilson Arguello
 * Fecha: 2026-01-02
 */

import { EventEmitter, eventBus } from '../core/event-emitter.js';
import { EVENTS, MESSAGE_STATUS, UI_CONFIG, QUICK_REACTIONS } from '../core/config.js';
import {
    escapeHtml,
    linkify,
    formatChatTime,
    formatDaySeparator,
    isSameDay,
    createElement,
    scrollToBottom,
    isNearBottom,
    getInitials,
} from '../core/utils.js';
import { chatStore } from '../state/chat-store.js';

// ============================================================================
// CLASE PRINCIPAL
// ============================================================================

export class MessageList extends EventEmitter {
    constructor(options = {}) {
        super();

        this.container = typeof options.container === 'string'
            ? document.querySelector(options.container)
            : options.container;

        this.options = {
            loadMoreThreshold: 100,    // px desde el top para cargar mas
            autoScroll: true,
            showAvatar: true,
            showTimestamp: true,
            groupByDate: true,
            ...options,
        };

        // Estado interno
        this._messages = [];
        this._renderedIds = new Set();
        this._loadingMore = false;
        this._shouldAutoScroll = true;
        this._activePickerMessageId = null; // ID del mensaje con picker abierto

        // Callbacks externos
        this.onLoadMore = options.onLoadMore || null;
        this.onMessageClick = options.onMessageClick || null;
        this.onReaction = options.onReaction || null;

        this._init();
    }

    // ========================================================================
    // INICIALIZACION
    // ========================================================================

    _init() {
        if (!this.container) {
            console.error('[MessageList] Container no encontrado');
            return;
        }

        // Crear estructura
        this.container.innerHTML = `
            <div class="message-list__loader" style="display: none;">
                <div class="spinner-border spinner-border-sm" role="status">
                    <span class="visually-hidden">Cargando...</span>
                </div>
            </div>
            <div class="message-list__content"></div>
            <div class="message-list__scroll-btn" style="display: none;">
                <i class="fas fa-chevron-down"></i>
                <span class="badge">0</span>
            </div>
            <div class="reaction-picker" style="display: none;">
                ${QUICK_REACTIONS.map(emoji => `<span class="reaction-picker__emoji">${emoji}</span>`).join('')}
            </div>
        `;

        this.loader = this.container.querySelector('.message-list__loader');
        this.content = this.container.querySelector('.message-list__content');
        this.scrollBtn = this.container.querySelector('.message-list__scroll-btn');
        this.reactionPicker = this.container.querySelector('.reaction-picker');

        this._setupEventListeners();
        this._subscribeToStore();
    }

    _setupEventListeners() {
        // Scroll para cargar mas y detectar posicion
        this.container.addEventListener('scroll', this._handleScroll.bind(this));

        // Click en boton de scroll
        this.scrollBtn?.addEventListener('click', () => {
            this.scrollToBottom();
            this._hideScrollButton();
        });

        // Click en mensajes (delegacion de eventos)
        this.content.addEventListener('click', this._handleContentClick.bind(this));

        // Doble click para reaccion rapida
        this.content.addEventListener('dblclick', this._handleDoubleClick.bind(this));

        // Click en emojis del picker de reacciones
        this.reactionPicker?.addEventListener('click', this._handlePickerClick.bind(this));

        // Click fuera del picker para cerrarlo
        document.addEventListener('click', this._handleDocumentClick.bind(this));
    }

    _subscribeToStore() {
        // Suscribirse a cambios en mensajes
        chatStore.subscribe('messages', () => {
            this._updateFromStore();
        });

        // Suscribirse a cambios en conversacion actual
        chatStore.subscribe('currentConversation', () => {
            this._onConversationChange();
        });

        // Eventos de mensajes
        eventBus.on(EVENTS.MESSAGE_RECEIVED, () => {
            if (!this._shouldAutoScroll) {
                this._showScrollButton();
            }
        });
    }

    // ========================================================================
    // RENDERIZADO
    // ========================================================================

    /**
     * Renderiza lista de mensajes
     * @param {Array} messages - Mensajes a renderizar
     */
    render(messages) {
        this._messages = messages;
        this.content.innerHTML = '';
        this._renderedIds.clear();

        if (messages.length === 0) {
            this._renderEmptyState();
            return;
        }

        let lastDate = null;

        messages.forEach((message, index) => {
            // Separador de fecha
            if (this.options.groupByDate) {
                const messageDate = new Date(message.timestamp);
                if (!lastDate || !isSameDay(messageDate, lastDate)) {
                    this._renderDateSeparator(messageDate);
                    lastDate = messageDate;
                }
            }

            // Mensaje
            this._renderMessage(message, index > 0 ? messages[index - 1] : null);
            this._renderedIds.add(message.id || message.tempId);
        });

        // Auto-scroll si corresponde
        if (this._shouldAutoScroll) {
            this.scrollToBottom(false);
        }
    }

    _renderMessage(message, previousMessage) {
        const userId = chatStore.user?.id;
        const isOwn = message.senderId == userId;
        const isGrouped = previousMessage &&
            previousMessage.senderId === message.senderId &&
            (message.timestamp - previousMessage.timestamp < 60000); // 1 min

        const element = createElement(this._getMessageHTML(message, isOwn, isGrouped));
        this.content.appendChild(element);
    }

    _getMessageHTML(message, isOwn, isGrouped) {
        const statusIcon = this._getStatusIcon(message.status);
        const timeStr = formatChatTime(message.timestamp);
        const avatarHTML = !isOwn && !isGrouped && this.options.showAvatar
            ? `<div class="message__avatar">${getInitials(message.senderName || 'U')}</div>`
            : '';

        const replyHTML = message.replyTo
            ? `<div class="message__reply">
                   <span class="message__reply-author">${escapeHtml(message.replyTo.senderName || '')}</span>
                   <span class="message__reply-text">${escapeHtml(message.replyTo.content || '')}</span>
               </div>`
            : '';

        const editedHTML = message.editedAt
            ? '<span class="message__edited">(editado)</span>'
            : '';

        const reactionsHTML = message.reactions?.length
            ? this._getReactionsHTML(message.reactions)
            : '';

        return `
            <div class="message ${isOwn ? 'message--own' : 'message--other'} ${isGrouped ? 'message--grouped' : ''}"
                 data-id="${message.id || message.tempId}"
                 data-temp-id="${message.tempId || ''}">
                ${avatarHTML}
                <div class="message__content">
                    ${replyHTML}
                    <div class="message__bubble">
                        ${!isOwn && !isGrouped ? `<div class="message__sender">${escapeHtml(message.senderName || 'Usuario')}</div>` : ''}
                        <div class="message__text">${linkify(message.content)}</div>
                        <div class="message__meta">
                            ${editedHTML}
                            <span class="message__time">${timeStr}</span>
                            ${isOwn ? `<span class="message__status">${statusIcon}</span>` : ''}
                        </div>
                    </div>
                    ${reactionsHTML}
                    <button class="message__react-btn" title="Reaccionar" type="button">
                        <i class="far fa-smile"></i>
                    </button>
                </div>
            </div>
        `;
    }

    _getStatusIcon(status) {
        switch (status) {
            case MESSAGE_STATUS.PENDING:
            case MESSAGE_STATUS.SENDING:
                return '<i class="fas fa-clock"></i>';
            case MESSAGE_STATUS.SENT:
                return '<i class="fas fa-check"></i>';
            case MESSAGE_STATUS.DELIVERED:
                return '<i class="fas fa-check-double"></i>';
            case MESSAGE_STATUS.READ:
                return '<i class="fas fa-check-double text-primary"></i>';
            case MESSAGE_STATUS.ERROR:
                return '<i class="fas fa-exclamation-circle text-danger"></i>';
            default:
                return '';
        }
    }

    _getReactionsHTML(reactions) {
        const grouped = reactions.reduce((acc, r) => {
            acc[r.emoji] = (acc[r.emoji] || 0) + 1;
            return acc;
        }, {});

        const items = Object.entries(grouped)
            .map(([emoji, count]) => `<span class="message__reaction">${emoji} ${count > 1 ? count : ''}</span>`)
            .join('');

        return `<div class="message__reactions">${items}</div>`;
    }

    _renderDateSeparator(date) {
        const element = createElement(`
            <div class="message-list__date-separator">
                <span>${formatDaySeparator(date)}</span>
            </div>
        `);
        this.content.appendChild(element);
    }

    _renderEmptyState() {
        this.content.innerHTML = `
            <div class="message-list__empty">
                <i class="fas fa-comments fa-3x text-muted mb-3"></i>
                <p class="text-muted">No hay mensajes aun</p>
                <p class="text-muted small">Envia un mensaje para iniciar la conversacion</p>
            </div>
        `;
    }

    // ========================================================================
    // ACTUALIZACION INCREMENTAL
    // ========================================================================

    /**
     * Agrega un mensaje al final
     * @param {Object} message - Mensaje a agregar
     */
    addMessage(message) {
        const messageId = message.id || message.tempId;

        // Si ya existe, actualizar
        if (this._renderedIds.has(messageId)) {
            this.updateMessage(messageId, message);
            return;
        }

        // Obtener ultimo mensaje para agrupar
        const lastMessage = this._messages[this._messages.length - 1];

        // Agregar separador de fecha si es necesario
        if (this.options.groupByDate && this._messages.length > 0) {
            const lastDate = new Date(lastMessage.timestamp);
            const newDate = new Date(message.timestamp);
            if (!isSameDay(lastDate, newDate)) {
                this._renderDateSeparator(newDate);
            }
        }

        // Renderizar mensaje
        this._renderMessage(message, lastMessage);
        this._messages.push(message);
        this._renderedIds.add(messageId);

        // Auto-scroll
        if (this._shouldAutoScroll) {
            this.scrollToBottom();
        }
    }

    /**
     * Actualiza un mensaje existente
     * @param {string} messageId - ID del mensaje
     * @param {Object} updates - Actualizaciones
     */
    updateMessage(messageId, updates) {
        const element = this.content.querySelector(`[data-id="${messageId}"], [data-temp-id="${messageId}"]`);
        if (!element) return;

        // Actualizar status
        if (updates.status) {
            const statusEl = element.querySelector('.message__status');
            if (statusEl) {
                statusEl.innerHTML = this._getStatusIcon(updates.status);
            }

            // Agregar clase de error
            if (updates.status === MESSAGE_STATUS.ERROR) {
                element.classList.add('message--error');
            }
        }

        // Actualizar contenido
        if (updates.content) {
            const textEl = element.querySelector('.message__text');
            if (textEl) {
                textEl.innerHTML = linkify(updates.content);
            }
        }

        // Actualizar ID real
        if (updates.id && updates.id !== messageId) {
            element.dataset.id = updates.id;
            this._renderedIds.add(updates.id);
        }
    }

    /**
     * Elimina un mensaje
     * @param {string} messageId - ID del mensaje
     */
    removeMessage(messageId) {
        const element = this.content.querySelector(`[data-id="${messageId}"], [data-temp-id="${messageId}"]`);
        if (element) {
            element.remove();
            this._renderedIds.delete(messageId);
        }
    }

    // ========================================================================
    // EVENTOS
    // ========================================================================

    _handleScroll() {
        // Detectar si usuario esta cerca del fondo
        this._shouldAutoScroll = isNearBottom(this.container, 100);

        if (this._shouldAutoScroll) {
            this._hideScrollButton();
        }

        // Cargar mas al llegar arriba
        if (this.container.scrollTop < this.options.loadMoreThreshold && !this._loadingMore) {
            this._triggerLoadMore();
        }
    }

    _handleContentClick(e) {
        const messageEl = e.target.closest('.message');
        if (!messageEl) return;

        const messageId = messageEl.dataset.id;
        const message = this._messages.find(m => (m.id || m.tempId) == messageId);

        // Click en boton de reaccion - mostrar picker
        if (e.target.closest('.message__react-btn')) {
            e.stopPropagation();
            this._showReactionPicker(messageEl, messageId);
            return;
        }

        // Click en reaccion existente - toggle
        if (e.target.closest('.message__reaction')) {
            const emoji = e.target.textContent.trim().charAt(0);
            this.onReaction?.(message, emoji);
            return;
        }

        // Click general en mensaje
        this.onMessageClick?.(message, messageEl);
        this.emit('messageClick', { message, element: messageEl });
    }

    _handlePickerClick(e) {
        const emojiEl = e.target.closest('.reaction-picker__emoji');
        if (!emojiEl) return;

        e.stopPropagation();
        const emoji = emojiEl.textContent.trim();
        const messageId = this._activePickerMessageId;

        if (messageId) {
            const message = this._messages.find(m => (m.id || m.tempId) == messageId);
            if (message) {
                this.onReaction?.(message, emoji);
            }
        }

        this._hideReactionPicker();
    }

    _handleDocumentClick(e) {
        // Si click es fuera del picker y del boton de reaccion, cerrar picker
        if (!e.target.closest('.reaction-picker') && !e.target.closest('.message__react-btn')) {
            this._hideReactionPicker();
        }
    }

    _showReactionPicker(messageEl, messageId) {
        if (!this.reactionPicker) return;

        // Si ya esta abierto para este mensaje, cerrar
        if (this._activePickerMessageId === messageId && this.reactionPicker.style.display !== 'none') {
            this._hideReactionPicker();
            return;
        }

        this._activePickerMessageId = messageId;

        // Posicionar picker cerca del mensaje
        const rect = messageEl.getBoundingClientRect();
        const containerRect = this.container.getBoundingClientRect();
        const isOwn = messageEl.classList.contains('message--own');

        // Posicionar arriba del mensaje
        let top = rect.top - containerRect.top + this.container.scrollTop - 50;
        let left;

        if (isOwn) {
            // Mensaje propio - picker a la izquierda
            left = rect.right - containerRect.left - 220;
        } else {
            // Mensaje de otro - picker a la derecha
            left = rect.left - containerRect.left + 40;
        }

        // Asegurar que no se salga del contenedor
        left = Math.max(10, Math.min(left, containerRect.width - 230));
        top = Math.max(10, top);

        this.reactionPicker.style.cssText = `
            display: flex;
            position: absolute;
            top: ${top}px;
            left: ${left}px;
        `;
    }

    _hideReactionPicker() {
        if (this.reactionPicker) {
            this.reactionPicker.style.display = 'none';
        }
        this._activePickerMessageId = null;
    }

    _handleDoubleClick(e) {
        const messageEl = e.target.closest('.message');
        if (!messageEl) return;

        const messageId = messageEl.dataset.id;
        const message = this._messages.find(m => (m.id || m.tempId) == messageId);

        // Reaccion rapida con doble click
        this.onReaction?.(message, QUICK_REACTIONS[0]);
        this.emit('quickReaction', { message });
    }

    async _triggerLoadMore() {
        if (!this.onLoadMore || this._loadingMore) return;

        this._loadingMore = true;
        this.loader.style.display = 'flex';

        // Guardar posicion de scroll
        const scrollHeight = this.container.scrollHeight;

        try {
            await this.onLoadMore();
        } catch (e) {
            console.error('[MessageList] Error cargando mas:', e);
        }

        // Restaurar posicion de scroll
        const newScrollHeight = this.container.scrollHeight;
        this.container.scrollTop = newScrollHeight - scrollHeight;

        this.loader.style.display = 'none';
        this._loadingMore = false;
    }

    // ========================================================================
    // SCROLL
    // ========================================================================

    scrollToBottom(smooth = true) {
        scrollToBottom(this.container, smooth);
        this._shouldAutoScroll = true;
        this._hideScrollButton();
    }

    _showScrollButton(newCount = 1) {
        if (!this.scrollBtn) return;
        const badge = this.scrollBtn.querySelector('.badge');
        const current = parseInt(badge.textContent) || 0;
        badge.textContent = current + newCount;
        this.scrollBtn.style.display = 'flex';
    }

    _hideScrollButton() {
        if (!this.scrollBtn) return;
        this.scrollBtn.style.display = 'none';
        this.scrollBtn.querySelector('.badge').textContent = '0';
    }

    // ========================================================================
    // INTEGRACION CON STORE
    // ========================================================================

    _updateFromStore() {
        const currentConv = chatStore.get('currentConversation');
        if (!currentConv) return;

        const messages = chatStore.getMessages(currentConv);
        this.render(messages);
    }

    _onConversationChange() {
        this._shouldAutoScroll = true;
        this._updateFromStore();
    }

    // ========================================================================
    // LIMPIEZA
    // ========================================================================

    clear() {
        this._messages = [];
        this._renderedIds.clear();
        this.content.innerHTML = '';
    }

    destroy() {
        this.clear();
        this.removeAllListeners();
    }
}

export default MessageList;
