/**
 * Acceso seguro a la API Notification (AM-10).
 * En el WebView de Android y en Safari de iPhone fuera de la PWA instalada no existe
 * `window.Notification`: leerlo sin comprobar lanza ReferenceError y tumba la interfaz.
 */
export type PermisoAviso = NotificationPermission | 'unsupported';

export function hayNotification(): boolean {
  return typeof window !== 'undefined' && typeof Notification !== 'undefined';
}

export function permisoNotificacion(): PermisoAviso {
  return hayNotification() ? Notification.permission : 'unsupported';
}

export async function pedirPermisoNotificacion(): Promise<PermisoAviso> {
  if (!hayNotification()) return 'unsupported';
  try {
    return await Notification.requestPermission();
  } catch {
    return 'denied';
  }
}
