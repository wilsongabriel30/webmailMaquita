/**
 * ╔══════════════════════════════════════════════════════════════════════════════╗
 * ║                          UTILIDADES - CHAT MODULAR                           ║
 * ║                      Funciones helper reutilizables                          ║
 * ╚══════════════════════════════════════════════════════════════════════════════╝
 *
 * Funciones utilitarias puras sin dependencias externas.
 *
 * Autor: Wilson Arguello
 * Fecha: 2026-01-02
 */

import { UI_CONFIG, DEBUG_CONFIG } from './config.js';

// ============================================================================
// GENERADORES DE ID
// ============================================================================

/**
 * Genera ID unico temporal para mensajes
 * @returns {string}
 */
export function generateTempId() {
    return Date.now().toString(36) + Math.random().toString(36).substr(2, 5);
}

/**
 * Genera UUID v4
 * @returns {string}
 */
export function generateUUID() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        const r = Math.random() * 16 | 0;
        const v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}

// ============================================================================
// FUNCIONES DE TIEMPO
// ============================================================================

/**
 * Retorna timestamp actual en ms
 * @returns {number}
 */
export function now() {
    return Date.now();
}

/**
 * Formatea fecha para mostrar en chat
 * @param {Date|number|string} date - Fecha a formatear
 * @returns {string}
 */
export function formatChatTime(date) {
    const d = date instanceof Date ? date : new Date(date);
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);

    // Hoy: solo hora
    if (isSameDay(d, today)) {
        return d.toLocaleTimeString(UI_CONFIG.DATE_FORMAT, UI_CONFIG.TIME_FORMAT);
    }

    // Ayer
    if (isSameDay(d, yesterday)) {
        return `Ayer ${d.toLocaleTimeString(UI_CONFIG.DATE_FORMAT, UI_CONFIG.TIME_FORMAT)}`;
    }

    // Esta semana: dia de la semana
    const diffDays = Math.floor((today - d) / (1000 * 60 * 60 * 24));
    if (diffDays < 7) {
        return d.toLocaleDateString(UI_CONFIG.DATE_FORMAT, {
            weekday: 'long',
            hour: '2-digit',
            minute: '2-digit'
        });
    }

    // Mas antiguo: fecha completa
    return d.toLocaleDateString(UI_CONFIG.DATE_FORMAT, {
        day: '2-digit',
        month: 'short',
        year: d.getFullYear() !== today.getFullYear() ? 'numeric' : undefined,
        hour: '2-digit',
        minute: '2-digit'
    });
}

/**
 * Formatea fecha para separador de dia en chat
 * @param {Date|number|string} date - Fecha
 * @returns {string}
 */
export function formatDaySeparator(date) {
    const d = date instanceof Date ? date : new Date(date);
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);

    if (isSameDay(d, today)) {
        return 'Hoy';
    }

    if (isSameDay(d, yesterday)) {
        return 'Ayer';
    }

    return d.toLocaleDateString(UI_CONFIG.DATE_FORMAT, {
        weekday: 'long',
        day: 'numeric',
        month: 'long',
        year: d.getFullYear() !== today.getFullYear() ? 'numeric' : undefined
    });
}

/**
 * Verifica si dos fechas son el mismo dia
 * @param {Date} d1
 * @param {Date} d2
 * @returns {boolean}
 */
export function isSameDay(d1, d2) {
    return d1.getFullYear() === d2.getFullYear() &&
           d1.getMonth() === d2.getMonth() &&
           d1.getDate() === d2.getDate();
}

/**
 * Retorna "hace X" para tiempos relativos
 * @param {Date|number|string} date - Fecha
 * @returns {string}
 */
export function timeAgo(date) {
    const d = date instanceof Date ? date : new Date(date);
    const seconds = Math.floor((Date.now() - d) / 1000);

    if (seconds < 60) return 'ahora';
    if (seconds < 3600) return `hace ${Math.floor(seconds / 60)} min`;
    if (seconds < 86400) return `hace ${Math.floor(seconds / 3600)} h`;
    if (seconds < 604800) return `hace ${Math.floor(seconds / 86400)} d`;

    return formatChatTime(d);
}

// ============================================================================
// FUNCIONES DE THROTTLE/DEBOUNCE
// ============================================================================

/**
 * Crea funcion con debounce
 * @param {Function} func - Funcion a ejecutar
 * @param {number} wait - Tiempo de espera en ms
 * @returns {Function}
 */
export function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func.apply(this, args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * Crea funcion con throttle
 * @param {Function} func - Funcion a ejecutar
 * @param {number} limit - Tiempo minimo entre ejecuciones en ms
 * @returns {Function}
 */
export function throttle(func, limit) {
    let lastCall = 0;
    return function executedFunction(...args) {
        const now = Date.now();
        if (now - lastCall >= limit) {
            lastCall = now;
            func.apply(this, args);
        }
    };
}

// ============================================================================
// FUNCIONES DE TEXTO
// ============================================================================

/**
 * Escapa HTML para prevenir XSS
 * @param {string} text - Texto a escapar
 * @returns {string}
 */
export function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}

/**
 * Trunca texto a longitud maxima
 * @param {string} text - Texto a truncar
 * @param {number} maxLength - Longitud maxima
 * @param {string} suffix - Sufijo (default: '...')
 * @returns {string}
 */
export function truncate(text, maxLength, suffix = '...') {
    if (!text || text.length <= maxLength) return text;
    return text.substring(0, maxLength - suffix.length) + suffix;
}

