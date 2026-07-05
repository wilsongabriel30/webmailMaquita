// =============================================================================
// NOTIFY PUSH - Sincronización en Tiempo Real (estilo Google Drive)
// =============================================================================

(function() {
    const NOTIFY_PUSH_URL = 'wss://nube.maquita.com.ec/push/ws';
    let notifySocket = null;
    let reconnectAttempts = 0;
    const MAX_RECONNECT_ATTEMPTS = 5;
    const BASE_RECONNECT_DELAY = 3000;
    let reconnectPaused = false;
    let pendingRefresh = false;
    let refreshDebounceTimer = null;

    // Indicador de sincronización en tiempo real
    function crearIndicadorSync() {
        // Ya no se crea el indicador inferior
        // Se usa el ícono del header (syncStatusIcon)
    }

    function actualizarIndicador(estado, texto) {
        const icon = document.getElementById('syncStatusIcon');
        const btn = document.getElementById('syncStatusBtn');
        if (!icon || !btn) return;

        // Limpiar clases anteriores
        icon.classList.remove('syncing', 'offline', 'updating');

        // Agregar nueva clase si hay estado
        if (estado) {
            icon.classList.add(estado);
        }

        // Actualizar tooltip
        const tooltips = {
            '': 'Sincronizado',
            'syncing': 'Sincronizando...',
            'offline': 'Desconectado',
            'updating': 'Actualizando...'
        };
        btn.title = texto || tooltips[estado] || 'Sincronizado';

        // Cambiar ícono según estado
        if (estado === 'offline') {
            icon.textContent = 'cloud_off';
        } else if (estado === 'syncing' || estado === 'updating') {
            icon.textContent = 'sync';
        } else {
            icon.textContent = 'check_circle';
        }
    }

    // Refresh inteligente con debounce
    function refreshConDebounce() {
        if (refreshDebounceTimer) {
            clearTimeout(refreshDebounceTimer);
        }

        pendingRefresh = true;
        actualizarIndicador('updating', 'Actualizando...');

        refreshDebounceTimer = setTimeout(() => {
            if (pendingRefresh) {
                console.log('[Notify Push] Refrescando archivos...');
                invalidarCache(rutaActual, false);
                cargarArchivos(rutaActual, false, true);  // silencioso: sin loader ni popups
                cargarCuota();
                pendingRefresh = false;

                setTimeout(() => {
                    actualizarIndicador('', 'Sincronizado');
                }, 1000);
            }
        }, 3000); // Esperar 3s para agrupar múltiples cambios (subida de varios archivos)
    }

    // Conectar a Notify Push WebSocket con pre-auth
    async function conectarNotifyPush() {
        if (notifySocket && notifySocket.readyState === WebSocket.OPEN) {
            return;
        }

        try {
            // Obtener token de pre-autenticación desde el backend FARO
            let preAuthToken = null;
            let ncUsername = '';
            try {
                const tokenResp = await fetch(`${API_BASE}/notify-push/token`);
                const tokenData = await tokenResp.json();
                if (tokenData.success) {
                    preAuthToken = tokenData.token;
                    ncUsername = tokenData.username;
                    console.log('[Notify Push] Pre-auth token obtenido para:', ncUsername);
                } else {
                    console.warn('[Notify Push] No se pudo obtener pre-auth token:', tokenData.error);
                }
            } catch (tokenErr) {
                console.warn('[Notify Push] Error obteniendo pre-auth token:', tokenErr);
            }

            console.log('[Notify Push] Conectando a', NOTIFY_PUSH_URL);
            actualizarIndicador('syncing', 'Conectando...');

            notifySocket = new WebSocket(NOTIFY_PUSH_URL);

            notifySocket.onopen = function() {
                notifySocket._openedAt = Date.now();

                // Enviar autenticación por pre-auth token
                if (preAuthToken) {
                    console.log('[Notify Push] Enviando autenticación pre-auth...');
                    notifySocket.send(ncUsername);  // username
                    notifySocket.send(preAuthToken);  // token como password
                } else {
                    console.log('[Notify Push] Sin token, conexión sin autenticación');
                }

                actualizarIndicador('syncing', 'Autenticando...');
            };

            notifySocket.onmessage = function(event) {
                const msg = event.data;

                // Mensajes de texto plano de Notify Push
                if (typeof msg === 'string') {
                    if (msg === 'authenticated') {
                        notifySocket._authenticated = true;
                        console.log('[Notify Push] ✓ Autenticado - Sincronización en tiempo real activa');
                        actualizarIndicador('', 'Sincronizado');
                        return;
                    }
                    if (msg === 'notify_file' || msg === 'notify_file_id') {
                        console.log('[Notify Push] Cambio detectado en archivos');
                        refreshConDebounce();
                        return;
                    }
                    if (msg === 'notify_activity') {
                        refreshConDebounce();
                        return;
                    }
                    if (msg === 'notify_notification') {
                        console.log('[Notify Push] Notificación recibida');
                        return;
                    }
                    if (msg.toLowerCase().includes('authentication')) {
                        console.warn('[Notify Push] Error de autenticación:', msg);
                        notifySocket._authFailed = true;
                        return;
                    }
                }

                // Intentar parsear como JSON (compatibilidad)
                try {
                    const data = JSON.parse(msg);
                    console.log('[Notify Push] Mensaje JSON:', data);

                    if (data.type === 'file' || data.type === 'notify_file_id') {
                        refreshConDebounce();
                    } else if (data.type === 'activity') {
                        refreshConDebounce();
                    } else if (data.type === 'notification') {
                        console.log('[Notify Push] Notificación:', data);
                    }
                } catch (e) {
                    console.log('[Notify Push] Mensaje:', msg);
                }
            };

            notifySocket.onclose = function(event) {
                const duracion = notifySocket._openedAt ? (Date.now() - notifySocket._openedAt) : 0;
                console.log(`[Notify Push] Desconectado, código: ${event.code}, duración: ${Math.round(duracion/1000)}s`);
                actualizarIndicador('offline', 'Desconectado');

                // Solo resetear intentos si la conexión fue estable (>10s) y no falló por auth
                if (duracion > 10000 && !notifySocket._authFailed) {
                    reconnectAttempts = 0;
                }

                if (reconnectPaused) return;

                // Intentar reconectar con backoff exponencial
                if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
                    reconnectAttempts++;
                    const delay = BASE_RECONNECT_DELAY * Math.pow(2, reconnectAttempts - 1);
                    console.log(`[Notify Push] Reintentando en ${delay/1000}s (intento ${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})`);
                    setTimeout(conectarNotifyPush, delay);
                } else {
                    console.log('[Notify Push] Máximo de reintentos alcanzado, usando polling. Reintento en 5 min.');
                    reconnectPaused = true;
                    iniciarPolling();
                    setTimeout(() => {
                        reconnectPaused = false;
                        reconnectAttempts = 0;
                        conectarNotifyPush();
                    }, 5 * 60 * 1000);
                }
            };

            notifySocket.onerror = function(error) {
                console.error('[Notify Push] Error:', error);
                actualizarIndicador('offline', 'Error de conexión');
            };

        } catch (e) {
            console.error('[Notify Push] Error al conectar:', e);
            iniciarPolling();
        }
    }

    // Polling como fallback si WebSocket no funciona
    let pollingInterval = null;

    function iniciarPolling() {
        if (pollingInterval) return;

        console.log('[Notify Push] Iniciando polling cada 15 segundos');
        actualizarIndicador('syncing', 'Sincronizando...');

        pollingInterval = setInterval(() => {
            if (document.visibilityState === 'visible') {
                cargarArchivos(rutaActual);
                actualizarIndicador('', 'Sincronizado');
            }
        }, 15000); // Cada 15 segundos
    }

    // Refrescar al volver a la pestaña
    document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible') {
            console.log('[Nube Maquita] Pestaña visible - refrescando');
            refreshConDebounce();

            // Reconectar WebSocket si está desconectado y no está pausado
            if (!reconnectPaused && (!notifySocket || notifySocket.readyState !== WebSocket.OPEN)) {
                conectarNotifyPush();
            }
        }
    });

    // Refrescar con F5 o botón refresh del navegador - interceptar para hacer soft refresh
    window.addEventListener('keydown', (e) => {
        if (e.key === 'F5' || (e.ctrlKey && e.key === 'r')) {
            e.preventDefault();
            console.log('[Nube Maquita] Refresh manual');
            refreshConDebounce();
        }
    });

    // Inicializar cuando el DOM esté listo
    document.addEventListener('DOMContentLoaded', () => {
        crearIndicadorSync();

        // Modo Almacén: el push server (wss://nube...) es de Nextcloud y NO aplica
        // al motor propio — conectar solo generaba 5 reintentos fallidos en consola.
        // Se usa el polling directamente hasta que el motor tenga su propio push.
        if (window.ALMACEN_OVERRIDE) {
            iniciarPolling();
            return;
        }

        // Intentar conectar a Notify Push después de 1 segundo
        setTimeout(() => {
            conectarNotifyPush();
        }, 1000);
    });

    // Limpiar al salir
    window.addEventListener('beforeunload', () => {
        if (notifySocket) {
            notifySocket.close();
        }
        if (pollingInterval) {
            clearInterval(pollingInterval);
        }
    });
})();

