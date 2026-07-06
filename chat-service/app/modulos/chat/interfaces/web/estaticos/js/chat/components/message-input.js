/**
 * ╔══════════════════════════════════════════════════════════════════════════════╗
 * ║                      MESSAGE INPUT - COMPONENTE UI                           ║
 * ║                     Campo de entrada para mensajes                           ║
 * ╚══════════════════════════════════════════════════════════════════════════════╝
 *
 * Componente de entrada de texto para chat.
 *
 * Caracteristicas:
 * - Textarea auto-expandible
 * - Indicador de "escribiendo" automatico
 * - Soporte para archivos
 * - Emoji picker
 * - Responder a mensajes
 * - Editar mensajes
 *
 * USO:
 *   const input = new MessageInput({
 *       container: '#input-container',
 *       onSend: (text) => sendMessage(text),
 *       onTyping: () => notifyTyping(),
 *   });
 *
 * Autor: Wilson Arguello
 * Fecha: 2026-01-02
 */

import { EventEmitter, eventBus } from '../core/event-emitter.js';
import { MESSAGE_CONFIG, UI_CONFIG, QUICK_REACTIONS } from '../core/config.js';
import { escapeHtml, debounce, truncate } from '../core/utils.js';
import { chatStore } from '../state/chat-store.js';

// ============================================================================
// CLASE PRINCIPAL
// ============================================================================

export class MessageInput extends EventEmitter {
    constructor(options = {}) {
        super();

        this.container = typeof options.container === 'string'
            ? document.querySelector(options.container)
            : options.container;

        this.options = {
            maxLength: MESSAGE_CONFIG.MAX_LENGTH,
            placeholder: 'Escribe un mensaje...',
            showEmoji: true,
            showAttach: true,
            ...options,
        };

        // Estado
        this._replyingTo = null;
        this._editingMessage = null;

        // Callbacks
        this.onSend = options.onSend || null;
        this.onTyping = options.onTyping || null;
        this.onStopTyping = options.onStopTyping || null;
        this.onFileSelect = options.onFileSelect || null;

        this._init();
    }

    // ========================================================================
    // INICIALIZACION
    // ========================================================================

    _init() {
        if (!this.container) {
            console.error('[MessageInput] Container no encontrado');
            return;
        }

        this._render();
        this._setupEventListeners();
        this._subscribeToStore();
    }

    _render() {
        this.container.innerHTML = `
            <div class="message-input">
                <!-- Barra de respuesta/edicion -->
                <div class="message-input__reply-bar" style="display: none;">
                    <div class="message-input__reply-content">
                        <i class="fas fa-reply"></i>
                        <div class="message-input__reply-info">
                            <span class="message-input__reply-author"></span>
                            <span class="message-input__reply-text"></span>
                        </div>
                    </div>
                    <button type="button" class="message-input__reply-close" aria-label="Cancelar">
                        <i class="fas fa-times"></i>
                    </button>
                </div>

                <!-- Area principal de entrada -->
                <div class="message-input__main">
                    ${this.options.showAttach ? `
                    <button type="button" class="message-input__btn message-input__attach" title="Adjuntar archivo">
                        <i class="fas fa-paperclip"></i>
                    </button>
                    <input type="file" class="message-input__file-input" hidden multiple>
                    ` : ''}

                    <div class="message-input__textarea-wrapper">
                        <textarea
                            class="message-input__textarea"
                            placeholder="${this.options.placeholder}"
                            maxlength="${this.options.maxLength}"
                            rows="1"
                        ></textarea>
                    </div>

                    ${this.options.showEmoji ? `
                    <button type="button" class="message-input__btn message-input__emoji" title="Emoji">
                        <i class="far fa-smile"></i>
                    </button>
                    ` : ''}

                    <button type="button" class="message-input__btn message-input__send" title="Enviar" disabled>
                        <i class="fas fa-paper-plane"></i>
                    </button>
                </div>

                <!-- Emoji picker -->
                ${this.options.showEmoji ? `
                <div class="message-input__emoji-picker" style="display: none;">
                    <div class="message-input__emoji-quick">
                        ${QUICK_REACTIONS.map(e => `<button type="button" class="message-input__emoji-btn">${e}</button>`).join('')}
                    </div>
                </div>
                ` : ''}
            </div>
        `;

        // Referencias a elementos
        this.textarea = this.container.querySelector('.message-input__textarea');
        this.sendBtn = this.container.querySelector('.message-input__send');
        this.attachBtn = this.container.querySelector('.message-input__attach');
        this.fileInput = this.container.querySelector('.message-input__file-input');
        this.emojiBtn = this.container.querySelector('.message-input__emoji');
        this.emojiPicker = this.container.querySelector('.message-input__emoji-picker');
        this.replyBar = this.container.querySelector('.message-input__reply-bar');
        this.replyCloseBtn = this.container.querySelector('.message-input__reply-close');
    }

