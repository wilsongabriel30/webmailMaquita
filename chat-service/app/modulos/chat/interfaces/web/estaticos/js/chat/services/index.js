/**
 * ╔══════════════════════════════════════════════════════════════════════════════╗
 * ║                         SERVICES - CHAT MODULAR                              ║
 * ║                        Exports del modulo services                           ║
 * ╚══════════════════════════════════════════════════════════════════════════════╝
 *
 * USO:
 *   import { webSocketService, apiService } from './services/index.js';
 *
 * Autor: Wilson Arguello
 * Fecha: 2026-01-02
 */

export { webSocketService, default as WebSocketService } from './websocket-service.js';
export { apiService, ApiError, default as ApiService } from './api-service.js';
