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
  mis: (completadas = false) => pedir<Tarea[]>(`/mis?completadas=${completadas}`),
  asignadasPorMi: (completadas = false) => pedir<Tarea[]>(`/asignadas-por-mi?completadas=${completadas}`),
  miDia: () => pedir<Tarea[]>('/mi-dia'),
  obtener: (id: string) => pedir<Tarea>(`/${id}`),
  asignar: (d: Record<string, unknown>) => pedir<Tarea>('/asignar', { method: 'POST', body: JSON.stringify(d) }),
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
