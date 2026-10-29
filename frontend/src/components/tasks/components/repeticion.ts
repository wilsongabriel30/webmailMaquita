// Reglas de repetición de una tarea (como en To Do). Las mismas que valida el backend (app/tasks/repeticion.py):
// daily, weekdays, weekly, monthly, yearly o cada:N:unidad[:días], con días 0 = lunes … 6 = domingo.

export type Unidad = 'dia' | 'semana' | 'mes' | 'anio';

export interface ReglaPersonalizada {
  cada: number;
  unidad: Unidad;
  dias: number[];
}

export const REPETICIONES_SIMPLES = [
  { valor: 'daily', etiqueta: 'Diariamente' },
  { valor: 'weekdays', etiqueta: 'Días laborables' },
  { valor: 'weekly', etiqueta: 'Semanalmente' },
  { valor: 'monthly', etiqueta: 'Mensualmente' },
  { valor: 'yearly', etiqueta: 'Anualmente' },
];

export const UNIDADES: { valor: Unidad; singular: string; plural: string }[] = [
  { valor: 'dia', singular: 'día', plural: 'días' },
  { valor: 'semana', singular: 'semana', plural: 'semanas' },
  { valor: 'mes', singular: 'mes', plural: 'meses' },
  { valor: 'anio', singular: 'año', plural: 'años' },
];

export const DIAS_SEMANA = ['lu', 'ma', 'mi', 'ju', 'vi', 'sá', 'do'];
const DIAS_LARGOS = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo'];

export function leerPersonalizada(regla?: string | null): ReglaPersonalizada | null {
  const m = (regla || '').match(/^cada:(\d+):(dia|semana|mes|anio)(?::([0-6](?:,[0-6])*))?$/);
  if (!m) return null;
  return { cada: Number(m[1]), unidad: m[2] as Unidad, dias: m[3] ? m[3].split(',').map(Number) : [] };
}

export function escribirPersonalizada(r: ReglaPersonalizada): string {
  const cada = Math.min(999, Math.max(1, Math.round(r.cada) || 1));
  const dias = r.unidad === 'semana' ? [...new Set(r.dias)].sort((a, b) => a - b) : [];
  return `cada:${cada}:${r.unidad}` + (dias.length ? `:${dias.join(',')}` : '');
}

function lista(palabras: string[]): string {
  return palabras.length > 1 ? `${palabras.slice(0, -1).join(', ')} y ${palabras[palabras.length - 1]}` : palabras.join('');
}

/** Texto para mostrar la regla: «Semanalmente», «Cada 2 semanas: lunes y jueves»… */
export function etiquetaRepeticion(regla?: string | null): string {
  if (!regla) return '';
  const simple = REPETICIONES_SIMPLES.find(o => o.valor === regla);
  if (simple) return simple.etiqueta;
  const r = leerPersonalizada(regla);
  if (!r) return 'Se repite';
  const u = UNIDADES.find(x => x.valor === r.unidad)!;
  const base = r.cada === 1 ? `Cada ${u.singular}` : `Cada ${r.cada} ${u.plural}`;
  return r.dias.length ? `${base}: ${lista(r.dias.map(d => DIAS_LARGOS[d]))}` : base;
}

/** Hoy en formato AAAA-MM-DD (al poner una repetición sin fecha, vence hoy, como en To Do). */
export function hoyTexto(): string {
  const h = new Date();
  return `${h.getFullYear()}-${String(h.getMonth() + 1).padStart(2, '0')}-${String(h.getDate()).padStart(2, '0')}`;
}
