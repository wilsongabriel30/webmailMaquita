// Tipos de T-34 (tareas asignadas con seguimiento). Espejo de app/tareas/esquemas.py
export type Estado = 'espera' | 'pendiente' | 'en_curso' | 'completada' | 'vencida';
export type Semaforo = 'verde' | 'amarillo' | 'rojo' | 'gris';

export interface Tarea {
  id: string;
  titulo: string;
  descripcion: string;
  asignados: string[];
  asignado_por: string;
  plazo: string | null;
  prioridad: 'low' | 'medium' | 'high' | 'urgent';
  etiquetas: string[];
  estado: Estado;
  semaforo: Semaforo;
  aceptacion: 'sin_responder' | 'aceptada' | 'rechazada';
  motivo_rechazo: string;
  recurrencia: string | null;
  activa_tarea_id: string | null;
  activada_por: string | null;
  escalar_a: string | null;
  escalado_en: string | null;
  correo: { folder: string; uid: number; subject?: string; from?: string } | null;
  subtareas_total: number;
  subtareas_hechas: number;
  comentarios: number;
  completada_por: string | null;
  completada_en: string | null;
  creada_en: string;
  url: string;
}

export interface Persona { email: string; nombre: string; departamento: string; cargo: string }
export interface Comentario { id: string; autor: string; texto: string; menciones: string[]; creado_en: string }

export const ESTADO_NOMBRE: Record<Estado, string> = {
  espera: 'En espera', pendiente: 'Pendiente', en_curso: 'En curso', completada: 'Completada', vencida: 'Vencida',
};
export const PRIORIDAD_NOMBRE: Record<string, string> = { low: 'Baja', medium: 'Normal', high: 'Alta', urgent: 'Urgente' };
export const PRIORIDAD_COLOR: Record<string, string> = { low: '#8a8886', medium: '#0078d4', high: '#ca5010', urgent: '#a4262c' };
export const SEMAFORO_COLOR: Record<Semaforo, string> = { verde: '#107c10', amarillo: '#c19c00', rojo: '#d13438', gris: '#a19f9d' };
export const RECURRENCIAS = [
  { valor: '', nombre: 'No se repite' }, { valor: 'daily', nombre: 'Cada día' }, { valor: 'weekdays', nombre: 'Días hábiles' },
  { valor: 'weekly', nombre: 'Cada semana' }, { valor: 'monthly', nombre: 'Cada mes' }, { valor: 'yearly', nombre: 'Cada año' },
];

export function nombreDe(correo: string): string {
  return (correo || '').split('@')[0].replace(/\./g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}
export function fechaCorta(iso: string | null): string {
  if (!iso) return 'Sin plazo';
  const d = new Date(iso);
  return d.toLocaleDateString('es-EC', { day: '2-digit', month: 'short' }) + ' ' + d.toLocaleTimeString('es-EC', { hour: '2-digit', minute: '2-digit' });
}
