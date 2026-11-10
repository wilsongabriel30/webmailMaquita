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

/** ¿Estamos dentro de un gesto de la persona (clic, tecla)? Sin él, Firefox rechaza la petición de permiso
 *  («may only be requested from inside a short running user-generated event handler») y Safari la ignora. */
function hayGestoDeUsuario(): boolean {
  const ua = (navigator as Navigator & { userActivation?: { isActive: boolean } }).userActivation;
  return ua ? ua.isActive : true;
}

let pendienteTrasGesto = false;

export async function pedirPermisoNotificacion(): Promise<PermisoAviso> {
  if (!hayNotification()) return 'unsupported';
  if (Notification.permission !== 'default') return Notification.permission;
  if (!hayGestoDeUsuario()) {
    // Fuera de un gesto (al cargar, al llegar un correo): se pide en el primer clic o tecla (10/11/2026).
    if (!pendienteTrasGesto) {
      pendienteTrasGesto = true;
      const pedir = () => {
        pendienteTrasGesto = false;
        void pedirPermisoNotificacion();
      };
      window.addEventListener('pointerdown', pedir, { once: true, capture: true });
      window.addEventListener('keydown', pedir, { once: true, capture: true });
    }
    return 'default';
  }
  try {
    return await Notification.requestPermission();
  } catch {
    return 'denied';
  }
}
