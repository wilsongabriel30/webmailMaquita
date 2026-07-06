/**
 * ╔══════════════════════════════════════════════════════════════════════════════╗
 * ║                     SISTEMA FARO - CHAT ULTRA-RÁPIDO v3.0                   ║
 * ║                    Fundación Maquita Cushunchic (MCCH)                       ║
 * ║                                                                              ║
 * ║  PROTOCOLO: WebSocket puro (sin HTTP para mensajes)                         ║
 * ║  LATENCIA: <5ms end-to-end                                                  ║
 * ║                                                                              ║
 * ║  Características:                                                            ║
 * ║  - Envío 100% WebSocket (sin HTTP POST)                                     ║
 * ║  - ACK instantáneo antes de guardar en DB                                   ║
 * ║  - UI Optimista ultra-rápida                                                ║
 * ║  - Cola offline con retry automático                                        ║
 * ║  - Detección de duplicados                                                  ║
 * ║  - Sincronización entre pestañas                                            ║
 * ║                                                                              ║
 * ║  Desarrollado por: Wilson Arguello                                          ║
 * ║  Email: gestiontecnologia@maquita.com.ec                                    ║
 * ║  Año: 2026                                                                  ║
 * ╚══════════════════════════════════════════════════════════════════════════════╝
 */

