import { useEffect, useRef, useCallback } from 'react';
import { nombreVisibleCarpeta } from '../lib/nombreCarpeta';
import { useMailStore } from '../store/mailStore';
import { showToast } from '../components/common/Toast';
import { textoAvisoCorreo, textoAvisoCuenta } from '../lib/textoAvisoCorreo';   // remitente y asunto en el aviso (06/11/2026)
import { avisar } from '../lib/avisosNavegador';   // T-53: icono propio y clic que lleva a la bandeja
import { permisoNotificacion, pedirPermisoNotificacion } from '../lib/notificacionSegura';   // AM-10
import { useAuthStore } from '../store/authStore';
import { cuentaActiva, elegirCuenta } from '../lib/cuentaActiva';
import { avisosActivos } from '../lib/avisosOtrasCuentas';
import { nombreApp } from '../lib/marca';
import { enlaceReunionSeguro } from '../lib/enlaceReunion';

/**
 * WebSocket hook for real-time mail notifications.
 *
 * - Connects to wss://mail.ejemplo.com/api/ws
 * - Reconnects automatically with exponential backoff (1s, 2s, 4s, 8s, max 30s)
 * - Responds to server pings with pongs
 * - Updates folder unseen counts when new mail arrives
 * - Plays notification sound (reuses existing Web Audio beep)
 * - Updates browser tab badge
 * - Does NOT replace polling — works alongside it for reliability
 */

const WS_URL = `${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/api/ws`;
const MIN_RECONNECT_MS = 1000;
const MAX_RECONNECT_MS = 30000;

