// Llamadas de T-34. Van por el cliente general (`api`), que renueva la sesión cuando vence el vale (401) y explica
// los errores del servidor. Antes iban con fetch directo: al vencer el vale, Seguimiento (que se recarga cada minuto)
// recibía 401 y mostraba «Nada pendiente por aquí» como si no hubiera tareas. Estas rutas no tienen caché de lectura
// en el cliente, así que siempre se ve el estado vivo.
import { api } from '../../api/client';
import type { Tarea, Persona, Comentario } from './tipos';

const B = '/tareas';

export const tareasApi = {
  mis: (completadas = false, archivadas = false) => api.get<Tarea[]>(`${B}/mis?completadas=${completadas}&archivadas=${archivadas}`),
  asignadasPorMi: (completadas = false, archivadas = false) => api.get<Tarea[]>(`${B}/asignadas-por-mi?completadas=${completadas}&archivadas=${archivadas}`),
  /** Quita del tablero de quien lo pide las completadas indicadas (no las borra: pasan a «Archivadas»). */
  archivar: (ids: string[]) => api.post<{ archivadas: number }>(`${B}/archivar`, { ids }),
  restaurar: (id: string) => api.post<void>(`${B}/${id}/restaurar`),
  miDia: () => api.get<Tarea[]>(`${B}/mi-dia`),
  obtener: (id: string) => api.get<Tarea>(`${B}/${id}`),
  asignar: (d: Record<string, unknown>) => api.post<Tarea>(`${B}/asignar`, d),
  /** Una tarea de lista pasa a tener seguimiento (la misma, no una copia). */
  desdeTarea: (id: string, d: Record<string, unknown>) => api.post<Tarea>(`${B}/desde-tarea/${id}`, d),
  editar: (id: string, d: Record<string, unknown>) => api.patch<Tarea>(`${B}/${id}`, d),
  eliminar: (id: string) => api.del<void>(`${B}/${id}`),
  estado: (id: string, estado: string) => api.patch<Tarea>(`${B}/${id}/estado`, { estado }),
  completar: (id: string) => api.post<Tarea>(`${B}/${id}/completar`),
  aceptar: (id: string) => api.post<Tarea>(`${B}/${id}/aceptar`),
  rechazar: (id: string, motivo: string) => api.post<Tarea>(`${B}/${id}/rechazar`, { motivo }),
  comentarios: (id: string) => api.get<Comentario[]>(`${B}/${id}/comentarios`),
  comentar: (id: string, texto: string) => api.post<Comentario>(`${B}/${id}/comentarios`, { texto }),
  personas: (q: string) => api.get<Persona[]>(`${B}/personas?q=${encodeURIComponent(q)}`),
};