(function(window) {
    'use strict';

    // ========================================================================
    // CONFIGURACIÓN
    // ========================================================================

    const CONFIG = {
        // Reconexión
        RECONNECT_DELAY: 300,
        RECONNECT_MAX_DELAY: 3000,
        RECONNECT_ATTEMPTS: 100,

        // Mensajes
        MESSAGE_TIMEOUT: 5000,     // 5s timeout para ACK
        RETRY_ATTEMPTS: 3,
        RETRY_DELAY: 200,

        // UI
        TYPING_THROTTLE: 200,      // 200ms throttle
        TYPING_TIMEOUT: 3000,      // 3s auto-stop

        // Cola offline
        OFFLINE_QUEUE_MAX: 200,

        // Debug
        DEBUG: false
    };

    // ========================================================================
    // UTILIDADES
    // ========================================================================

    const Utils = {
        genId: () => Date.now().toString(36) + Math.random().toString(36).substr(2, 5),
        now: () => Date.now(),
        log: (...args) => CONFIG.DEBUG && console.log(`[UltraFast ${new Date().toISOString().substr(11, 12)}]`, ...args)
    };

    // ========================================================================
    // CLASE PRINCIPAL
    // ========================================================================

    class ChatUltraFast {
        constructor(options = {}) {
            this.userId = options.userId;
            this.socket = null;
            this.connected = false;

            // Estado
            this.currentConversation = null;
            this.reconnectAttempts = 0;
            this.latency = 0;

            // Colas y tracking
            this.pendingMessages = new Map();   // tempId -> messageData
            this.shownMessages = new Set();     // IDs de mensajes mostrados
            this.offlineQueue = [];             // Mensajes para enviar cuando reconecte
            this.typingTimer = null;

            // Callbacks
            this.callbacks = {
                onMessage: null,
                onAck: null,
                onSaved: null,
                onTyping: null,
                onOnline: null,
                onOffline: null,
                onRead: null,
                onConnect: null,
                onDisconnect: null,
                onLatency: null,
                onError: null
            };

            this._init();
        }

        // ====================================================================
        // INICIALIZACIÓN
        // ====================================================================

        _init() {
            // Red online/offline
            window.addEventListener('online', () => this._onNetworkChange(true));
            window.addEventListener('offline', () => this._onNetworkChange(false));

            // Sync entre tabs
            if (window.BroadcastChannel) {
                this.bc = new BroadcastChannel('chat_ultrafast');
                this.bc.onmessage = (e) => this._onBroadcast(e.data);
            }

            Utils.log('ChatUltraFast v3.0 inicializado');
        }

        // ====================================================================
        // CONEXIÓN
        // ====================================================================

        connect() {
            return new Promise((resolve, reject) => {
                if (this.connected) {
                    resolve();
                    return;
                }

                try {
                    this.socket = io({
                        transports: ['websocket'],  // Solo WebSocket!
                        upgrade: false,
                        reconnection: true,
                        reconnectionDelay: CONFIG.RECONNECT_DELAY,
                        reconnectionDelayMax: CONFIG.RECONNECT_MAX_DELAY,
                        reconnectionAttempts: CONFIG.RECONNECT_ATTEMPTS,
                        timeout: 20000,  // 20s timeout para conexiones lentas
                        forceNew: true   // Forzar nueva conexión
                    });

                    this._setupHandlers(resolve, reject);

                    // Timeout de seguridad - resolver después de 15s aunque no conecte
                    // (para evitar que la Promise quede pendiente indefinidamente)
                    setTimeout(() => {
                        if (!this.connected) {
                            Utils.log('⚠️ Timeout de conexión - continuando sin WebSocket');
                            resolve(); // Resolver para no bloquear, pero connected = false
                        }
                    }, 15000);

                } catch (e) {
                    reject(e);
                }
            });
        }

        _setupHandlers(resolve, reject) {
            // Conexión
            this.socket.on('connect', () => {
                this.connected = true;
                this.reconnectAttempts = 0;
                Utils.log('⚡ Conectado');

                // Enviar cola offline
                this._flushOfflineQueue();

                // Callback
                this._trigger('onConnect');
                resolve();
            });

            // Desconexión
            this.socket.on('disconnect', (reason) => {
                this.connected = false;
                Utils.log('❌ Desconectado:', reason);
                this._trigger('onDisconnect', { reason });
            });

            // Error
            this.socket.on('connect_error', (err) => {
                this.reconnectAttempts++;
                Utils.log('Error conexión:', err.message);

                if (this.reconnectAttempts >= CONFIG.RECONNECT_ATTEMPTS) {
                    reject(new Error('Max reconnect attempts'));
                }
            });

            // ================================================================
            // HANDLERS DE MENSAJES
            // ================================================================

            // ACK instantáneo (mensaje recibido por servidor)
            this.socket.on('ack', (data) => {
                Utils.log('✓ ACK:', data.t);
                const pending = this.pendingMessages.get(data.t);
                if (pending) {
                    pending.status = 'received';
                    pending.serverTs = data.ts;
                    this._trigger('onAck', { tempId: data.t, status: 'received' });
                }
            });

            // Mensaje guardado en DB (con ID real)
            this.socket.on('msg_saved', (data) => {
                Utils.log('✓✓ Guardado:', data.t, '->', data.id);
                const pending = this.pendingMessages.get(data.t);
                if (pending) {
                    pending.realId = data.id;
                    pending.status = data.s === 'saved' ? 'saved' : 'error';
                    this.pendingMessages.delete(data.t);

                    // Registrar ID real
                    if (data.id) {
                        this.shownMessages.add(String(data.id));
                    }

                    this._trigger('onSaved', {
                        tempId: data.t,
                        realId: data.id,
                        status: data.s
                    });
                }
            });

            // Mensaje nuevo recibido
            this.socket.on('msg', (data) => {
                console.log('📩📩📩 [UltraFast] MENSAJE RECIBIDO VIA WEBSOCKET:', data);
                Utils.log('📩 Mensaje:', data);

                const msgId = String(data.id || data.t || '');

                // Evitar duplicados
                if (msgId && this.shownMessages.has(msgId)) {
                    console.log('📩 [UltraFast] Duplicado ignorado:', msgId);
                    Utils.log('Duplicado ignorado:', msgId);
                    return;
                }

                // Ignorar mensajes propios (ya mostrados via UI optimista)
                if (data.from == this.userId) {
                    console.log('📩 [UltraFast] Mensaje propio ignorado, from:', data.from, 'userId:', this.userId);
                    Utils.log('Mensaje propio ignorado');
                    if (msgId) this.shownMessages.add(msgId);
                    return;
                }

                // Registrar
                if (msgId) this.shownMessages.add(msgId);

                console.log('📩 [UltraFast] Disparando callback onMessage para:', msgId);

                // Callback
                this._trigger('onMessage', {
                    id: data.id,
                    tempId: data.t,
                    conversationId: data.c,
                    content: data.m,
                    senderId: data.from,
                    senderName: data.nombre || '',
                    timestamp: data.ts,
                    type: data.type || 'text',
                    status: data.s,
                    gif_url: data.gif_url
                });
            });

            // Typing
            this.socket.on('typ', (data) => {
                this._trigger('onTyping', { userId: data.u, conversationId: data.c, isTyping: true });
            });

            this.socket.on('styp', (data) => {
                this._trigger('onTyping', { userId: data.u, conversationId: data.c, isTyping: false });
            });

            // Online/Offline
            this.socket.on('online', (data) => {
                this._trigger('onOnline', { userId: data.u });
            });

            this.socket.on('offline', (data) => {
                this._trigger('onOffline', { userId: data.u });
            });

            // Read
            this.socket.on('rd', (data) => {
                this._trigger('onRead', { userId: data.u, conversationId: data.c });
            });

            // Pong
            this.socket.on('pong_chat', (data) => {
                this.latency = Date.now() - this._lastPing;
                this._trigger('onLatency', { latency: this.latency });
            });
        }

        disconnect() {
            if (this.socket) {
                this.socket.disconnect();
                this.socket = null;
            }
            this.connected = false;
        }

        // ====================================================================
        // ENVÍO DE MENSAJES (100% WebSocket!)
        // ====================================================================

        /**
         * Envía mensaje ultra-rápido via WebSocket.
         * NO usa HTTP - todo por socket.
         *
         * @param {string} conversationId
         * @param {string} content
         * @param {string} type - 'text', 'image', 'file', 'gif'
         * @param {object} options - Opciones adicionales { gif_url }
         * @returns {object} Mensaje con ID temporal
         */
        send(conversationId, content, type = 'text', options = {}) {
            if (!content || !content.trim()) return null;

            const tempId = Utils.genId();
            const timestamp = Utils.now();

            // Crear mensaje
            const message = {
                tempId,
                id: `temp_${tempId}`,
                conversationId,
                content: content.trim(),
                senderId: this.userId,
                timestamp,
                type,
                status: 'pending',
                gif_url: options.gif_url || null
            };

            // Guardar en pendientes
            this.pendingMessages.set(tempId, message);

            // Registrar para evitar duplicado
            this.shownMessages.add(`temp_${tempId}`);

            // ⚡ ENVIAR VIA WEBSOCKET (no HTTP!)
            if (this.connected) {
                const payload = {
                    c: conversationId,
                    m: content.trim(),
                    t: tempId,
                    type
                };

                // Agregar gif_url si es un GIF
                if (type === 'gif' && options.gif_url) {
                    payload.gif_url = options.gif_url;
                }

                this.socket.emit('send', payload);
                message.status = 'sending';
            } else {
                // Encolar para cuando reconecte
                this._queueOffline(message);
            }

            Utils.log('📤 Enviado:', tempId);

            return message;
        }

        /**
         * Reintenta enviar mensaje fallido
         */
        retry(tempId) {
            const msg = this.pendingMessages.get(tempId);
            if (msg && (msg.status === 'error' || msg.status === 'pending')) {
                msg.status = 'sending';
                this.socket.emit('send', {
                    c: msg.conversationId,
                    m: msg.content,
                    t: tempId,
                    type: msg.type
                });
            }
        }

        // ====================================================================
        // CONVERSACIONES
        // ====================================================================

        join(conversationId) {
            this.currentConversation = conversationId;
            if (this.connected) {
                this.socket.emit('join', { c: conversationId });
            }
        }

        leave(conversationId) {
            if (this.connected) {
                this.socket.emit('leave', { c: conversationId || this.currentConversation });
            }
            if (conversationId === this.currentConversation) {
                this.currentConversation = null;
            }
        }

        // ====================================================================
        // TYPING
        // ====================================================================

        startTyping(conversationId) {
            if (!this.connected) return;

            const now = Date.now();
            if (this._lastTyping && now - this._lastTyping < CONFIG.TYPING_THROTTLE) {
                return;
            }
            this._lastTyping = now;

            this.socket.emit('typing', { c: conversationId || this.currentConversation });

            // Auto-stop
            clearTimeout(this.typingTimer);
            this.typingTimer = setTimeout(() => {
                this.stopTyping(conversationId);
            }, CONFIG.TYPING_TIMEOUT);
        }

        stopTyping(conversationId) {
            if (this.connected) {
                this.socket.emit('stop_typing', { c: conversationId || this.currentConversation });
            }
            clearTimeout(this.typingTimer);
            this._lastTyping = 0;
        }

        // ====================================================================
        // LECTURA
        // ====================================================================

        markRead(conversationId) {
            if (this.connected) {
                this.socket.emit('read', { c: conversationId || this.currentConversation });
            }
        }

        // ====================================================================
        // LATENCIA
        // ====================================================================

        ping() {
            if (this.connected) {
                this._lastPing = Date.now();
                this.socket.emit('ping_chat');
            }
        }

        startLatencyMonitor(intervalMs = 5000) {
            setInterval(() => this.ping(), intervalMs);
        }

        // ====================================================================
        // CALLBACKS
        // ====================================================================

        on(event, callback) {
            if (this.callbacks.hasOwnProperty(event)) {
                this.callbacks[event] = callback;
            }
            return this;
        }

        _trigger(event, data) {
            if (this.callbacks[event]) {
                try {
                    this.callbacks[event](data);
                } catch (e) {
                    console.error('Callback error:', e);
                }
            }

            // Broadcast a otras tabs
            if (this.bc && ['onMessage', 'onOnline', 'onOffline'].includes(event)) {
                this.bc.postMessage({ event, data });
            }
        }

        // ====================================================================
        // COLA OFFLINE
        // ====================================================================

        _queueOffline(message) {
            if (this.offlineQueue.length >= CONFIG.OFFLINE_QUEUE_MAX) {
                this.offlineQueue.shift();
            }
            this.offlineQueue.push(message);
            Utils.log('Encolado offline:', message.tempId);
        }

        _flushOfflineQueue() {
            while (this.offlineQueue.length > 0) {
                const msg = this.offlineQueue.shift();
                const payload = {
                    c: msg.conversationId,
                    m: msg.content,
                    t: msg.tempId,
                    type: msg.type
                };

                // Agregar gif_url si es un GIF
                if (msg.type === 'gif' && msg.gif_url) {
                    payload.gif_url = msg.gif_url;
                }

                this.socket.emit('send', payload);
            }
        }

        // ====================================================================
        // RED
        // ====================================================================

        _onNetworkChange(online) {
            Utils.log('Red:', online ? 'online' : 'offline');
            if (online && !this.connected) {
                this.connect().catch(e => Utils.log('Error reconexión:', e));
            }
        }

        _onBroadcast(msg) {
            // Sync entre tabs
            if (msg.event === 'onOnline' || msg.event === 'onOffline') {
                this._trigger(msg.event, msg.data);
            }
        }

        // ====================================================================
        // STATS
        // ====================================================================

        getStats() {
            return {
                connected: this.connected,
                latency: this.latency,
                pending: this.pendingMessages.size,
                offline: this.offlineQueue.length,
                shown: this.shownMessages.size
            };
        }
    }

    // ========================================================================
    // EXPORTAR
    // ========================================================================

    window.ChatUltraFast = ChatUltraFast;

})(window);