    _setupEventListeners() {
        // Textarea - entrada de texto
        this.textarea.addEventListener('input', this._handleInput.bind(this));
        this.textarea.addEventListener('keydown', this._handleKeydown.bind(this));

        // Boton enviar
        this.sendBtn.addEventListener('click', this._handleSend.bind(this));

        // Adjuntar archivo
        if (this.attachBtn) {
            this.attachBtn.addEventListener('click', () => this.fileInput?.click());
        }
        if (this.fileInput) {
            this.fileInput.addEventListener('change', this._handleFileSelect.bind(this));
        }

        // Emoji
        if (this.emojiBtn) {
            this.emojiBtn.addEventListener('click', this._toggleEmojiPicker.bind(this));
        }
        if (this.emojiPicker) {
            this.emojiPicker.addEventListener('click', this._handleEmojiClick.bind(this));
        }

        // Cerrar respuesta
        if (this.replyCloseBtn) {
            this.replyCloseBtn.addEventListener('click', () => this.cancelReply());
        }

        // Cerrar emoji picker al hacer click fuera
        document.addEventListener('click', (e) => {
            if (!this.container.contains(e.target)) {
                this._hideEmojiPicker();
            }
        });

        // Typing con debounce para stop
        this._debouncedStopTyping = debounce(() => {
            this.onStopTyping?.();
        }, UI_CONFIG.TYPING_TIMEOUT);
    }

    _subscribeToStore() {
        // Cambios en UI (responder/editar)
        chatStore.subscribe('ui', (ui) => {
            if (ui.replyingTo !== this._replyingTo) {
                this._updateReplyBar(ui.replyingTo);
            }
            if (ui.editingMessage !== this._editingMessage) {
                this._updateEditMode(ui.editingMessage);
            }
        });
    }

    // ========================================================================
    // HANDLERS
    // ========================================================================

    _handleInput() {
        // Auto-expand textarea
        this._autoResize();

        // Actualizar estado del boton enviar
        const hasContent = this.textarea.value.trim().length > 0;
        this.sendBtn.disabled = !hasContent;

        // Notificar typing
        if (hasContent) {
            this.onTyping?.();
            this._debouncedStopTyping();
        }

        this.emit('input', { value: this.textarea.value });
    }

    _handleKeydown(e) {
        // Enter para enviar (Shift+Enter para nueva linea)
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            this._handleSend();
        }

