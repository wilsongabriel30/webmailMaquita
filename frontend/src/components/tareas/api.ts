// Llamadas de T-34. Se usa fetch directo (sin la caché de lectura del cliente general) para ver siempre el estado vivo.
import type { Tarea, Persona, Comentario } from './tipos';

const BASE = '/api/tareas';

async function pedir<T>(ruta: string, init?: RequestInit): Promise<T> {
  const r = await fetch(BASE + ruta, { credentials: 'include', headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) }, ...init });
  if (r.status === 204) return undefined as unknown as T;
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error((j && (j.detail || j.mensaje)) || 'HTTP ' + r.status);
  return j as T;
}

export const tareasApi = {
  mis: (completadas = false, archivadas = false) => pedir<Tarea[]>(`/mis?completadas=${completadas}&archivadas=${archivadas}`),
  asignadasPorMi: (completadas = false, archivadas = false) => pedir<Tarea[]>(`/asignadas-por-mi?completadas=${completadas}&archivadas=${archivadas}`),
  /** Quita del tablero de quien lo pide las completadas indicadas (no las borra: pasan a «Archivadas»). */
  archivar: (ids: string[]) => pedir<{ archivadas: number }>('/archivar', { method: 'POST', body: JSON.stringify({ ids }) }),
  restaurar: (id: string) => pedir<void>(`/${id}/restaurar`, { method: 'POST' }),
  miDia: () => pedir<Tarea[]>('/mi-dia'),
  obtener: (id: string) => pedir<Tarea>(`/${id}`),
  asignar: (d: Record<string, unknown>) => pedir<Tarea>('/asignar', { method: 'POST', body: JSON.stringify(d) }),
  /** Una tarea de lista pasa a tener seguimiento (la misma, no una copia). */
  desdeTarea: (id: string, d: Record<string, unknown>) => pedir<Tarea>(`/desde-tarea/${id}`, { method: 'POST', body: JSON.stringify(d) }),
  editar: (id: string, d: Record<string, unknown>) => pedir<Tarea>(`/${id}`, { method: 'PATCH', body: JSON.stringify(d) }),
  eliminar: (id: string) => pedir<void>(`/${id}`, { method: 'DELETE' }),
  estado: (id: string, estado: string) => pedir<Tarea>(`/${id}/estado`, { method: 'PATCH', body: JSON.stringify({ estado }) }),
  completar: (id: string) => pedir<Tarea>(`/${id}/completar`, { method: 'POST' }),
  aceptar: (id: string) => pedir<Tarea>(`/${id}/aceptar`, { method: 'POST' }),
  rechazar: (id: string, motivo: string) => pedir<Tarea>(`/${id}/rechazar`, { method: 'POST', body: JSON.stringify({ motivo }) }),
  comentarios: (id: string) => pedir<Comentario[]>(`/${id}/comentarios`),
  comentar: (id: string, texto: string) => pedir<Comentario>(`/${id}/comentarios`, { method: 'POST', body: JSON.stringify({ texto }) }),
  personas: (q: string) => pedir<Persona[]>(`/personas?q=${encodeURIComponent(q)}`),
};
