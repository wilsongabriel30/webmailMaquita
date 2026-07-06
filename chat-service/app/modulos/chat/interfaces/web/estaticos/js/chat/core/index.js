/**
 * ╔══════════════════════════════════════════════════════════════════════════════╗
 * ║                            CORE - CHAT MODULAR                               ║
 * ║                         Exports del modulo core                              ║
 * ╚══════════════════════════════════════════════════════════════════════════════╝
 *
 * Punto de entrada para el modulo core.
 *
 * USO:
 *   import { EventEmitter, eventBus, EVENTS, debounce } from './core/index.js';
 *
 * Autor: Wilson Arguello
 * Fecha: 2026-01-02
 */

// Event Emitter
export { EventEmitter, eventBus } from './event-emitter.js';

// Configuracion
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
} from './config.js';

// Utilidades
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
} from './utils.js';

// Re-exportar defaults como namespace
import EventEmitterModule from './event-emitter.js';
import ConfigModule from './config.js';
import UtilsModule from './utils.js';

export const Core = {
    ...EventEmitterModule,
    ...ConfigModule,
    ...UtilsModule,
};

export default Core;
