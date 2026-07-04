// @ts-nocheck
import { useEffect, useRef, useCallback } from 'react';
import { useMailStore } from '../store/mailStore';
import { showToast } from '../components/common/Toast';

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
      const ctx = new (window.AudioContext || (window as any).webkitAudioContext)();
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
    } catch {}
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
              showToast(
                delta === 1
                  ? 'Nuevo correo recibido'
                  : `${delta} correos nuevos`,
              );

              // Play sound
              playNotificationSound();

              // Browser notification (if permitted)
              if (Notification.permission === 'granted') {
                try {
                  new Notification('Maquita Mail', {
                    body: delta === 1 ? 'Nuevo correo recibido' : `${delta} correos nuevos`,
                    icon: '/webmail/favicon.svg',
                    tag: 'new-mail',
                  });
                } catch {}
              }

              // Trigger message list refresh if user is viewing the affected folder
              if (useMailStore.getState().currentFolder === data.folder) {
                window.dispatchEvent(new CustomEvent('refresh-messages'));
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
              if (Notification.permission === 'granted') {
                try {
                  new Notification('Maquita - Tareas', {
                    body: taskMsg,
                    icon: '/webmail/favicon.svg',
                    tag: 'task-' + (data.task_id || ''),
                  });
                } catch {}
              }
              window.dispatchEvent(new CustomEvent('refresh-tasks'));
              break;
            }

            case 'reminder': {
              const remMsg = data.message || 'Recordatorio';
              window.dispatchEvent(new CustomEvent('show-reminder', { detail: data }));
              playNotificationSound();
              if (Notification.permission === 'granted') {
                try {
                  new Notification('Maquita — Recordatorio', {
                    body: remMsg,
                    icon: '/webmail/favicon.svg',
                    tag: data.tag || 'reminder',
                  });
                } catch {}
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
        } catch {}
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
    } catch {}
  }, [playNotificationSound, updateTabBadge]);

  useEffect(() => {
    mountedRef.current = true;
    if (enabled) {
      // Small delay to ensure auth cookies are set after login
      const initTimer = setTimeout(() => {
        connect();
      }, 1000);
      // Request notification permission once
      if (Notification.permission === 'default') {
        Notification.requestPermission().catch(() => {});
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