        // Escape para cancelar respuesta/edicion
        if (e.key === 'Escape') {
            this.cancelReply();
            this.cancelEdit();
        }
    }

    _handleSend() {
        const content = this.textarea.value.trim();
        if (!content) return;

        const data = {
            content,
            replyTo: this._replyingTo?.id || null,
            editingId: this._editingMessage?.id || null,
        };

        // Callback externo
        this.onSend?.(content, data);

        // Emitir evento
        this.emit('send', data);

        // Limpiar
        this.clear();
        this.cancelReply();
        this.cancelEdit();
    }

    _handleFileSelect(e) {
        const files = Array.from(e.target.files);
        if (files.length === 0) return;

        // Validar tamano
        const oversized = files.filter(f => f.size > MESSAGE_CONFIG.MAX_FILE_SIZE);
        if (oversized.length > 0) {
            this.emit('error', { type: 'file_size', files: oversized });
            return;
        }

        this.onFileSelect?.(files);
        this.emit('fileSelect', { files });

        // Limpiar input
        this.fileInput.value = '';
    }

    _handleEmojiClick(e) {
        const btn = e.target.closest('.message-input__emoji-btn');
        if (!btn) return;

        const emoji = btn.textContent;
        this.insertText(emoji);
        this._hideEmojiPicker();
    }

    // ========================================================================
    // TEXTAREA
    // ========================================================================

    _autoResize() {
        this.textarea.style.height = 'auto';
        const maxHeight = 150; // px
        this.textarea.style.height = Math.min(this.textarea.scrollHeight, maxHeight) + 'px';
    }

    /**
     * Inserta texto en la posicion del cursor
     * @param {string} text - Texto a insertar
     */
    insertText(text) {
        const start = this.textarea.selectionStart;
        const end = this.textarea.selectionEnd;
        const value = this.textarea.value;

        this.textarea.value = value.substring(0, start) + text + value.substring(end);
        this.textarea.selectionStart = this.textarea.selectionEnd = start + text.length;

        this._handleInput();
        this.focus();
    }

    /**
     * Establece el valor del textarea
     * @param {string} text - Texto
     */
    setValue(text) {
        this.textarea.value = text;
        this._handleInput();
    }

    /**
     * Obtiene el valor actual
     * @returns {string}
     */
    getValue() {
        return this.textarea.value;
    }

    /**
     * Limpia el textarea
     */
    clear() {
        this.textarea.value = '';
        this._autoResize();
        this.sendBtn.disabled = true;
    }

    /**
     * Da foco al textarea
     */
    focus() {
        this.textarea.focus();
    }

    // ========================================================================
    // RESPONDER
    // ========================================================================

    /**
     * Establece mensaje para responder
     * @param {Object} message - Mensaje
     */
    setReplyTo(message) {
        this._replyingTo = message;
        chatStore.setReplyingTo(message);
        this._updateReplyBar(message);
        this.focus();
    }

    /**
     * Cancela respuesta
     */
    cancelReply() {
        this._replyingTo = null;
        chatStore.setReplyingTo(null);
        this._updateReplyBar(null);
    }

    _updateReplyBar(message) {
        this._replyingTo = message;

        if (!message) {
            this.replyBar.style.display = 'none';
            this.replyBar.querySelector('i').className = 'fas fa-reply';
            return;
        }

        this.replyBar.style.display = 'flex';
        this.replyBar.querySelector('.message-input__reply-author').textContent =
            message.senderName || 'Usuario';
        this.replyBar.querySelector('.message-input__reply-text').textContent =
            truncate(message.content, 50);
        this.replyBar.querySelector('i').className = 'fas fa-reply';
    }

    // ========================================================================
    // EDITAR
    // ========================================================================

    /**
     * Establece mensaje para editar
     * @param {Object} message - Mensaje
     */
    setEditMessage(message) {
        this._editingMessage = message;
        chatStore.setEditingMessage(message);
        this._updateEditMode(message);
        this.focus();
    }

    /**
     * Cancela edicion
     */
    cancelEdit() {
        this._editingMessage = null;
        chatStore.setEditingMessage(null);
        this._updateEditMode(null);
    }

    _updateEditMode(message) {
        this._editingMessage = message;

        if (!message) {
            this.replyBar.style.display = 'none';
            this.clear();
            return;
        }

        // Mostrar barra como "editando"
        this.replyBar.style.display = 'flex';
        this.replyBar.querySelector('.message-input__reply-author').textContent = 'Editando mensaje';
        this.replyBar.querySelector('.message-input__reply-text').textContent = '';
        this.replyBar.querySelector('i').className = 'fas fa-edit';

        // Cargar contenido en textarea
        this.setValue(message.content);
    }

    // ========================================================================
    // EMOJI PICKER
    // ========================================================================

    _toggleEmojiPicker() {
        if (this.emojiPicker.style.display === 'none') {
            this._showEmojiPicker();
        } else {
            this._hideEmojiPicker();
        }
    }

    _showEmojiPicker() {
        if (this.emojiPicker) {
            this.emojiPicker.style.display = 'block';
        }
    }

    _hideEmojiPicker() {
        if (this.emojiPicker) {
            this.emojiPicker.style.display = 'none';
        }
    }

    // ========================================================================
    // ESTADO
    // ========================================================================

    /**
     * Habilita/deshabilita el input
     * @param {boolean} disabled
     */
    setDisabled(disabled) {
        this.textarea.disabled = disabled;
        this.sendBtn.disabled = disabled;
        if (this.attachBtn) this.attachBtn.disabled = disabled;
        if (this.emojiBtn) this.emojiBtn.disabled = disabled;
    }

    // ========================================================================
    // LIMPIEZA
    // ========================================================================

    destroy() {
        this.container.innerHTML = '';
        this.removeAllListeners();
    }
}

export default MessageInput;