/**
 * Convierte URLs en texto a enlaces HTML
 * @param {string} text - Texto con URLs
 * @returns {string}
 */
export function linkify(text) {
    const urlRegex = /(https?:\/\/[^\s]+)/g;
    return escapeHtml(text).replace(urlRegex, '<a href="$1" target="_blank" rel="noopener">$1</a>');
}

/**
 * Obtiene iniciales de un nombre
 * @param {string} name - Nombre completo
 * @returns {string}
 */
export function getInitials(name) {
    if (!name) return '?';
    const parts = name.trim().split(/\s+/);
    if (parts.length === 1) {
        return parts[0].charAt(0).toUpperCase();
    }
    return (parts[0].charAt(0) + parts[parts.length - 1].charAt(0)).toUpperCase();
}

// ============================================================================
// FUNCIONES DE ARCHIVOS
// ============================================================================

/**
 * Formatea tamano de archivo
 * @param {number} bytes - Bytes
 * @returns {string}
 */
export function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

/**
 * Obtiene icono de tipo de archivo
 * @param {string} mimeType - Tipo MIME
 * @returns {string} - Clase de icono
 */
export function getFileIcon(mimeType) {
    if (!mimeType) return 'fa-file';

    if (mimeType.startsWith('image/')) return 'fa-file-image';
    if (mimeType.startsWith('video/')) return 'fa-file-video';
    if (mimeType.startsWith('audio/')) return 'fa-file-audio';
    if (mimeType.includes('pdf')) return 'fa-file-pdf';
    if (mimeType.includes('word') || mimeType.includes('document')) return 'fa-file-word';
    if (mimeType.includes('excel') || mimeType.includes('spreadsheet')) return 'fa-file-excel';
    if (mimeType.includes('powerpoint') || mimeType.includes('presentation')) return 'fa-file-powerpoint';
    if (mimeType.includes('zip') || mimeType.includes('compressed')) return 'fa-file-archive';

    return 'fa-file';
}

/**
 * Verifica si un archivo es imagen
 * @param {string} mimeType - Tipo MIME
 * @returns {boolean}
 */
export function isImage(mimeType) {
    return mimeType && mimeType.startsWith('image/');
}

// ============================================================================
// FUNCIONES DE DOM
// ============================================================================

/**
 * Crea elemento HTML desde template string
 * @param {string} html - HTML string
 * @returns {HTMLElement}
 */
export function createElement(html) {
    const template = document.createElement('template');
    template.innerHTML = html.trim();
    return template.content.firstChild;
}

/**
 * Hace scroll al fondo de un elemento
 * @param {HTMLElement} element - Elemento
 * @param {boolean} smooth - Usar animacion suave
 */
export function scrollToBottom(element, smooth = true) {
    if (!element) return;

    element.scrollTo({
        top: element.scrollHeight,
        behavior: smooth ? 'smooth' : 'auto'
    });
}

/**
 * Verifica si el scroll esta cerca del fondo
 * @param {HTMLElement} element - Elemento
 * @param {number} threshold - Umbral en pixels
 * @returns {boolean}
 */
export function isNearBottom(element, threshold = 100) {
    if (!element) return true;
    return element.scrollHeight - element.scrollTop - element.clientHeight < threshold;
}

// ============================================================================
// FUNCIONES DE LOGGING
// ============================================================================

/**
 * Log con prefijo de chat
 * @param  {...any} args - Argumentos
 */
export function log(...args) {
    if (DEBUG_CONFIG.ENABLED) {
        console.log(`[Chat ${new Date().toISOString().substr(11, 12)}]`, ...args);
    }
}

/**
 * Log de WebSocket
 * @param  {...any} args - Argumentos
 */
export function logWS(...args) {
    if (DEBUG_CONFIG.ENABLED && DEBUG_CONFIG.LOG_WEBSOCKET) {
        console.log(`[WS ${new Date().toISOString().substr(11, 12)}]`, ...args);
    }
}

/**
 * Log de estado
 * @param  {...any} args - Argumentos
 */
export function logState(...args) {
    if (DEBUG_CONFIG.ENABLED && DEBUG_CONFIG.LOG_STATE) {
        console.log(`[State ${new Date().toISOString().substr(11, 12)}]`, ...args);
    }
}

// ============================================================================
// FUNCIONES DE STORAGE
// ============================================================================

/**
 * Guarda en localStorage con JSON
 * @param {string} key - Clave
 * @param {*} value - Valor
 */
export function saveToStorage(key, value) {
    try {
        localStorage.setItem(key, JSON.stringify(value));
    } catch (e) {
        console.warn('[Storage] Error guardando:', e);
    }
}

/**
 * Obtiene de localStorage con JSON
 * @param {string} key - Clave
 * @param {*} defaultValue - Valor por defecto
 * @returns {*}
 */
export function getFromStorage(key, defaultValue = null) {
    try {
        const item = localStorage.getItem(key);
        return item ? JSON.parse(item) : defaultValue;
    } catch (e) {
        return defaultValue;
    }
}

/**
 * Elimina de localStorage
 * @param {string} key - Clave
 */
export function removeFromStorage(key) {
    try {
        localStorage.removeItem(key);
    } catch (e) {
        // Ignorar
    }
}

// ============================================================================
// EXPORT DEFAULT
// ============================================================================

export default {
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
};
