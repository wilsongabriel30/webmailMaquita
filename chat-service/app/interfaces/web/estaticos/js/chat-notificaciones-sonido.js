// chat-notificaciones-sonido.js — Sonido y notificaciones del navegador.
// Extraído de chat-page.js (líneas 706-833) el 28/08/2026 SIN cambios de código; ámbito global compartido.
// Orden de carga: ver plantillas/chat/index.html (mismo orden que el archivo original).

    // ============================================
    // SONIDO DE NOTIFICACIÓN (MEJORADO)
    // ============================================
    let notificationSound = null;
    let originalTitle = document.title;
    let unreadNotifications = 0;
    let soundEnabled = true;  // Control de sonido
    let lastSoundTime = 0;    // Anti-spam de sonido

    function initNotificationSound() {
        try {
            notificationSound = new Audio('/static/sounds/notification.mp3');
            notificationSound.volume = 0.7;
            notificationSound.preload = 'auto';

            // Precargar el audio
            notificationSound.load();

            // Verificar que el audio se puede reproducir
            notificationSound.addEventListener('canplaythrough', () => {
                console.log('🔊 Sonido de notificación precargado correctamente');
            });

            notificationSound.addEventListener('error', (e) => {
                console.error('❌ Error cargando sonido:', e);
                soundEnabled = false;
            });

            // Habilitar sonido con la primera interacción del usuario
            const enableSoundOnInteraction = () => {
                if (notificationSound) {
                    // Reproducir silenciosamente para desbloquear el audio
                    const originalVolume = notificationSound.volume;
                    notificationSound.volume = 0;
                    notificationSound.play().then(() => {
                        notificationSound.pause();
                        notificationSound.currentTime = 0;
                        notificationSound.volume = originalVolume;
                        console.log('🔊 Audio desbloqueado por interacción del usuario');
                    }).catch(() => {});
                }
                document.removeEventListener('click', enableSoundOnInteraction);
                document.removeEventListener('keydown', enableSoundOnInteraction);
            };

            document.addEventListener('click', enableSoundOnInteraction);
            document.addEventListener('keydown', enableSoundOnInteraction);

        } catch (e) {
            console.error('Error inicializando sonido:', e);
            soundEnabled = false;
        }
    }

    function playNotificationSound() {
        // Anti-spam: no reproducir más de 1 vez por segundo
        const now = Date.now();
        if (now - lastSoundTime < 1000) {
            console.log('🔇 Sonido omitido (anti-spam)');
            return;
        }
        lastSoundTime = now;

        // Reproducir sonido
        if (notificationSound && soundEnabled) {
            try {
                // Clonar el audio para permitir múltiples reproducciones
                const soundClone = notificationSound.cloneNode();
                soundClone.volume = 0.7;
                soundClone.play().then(() => {
                    console.log('🔔 Sonido de notificación reproducido');
                }).catch(err => {
                    console.log('No se pudo reproducir sonido:', err.message);
                });
            } catch (e) {
                console.error('Error reproduciendo sonido:', e);
            }
        }

        // Actualizar título de la página para mostrar mensajes nuevos
        unreadNotifications++;
        document.title = `(${unreadNotifications}) Nuevo mensaje - Chat`;

        // Mostrar notificación del navegador si está permitido
        showBrowserNotification();

        // Restaurar título cuando el usuario vuelva a la pestaña
        if (!document.hasFocus()) {
            const restoreTitle = () => {
                unreadNotifications = 0;
                document.title = originalTitle;
                window.removeEventListener('focus', restoreTitle);
            };
            window.addEventListener('focus', restoreTitle);
        } else {
            // Si ya tiene foco, restaurar después de 3 segundos
            setTimeout(() => {
                unreadNotifications = 0;
                document.title = originalTitle;
            }, 3000);
        }
    }

    // Notificaciones del navegador
    function showBrowserNotification() {
        if (!('Notification' in window)) return;

        if (Notification.permission === 'granted') {
            new Notification('Nuevo mensaje', {
                body: 'Tienes un nuevo mensaje en el chat',
                icon: '/static/images/logo-maquita-icon.png',
                tag: 'chat-notification',
                silent: true  // El sonido ya lo manejamos nosotros
            });
        } else if (Notification.permission !== 'denied') {
            Notification.requestPermission();
        }
    }

    // Solicitar permisos de notificación al cargar
    if ('Notification' in window && Notification.permission === 'default') {
        // No solicitar inmediatamente, esperar interacción
        document.addEventListener('click', function requestNotifPermission() {
            Notification.requestPermission();
            document.removeEventListener('click', requestNotifPermission);
        }, { once: true });
    }

