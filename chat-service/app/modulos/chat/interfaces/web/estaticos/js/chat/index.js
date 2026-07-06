/**
 * ╔══════════════════════════════════════════════════════════════════════════════╗
 * ║                     MODULO CHAT - PUNTO DE ENTRADA                           ║
 * ║                        Sistema FARO - Maquita MCCH                           ║
 * ╚══════════════════════════════════════════════════════════════════════════════╝
 *
 * Este es el punto de entrada principal del modulo de chat modular.
 * Exporta todos los componentes, servicios y utilidades necesarios.
 *
 * ARQUITECTURA:
 * -------------
 * chat/
 * ├── core/           # Utilidades base (EventEmitter, config, utils)
 * ├── state/          # Gestor de estado (ChatStore)
 * ├── services/       # Servicios (WebSocket, API)
 * ├── components/     # Componentes UI
 * ├── chat-app.js     # Orquestador principal
 * └── index.js        # Este archivo
 *
 * USO BASICO:
 * -----------
 * // Importar todo el modulo
 * import Chat from './chat/index.js';
 *
 * // Usar ChatApp (recomendado)
 * const chat = new Chat.ChatApp({
 *     container: '#chat-container',
 *     userId: 123,
 *     userName: 'Juan',
 * });
 * await chat.init();
 *
 * USO AVANZADO:
 * -------------
 * // Importar componentes individuales
 * import { chatStore, webSocketService, MessageList } from './chat/index.js';
 *
 * // Usar store directamente
 * chatStore.setUser({ id: 123, name: 'Juan' });
 *
 * // Usar servicio WebSocket
 * await webSocketService.connect();
 * webSocketService.sendMessage(1, 'Hola!');
 *
 * COMPATIBILIDAD:
 * ---------------
 * Este modulo es compatible con los clientes legacy:
 * - ChatWebSocket (chat-websocket.js)
 * - ChatUltraFast (chat-ultrafast.js)
 *
 * Autor: Wilson Arguello
 * Correo: gestiontecnologia@maquita.com.ec
 * Fecha: 2026-01-02
 */

// ============================================================================
// CORE
// ============================================================================

export {
    EventEmitter,
    eventBus,
} from './core/event-emitter.js';

export {
    WEBSOCKET_CONFIG,
    MESSAGE_CONFIG,
    UI_CONFIG,
    EVENTS,
    MESSAGE_TYPES,
    MESSAGE_STATUS,
    CONVERSATION_TYPES,
    USER_STATUS,
    QUICK_REACTIONS,
    DEBUG_CONFIG,
    getConfig,
    setConfig,
} from './core/config.js';

export {
    generateTempId,
    generateUUID,
    now,
    formatChatTime,
    formatDaySeparator,
    isSameDay,
    timeAgo,
    debounce,
    throttle,
    escapeHtml,
    truncate,
    linkify,
    getInitials,
    formatFileSize,
    getFileIcon,
    isImage,
    createElement,
    scrollToBottom,
    isNearBottom,
    log,
    logWS,
    logState,
    saveToStorage,
    getFromStorage,
    removeFromStorage,
} from './core/utils.js';

// ============================================================================
// STATE
// ============================================================================

export { chatStore } from './state/chat-store.js';

// ============================================================================
// SERVICES
// ============================================================================

export { webSocketService } from './services/websocket-service.js';
export { apiService, ApiError } from './services/api-service.js';

// ============================================================================
// COMPONENTS
// ============================================================================

export { MessageList } from './components/message-list.js';
export { MessageInput } from './components/message-input.js';
export { ConversationList } from './components/conversation-list.js';

// ============================================================================
// MAIN APP
// ============================================================================

export { ChatApp, default } from './chat-app.js';

// ============================================================================
// NAMESPACE GLOBAL
// ============================================================================

// Para uso sin module bundler
const ChatModule = {
    // Core
    EventEmitter: (await import('./core/event-emitter.js')).EventEmitter,
    eventBus: (await import('./core/event-emitter.js')).eventBus,

    // State
    chatStore: (await import('./state/chat-store.js')).chatStore,

    // Services
    webSocketService: (await import('./services/websocket-service.js')).webSocketService,
    apiService: (await import('./services/api-service.js')).apiService,

    // Components
    MessageList: (await import('./components/message-list.js')).MessageList,
    MessageInput: (await import('./components/message-input.js')).MessageInput,
    ConversationList: (await import('./components/conversation-list.js')).ConversationList,

    // Main
    ChatApp: (await import('./chat-app.js')).ChatApp,
};

// Exponer globalmente
if (typeof window !== 'undefined') {
    window.ChatModule = ChatModule;
}

export { ChatModule };
