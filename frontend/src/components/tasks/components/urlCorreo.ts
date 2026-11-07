// Dirección que abre en el correo el mensaje del que salió una tarea (la misma que usa Seguimiento).
import type { CorreoTarea } from '../types';

export function urlCorreo(c: CorreoTarea) {
  return `/webmail/?folder=${encodeURIComponent(c.carpeta)}&uid=${c.uid}`;
}