export function useWebSocket(enabled: boolean = true) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectDelay = useRef(MIN_RECONNECT_MS);
  const mountedRef = useRef(true);

  const playNotificationSound = useCallback(() => {
    try {
      const ctx = new (window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext)();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.frequency.value = 880;
      osc.type = 'sine';
      gain.gain.value = 0.08;
      osc.start();
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.3);
      osc.stop(ctx.currentTime + 0.3);
    } catch { /* no es crítico: se sigue sin aviso */ }
  }, []);

  const updateTabBadge = useCallback((unseen: number) => {
    if (unseen < 0 || unseen > 99999) return;
    const base = document.title.replace(/^\(\d+\)\s*/, '');
    document.title = unseen > 0 ? `(${unseen}) ${base}` : base;
  }, []);

  const connect = useCallback(() => {
    if (!mountedRef.current) return;
    if (wsRef.current?.readyState === WebSocket.OPEN || wsRef.current?.readyState === WebSocket.CONNECTING) return;

    try {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        reconnectDelay.current = MIN_RECONNECT_MS;
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          switch (data.type) {
            case 'ping':
              ws.send(JSON.stringify({ type: 'pong' }));
              break;

            case 'new_mail': {
              // Update folder unseen count in store
              const folders = useMailStore.getState().folders.map(f =>
                f.name === data.folder ? { ...f, unseen: data.unseen } : f
              );
              useMailStore.getState().setFolders(folders);

              // Update tab badge — only from INBOX unseen
              if (data.folder === 'INBOX') {
                updateTabBadge(data.unseen);
              }

              // Show toast notification
              const delta = data.delta || 1;
              const aviso = textoAvisoCorreo(delta, data.de, data.asunto);   // 06/11/2026
              // Correo archivado por una regla en otra carpeta (09/11/2026): se dice en cuál.
              const enCarpeta = data.folder && data.folder !== 'INBOX' ? `En «${nombreVisibleCarpeta(data.folder)}»: ` : '';
              showToast(enCarpeta + aviso.cuerpo.replace(/\n/g, ' · '));

              // Play sound
              playNotificationSound();

              // Browser notification (if permitted)
              if (permisoNotificacion() === 'granted') {
                try {
                  avisar(aviso.titulo, {
                    cuerpo: aviso.cuerpo,
                    tipo: 'correo',
                    etiqueta: 'new-mail',
                    carpeta: data.folder || 'INBOX',
                    uid: data.uid,
                    // carpeta + total: si llega el mismo suceso por dos conexiones, un solo aviso (05/11/2026)
                    claveSuceso: `${data.folder || 'INBOX'}:${data.total ?? ''}:${data.unseen ?? ''}`,
                  });
                } catch { /* no es crítico: se sigue sin aviso */ }
              }

              // Trigger message list refresh if user is viewing the affected folder
              if (useMailStore.getState().currentFolder === data.folder) {
                window.dispatchEvent(new CustomEvent('refresh-messages'));
              }
              break;
            }

            case 'reaccion_correo': {
              // Alguien reaccionó a un correo que esta persona tiene: se refresca si está abierto y,
              // si es quien lo envió, se le avisa (sin correo nuevo ni sonido).
              window.dispatchEvent(new CustomEvent('reaccion-correo', { detail: data }));
              if (data.para_autor && data.emoji && data.estado !== 'quitada') {
                showToast(`${data.de || 'Alguien'} reaccionó ${data.emoji} a «${data.asunto || 'su correo'}»`);
              }
              break;
            }

            case 'programado_enviado':
            case 'programado_fallido': {
              // Un envío programado salió o falló: se avisa y la sección «Programados» se actualiza.
              window.dispatchEvent(new CustomEvent('programados-cambio'));
              if (data.type === 'programado_fallido') showToast(`No se pudo enviar el correo programado «${data.asunto || '(sin asunto)'}». Revíselo en Programados.`, undefined, { fijo: true });
              else showToast(`Se envió el correo programado «${data.asunto || '(sin asunto)'}»`);
              break;
            }

            case 'correo_recuperado': {
              // El remitente recuperó un correo de este buzón: la lista debe refrescarse al
              // instante, sin aviso ni sonido de «correo nuevo» (incidente 09/11/2026).
              const carpetas: string[] = Array.isArray(data.folders) ? data.folders : ['INBOX'];
              if (carpetas.includes(useMailStore.getState().currentFolder)) {
                window.dispatchEvent(new CustomEvent('refresh-messages'));
              }
              break;
            }

            case 'new_mail_cuenta': {
              // Correo nuevo en una cuenta asignada (multicuenta, fase 5).
              const cuenta = String(data.cuenta || '').toLowerCase();
              const delta = data.delta || 1;
              const activa = cuentaActiva();
              window.dispatchEvent(new CustomEvent('refresh-cuentas'));
              if (activa && activa === cuenta) {
                // Es la cuenta con la que se trabaja en esta pestaña: como un correo propio.
                const folders = useMailStore.getState().folders.map(f =>
                  f.name === 'INBOX' ? { ...f, unseen: data.unseen } : f
                );
                useMailStore.getState().setFolders(folders);
                updateTabBadge(data.unseen);
                // 06/11/2026: remitente y asunto, como un correo propio.
                const avisoActiva = textoAvisoCorreo(delta, data.de, data.asunto);
                showToast(data.de ? `${avisoActiva.titulo} — ${avisoActiva.cuerpo}` : avisoActiva.cuerpo);
                playNotificationSound();
                if (permisoNotificacion() === 'granted') {
                  try {
                    avisar(data.de ? avisoActiva.titulo : (data.nombre || cuenta), { cuerpo: avisoActiva.cuerpo, tipo: 'correo', etiqueta: 'new-mail-' + cuenta, carpeta: 'INBOX', uid: data.uid });
                  } catch { /* sin aviso */ }
                }
                if (useMailStore.getState().currentFolder === 'INBOX') {
                  window.dispatchEvent(new CustomEvent('refresh-messages'));
                }
                break;
              }
              if (!avisosActivos()) break;
              const propia = useAuthStore.getState().user?.username || '';
              // 06/11/2026: remitente, asunto y la cuenta a la que llegó.
              const avisoCuenta = textoAvisoCuenta(delta, cuenta, data.de, data.asunto);
              const texto = data.de ? `${avisoCuenta.titulo} — ${avisoCuenta.cuerpo}` : avisoCuenta.cuerpo;
              showToast(texto, { label: 'Ver', onClick: () => elegirCuenta(cuenta, propia) });
              playNotificationSound();
              if (permisoNotificacion() === 'granted') {
                try {
                  avisar(data.de ? avisoCuenta.titulo : (data.nombre || cuenta), { cuerpo: avisoCuenta.cuerpo, tipo: 'correo', etiqueta: 'new-mail-' + cuenta, destino: `/webmail/?cuenta=${encodeURIComponent(cuenta)}&folder=INBOX${data.uid ? `&uid=${data.uid}` : ''}` });
                } catch { /* sin aviso */ }
              }
              break;
            }
            case 'folder_update': {
              const folders = useMailStore.getState().folders.map(f =>
                f.name === data.folder ? { ...f, unseen: data.unseen } : f
              );
              useMailStore.getState().setFolders(folders);
              updateTabBadge(
                folders.find(f => f.name === 'INBOX')?.unseen || 0
              );
              break;
            }


            case 'task_notification': {
              // Notificacion de tarea asignada/actualizada/completada
              const taskMsg = data.message || 'Actualizacion de tarea';
              showToast(taskMsg);
              playNotificationSound();
              if (permisoNotificacion() === 'granted') {
                try {
                  avisar(`${nombreApp()} · Tareas`, {
                    cuerpo: taskMsg,
                    tipo: 'tarea',
                    etiqueta: 'task-' + (data.task_id || ''),
                    destino: '/webmail/tasks',
                  });
                } catch { /* no es crítico: se sigue sin aviso */ }
              }
              window.dispatchEvent(new CustomEvent('refresh-tasks'));
              break;
            }

            case 'tareas_cambio': {
              // Otra persona cambió algo en una lista de Tareas compartida: se recarga sin aviso.
              window.dispatchEvent(new CustomEvent('refresh-tasks'));
              break;
            }

            case 'reminder': {
              const remMsg = data.message || 'Recordatorio';
              window.dispatchEvent(new CustomEvent('show-reminder', { detail: data }));
              playNotificationSound();
              if (data.kind === 'task') window.dispatchEvent(new CustomEvent('refresh-tasks'));
              if (permisoNotificacion() === 'granted') {
                try {
                  avisar(`${nombreApp()} · Recordatorio`, {
                    cuerpo: remMsg,
                    tipo: 'recordatorio',
                    etiqueta: data.tag || 'reminder',
                    destino: data.kind === 'task' ? '/webmail/tasks' : '/webmail/calendar',
                    enlaceExterno: enlaceReunionSeguro(data.link) || undefined,
                  });
                } catch { /* no es crítico: se sigue sin aviso */ }
              }
              break;
            }

            case 'session_expired':
              // Session lost — redirect to login
              ws.close();
              window.location.href = '/webmail/login';
              break;

            case 'connected':
              // Connection confirmed
              break;
          }
        } catch { /* no es crítico: se sigue sin aviso */ }
      };

      ws.onclose = (event) => {
        wsRef.current = null;
        // Don't reconnect on auth failure (1008)
        if (event.code === 1008) return;
        // Reconnect with exponential backoff
        if (mountedRef.current) {
          reconnectTimer.current = setTimeout(() => {
            reconnectDelay.current = Math.min(
              reconnectDelay.current * 2,
              MAX_RECONNECT_MS,
            );
            connect();
          }, reconnectDelay.current);
        }
      };

      ws.onerror = () => {
        // onclose will fire after this — reconnect is handled there
      };
    } catch { /* no es crítico: se sigue sin aviso */ }
  }, [playNotificationSound, updateTabBadge]);

  useEffect(() => {
    mountedRef.current = true;
    if (enabled) {
      // Small delay to ensure auth cookies are set after login
      const initTimer = setTimeout(() => {
        connect();
      }, 1000);
      // Request notification permission once
      if (permisoNotificacion() === 'default') {
        void pedirPermisoNotificacion();
      }
      return () => {
        clearTimeout(initTimer);
        mountedRef.current = false;
        if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
        if (wsRef.current) {
          wsRef.current.close(1000);
          wsRef.current = null;
        }
      };
    }
    return () => {
      mountedRef.current = false;
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled]);
}