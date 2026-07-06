/**
 * ╔══════════════════════════════════════════════════════════════════════════════╗
 * ║                         CONFIGURACION - CHAT MODULAR                         ║
 * ║                    Constantes y configuracion centralizada                   ║
 * ╚══════════════════════════════════════════════════════════════════════════════╝
 *
 * Configuracion centralizada del modulo de chat.
 * Todas las constantes configurables deben estar aqui.
 *
 * Autor: Wilson Arguello
 * Fecha: 2026-01-02
 */

// ============================================================================
// CONFIGURACION DE WEBSOCKET
// ============================================================================

export const WEBSOCKET_CONFIG = {
    // Reconexion
    RECONNECT_DELAY: 300,           // ms inicial entre reconexiones
    RECONNECT_MAX_DELAY: 3000,      // ms maximo entre reconexiones
    RECONNECT_ATTEMPTS: 100,        // intentos maximos

    // Timeouts
    CONNECTION_TIMEOUT: 5000,       // ms para timeout de conexion
    MESSAGE_TIMEOUT: 5000,          // ms para timeout de ACK de mensaje

    // Heartbeat
    HEARTBEAT_INTERVAL: 30000,      // ms entre heartbeats

    // Transporte
    TRANSPORTS: ['websocket'],      // Solo WebSocket para minima latencia
    UPGRADE: false,                 // No upgrade desde polling
};

// ============================================================================
// CONFIGURACION DE MENSAJES
// ============================================================================

export const MESSAGE_CONFIG = {
    // Reintentos
    RETRY_ATTEMPTS: 3,              // intentos de reenvio
    RETRY_DELAY: 200,               // ms entre reintentos

    // Timeout
    MESSAGE_TIMEOUT: 10000,         // ms para timeout de mensaje (10s)

    // Cola offline
    OFFLINE_QUEUE_MAX: 200,         // maximo mensajes en cola

    // Paginacion
    MESSAGES_PER_PAGE: 50,          // mensajes por carga

    // Cache
    CACHE_MESSAGES: 100,            // mensajes en memoria por conversacion

    // Contenido
    MAX_LENGTH: 5000,               // caracteres maximos por mensaje
    MAX_FILE_SIZE: 10 * 1024 * 1024, // 10MB maximo por archivo
};

// ============================================================================
// CONFIGURACION DE UI
// ============================================================================

export const UI_CONFIG = {
    // Typing
    TYPING_THROTTLE: 200,           // ms minimo entre eventos typing
    TYPING_TIMEOUT: 3000,           // ms para auto-stop typing
    TYPING_INDICATOR_DURATION: 4000, // ms que se muestra "escribiendo..."

    // Animaciones
    ANIMATION_DURATION: 200,        // ms duracion animaciones
    SCROLL_BEHAVIOR: 'smooth',      // comportamiento de scroll

    // Notificaciones
    NOTIFICATION_DURATION: 5000,    // ms que se muestra notificacion

    // Fechas
    DATE_FORMAT: 'es-EC',           // locale para formateo de fechas
    TIME_FORMAT: { hour: '2-digit', minute: '2-digit' },

    // Tema
    DEFAULT_THEME: 'light',
};

// ============================================================================
// EVENTOS DEL SISTEMA
// ============================================================================

export const EVENTS = {
    // Conexion
    CONNECT: 'chat:connect',
    DISCONNECT: 'chat:disconnect',
    RECONNECTING: 'chat:reconnecting',

    // Mensajes
    MESSAGE_SENT: 'message:sent',
    MESSAGE_RECEIVED: 'message:received',
    MESSAGE_ACK: 'message:ack',
    MESSAGE_SAVED: 'message:saved',
    MESSAGE_ERROR: 'message:error',
    MESSAGE_EDITED: 'message:edited',
    MESSAGE_DELETED: 'message:deleted',
    MESSAGE_STATUS_UPDATED: 'message:status-updated',
    MESSAGE_STATUS_BATCH: 'message:status-batch',

    // Sync / Reconexion
    MESSAGES_SYNCED: 'messages:synced',

    // Conversaciones
    CONVERSATION_JOINED: 'conversation:joined',
    CONVERSATION_LEFT: 'conversation:left',
    CONVERSATION_UPDATED: 'conversation:updated',
    CONVERSATION_NEW: 'conversation:new',

    // Presencia
    USER_ONLINE: 'user:online',
    USER_OFFLINE: 'user:offline',
    USER_TYPING: 'user:typing',
    USER_STOP_TYPING: 'user:stop-typing',

    // Lectura
    MESSAGES_READ: 'messages:read',

    // Reacciones
    REACTION_ADDED: 'reaction:added',
    REACTION_REMOVED: 'reaction:removed',

    // UI
    UI_SCROLL_BOTTOM: 'ui:scroll-bottom',
    UI_SHOW_NOTIFICATION: 'ui:notification',
    UI_THEME_CHANGED: 'ui:theme-changed',

    // Estado
    STATE_CHANGED: 'state:changed',
};

// ============================================================================
// TIPOS Y CONSTANTES
// ============================================================================

export const MESSAGE_TYPES = {
    TEXT: 'text',
    IMAGE: 'image',
    FILE: 'file',
    AUDIO: 'audio',
    VIDEO: 'video',
    GIF: 'gif',
    STICKER: 'sticker',
    SYSTEM: 'system',
};

export const MESSAGE_STATUS = {
    PENDING: 'pending',
    SENDING: 'sending',
    SENT: 'sent',
    DELIVERED: 'delivered',
    READ: 'read',
    ERROR: 'error',
};

export const CONVERSATION_TYPES = {
    DIRECT: 'direct',
    GROUP: 'group',
    CHANNEL: 'channel',
};

export const USER_STATUS = {
    ONLINE: 'online',
    OFFLINE: 'offline',
    AWAY: 'away',
    BUSY: 'busy',
};

// ============================================================================
// EMOJIS DE REACCIONES RAPIDAS
// ============================================================================

export const QUICK_REACTIONS = ['👍', '❤️', '😂', '😮', '😢', '🙏'];

// ============================================================================
// CONFIGURACION DE DEBUG
// ============================================================================

export const DEBUG_CONFIG = {
    ENABLED: false,                 // Activar logs de debug
    LOG_WEBSOCKET: false,           // Logs de eventos WebSocket
    LOG_STATE: false,               // Logs de cambios de estado
    LOG_EVENTS: false,              // Logs de eventos emitidos
};

// ============================================================================
// HELPER PARA OBTENER CONFIGURACION
// ============================================================================

/**
 * Obtiene configuracion con soporte para override via localStorage
 * @param {string} key - Clave de configuracion
 * @param {*} defaultValue - Valor por defecto
 * @returns {*}
 */
export function getConfig(key, defaultValue) {
    try {
        const stored = localStorage.getItem(`chat_config_${key}`);
        if (stored !== null) {
            return JSON.parse(stored);
        }
    } catch (e) {
        // Ignorar errores de localStorage
    }
    return defaultValue;
}

/**
 * Guarda configuracion en localStorage
 * @param {string} key - Clave de configuracion
 * @param {*} value - Valor a guardar
 */
export function setConfig(key, value) {
    try {
        localStorage.setItem(`chat_config_${key}`, JSON.stringify(value));
    } catch (e) {
        console.warn('[Config] No se pudo guardar en localStorage:', e);
    }
}

// Exportar todo como objeto
export default {
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
};
