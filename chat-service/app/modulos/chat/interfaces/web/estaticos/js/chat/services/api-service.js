/**
 * ╔══════════════════════════════════════════════════════════════════════════════╗
 * ║                        API SERVICE - CHAT MODULAR                            ║
 * ║                    Servicio HTTP para operaciones REST                       ║
 * ╚══════════════════════════════════════════════════════════════════════════════╝
 *
 * Servicio para comunicacion HTTP con el backend.
 * Usado para operaciones que no requieren tiempo real.
 *
 * USO:
 *   import { apiService } from './services/api-service.js';
 *
 *   const conversations = await apiService.getConversations();
 *   const messages = await apiService.getMessages(conversationId);
 *
 * Autor: Wilson Arguello
 * Fecha: 2026-01-02
 */

import { log } from '../core/utils.js';

// ============================================================================
// CONFIGURACION
// ============================================================================

const API_CONFIG = {
    BASE_URL: '/api/chat',
    TIMEOUT: 10000,
    HEADERS: {
        'Content-Type': 'application/json',
    },
};

// ============================================================================
// CLASE PRINCIPAL
// ============================================================================

class ApiService {
    constructor() {
        this.baseUrl = API_CONFIG.BASE_URL;
    }

    // ========================================================================
    // METODOS HTTP BASE
    // ========================================================================

    /**
     * Realiza peticion HTTP
     * @param {string} endpoint - Endpoint
     * @param {Object} options - Opciones fetch
     * @returns {Promise<Object>}
     */
    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;

        const config = {
            headers: { ...API_CONFIG.HEADERS },
            ...options,
        };

        // Agregar body si existe
        if (options.body && typeof options.body === 'object') {
            config.body = JSON.stringify(options.body);
        }

