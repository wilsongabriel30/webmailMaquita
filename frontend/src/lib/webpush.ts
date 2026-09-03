import { api } from '../api/client';

/** Convierte la clave pública VAPID (base64url) a Uint8Array para pushManager. */
function base64UrlToUint8Array(base64: string): Uint8Array {
  const padding = '='.repeat((4 - (base64.length % 4)) % 4);
  const b64 = (base64 + padding).replace(/-/g, '+').replace(/_/g, '/');
  const raw = atob(b64);
  const arr = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) arr[i] = raw.charCodeAt(i);
  return arr;
}

/**
 * Activa las notificaciones web push del correo (#17). Idempotente y silencioso:
 * si el navegador no soporta push, el permiso está denegado, o el servidor no tiene
 * VAPID, no hace nada. Nunca rompe la app.
 */
export async function activarPush(): Promise<void> {
  try {
    if (!('serviceWorker' in navigator) || !('PushManager' in window) || !('Notification' in window)) return;
    if (Notification.permission === 'denied') return;

    const info = await api.get<{ key: string; enabled: boolean }>('/push/vapid-public-key').catch(() => null);
    if (!info || !info.enabled || !info.key) return;

    const reg = await navigator.serviceWorker.ready;
    let sub = await reg.pushManager.getSubscription();
    if (!sub) {
      if (Notification.permission === 'default') {
        const p = await Notification.requestPermission();
        if (p !== 'granted') return;
      }
      if (Notification.permission !== 'granted') return;
      sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: base64UrlToUint8Array(info.key),
      });
    }
    const j = sub.toJSON() as { endpoint?: string; keys?: { p256dh?: string; auth?: string } };
    if (j.endpoint && j.keys && j.keys.p256dh && j.keys.auth) {
      await api.post('/push/subscribe', {
        endpoint: j.endpoint,
        keys: { p256dh: j.keys.p256dh, auth: j.keys.auth },
      });
    }
  } catch {
    /* push es opcional: jamás romper la app */
  }
}
