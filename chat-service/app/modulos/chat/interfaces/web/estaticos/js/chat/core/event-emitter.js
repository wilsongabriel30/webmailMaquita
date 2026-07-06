/**
 * ╔══════════════════════════════════════════════════════════════════════════════╗
 * ║                          EVENT EMITTER - CHAT MODULAR                        ║
 * ║                  Sistema de eventos pub/sub para componentes                  ║
 * ╚══════════════════════════════════════════════════════════════════════════════╝
 *
 * Implementacion ligera de EventEmitter para comunicacion entre componentes.
 * Permite desacoplar modulos manteniendo comunicacion reactiva.
 *
 * USO:
 *   import { EventEmitter } from './core/event-emitter.js';
 *
 *   class MiComponente extends EventEmitter {
 *       hacerAlgo() {
 *           this.emit('algo-paso', { data: 'valor' });
 *       }
 *   }
 *
 * Autor: Wilson Arguello
 * Fecha: 2026-01-02
 */

export class EventEmitter {
    constructor() {
        this._events = new Map();
        this._onceEvents = new Map();
    }

    /**
     * Suscribe a un evento
     * @param {string} event - Nombre del evento
     * @param {Function} callback - Funcion a ejecutar
     * @returns {Function} - Funcion para desuscribirse
     */
    on(event, callback) {
        if (!this._events.has(event)) {
            this._events.set(event, new Set());
        }
        this._events.get(event).add(callback);

        // Retorna funcion de limpieza
        return () => this.off(event, callback);
    }

    /**
     * Suscribe a un evento una sola vez
     * @param {string} event - Nombre del evento
     * @param {Function} callback - Funcion a ejecutar
     * @returns {Function} - Funcion para desuscribirse
     */
    once(event, callback) {
        if (!this._onceEvents.has(event)) {
            this._onceEvents.set(event, new Set());
        }
        this._onceEvents.get(event).add(callback);

        return () => {
            if (this._onceEvents.has(event)) {
                this._onceEvents.get(event).delete(callback);
            }
        };
    }

    /**
     * Desuscribe de un evento
     * @param {string} event - Nombre del evento
     * @param {Function} callback - Funcion a remover
     */
    off(event, callback) {
        if (this._events.has(event)) {
            this._events.get(event).delete(callback);
        }
        if (this._onceEvents.has(event)) {
            this._onceEvents.get(event).delete(callback);
        }
    }

    /**
     * Emite un evento
     * @param {string} event - Nombre del evento
     * @param {*} data - Datos a enviar
     */
    emit(event, data) {
        // Ejecutar listeners regulares
        if (this._events.has(event)) {
            this._events.get(event).forEach(callback => {
                try {
                    callback(data);
                } catch (error) {
                    console.error(`[EventEmitter] Error en callback para '${event}':`, error);
                }
            });
        }

        // Ejecutar listeners once y limpiar
        if (this._onceEvents.has(event)) {
            const onceCallbacks = this._onceEvents.get(event);
            this._onceEvents.delete(event);
            onceCallbacks.forEach(callback => {
                try {
                    callback(data);
                } catch (error) {
                    console.error(`[EventEmitter] Error en callback once para '${event}':`, error);
                }
            });
        }
    }

    /**
     * Remueve todos los listeners de un evento o todos
     * @param {string} [event] - Evento especifico (opcional)
     */
    removeAllListeners(event) {
        if (event) {
            this._events.delete(event);
            this._onceEvents.delete(event);
        } else {
            this._events.clear();
            this._onceEvents.clear();
        }
    }

    /**
     * Cuenta listeners de un evento
     * @param {string} event - Nombre del evento
     * @returns {number}
     */
    listenerCount(event) {
        let count = 0;
        if (this._events.has(event)) {
            count += this._events.get(event).size;
        }
        if (this._onceEvents.has(event)) {
            count += this._onceEvents.get(event).size;
        }
        return count;
    }

    /**
     * Lista todos los eventos con listeners
     * @returns {string[]}
     */
    eventNames() {
        const names = new Set([
            ...this._events.keys(),
            ...this._onceEvents.keys()
        ]);
        return Array.from(names);
    }
}

// ============================================================================
// SINGLETON GLOBAL - Bus de eventos de la aplicacion
// ============================================================================

/**
 * Bus de eventos global para comunicacion entre modulos desacoplados.
 *
 * USO:
 *   import { eventBus } from './core/event-emitter.js';
 *
 *   // Emitir
 *   eventBus.emit('user:logged-in', { userId: 123 });
 *
 *   // Escuchar
 *   eventBus.on('user:logged-in', (data) => console.log(data));
 */
export const eventBus = new EventEmitter();

// Exportar por defecto la clase
export default EventEmitter;