        try {
            const controller = new AbortController();
            const timeout = setTimeout(() => controller.abort(), API_CONFIG.TIMEOUT);

            const response = await fetch(url, {
                ...config,
                signal: controller.signal,
            });

            clearTimeout(timeout);

            if (!response.ok) {
                const error = await response.json().catch(() => ({}));
                throw new ApiError(
                    error.message || `Error ${response.status}`,
                    response.status,
                    error
                );
            }

            return await response.json();

        } catch (error) {
            if (error.name === 'AbortError') {
                throw new ApiError('Timeout de peticion', 408);
            }
            throw error;
        }
    }

    async get(endpoint, params = {}) {
        const queryString = new URLSearchParams(params).toString();
        const url = queryString ? `${endpoint}?${queryString}` : endpoint;
        return this.request(url, { method: 'GET' });
    }

    async post(endpoint, data = {}) {
        return this.request(endpoint, { method: 'POST', body: data });
    }

    async put(endpoint, data = {}) {
        return this.request(endpoint, { method: 'PUT', body: data });
    }

    async delete(endpoint) {
        return this.request(endpoint, { method: 'DELETE' });
    }

    // ========================================================================
    // CONVERSACIONES
    // ========================================================================

    /**
     * Obtiene lista de conversaciones
     * @param {Object} params - Parametros de filtro
     * @returns {Promise<Array>}
     */
    async getConversations(params = {}) {
        log('[API] Obteniendo conversaciones');
        const response = await this.get('/conversaciones', params);
        return response.data || response.conversaciones || response;
    }

    /**
     * Obtiene una conversacion por ID
     * @param {number|string} id - ID de conversacion
     * @returns {Promise<Object>}
     */
    async getConversation(id) {
        log('[API] Obteniendo conversacion:', id);
        const response = await this.get(`/conversaciones/${id}`);
        return response.data || response.conversacion || response;
    }

    /**
     * Crea nueva conversacion
     * @param {Object} data - Datos de la conversacion
     * @returns {Promise<Object>}
     */
    async createConversation(data) {
        log('[API] Creando conversacion');
        const response = await this.post('/conversaciones', data);
        return response.data || response.conversacion || response;
    }

    /**
     * Actualiza conversacion
     * @param {number|string} id - ID
     * @param {Object} data - Datos a actualizar
     * @returns {Promise<Object>}
     */
    async updateConversation(id, data) {
        log('[API] Actualizando conversacion:', id);
        const response = await this.put(`/conversaciones/${id}`, data);
        return response.data || response;
    }

    /**
     * Busca o crea conversacion directa con usuario
     * @param {number|string} userId - ID del usuario
     * @returns {Promise<Object>}
     */
    async getOrCreateDirectConversation(userId) {
        log('[API] Obteniendo/creando conversacion directa con:', userId);
        const response = await this.post('/conversaciones/directa', { usuario_id: userId });
        return response.data || response.conversacion || response;
    }

    // ========================================================================
    // MENSAJES
    // ========================================================================

    /**
     * Obtiene mensajes de una conversacion
     * @param {number|string} conversationId - ID de conversacion
     * @param {Object} params - Parametros (page, limit, before, after)
     * @returns {Promise<Object>} - { mensajes, total, hasMore }
     */
    async getMessages(conversationId, params = {}) {
        log('[API] Obteniendo mensajes de:', conversationId);
        const response = await this.get(`/conversaciones/${conversationId}/mensajes`, params);
        return {
            mensajes: response.data || response.mensajes || response,
            total: response.total || 0,
            hasMore: response.has_more || response.hasMore || false,
        };
    }

    /**
     * Envia mensaje via HTTP (fallback si WS no disponible)
     * @param {number|string} conversationId - ID
     * @param {Object} data - Datos del mensaje
     * @returns {Promise<Object>}
     */
    async sendMessage(conversationId, data) {
        log('[API] Enviando mensaje via HTTP a:', conversationId);
        const response = await this.post(`/conversaciones/${conversationId}/mensajes`, data);
        return response.data || response.mensaje || response;
    }

    /**
     * Edita un mensaje
     * @param {number|string} messageId - ID del mensaje
     * @param {Object} data - Datos a actualizar
     * @returns {Promise<Object>}
     */
    async editMessage(messageId, data) {
        log('[API] Editando mensaje:', messageId);
        const response = await this.put(`/mensajes/${messageId}`, data);
        return response.data || response;
    }

    /**
     * Elimina un mensaje
     * @param {number|string} messageId - ID del mensaje
     * @returns {Promise<void>}
     */
    async deleteMessage(messageId) {
        log('[API] Eliminando mensaje:', messageId);
        await this.delete(`/mensajes/${messageId}`);
    }

    // ========================================================================
    // PARTICIPANTES
    // ========================================================================

    /**
     * Obtiene participantes de una conversacion
     * @param {number|string} conversationId - ID
     * @returns {Promise<Array>}
     */
    async getParticipants(conversationId) {
        log('[API] Obteniendo participantes de:', conversationId);
        const response = await this.get(`/conversaciones/${conversationId}/participantes`);
        return response.data || response.participantes || response;
    }

    /**
     * Agrega participante a conversacion grupal
     * @param {number|string} conversationId - ID
     * @param {number|string} userId - ID usuario
     * @returns {Promise<Object>}
     */
    async addParticipant(conversationId, userId) {
        log('[API] Agregando participante:', userId, 'a:', conversationId);
        const response = await this.post(`/conversaciones/${conversationId}/participantes`, {
            usuario_id: userId,
        });
        return response.data || response;
    }

    /**
     * Remueve participante
     * @param {number|string} conversationId - ID
     * @param {number|string} userId - ID usuario
     * @returns {Promise<void>}
     */
    async removeParticipant(conversationId, userId) {
        log('[API] Removiendo participante:', userId, 'de:', conversationId);
        await this.delete(`/conversaciones/${conversationId}/participantes/${userId}`);
    }

    // ========================================================================
    // BUSQUEDA
    // ========================================================================

    /**
     * Busca mensajes
     * @param {string} query - Texto a buscar
     * @param {Object} params - Parametros adicionales
     * @returns {Promise<Object>}
     */
    async searchMessages(query, params = {}) {
        log('[API] Buscando:', query);
        const response = await this.get('/buscar', { q: query, ...params });
        return {
            resultados: response.data || response.resultados || response,
            total: response.total || 0,
        };
    }

    /**
     * Busca usuarios para mencionar o agregar
     * @param {string} query - Texto a buscar
     * @returns {Promise<Array>}
     */
    async searchUsers(query) {
        log('[API] Buscando usuarios:', query);
        const response = await this.get('/usuarios/buscar', { q: query });
        return response.data || response.usuarios || response;
    }

    // ========================================================================
    // ARCHIVOS
    // ========================================================================

    /**
     * Sube un archivo
     * @param {File} file - Archivo a subir
     * @param {Object} options - Opciones
     * @returns {Promise<Object>}
     */
    async uploadFile(file, options = {}) {
        log('[API] Subiendo archivo:', file.name);

        const formData = new FormData();
        formData.append('file', file);

        if (options.conversationId) {
            formData.append('conversation_id', options.conversationId);
        }

        const response = await fetch(`${this.baseUrl}/archivos`, {
            method: 'POST',
            body: formData,
        });

        if (!response.ok) {
            throw new ApiError('Error subiendo archivo', response.status);
        }

        return await response.json();
    }

    // ========================================================================
    // CONFIGURACION
    // ========================================================================

    /**
     * Obtiene configuracion de chat del usuario
     * @returns {Promise<Object>}
     */
    async getSettings() {
        log('[API] Obteniendo configuracion');
        const response = await this.get('/configuracion');
        return response.data || response;
    }

    /**
     * Actualiza configuracion
     * @param {Object} settings - Configuracion
     * @returns {Promise<Object>}
     */
    async updateSettings(settings) {
        log('[API] Actualizando configuracion');
        const response = await this.put('/configuracion', settings);
        return response.data || response;
    }
}

// ============================================================================
// ERROR PERSONALIZADO
// ============================================================================

class ApiError extends Error {
    constructor(message, status, data = {}) {
        super(message);
        this.name = 'ApiError';
        this.status = status;
        this.data = data;
    }
}

// ============================================================================
// SINGLETON
// ============================================================================

export const apiService = new ApiService();

export { ApiError };
export default apiService;
